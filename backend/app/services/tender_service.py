"""标书解析业务逻辑（P0-01 + P0-02 + P0-03）。

处理标书文件上传、格式转换、RAG 解析、LLM 提取资质要求等流程。
长时解析任务通过 BackgroundTask 异步执行，前端轮询状态。

文档提取方案采用 PDF 直接文本提取 + Vision OCR 扫描页兜底，
参考 industrial-marketing-ai 项目的成熟实现。
"""

import json
import logging
import os
import pathlib
import time
from datetime import datetime
from typing import Any, Optional

from app.config import MAX_FILE_SIZE, SUPPORTED_TENDER_FORMATS, TENDER_UPLOAD_DIR
from app.database import get_db
from app.models.tender import Tender, TenderRequirement
from app.services import file_convert
from app.services.document_parser import (
    extract_pdf_text,
    extract_pdf_with_pages,
    extract_docx_text,
    get_pdf_page_count,
    ocr_vision_pages,
)
from app.services.rag_service import get_llm_func
from app.utils.file_utils import detect_file_type, get_file_extension
from app.utils.text_chunks import split_text_chunks

logger = logging.getLogger(__name__)

# 各标书解析进度（供前端轮询）
_parse_progress: dict[int, dict[str, Any]] = {}

# 标书要求分类（7 类：原 5 + 新增 product_spec / submission）
REQUIREMENT_CATEGORIES = [
    "qualification",   # 企业资质
    "product_spec",    # 产品技术参数
    "submission",      # 投标待办提交件
    "performance",     # 业绩要求
    "financial",       # 财务要求
    "personnel",       # 人员要求
    "other",           # 其他要求
]

# LLM 提取标书要求的系统提示词（含新分类体系 + nature + 拆条 + few-shot 示例）
_EXTRACT_SYSTEM_PROMPT = """你是一个标书要求分析专家。你需要从标书文本中提取所有要求，并按"处理动作"对每条要求进行分类。

## 一、标书元数据
从标书正文中提取以下信息（找不到则填 null）：
{
    "region": "项目实施地区，如'江苏省南京市'，找不到填null",
    "procurement_type": "采购方式：公开招标/邀请招标/竞争性谈判/竞争性磋商/询价/单一来源/其他",
    "budget": "预算金额或最高限价，如'500万元'",
    "agency": "采购代理机构或采购单位全称"
}

## 二、分类体系（category 字段）

每条要求必须归入以下 7 类之一：

| category 值 | 中文 | 含义 | 后续处理 |
|-------------|------|------|---------|
| qualification | 企业资质 | 营业执照、资质证书、ISO认证、安全生产许可证等企业资质要求 | 走知识库匹配 |
| product_spec | 产品技术参数 | 设备/产品的技术规格、性能参数、配置要求 | 生成技术响应表 |
| submission | 投标待办提交件 | 需要投标人准备并提交的文件、承诺书、格式要求等 | 生成待办清单 |
| performance | 业绩 | 类似项目业绩、合同金额要求 | 走知识库匹配或待办 |
| financial | 财务 | 营收、资产负债率等财务指标 | 走知识库匹配或待办 |
| personnel | 人员 | 项目经理、技术人员资格及数量 | 走知识库匹配或待办 |
| other | 其他 | 信用要求、法律合规、本地化服务等 | 走知识库匹配或待办 |

### 各类具体说明

#### qualification（企业资质）：
- 主体资格：营业执照、法人资格、独立承担民事责任能力
- 专业资质：ISO 认证、3C 认证、行业许可证、安全生产许可证、特种设备制造/安装许可证
- 资质证书要求：建筑资质（总承包、专业承包等级）、承装(修、试)电力设施许可证、市政/水利/公路等各类专业资质
- 能力证明：生产/供货能力、设备证明、检测报告
- 授权要求：制造商授权书、代理商资格等
- 联合体要求：是否允许联合体投标，联合体各方要求
- 分包要求：允许分包的范围和条件

#### product_spec（产品技术参数）：
- 设备/产品的技术规格、性能参数、配置要求
- 处理器、内存、存储等硬件参数
- 软件功能、性能指标
- 材质、尺寸、功率等物理参数

#### submission（投标待办提交件）：
- 需要投标人准备并提交的文件：承诺书、声明函、格式文件
- 投标保证金缴纳凭证
- 中小企业声明函
- 保密协议
- 各种需要盖章/签字的格式文件

#### performance（业绩要求）：
- 同类项目业绩：近 N 年的项目数量、合同金额下限
- 业绩证明材料：合同、验收报告、中标通知书
- 正在履行的合同情况

#### financial（财务要求）：
- 注册资本/实收资本要求
- 营业收入/主营业务收入
- 资产负债率、净资产、净利润
- 纳税证明、社保缴纳证明
- 财务审计报告
- 履约保证金/投标保证金金额

#### personnel（人员要求）：
- 项目负责人资格（注册建造师等级、专业、数量）
- 技术负责人职称/工作年限
- 团队成员资格证书
- 特种作业人员持证要求

#### other（其他要求）：
- 信用要求：失信被执行人限制、重大税收违法记录
- 法律合规：参加政府采购活动前三年内无重大违法记录
- 关联关系限制
- 节能环保产品认证要求
- 本地化服务要求
- 投标有效期要求

## 三、处理性质（requirement_nature 字段）

对 performance、financial、personnel、other 四类，还需判断其"处理性质"：

| requirement_nature 值 | 含义 | 后续处理 |
|----------------------|------|---------|
| capability | 能力资质型——考核投标人是否"具备"某条件 | 走知识库匹配 |
| submission | 提交件型——需要投标人"准备并提交"某文件/承诺 | 走待办清单 |

判断标准：
- 如果该要求是"投标人须具备 XXX"（具备即可证明），且能在企业资质库中找到对应 → capability
- 如果该要求是"投标人须提交 XXX 承诺书/声明函/格式文件"（需要专门制作提交） → submission

对 qualification 类：requirement_nature 固定为 capability（无需判断）。
对 product_spec 类：requirement_nature 固定为 capability（不参与匹配，仅标记）。
对 submission 类：requirement_nature 固定为 submission。

## 四、拆条规则

如果一条原始要求同时具备"能力资质"和"提交件"两种性质，必须拆分为两条独立要求：
- 一条 requirement_nature = capability
- 一条 requirement_nature = submission
两条的 category 可以相同（如同为 performance），但 nature 不同。

## 五、灰色地带处理

如果某要求难以明确归类，归入最接近的 category，并在 content 中添加备注前缀【灰色地带】，
后续由人工在核对工作台调整。

## 六、输出格式

输出一个 JSON 对象（不是数组）：
{
    "metadata": { "region": ..., "procurement_type": ..., "budget": ..., "agency": ... },
    "requirements": [
        {
            "category": "qualification|product_spec|submission|performance|financial|personnel|other",
            "requirement_nature": "capability|submission",
            "title": "要求标题（简短概括，15字以内）",
            "content": "要求完整描述（原样保留标书中的措辞）",
            "is_hard": true,
            "raw_text": "原文片段",
            "page_number": 1,
            "numeric_value": "1000",
            "numeric_operator": ">=",
            "numeric_unit": "万元"
        }
    ]
}

字段说明：
- is_hard：是否为硬性要求（废标条件），true/false
- numeric_value/operator/unit：如果该要求包含数值阈值，提取数值、运算符、单位；无则填 null
- page_number：该要求所在页码（从文本段元数据获取，不确定时填 null）

## 七、重要原则
1. **穷举**：宁可多提取，不可遗漏。标书评审中遗漏一条硬性要求可能导致废标
2. **准确**：直接引用标书原文措辞，不要改写
3. **数值提取**：所有带数字的硬性要求（金额、年限、数量）必须提取 numeric_value/operator/unit
4. **is_hard 判断**：证书/资质缺失直接废标的为 hard=true；形式性/声明性文件为 hard=false

## 八、示例

### 示例 1：边界——兼具 capability + submission（拆条）

原文："投标人须具有 ISO9001 质量管理体系认证，并在投标文件中提供认证证书复印件及有效期内的年审记录。"

输出：
```json
{
    "metadata": {},
    "requirements": [
        {
            "category": "qualification",
            "requirement_nature": "capability",
            "title": "ISO9001质量管理体系认证",
            "content": "投标人须具有ISO9001质量管理体系认证",
            "is_hard": true,
            "raw_text": "投标人须具有 ISO9001 质量管理体系认证，并在投标文件中提供认证证书复印件及有效期内的年审记录。",
            "page_number": null,
            "numeric_value": null,
            "numeric_operator": null,
            "numeric_unit": null
        },
        {
            "category": "submission",
            "requirement_nature": "submission",
            "title": "提供ISO9001认证证书复印件及年审记录",
            "content": "在投标文件中提供认证证书复印件及有效期内的年审记录",
            "is_hard": true,
            "raw_text": "投标人须具有 ISO9001 质量管理体系认证，并在投标文件中提供认证证书复印件及有效期内的年审记录。",
            "page_number": null,
            "numeric_value": null,
            "numeric_operator": null,
            "numeric_unit": null
        }
    ]
}
```

### 示例 2：产品技术参数

原文："投标设备处理器不低于 Intel i7-13700，内存不低于 32GB DDR5，固态硬盘不低于 1TB NVMe。"

输出：
```json
{
    "metadata": {},
    "requirements": [
        {
            "category": "product_spec",
            "requirement_nature": "capability",
            "title": "处理器规格",
            "content": "投标设备处理器不低于 Intel i7-13700",
            "is_hard": true,
            "raw_text": "投标设备处理器不低于 Intel i7-13700",
            "page_number": null,
            "numeric_value": "i7-13700",
            "numeric_operator": ">=",
            "numeric_unit": "型号"
        },
        {
            "category": "product_spec",
            "requirement_nature": "capability",
            "title": "内存容量",
            "content": "内存不低于 32GB DDR5",
            "is_hard": true,
            "raw_text": "内存不低于 32GB DDR5",
            "page_number": null,
            "numeric_value": "32",
            "numeric_operator": ">=",
            "numeric_unit": "GB"
        }
    ]
}
```

### 示例 3：提交件

原文："投标人须提交近三年（2021-2023年）类似项目业绩证明材料，包含合同关键页复印件和用户验收证明。"

输出：
```json
{
    "metadata": {},
    "requirements": [
        {
            "category": "performance",
            "requirement_nature": "capability",
            "title": "近三年类似项目业绩",
            "content": "投标人须具有近三年（2021-2023年）类似项目业绩",
            "is_hard": true,
            "raw_text": "投标人须提交近三年（2021-2023年）类似项目业绩证明材料，包含合同关键页复印件和用户验收证明。",
            "page_number": null,
            "numeric_value": "3",
            "numeric_operator": ">=",
            "numeric_unit": "年"
        },
        {
            "category": "submission",
            "requirement_nature": "submission",
            "title": "提交业绩证明材料",
            "content": "提交近三年类似项目业绩证明材料，包含合同关键页复印件和用户验收证明",
            "is_hard": true,
            "raw_text": "投标人须提交近三年（2021-2023年）类似项目业绩证明材料，包含合同关键页复印件和用户验收证明。",
            "page_number": null,
            "numeric_value": null,
            "numeric_operator": null,
            "numeric_unit": null
        }
    ]
}
```

只输出 JSON，不要输出其他任何内容。"""


def _now_iso() -> str:
    """返回当前时间的 ISO 8601 字符串。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def upload_tender(file_name: str, file_content: bytes) -> Tender:
    """保存上传的标书文件并创建 Tender 记录。

    Args:
        file_name: 原始文件名。
        file_content: 文件二进制内容。

    Returns:
        创建的 Tender 模型实例（status=pending）。

    Raises:
        ValueError: 文件格式不支持或大小超限时抛出。
    """
    # 校验文件格式
    ext = get_file_extension(file_name)
    if ext not in SUPPORTED_TENDER_FORMATS:
        raise ValueError(f"不支持的标书文件格式: {ext}，支持的格式: {SUPPORTED_TENDER_FORMATS}")

    # 校验文件大小
    if len(file_content) > MAX_FILE_SIZE:
        raise ValueError(f"文件大小超限（>{MAX_FILE_SIZE // 1024 // 1024}MB）")

    # 保存文件
    timestamp = int(time.time())
    safe_name = os.path.basename(file_name).replace("..", "").replace("/", "").replace("\\", "")
    saved_name = f"{timestamp}_{safe_name}"
    file_path = os.path.join(TENDER_UPLOAD_DIR, saved_name)
    os.makedirs(TENDER_UPLOAD_DIR, exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(file_content)

    # 检测文件类型
    file_type = detect_file_type(file_path)

    # 从文件名提取标题（去掉扩展名和时间戳前缀）
    title = os.path.splitext(safe_name)[0]

    # 创建数据库记录
    now = _now_iso()
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO tenders
               (filename, original_path, title, file_type, status, upload_time, created_at)
               VALUES (?, ?, ?, ?, 'pending', ?, ?)""",
            (file_name, file_path, title, file_type, now, now),
        )
        await db.commit()
        tender_id = cursor.lastrowid
    finally:
        await db.close()

    logger.info("标书上传成功: id=%s, filename=%s, path=%s", tender_id, file_name, file_path)

    return Tender(
        id=tender_id,
        filename=file_name,
        original_path=file_path,
        title=title,
        file_type=file_type,
        status="pending",
        upload_time=now,
        created_at=now,
    )


async def _update_tender_status(tender_id: int, status: str, **extra: Any) -> None:
    """更新标书状态。

    Args:
        tender_id: 标书 ID。
        status: 新状态。
        **extra: 额外要更新的字段（如 pdf_path, parsed_at, total_pages）。
    """
    db = await get_db()
    try:
        sets = ["status = ?"]
        params: list[Any] = [status]
        for key, value in extra.items():
            sets.append(f"{key} = ?")
            params.append(value)
        params.append(tender_id)
        await db.execute(
            f"UPDATE tenders SET {', '.join(sets)} WHERE id = ?",
            params,
        )
        await db.commit()
    finally:
        await db.close()


async def parse_tender(tender_id: int) -> None:
    """异步解析标书流程（通过 BackgroundTask 调用）。

    流程：
    1. DOC/DOCX → LibreOffice 转 PDF
    2. PyPDF2 按页提取文本（1-2 秒跑完 148 页）
    3. 扫描页检测 + Vision API OCR 兜底
    4. LLM 提取资质要求和元数据
    5. 保存到数据库

    Args:
        tender_id: 标书 ID。
    """
    logger.info("开始解析标书: tender_id=%s", tender_id)

    try:
        # ── 获取标书信息 ──
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM tenders WHERE id = ?", (tender_id,))
            row = await cursor.fetchone()
        finally:
            await db.close()

        if row is None:
            logger.error("标书不存在: tender_id=%s", tender_id)
            return

        tender = Tender(**dict(row))
        file_path = tender.original_path

        # ── 步骤 1：DOC/DOCX 转 PDF ──
        await _update_tender_status(tender_id, "converting")
        _parse_progress[tender_id] = {"stage": "格式转换中…", "progress": 0, "total_pages": 0, "parsed_pages": 0}

        pdf_path = file_path
        if tender.file_type in ("docx", "doc"):
            logger.info("转换 DOCX/DOC 为 PDF: tender_id=%s", tender_id)
            pdf_path = await file_convert.convert_to_pdf(file_path, TENDER_UPLOAD_DIR)

        total_pages = get_pdf_page_count(pdf_path)
        await _update_tender_status(tender_id, "parsing", pdf_path=pdf_path, total_pages=total_pages)

        # ── 步骤 2：按页提取文本 ──
        _parse_progress[tender_id] = {
            "stage": "提取文档文本中…", "progress": 10, "total_pages": total_pages, "parsed_pages": 0,
        }
        pages = await extract_pdf_with_pages(pdf_path)
        text_pages = [p for p in pages if p["parse_mode"] == "text"]
        vision_pages_idx = [p["page"] for p in pages if p["parse_mode"] == "vision"]

        logger.info(
            "页面分析: %d 页, %d 文本页, %d 需 OCR",
            total_pages, len(text_pages), len(vision_pages_idx),
        )

        # ── 步骤 3：扫描页 OCR 兜底 ──
        ocr_results = {}
        if vision_pages_idx:
            _parse_progress[tender_id] = {
                "stage": f"OCR 识别 {len(vision_pages_idx)} 页扫描图片中…",
                "progress": 30, "total_pages": total_pages,
                "parsed_pages": len(text_pages),
            }

            ocr_done = 0

            def _ocr_progress(_page_num: int):
                nonlocal ocr_done
                ocr_done += 1
                _parse_progress[tender_id] = {
                    "stage": f"OCR 识别中 {ocr_done}/{len(vision_pages_idx)} 页",
                    "progress": 30 + int(ocr_done / len(vision_pages_idx) * 30),
                    "total_pages": total_pages,
                    "parsed_pages": len(text_pages) + ocr_done,
                }

            ocr_results = await ocr_vision_pages(pdf_path, vision_pages_idx, _ocr_progress)

        # ── 步骤 4：合并文本 ──
        _parse_progress[tender_id] = {
            "stage": "LLM 提取资质要求中…", "progress": 70,
            "total_pages": total_pages, "parsed_pages": total_pages,
        }
        await _update_tender_status(tender_id, "extracting")

        full_text_parts = []
        for p in pages:
            if p["parse_mode"] == "text" and p["content"]:
                full_text_parts.append(f"[第{p['page']}页]\n{p['content']}")
            elif p["parse_mode"] == "vision":
                ocr_text = ocr_results.get(p["page"], "")
                if ocr_text:
                    full_text_parts.append(f"[第{p['page']}页 扫描]\n{ocr_text}")

        full_text = "\n\n".join(full_text_parts)
        text_length = len(full_text)
        logger.info("文本提取完成: %d 字符, %d 页", text_length, len(full_text_parts))

        # ── 步骤 5：LLM 提取资质要求和元数据 ──
        requirements, metadata = await _extract_requirements_from_text(tender_id, full_text)

        # ── 步骤 6：保存元数据到 tender ──
        meta_fields = {}
        for k in ["region", "procurement_type", "budget", "agency"]:
            if metadata.get(k):
                meta_fields[k] = metadata[k]
        if meta_fields:
            await _update_tender_status(tender_id, "extracting", **meta_fields)

        # ── 步骤 7：保存 requirements 到 DB ──
        now = _now_iso()
        db = await get_db()
        try:
            for req in requirements:
                category = req.get("category", "other")
                if category not in REQUIREMENT_CATEGORIES:
                    category = "other"
                nature = req.get("requirement_nature", "capability")
                if nature not in ("capability", "submission"):
                    nature = "capability"
                await db.execute(
                    """INSERT INTO tender_requirements
                       (tender_id, category, requirement_nature, title, content, is_hard, raw_text,
                        page_number, numeric_value, numeric_operator, numeric_unit, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (tender_id, category, nature, req.get("title"), req.get("content"),
                     1 if req.get("is_hard", True) else 0, req.get("raw_text"),
                     req.get("page_number"), req.get("numeric_value"),
                     req.get("numeric_operator"), req.get("numeric_unit"), now),
                )
            await db.commit()
        finally:
            await db.close()

        # ═══════════════════ 完成 ═══════════════════
        await _update_tender_status(tender_id, "completed", parsed_at=now)
        _parse_progress.pop(tender_id, None)
        logger.info(
            "标书解析完成: tender_id=%s, pages=%d, text=%d chars, requirements=%d",
            tender_id, total_pages, text_length, len(requirements),
        )

    except Exception as e:
        logger.error("标书解析失败: tender_id=%s, error=%s", tender_id, str(e), exc_info=True)
        await _update_tender_status(tender_id, "failed")
        _parse_progress.pop(tender_id, None)


async def _extract_requirements_from_text(
    tender_id: int, full_text: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """用 LLM 从文档文本中分块提取资质要求和元数据，然后合并去重。

    长文档自动分段提取，每段约 25000 字符，确保不丢失内容。

    Args:
        tender_id: 标书 ID。
        full_text: 完整的文档文本（含页码标记）。

    Returns:
        (requirements_list, metadata_dict)
    """
    llm_func = await get_llm_func()
    total_len = len(full_text)
    logger.info("LLM 提取: tender_id=%s, text_length=%d", tender_id, total_len)

    # 分段策略：每段最多 25000 字符，段间重叠 2000 字符防止截断
    CHUNK_SIZE = 25000
    OVERLAP = 2000
    metadata = {}

    # 如果文本较短，直接提取
    if total_len <= CHUNK_SIZE:
        all_reqs, metadata = await _extract_one_chunk(
            llm_func, full_text, tender_id, "全文", 1, 1
        )
        return all_reqs, metadata

    # 长文档分段提取
    chunks = split_text_chunks(
        full_text,
        chunk_size=CHUNK_SIZE,
        overlap=OVERLAP,
    )
    total_chunks = len(chunks)

    logger.info("文档分 %d 段提取: tender_id=%s, total_len=%d", total_chunks, tender_id, total_len)

    all_requirements = []
    seen_keys: set[tuple[str, str, str]] = set()

    for i, chunk in enumerate(chunks):
        chunk_label = f"第{i+1}/{total_chunks}段"
        _parse_progress[tender_id] = {
            "stage": f"LLM 提取中 {chunk_label}",
            "progress": 70 + int(i / total_chunks * 25),
            "total_pages": 0, "parsed_pages": 0,
        }

        reqs, meta = await _extract_one_chunk(
            llm_func, chunk, tender_id, chunk_label, i + 1, total_chunks
        )

        # 第一段提取元数据
        if i == 0 and meta:
            metadata = meta

        # 去重合并 — key 改为 (raw_text, category, requirement_nature) 三元组
        # 防止拆条后两条 raw_text 相同的记录被误删
        for r in reqs:
            dedup_key = (
                (r.get("raw_text") or r.get("title") or "").strip(),
                r.get("category", "other").strip(),
                r.get("requirement_nature", "capability").strip(),
            )
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            all_requirements.append(r)

        logger.info("段 %d/%d: 新提取 %d 条, 累计 %d 条", i+1, total_chunks, len(reqs), len(all_requirements))

    logger.info("LLM 提取完成: %d 条要求 (去重后)", len(all_requirements))
    return all_requirements, metadata


async def _extract_one_chunk(
    llm_func, chunk_text: str, tender_id: int, label: str,
    chunk_idx: int, total_chunks: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """发送单个文本段给 LLM 提取。

    Args:
        llm_func: LLM 函数。
        chunk_text: 文本段。
        tender_id: 标书 ID。
        label: 分段标签。
        chunk_idx: 当前段序号。
        total_chunks: 总段数。

    Returns:
        (requirements, metadata)
    """
    is_first = chunk_idx == 1
    meta_hint = "提取标书基本元数据（地区、采购方式、预算、采购单位），并" if is_first else ""

    prompt = f"""请分析以下标书内容的{label}，{meta_hint}穷举提取其中所有的资格要求、门槛条件、实质性条款。

{chunk_text}

请按要求格式输出 JSON。"""

    try:
        response = await llm_func(
            prompt,
            system_prompt=_EXTRACT_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=8000,
        )

        json_str = response.strip()
        if "```" in json_str:
            import re
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", json_str)
            if match:
                json_str = match.group(1).strip()

        data = json.loads(json_str)

        if isinstance(data, dict) and "requirements" in data:
            metadata = data.get("metadata") or {}
            requirements = data.get("requirements") or []
        elif isinstance(data, list):
            requirements = data
            metadata = {}
        else:
            requirements = [data] if data else []
            metadata = {}

        logger.info("LLM 提取: %d 条要求, metadata=%s", len(requirements), metadata)
        return requirements, metadata

    except json.JSONDecodeError as e:
        logger.error("LLM 返回 JSON 解析失败: tender_id=%s, error=%s", tender_id, e)
        return [], {}
    except Exception as e:
        logger.error("LLM 提取要求失败: tender_id=%s, error=%s", tender_id, e)
        return [], {}


# ========== 以下三个旧函数已废弃，保留兼容引用 ==========

async def _analyze_pdf_text_coverage(pdf_path: str) -> dict[str, Any]:
    """已废弃，改用 document_parser.extract_pdf_with_pages()。"""
    from app.services.document_parser import get_pdf_page_count
    return {"total_pages": get_pdf_page_count(pdf_path), "text_coverage_pct": 100, "recommendation": "text"}


async def _validate_parse_quality(tender_id: int, pdf_path: str) -> dict[str, Any]:
    """已废弃，新方案不依赖 raganything 输出校验。"""
    return {"passed": True, "reason": "legacy", "page_completion_rate": 100, "parsed_pages": 0, "total_pages": 0, "requirements_count": 0}


async def get_tender(tender_id: int) -> Optional[Tender]:
    """获取标书详情。

    Args:
        tender_id: 标书 ID。

    Returns:
        Tender 模型实例，不存在时返回 None。
    """
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM tenders WHERE id = ?", (tender_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return Tender(**dict(row))
    finally:
        await db.close()


async def get_tender_requirements(tender_id: int) -> list[TenderRequirement]:
    """获取标书的所有要求列表。

    Args:
        tender_id: 标书 ID。

    Returns:
        TenderRequirement 列表。
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM tender_requirements WHERE tender_id = ? ORDER BY category, id",
            (tender_id,),
        )
        rows = await cursor.fetchall()
        return [TenderRequirement(**dict(r)) for r in rows]
    finally:
        await db.close()


async def update_requirement(
    tender_id: int,
    requirement_id: int,
    data: Any,
) -> Optional[TenderRequirement]:
    """更新一条标书要求并返回最新记录。"""
    allowed_fields = {
        "category", "requirement_nature", "title", "content", "is_hard", "raw_text",
        "page_number", "numeric_value", "numeric_operator",
        "numeric_unit", "review_status",
    }
    values = data.model_dump(exclude_unset=True)
    updates = {key: value for key, value in values.items() if key in allowed_fields}
    if not updates:
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT * FROM tender_requirements WHERE id = ? AND tender_id = ?",
                (requirement_id, tender_id),
            )
            row = await cursor.fetchone()
            return TenderRequirement(**dict(row)) if row else None
        finally:
            await db.close()

    db = await get_db()
    try:
        sets = ", ".join(f"{field} = ?" for field in updates)
        params = list(updates.values()) + [requirement_id, tender_id]
        await db.execute(
            f"UPDATE tender_requirements SET {sets} WHERE id = ? AND tender_id = ?",
            params,
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM tender_requirements WHERE id = ? AND tender_id = ?",
            (requirement_id, tender_id),
        )
        row = await cursor.fetchone()
        return TenderRequirement(**dict(row)) if row else None
    finally:
        await db.close()


async def create_requirement(
    tender_id: int,
    data: Any,
) -> TenderRequirement:
    """手动新增一条标书要求。"""
    values = data.model_dump(exclude_unset=True)
    now = _now_iso()
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO tender_requirements
               (tender_id, category, requirement_nature, title, content, is_hard, raw_text,
                page_number, numeric_value, numeric_operator, numeric_unit,
                review_status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                tender_id,
                values.get("category", "other"),
                values.get("requirement_nature", "capability"),
                values.get("title"),
                values.get("content"),
                1 if values.get("is_hard", False) else 0,
                values.get("raw_text"),
                values.get("page_number"),
                values.get("numeric_value"),
                values.get("numeric_operator"),
                values.get("numeric_unit"),
                values.get("review_status", "pending"),
                now,
            ),
        )
        await db.commit()
        new_id = cursor.lastrowid
        result = await db.execute(
            "SELECT * FROM tender_requirements WHERE id = ?",
            (new_id,),
        )
        row = await result.fetchone()
        return TenderRequirement(**dict(row))
    finally:
        await db.close()


async def delete_requirement(tender_id: int, requirement_id: int) -> bool:
    """删除一条标书要求。"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM tender_requirements WHERE id = ? AND tender_id = ?",
            (requirement_id, tender_id),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def batch_update_requirement_status(
    tender_id: int,
    requirement_ids: list[int],
    review_status: str,
) -> int:
    """批量更新解析确认状态。"""
    if not requirement_ids:
        return 0
    placeholders = ",".join("?" for _ in requirement_ids)
    db = await get_db()
    try:
        cursor = await db.execute(
            f"""UPDATE tender_requirements
                SET review_status = ?
                WHERE tender_id = ? AND id IN ({placeholders})""",
            [review_status, tender_id, *requirement_ids],
        )
        await db.commit()
        return cursor.rowcount
    finally:
        await db.close()


async def batch_delete_requirements(
    tender_id: int,
    requirement_ids: list[int],
) -> int:
    """批量删除标书要求。"""
    if not requirement_ids:
        return 0
    placeholders = ",".join("?" for _ in requirement_ids)
    db = await get_db()
    try:
        cursor = await db.execute(
            f"DELETE FROM tender_requirements WHERE tender_id = ? AND id IN ({placeholders})",
            [tender_id, *requirement_ids],
        )
        await db.commit()
        return cursor.rowcount
    finally:
        await db.close()


async def get_tender_pdf_path(tender_id: int) -> Optional[str]:
    """返回可供阅读的 PDF 路径。"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT original_path, pdf_path, file_type FROM tenders WHERE id = ?",
            (tender_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        path = row["pdf_path"]
        if not path and row["file_type"] == "pdf":
            path = row["original_path"]
        return path if path and os.path.isfile(path) else None
    finally:
        await db.close()


async def list_tenders(
    search: str = "",
    status: str = "",
    region: str = "",
) -> list[Tender]:
    """获取标书列表（按上传时间倒序），支持搜索和筛选。

    Args:
        search: 按标题/文件名模糊搜索。
        status: 按状态筛选（空=全部）。
        region: 按地区筛选（省份名模糊匹配）。

    Returns:
        Tender 列表。
    """
    db = await get_db()
    try:
        sql = "SELECT * FROM tenders WHERE 1=1"
        params: list[Any] = []

        if search:
            sql += " AND (title LIKE ? OR filename LIKE ?)"
            like_val = f"%{search}%"
            params.extend([like_val, like_val])
        if status:
            sql += " AND status = ?"
            params.append(status)
        if region:
            sql += " AND region LIKE ?"
            params.append(f"%{region}%")

        sql += " ORDER BY upload_time DESC, id DESC"
        cursor = await db.execute(sql, params)
        rows = await cursor.fetchall()
        return [Tender(**dict(r)) for r in rows]
    finally:
        await db.close()


async def get_tender_status(tender_id: int) -> Optional[dict[str, Any]]:
    """获取标书解析状态（含实时进度）。

    Args:
        tender_id: 标书 ID。

    Returns:
        包含 status / total_pages / progress / stage 的字典。
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, status, total_pages FROM tenders WHERE id = ?",
            (tender_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        result = {
            "tender_id": row["id"],
            "status": row["status"],
            "total_pages": row["total_pages"] or 0,
        }
        # 合并实时进度
        progress = _parse_progress.get(tender_id)
        if progress:
            result["progress"] = progress.get("progress", 0)
            result["stage"] = progress.get("stage", "")
            result["parsed_pages"] = progress.get("parsed_pages", 0)
        return result
    finally:
        await db.close()


async def delete_tender(tender_id: int) -> bool:
    """删除标书及其关联数据和磁盘文件。

    级联删除 tender_requirements / match_results / fill_templates 中的关联记录，
    同时删除 original_path 和 pdf_path 指向的磁盘文件。

    Args:
        tender_id: 标书 ID。

    Returns:
        True 表示删除成功，False 表示记录不存在。
    """
    db = await get_db()
    try:
        # 先查出文件路径用于后续删除
        cursor = await db.execute(
            "SELECT original_path, pdf_path FROM tenders WHERE id = ?",
            (tender_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return False

        original_path = row["original_path"]
        pdf_path = row["pdf_path"]

        # 删除数据库记录（CASCADE 自动删除关联的子表记录）
        await db.execute("DELETE FROM tenders WHERE id = ?", (tender_id,))
        await db.commit()

        # 删除磁盘文件（静默处理，不影响主流程）
        import os
        for path in (original_path, pdf_path):
            if path and os.path.isfile(path):
                try:
                    os.remove(path)
                    logger.info("已删除文件: %s", path)
                except OSError as e:
                    logger.warning("删除文件失败: %s, error=%s", path, str(e))

        logger.info("标书及其关联数据已删除: id=%s", tender_id)
        return True
    finally:
        await db.close()


async def reparse_requirements(tender_id: int) -> dict[str, Any]:
    """按新分类重新解析标书要求的前置清理。

    清空该标书下的所有旧数据（要求、匹配结果、技术响应、待办清单），
    供后续调用 parse_tender() 重新提取。

    清理步骤：
    1. 删除 tender_requirements 记录
    2. 删除 match_results 记录
    3. 删除 technical_responses 记录
    4. 删除 submission_checklist 记录

    Args:
        tender_id: 标书 ID。

    Returns:
        包含各表删除数量的字典。
    """
    db = await get_db()
    try:
        counts = {}
        for table in ("match_results", "technical_responses", "submission_checklist", "tender_requirements"):
            cursor = await db.execute(
                f"DELETE FROM {table} WHERE tender_id = ?",
                (tender_id,),
            )
            counts[table] = cursor.rowcount
        await db.commit()
        logger.info("重新解析清理完成: tender_id=%s, counts=%s", tender_id, counts)
        return counts
    finally:
        await db.close()
