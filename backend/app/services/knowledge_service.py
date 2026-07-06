"""知识库解析业务逻辑（P0-04 + P0-05 + P0-06）。

处理知识库文件上传、格式识别、纯文本提取/Vision 解析、LLM 提取资质信息等流程。
支持全格式文件（PDF/图片/DOCX/扫描件/XLSX），按分类管理。
"""

import base64
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Optional

from app.config import (
    KNOWLEDGE_UPLOAD_DIR,
    MAX_FILE_SIZE,
    SUPPORTED_KNOWLEDGE_FORMATS,
)
from app.database import get_db
from app.models.knowledge import KnowledgeFile, Qualification
from app.services import file_convert
from app.services import performance_project_service
from app.services.document_parser import (
    extract_pdf_text,
    extract_pdf_with_pages,
    ocr_vision_pages,
)
from app.services.rag_service import get_llm_func, get_vision_func
from app.utils.file_utils import detect_file_type, get_file_extension

logger = logging.getLogger(__name__)

# 知识库分类
KNOWLEDGE_CATEGORIES = ["enterprise", "personnel", "performance", "financial"]

# LLM 提取资质信息的系统提示词
_EXTRACT_QUAL_SYSTEM_PROMPT = """你是一个专业的资质信息提取助手。请从以下文件内容中提取资质/证书信息。

提取以下 7 项字段（如果文件中没有某项信息，对应字段设为 null）：
1. name: 证书/资质名称
2. number: 证书编号
3. issue_date: 发证日期（格式 YYYY-MM-DD）
4. expiry_date: 有效期至（格式 YYYY-MM-DD）
5. issuing_authority: 发证机构
6. scope: 认证范围
7. level: 等级
8. holder: 持证主体（企业名称或人员姓名）

输出 JSON 对象：
{
    "name": "证书名称",
    "number": "证书编号",
    "issue_date": "发证日期",
    "expiry_date": "有效期至",
    "issuing_authority": "发证机构",
    "scope": "认证范围",
    "level": "等级",
    "holder": "持证主体"
}

只输出 JSON 对象，不要输出其他内容。"""

# Vision 提取资质信息的提示词
_VISION_PROMPT = "请识别图片中的证书/资质信息，包括证书名称、编号、有效期、发证机构、认证范围、等级、持证主体。"

_PERSONNEL_EXTRACT_GUIDE = """当前文件分类是人员资质/人员证明材料。请按材料实际类型抽取，不要只按企业证书理解。

常见类型与字段映射：
- 身份证明：name 填“身份证明”；number 填身份证号；holder 填姓名；issue_date/expiry_date 可填签发日期/有效期限；issuing_authority 填签发机关；scope 可填住址或证件用途摘要。
- 社保证明：name 填“社保证明”；holder 填参保人姓名；number 可填证件号/社保编号；issue_date 填出具日期；expiry_date 通常为 null；issuing_authority 填社保经办机构；scope 填参保单位、缴费区间、险种或缴费状态摘要。
- 职称/资格证明：name 填职称或资格证书名称；number 填证书编号；holder 填人员姓名；issue_date/expiry_date/issuing_authority/level/scope 按原文填写。
- 特种作业证：name 填证书名称；number 填证书编号；holder 填姓名；issue_date/expiry_date 填发证日期/有效期；issuing_authority 填发证机关；scope 填准操项目/作业类别；level 填级别或准操资格。
"""


def _build_extract_qualification_prompt(
    content_text: str,
    category: Optional[str] = None,
    filename: Optional[str] = None,
) -> str:
    """构建资质抽取提示词。"""
    context_parts = []
    if filename:
        context_parts.append(f"文件名：{filename}")
    if category == "personnel":
        context_parts.append(_PERSONNEL_EXTRACT_GUIDE)

    context = "\n\n".join(context_parts)
    if context:
        return f"{context}\n\n请从以下文件内容中提取资质/证明信息：\n\n{content_text}"
    return f"请从以下文件内容中提取资质/证书信息：\n\n{content_text}"


def _build_vision_prompt(
    category: Optional[str] = None,
    filename: Optional[str] = None,
) -> str:
    """构建图片识别提示词。"""
    prompt = _VISION_PROMPT
    if category == "personnel":
        prompt = (
            "请识别图片中的人员资质/人员证明材料信息，可能是身份证明、社保证明、"
            "职称/资格证明、特种作业证。请输出 JSON，字段包含 "
            "name/number/issue_date/expiry_date/issuing_authority/scope/level/holder。"
        )
    if filename:
        prompt = f"文件名：{filename}\n{prompt}"
    return prompt


def _now_iso() -> str:
    """返回当前时间的 ISO 8601 字符串。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _compute_status(expiry_date: Optional[str]) -> Optional[str]:
    """根据有效期计算资质状态。

    Args:
        expiry_date: 有效期至日期字符串。

    Returns:
        valid / expiring / expired / None。
    """
    if not expiry_date:
        return None
    try:
        expiry = datetime.strptime(expiry_date, "%Y-%m-%d")
        now = datetime.now()
        days_left = (expiry - now).days
        if days_left < 0:
            return "expired"
        elif days_left <= 90:
            return "expiring"
        else:
            return "valid"
    except (ValueError, TypeError):
        return None


def normalize_qualification_field(value: Any) -> Optional[str]:
    """将 LLM/Vision 返回的任意字段值归一化为 SQLite 可存储字符串。

    Vision/LLM 对多发证机构、多个范围等字段可能返回 list/dict。
    SQLite TEXT 不能直接绑定 list/dict，因此入库前统一转字符串。
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "、".join(
            part
            for part in (normalize_qualification_field(item) for item in value)
            if part
        )
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


_QUALIFICATION_MEANINGFUL_FIELDS = (
    "name",
    "number",
    "issue_date",
    "expiry_date",
    "issuing_authority",
    "scope",
    "level",
    "holder",
)


def has_meaningful_qualification_data(qual_data: Optional[dict[str, Any]]) -> bool:
    """判断提取结果是否包含可展示的资质信息。"""
    if not qual_data:
        return False
    return any(
        bool(normalize_qualification_field(qual_data.get(field)))
        for field in _QUALIFICATION_MEANINGFUL_FIELDS
    )


def _strip_personnel_material_keywords(filename_stem: str) -> str:
    """从人员材料文件名中粗略去除资料类型词，保留可能的人员姓名。"""
    holder = filename_stem
    for keyword in (
        "身份证明",
        "身份证",
        "社保证明",
        "社会保险个人社保参保证明",
        "社会保险",
        "社保",
        "养老保险",
        "参保证明",
        "职称证明",
        "职称证书",
        "职称证",
        "职称",
        "资格证书",
        "资格证",
        "证书",
        "证明",
    ):
        holder = holder.replace(keyword, "")
    holder = holder.strip(" _-（）()")
    return holder or ""


def _looks_like_person_name(value: str) -> bool:
    """粗略判断文件名残留部分是否像人员姓名，避免把地区/编号当姓名。"""
    if not value:
        return False
    if re.search(r"\d", value):
        return False
    if any(
        word in value
        for word in ("上海市", "北京市", "江苏省", "浙江省", "证明", "个人", "项目经理", "代理人", "法人")
    ):
        return False
    return 2 <= len(value) <= 6


def _normalize_date_text(value: Optional[str]) -> Optional[str]:
    """把常见中文/点分日期归一为 YYYY-MM-DD。"""
    if not value:
        return None
    text = value.strip()
    patterns = [
        r"(?P<y>\d{4})[年./-](?P<m>\d{1,2})[月./-](?P<d>\d{1,2})日?",
        r"(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        y = int(match.group("y"))
        m = int(match.group("m"))
        d = int(match.group("d"))
        try:
            return datetime(y, m, d).strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None


def _extract_first_match(text: str, patterns: tuple[str, ...]) -> Optional[str]:
    """按多个正则模式提取第一个非空值。"""
    for pattern in patterns:
        match = re.search(pattern, text, re.S)
        if match:
            value = next((g for g in match.groups() if g), None)
            if value:
                return re.sub(r"\s+", "", value).strip("：:，,。 ")
    return None


def _extract_tax_authority(text: str) -> Optional[str]:
    """提取税务机关，避免把“纳税人识别号”等字段标签误当机构。"""
    if not text:
        return None

    candidates: list[str] = []

    for match in re.finditer(
        r"(国家税务总局[\u4e00-\u9fffA-Za-z0-9（）()·\-]*税务局(?:第[\u4e00-\u9fff0-9]+税务)?)",
        text,
    ):
        candidates.append(match.group(1))

    for match in re.finditer(
        r"税务机关\s*[:：]?\s*([^\n\r]{2,80})",
        text,
    ):
        candidates.append(match.group(1))

    for candidate in candidates:
        value = re.sub(r"\s+", "", candidate).strip("：:，,。 ")
        if not value:
            continue
        if any(bad in value for bad in ("纳税人识别号", "纳税人名称", "原凭证号", "税种", "品目名称")):
            continue
        if "税务" in value and "局" in value:
            return value
    return None


def _extract_personnel_qualification_from_text(
    content_text: str,
    filename: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """对格式明确的人员材料做本地字段抽取，避免完全依赖 LLM。"""
    if not content_text or len(content_text.strip()) < 10:
        return None

    compact = re.sub(r"\s+", " ", content_text)
    normalized = content_text.replace(" ", "")
    filename_stem = os.path.splitext(os.path.basename(filename or ""))[0]

    if "公民身份号码" in normalized or "居民身份证" in normalized or "身份证" in filename_stem:
        holder = _extract_first_match(
            compact,
            (
                r"姓名\s*[:：]?\s*([\u4e00-\u9fff\s]{2,8}?)(?=\s*性别|\s*民族)",
            ),
        )
        if not holder:
            holder = _extract_first_match(
                normalized,
                (
                    r"姓名[:：]?([\u4e00-\u9fff]{2,6})性别",
                ),
            )
        number = _extract_first_match(
            normalized,
            (
                r"公民身份号码[:：]?([0-9]{17}[0-9Xx])",
                r"身份证号(?:码)?[:：]?([0-9]{17}[0-9Xx])",
            ),
        )
        authority = _extract_first_match(
            compact,
            (
                r"签发机关\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
            ),
        )
        validity = re.search(
            r"有效期\s*[:：]?\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)\s*[-至]\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?|长期)",
            compact,
        )
        issue_date = _normalize_date_text(validity.group(1)) if validity else None
        expiry_date = None if validity and validity.group(2) == "长期" else (
            _normalize_date_text(validity.group(2)) if validity else None
        )
        address = _extract_first_match(
            compact,
            (
                r"住址\s*[:：]?\s*(.+?)\s*公民身份号码",
            ),
        )
        return {
            "name": "身份证明",
            "number": number,
            "issue_date": issue_date,
            "expiry_date": expiry_date,
            "issuing_authority": authority,
            "scope": f"住址：{address}" if address else "居民身份证明",
            "level": None,
            "holder": holder or (
                _strip_personnel_material_keywords(filename_stem)
                if _looks_like_person_name(_strip_personnel_material_keywords(filename_stem))
                else None
            ),
        }

    if any(word in normalized for word in ("低压电工作业", "电工作业", "特种作业")):
        operation_scope = _extract_first_match(
            compact,
            (
                r"(低压电工作业)",
                r"(高压电工作业)",
                r"([\u4e00-\u9fff]{2,10}作业)",
            ),
        )
        cert_number = _extract_first_match(
            compact,
            (
                r"\b(A[0-9A-Za-z]{10,})\b",
                r"证书编号\s*[:：]?\s*([A-Za-z0-9]+)",
            ),
        )
        holder = _extract_first_match(
            compact,
            (
                r"[\r\n\s]([\u4e00-\u9fff]{2,4})\s+电工作业",
                r"姓名\s*[:：]?\s*([\u4e00-\u9fff]{2,4})",
            ),
        )
        validity = re.search(
            r"([0-9]{4}-[0-9]{1,2}-[0-9]{1,2})\s*至\s*([0-9]{4}-[0-9]{1,2}-[0-9]{1,2})",
            compact,
        )
        issue_date = _normalize_date_text(validity.group(1)) if validity else _normalize_date_text(
            _extract_first_match(compact, (r"([0-9]{4}-[0-9]{1,2}-[0-9]{1,2})",))
        )
        expiry_date = _normalize_date_text(validity.group(2)) if validity else None
        authority = _extract_first_match(
            compact,
            (
                r"([\u4e00-\u9fff]{2,20}应急管理局)",
                r"发证机关\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
            ),
        )
        if operation_scope or cert_number:
            return {
                "name": f"特种作业操作证（{operation_scope}）" if operation_scope else "特种作业操作证",
                "number": cert_number,
                "issue_date": issue_date,
                "expiry_date": expiry_date,
                "issuing_authority": authority,
                "scope": operation_scope,
                "level": None,
                "holder": holder,
                "status": "valid",
            }

    if any(word in normalized for word in ("社保证明", "社会保险", "参保证明", "养老保险")):
        holder = _extract_first_match(
            compact,
            (
                r"姓名\s*[:：]\s*([\u4e00-\u9fff]{2,6})",
                r"参保人\s*[:：]\s*([\u4e00-\u9fff]{2,6})",
            ),
        )
        number = _extract_first_match(
            compact,
            (
                r"证件号码\s*[:：]\s*([0-9]{17}[0-9Xx])",
                r"身份证号(?:码)?\s*[:：]\s*([0-9]{17}[0-9Xx])",
                r"社会保障号码\s*[:：]\s*([A-Za-z0-9\-]+)",
            ),
        )
        issue_raw = _extract_first_match(
            compact,
            (
                r"出具日期\s*[:：]?\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)",
                r"打印日期\s*[:：]?\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)",
            ),
        )
        unit = _extract_first_match(
            compact,
            (
                r"参保单位\s*[:：]\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
                r"单位名称\s*[:：]\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
            ),
        )
        period = _extract_first_match(
            compact,
            (
                r"缴费年月\s*[:：]\s*([^\n。；;]+)",
                r"缴费区间\s*[:：]\s*([^\n。；;]+)",
            ),
        )
        scope_parts = []
        if unit:
            scope_parts.append(f"参保单位：{unit}")
        if period:
            scope_parts.append(f"缴费区间：{period}")
        if not scope_parts:
            scope_parts.append("社会保险参保证明")
        return {
            "name": "社保证明",
            "number": number,
            "issue_date": _normalize_date_text(issue_raw),
            "expiry_date": None,
            "issuing_authority": _extract_first_match(
                compact,
                (
                    r"([\u4e00-\u9fff]{2,20}(?:社会保险|社保)[\u4e00-\u9fff]{0,20}(?:中心|局|机构))",
                ),
            ),
            "scope": "；".join(scope_parts),
            "level": None,
            "status": "valid",
            "holder": holder or (
                _strip_personnel_material_keywords(filename_stem)
                if _looks_like_person_name(_strip_personnel_material_keywords(filename_stem))
                else None
            ),
        }

    if any(word in normalized for word in ("QualificationTitle", "资格名称", "职称", "工程师", "CertificateNo")):
        holder = _extract_first_match(
            compact,
            (
                r"Full Name[:：]?\s*([\u4e00-\u9fff]{2,6})",
                r"姓名\s*[:：]?\s*([\u4e00-\u9fff]{2,6})",
            ),
        )
        title = _extract_first_match(
            compact,
            (
                r"Qualification Title\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
                r"资格名称\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
            ),
        )
        number = _extract_first_match(
            compact,
            (
                r"Certificate No\.\s*([A-Za-z0-9\-]+)",
                r"证件号\s*[:：]?\s*([A-Za-z0-9\-]+)",
                r"证书编号\s*[:：]?\s*([A-Za-z0-9\-]+)",
            ),
        )
        field = _extract_first_match(
            compact,
            (
                r"Professional Field\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
                r"专业名称\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
            ),
        )
        authority = _extract_first_match(
            compact,
            (
                r"Issuing Authority\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
                r"发证机关\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
            ),
        )
        issue_raw = _extract_first_match(
            compact,
            (
                r"Issue Date\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)",
                r"发证日期\s*[:：]?\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)",
            ),
        )
        if title or number or field:
            return {
                "name": title or "职称/资格证明",
                "number": number,
                "issue_date": _normalize_date_text(issue_raw),
                "expiry_date": None,
                "issuing_authority": authority,
                "scope": field,
                "level": title,
                "holder": holder,
                "status": "valid",
            }

    if "毕业证书" in normalized or "毕业学校" in normalized:
        holder = _extract_first_match(
            compact,
            (
                r"学生\s*([\u4e00-\u9fff]{2,6})\s*系",
                r"姓名\s*[:：]?\s*([\u4e00-\u9fff]{2,6})",
            ),
        )
        number = _extract_first_match(
            compact,
            (
                r"编号\s*([A-Za-z0-9\u4e00-\u9fff\s]+号)",
            ),
        )
        authority = _extract_first_match(
            compact,
            (
                r"毕业学校\s*[:：]\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
                r"学校\s*[:：]\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
            ),
        )
        major = _extract_first_match(
            compact,
            (
                r"在本校\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-\s]+?专业)\s*学习",
                r"专业\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
            ),
        )
        return {
            "name": "毕业证书",
            "number": number,
            "issue_date": None,
            "expiry_date": None,
            "issuing_authority": authority,
            "scope": major,
            "level": None,
            "holder": holder,
            "status": "valid",
        }

    return None


def _extract_enterprise_qualification_from_text(
    content_text: str,
    filename: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """对常见企业资质做本地字段抽取。"""
    if not content_text or len(content_text.strip()) < 10:
        return None
    compact = re.sub(r"\s+", " ", content_text)
    normalized = content_text.replace(" ", "")
    filename_stem = os.path.splitext(os.path.basename(filename or ""))[0]

    if any(word in normalized for word in ("营业执照", "统一社会信用代码", "法定代表人")):
        holder = _extract_first_match(
            compact,
            (
                r"名称\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+(?:公司|厂|中心|集团))",
                r"企业名称\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
            ),
        )
        number = _extract_first_match(
            normalized,
            (
                r"统一社会信用代码[:：]?([0-9A-Z]{15,20})",
                r"注册号[:：]?([0-9A-Z]{10,20})",
            ),
        )
        authority = _extract_first_match(
            compact,
            (
                r"登记机关\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
                r"发证机关\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
            ),
        )
        issue_raw = _extract_first_match(
            compact,
            (
                r"成立日期\s*[:：]?\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)",
                r"发证日期\s*[:：]?\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)",
            ),
        )
        scope = _extract_first_match(
            compact,
            (
                r"经营范围\s*[:：]?\s*(.+?)(?:登记机关|发证机关|成立日期|$)",
            ),
        )
        return {
            "name": "营业执照",
            "number": number,
            "issue_date": _normalize_date_text(issue_raw),
            "expiry_date": None,
            "issuing_authority": authority,
            "scope": scope,
            "level": None,
            "holder": holder,
            "status": "valid",
        }

    if any(word in normalized for word in ("质量管理体系", "环境管理体系", "职业健康安全管理体系", "ISO9001", "ISO14001", "ISO45001")):
        if "环境管理体系" in normalized or "ISO14001" in normalized:
            cert_name = "环境管理体系认证证书"
        elif "职业健康安全管理体系" in normalized or "ISO45001" in normalized:
            cert_name = "职业健康安全管理体系认证证书"
        else:
            cert_name = "质量管理体系认证证书"
        number = _extract_first_match(
            compact,
            (
                r"证书编号\s*[:：]?\s*([A-Za-z0-9\-_/]+)",
                r"注册号\s*[:：]?\s*([A-Za-z0-9\-_/]+)",
            ),
        )
        holder = _extract_first_match(
            compact,
            (
                r"兹证明\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+(?:公司|厂|中心|集团))",
                r"组织名称\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
                r"企业名称\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
            ),
        )
        scope = _extract_first_match(
            compact,
            (
                r"认证范围\s*[:：]?\s*(.+?)(?:发证日期|有效期|发证机构|$)",
                r"覆盖范围\s*[:：]?\s*(.+?)(?:发证日期|有效期|发证机构|$)",
            ),
        )
        issue_raw = _extract_first_match(
            compact,
            (
                r"发证日期\s*[:：]?\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)",
                r"签发日期\s*[:：]?\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)",
            ),
        )
        expiry_raw = _extract_first_match(
            compact,
            (
                r"有效期至\s*[:：]?\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)",
                r"有效期\s*[:：]?\s*至\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)",
            ),
        )
        authority = _extract_first_match(
            compact,
            (
                r"发证机构\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
                r"认证机构\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
            ),
        )
        return {
            "name": cert_name,
            "number": number,
            "issue_date": _normalize_date_text(issue_raw),
            "expiry_date": _normalize_date_text(expiry_raw),
            "issuing_authority": authority,
            "scope": scope,
            "level": None,
            "holder": holder,
            "status": "valid",
        }

    if "高新技术企业" in normalized or "GR" in filename_stem.upper():
        holder = _extract_first_match(
            compact,
            (
                r"企业名称\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
                r"名称\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+(?:公司|厂|中心|集团))",
            ),
        )
        number = _extract_first_match(
            compact,
            (
                r"证书编号\s*[:：]?\s*(GR[0-9A-Z]+)",
                r"\b(GR[0-9A-Z]{8,})\b",
            ),
        ) or _extract_first_match(filename_stem, (r"\b(GR[0-9A-Z]{8,})\b",))
        issue_raw = _extract_first_match(
            compact,
            (
                r"发证时间\s*[:：]?\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)",
                r"发证日期\s*[:：]?\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)",
            ),
        )
        authority = _extract_first_match(
            compact,
            (
                r"批准机关\s*[:：]?\s*(.+?)(?:$|有效期|发证时间)",
                r"发证机关\s*[:：]?\s*(.+?)(?:$|有效期|发证时间)",
            ),
        )
        return {
            "name": "高新技术企业证书",
            "number": number,
            "issue_date": _normalize_date_text(issue_raw),
            "expiry_date": None,
            "issuing_authority": authority,
            "scope": "高新技术企业",
            "level": None,
            "holder": holder,
            "status": "valid",
        }

    if any(word in normalized for word in ("强制性产品认证", "CCC认证", "3C认证", "产品认证证书")):
        number = _extract_first_match(compact, (r"证书编号\s*[:：]?\s*([A-Za-z0-9\-_/]+)",))
        holder = _extract_first_match(
            compact,
            (
                r"委托人\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
                r"制造商\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
            ),
        )
        scope = _extract_first_match(
            compact,
            (
                r"产品名称\s*[:：]?\s*(.+?)(?:型号|规格|发证日期|有效期|$)",
                r"认证产品\s*[:：]?\s*(.+?)(?:型号|规格|发证日期|有效期|$)",
            ),
        )
        return {
            "name": "强制性产品认证证书",
            "number": number,
            "issue_date": _normalize_date_text(_extract_first_match(compact, (r"发证日期\s*[:：]?\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)",))),
            "expiry_date": _normalize_date_text(_extract_first_match(compact, (r"有效期至\s*[:：]?\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)",))),
            "issuing_authority": _extract_first_match(compact, (r"发证机构\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",)),
            "scope": scope,
            "level": None,
            "holder": holder,
            "status": "valid",
        }

    if any(word in normalized for word in ("软件著作权", "软著", "国家版权局", "登记号")):
        software_name = _extract_first_match(
            compact,
            (
                r"软件名称\s*[:：]?\s*(.+?)(?:著作权人|登记号|证书号|$)",
            ),
        )
        number = _extract_first_match(
            compact,
            (
                r"登记号\s*[:：]?\s*([0-9A-Z]{4}SR[0-9]+)",
                r"证书号\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9第]+号)",
            ),
        )
        return {
            "name": "计算机软件著作权登记证书",
            "number": number,
            "issue_date": _normalize_date_text(
                _extract_first_match(compact, (r"发证日期\s*[:：]?\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)",))
            ),
            "expiry_date": None,
            "issuing_authority": _extract_first_match(compact, (r"发证机关\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",))
            or "中华人民共和国国家版权局",
            "scope": "；".join(
                part for part in (
                    f"软件名称：{software_name}" if software_name else None,
                    _extract_first_match(compact, (r"权利范围\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",)),
                )
                if part
            ) or software_name,
            "level": None,
            "holder": _extract_first_match(compact, (r"著作权人\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",)),
            "status": "valid",
        }

    if any(word in normalized for word in ("检测报告", "测试报告", "检验报告", "防护等级")):
        sample = _extract_first_match(
            compact,
            (
                r"样品名称\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-\s]+)",
                r"产品名称\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-\s]+)",
            ),
        )
        test_item = _extract_first_match(
            compact,
            (
                r"检测项目\s*[:：]?\s*(.+?)(?:签发日期|检测机构|$)",
                r"测试项目\s*[:：]?\s*(.+?)(?:签发日期|检测机构|$)",
            ),
        )
        level = _extract_first_match(compact, (r"\b(IP[0-9]{2})\b",))
        return {
            "name": "检测报告",
            "number": _extract_first_match(compact, (r"报告编号\s*[:：]?\s*([A-Za-z0-9\-_/]+)",)),
            "issue_date": _normalize_date_text(
                _extract_first_match(
                    compact,
                    (
                        r"签发日期\s*[:：]?\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)",
                        r"报告日期\s*[:：]?\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)",
                    ),
                )
            ),
            "expiry_date": None,
            "issuing_authority": _extract_first_match(
                compact,
                (
                    r"检测机构\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
                    r"检验机构\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
                ),
            ),
            "scope": "；".join(part for part in (sample, test_item) if part),
            "level": level,
            "holder": None,
            "status": "valid",
        }

    if any(word in normalized for word in ("防爆合格证", "防爆配电箱")):
        return {
            "name": "防爆合格证",
            "number": _extract_first_match(compact, (r"(?:证书编号|编号)\s*[:：]?\s*([A-Za-z0-9.\-_/]+)",)),
            "issue_date": _normalize_date_text(_extract_first_match(compact, (r"(?:发证日期|签发日期)\s*[:：]?\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)",))),
            "expiry_date": _normalize_date_text(_extract_first_match(compact, (r"有效期至\s*[:：]?\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)",))),
            "issuing_authority": _extract_first_match(compact, (r"(?:发证机构|检验机构)\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",)),
            "scope": _extract_first_match(compact, (r"产品\s*[:：]?\s*(.+?)(?:型号|依据标准|发证日期|$)",)) or "防爆产品",
            "level": None,
            "holder": _extract_first_match(compact, (r"(?:制造商|申请人)\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",)),
            "status": "valid",
        }

    if "开户许可证" in normalized or "基本存款账户" in normalized:
        return {
            "name": "开户许可证",
            "number": _extract_first_match(compact, (r"(?:核准号|编号|账号)\s*[:：]?\s*([A-Za-z0-9\-_/]+)",)),
            "issue_date": _normalize_date_text(_extract_first_match(compact, (r"(?:发证日期|开户日期)\s*[:：]?\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)",))),
            "expiry_date": None,
            "issuing_authority": _extract_first_match(compact, (r"(?:开户银行|开户行)\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",)),
            "scope": "基本存款账户",
            "level": None,
            "holder": _extract_first_match(compact, (r"(?:存款人名称|单位名称)\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",)),
            "status": "valid",
        }

    return None


def _extract_financial_qualification_from_text(
    content_text: str,
    filename: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """对常见财务资料做本地字段抽取。"""
    if not content_text or len(content_text.strip()) < 10:
        return None
    compact = re.sub(r"\s+", " ", content_text)
    normalized = content_text.replace(" ", "")
    filename_stem = os.path.splitext(os.path.basename(filename or ""))[0]

    if any(word in normalized for word in ("资产负债表", "利润表", "财务会计报告", "会小企")):
        start_date = _extract_first_match(
            compact,
            (
                r"税款所属期起止\s*[:：]?\s*([0-9]{4}-[0-9]{1,2}-[0-9]{1,2})\s*至\s*[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}",
            ),
        )
        end_date = _extract_first_match(
            compact,
            (
                r"税款所属期起止\s*[:：]?\s*[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}\s*至\s*([0-9]{4}-[0-9]{1,2}-[0-9]{1,2})",
            ),
        )
        holder = _extract_first_match(
            compact,
            (
                r"纳税人名称\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
            ),
        )
        report_date = _extract_first_match(
            compact,
            (
                r"报送日期\s*[:：]?\s*([0-9]{4}-[0-9]{1,2}-[0-9]{1,2})",
            ),
        )
        total_assets = _extract_first_match(
            compact,
            (
                r"资产总计\s*\d+\s*([0-9,.]+)",
            ),
        )
        revenue = _extract_first_match(
            compact,
            (
                r"营业收入\s*\d+\s*([0-9,.]+)",
            ),
        )
        scope_parts = []
        if start_date and end_date:
            scope_parts.append(f"所属期{start_date}至{end_date}")
        if total_assets:
            scope_parts.append(f"资产总计{total_assets.replace(',', '')}元")
        if revenue:
            scope_parts.append(f"营业收入{revenue.replace(',', '')}元")
        return {
            "name": "财务会计报告（季报）" if "季报" in filename_stem or "季报" in normalized else "财务会计报告",
            "number": f"{start_date}至{end_date}" if start_date and end_date else None,
            "issue_date": _normalize_date_text(report_date),
            "expiry_date": end_date,
            "issuing_authority": "电子税务局/纳税申报系统",
            "scope": "；".join(scope_parts) if scope_parts else "财务会计报告",
            "level": None,
            "holder": holder,
            "status": "valid",
        }

    if any(word in normalized for word in ("审计报告", "财务审计", "会计师事务所")):
        number = _extract_first_match(
            compact,
            (
                r"报告编号\s*[:：]?\s*([A-Za-z0-9\u4e00-\u9fff/（）()第\-]+号?)",
                r"文号\s*[:：]?\s*([A-Za-z0-9\u4e00-\u9fff/（）()第\-]+号?)",
            ),
        )
        holder = _extract_first_match(
            compact,
            (
                r"被审计单位\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
                r"公司名称\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
            ),
        )
        year = _extract_first_match(
            compact,
            (
                r"审计年度\s*[:：]?\s*([0-9]{4}年度)",
                r"([0-9]{4}年度)",
            ),
        )
        revenue = _extract_first_match(compact, (r"营业收入\s*([0-9,.]+)\s*万元",))
        assets = _extract_first_match(compact, (r"资产总额\s*([0-9,.]+)\s*万元",))
        scope_parts = []
        if year:
            scope_parts.append(year)
        if revenue:
            scope_parts.append(f"营业收入{revenue}万元")
        if assets:
            scope_parts.append(f"资产总额{assets}万元")
        return {
            "name": "审计报告",
            "number": number,
            "issue_date": _normalize_date_text(
                _extract_first_match(
                    compact,
                    (
                        r"出具日期\s*[:：]?\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)",
                        r"报告日期\s*[:：]?\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)",
                    ),
                )
            ),
            "expiry_date": None,
            "issuing_authority": _extract_first_match(
                compact,
                (
                    r"会计师事务所\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
                    r"出具机构\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",
                ),
            ),
            "scope": "；".join(scope_parts) if scope_parts else "财务审计报告",
            "level": None,
            "holder": holder,
            "status": "valid",
        }

    if any(word in normalized for word in ("纳税证明", "完税证明", "税收完税")):
        return {
            "name": "纳税证明",
            "number": _extract_first_match(compact, (r"证明编号\s*[:：]?\s*([A-Za-z0-9\-_/]+)",)),
            "issue_date": _normalize_date_text(_extract_first_match(compact, (r"开具日期\s*[:：]?\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)",))),
            "expiry_date": None,
            "issuing_authority": _extract_tax_authority(content_text),
            "scope": "纳税/完税证明",
            "level": None,
            "holder": _extract_first_match(compact, (r"纳税人名称\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",)),
            "status": "valid",
        }

    if "银行" in normalized and any(word in normalized for word in ("资信证明", "开户许可证", "基本存款账户")):
        cert_name = "开户许可证" if "开户许可证" in normalized or "基本存款账户" in normalized else "银行资信证明"
        return {
            "name": cert_name,
            "number": _extract_first_match(compact, (r"(?:编号|核准号|账号)\s*[:：]?\s*([A-Za-z0-9\-_/]+)",)),
            "issue_date": _normalize_date_text(_extract_first_match(compact, (r"(?:出具日期|发证日期)\s*[:：]?\s*([0-9]{4}[年./-][0-9]{1,2}[月./-][0-9]{1,2}日?)",))),
            "expiry_date": None,
            "issuing_authority": _extract_first_match(compact, (r"([\u4e00-\u9fffA-Za-z0-9（）()·\-]+银行[\u4e00-\u9fffA-Za-z0-9（）()·\-]*)",)),
            "scope": cert_name,
            "level": None,
            "holder": _extract_first_match(compact, (r"(?:单位名称|存款人名称|客户名称)\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9（）()·\-]+)",)),
            "status": "valid",
        }

    return None


def _extract_qualification_from_text_locally(
    content_text: str,
    category: Optional[str] = None,
    filename: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """按分类优先使用本地规则抽取资质字段，失败再交给 LLM。"""
    if category == "personnel":
        return _extract_personnel_qualification_from_text(content_text, filename)
    if category == "enterprise":
        return _extract_enterprise_qualification_from_text(content_text, filename)
    if category == "financial":
        return _extract_financial_qualification_from_text(content_text, filename)
    return (
        _extract_enterprise_qualification_from_text(content_text, filename)
        or _extract_financial_qualification_from_text(content_text, filename)
        or _extract_personnel_qualification_from_text(content_text, filename)
    )


def _infer_personnel_placeholder(filename_stem: str, reason: str) -> dict[str, Any]:
    """根据人员材料文件名生成更贴合人员资质表头的占位记录。"""
    normalized = filename_stem.replace(" ", "")
    if "身份证" in normalized:
        material_type = "身份证明"
    elif any(word in normalized for word in ("社保", "社会保险", "养老保险", "参保")):
        material_type = "社保证明"
    elif "职称" in normalized:
        material_type = "职称/资格证明"
    elif any(word in normalized for word in ("电工", "作业证", "操作证")):
        material_type = "特种作业证"
    elif any(word in normalized for word in ("项目经理", "任命", "委派")):
        material_type = "项目人员证明"
    else:
        material_type = "人员证明材料"

    holder = _strip_personnel_material_keywords(filename_stem)
    return {
        "name": material_type,
        "number": None,
        "issue_date": None,
        "expiry_date": None,
        "issuing_authority": None,
        "scope": f"待人工补全：{reason}",
        "level": None,
        "holder": holder if _looks_like_person_name(holder) else None,
        "status": "needs_completion",
    }


def build_placeholder_qualification(
    filename: str,
    reason: str,
    category: Optional[str] = None,
) -> dict[str, Any]:
    """为未能自动提取的文件生成占位资质记录，保证文件和列表行能对应。"""
    name = os.path.splitext(os.path.basename(filename))[0]
    if category == "personnel":
        return _infer_personnel_placeholder(name, reason)
    return {
        "name": name,
        "number": None,
        "issue_date": None,
        "expiry_date": None,
        "issuing_authority": None,
        "scope": f"待人工补全：{reason}",
        "level": None,
        "holder": None,
        "status": "needs_completion",
    }


async def upload_file(file_name: str, file_content: bytes, category: str) -> KnowledgeFile:
    """保存上传的知识库文件并创建 KnowledgeFile 记录。

    Args:
        file_name: 原始文件名。
        file_content: 文件二进制内容。
        category: 文件分类（enterprise/personnel/performance/financial）。

    Returns:
        创建的 KnowledgeFile 模型实例（status=pending）。

    Raises:
        ValueError: 文件格式不支持或大小超限时抛出。
    """
    # 校验文件格式
    ext = get_file_extension(file_name)
    if ext not in SUPPORTED_KNOWLEDGE_FORMATS:
        raise ValueError(
            f"不支持的知识库文件格式: {ext}，支持的格式: {SUPPORTED_KNOWLEDGE_FORMATS}"
        )

    # 校验文件大小
    if len(file_content) > MAX_FILE_SIZE:
        raise ValueError(f"文件大小超限（>{MAX_FILE_SIZE // 1024 // 1024}MB）")

    # 确定存储目录
    category_dir = os.path.join(KNOWLEDGE_UPLOAD_DIR, category)
    os.makedirs(category_dir, exist_ok=True)

    # 保存文件
    timestamp = int(time.time())
    safe_name = os.path.basename(file_name).replace("..", "").replace("/", "").replace("\\", "")
    saved_name = f"{timestamp}_{safe_name}"
    file_path = os.path.join(category_dir, saved_name)
    with open(file_path, "wb") as f:
        f.write(file_content)

    # 检测文件类型
    file_type = detect_file_type(file_path)

    # 创建数据库记录
    now = _now_iso()
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO knowledge_files
               (filename, file_path, file_type, category, status, upload_time, created_at)
               VALUES (?, ?, ?, ?, 'pending', ?, ?)""",
            (file_name, file_path, file_type, category, now, now),
        )
        await db.commit()
        file_id = cursor.lastrowid
    finally:
        await db.close()

    logger.info(
        "知识库文件上传成功: id=%s, filename=%s, category=%s", file_id, file_name, category
    )

    return KnowledgeFile(
        id=file_id,
        filename=file_name,
        file_path=file_path,
        file_type=file_type,
        category=category,
        status="pending",
        upload_time=now,
        created_at=now,
    )


async def _update_file_status(file_id: int, status: str, **extra: Any) -> None:
    """更新知识库文件状态。"""
    db = await get_db()
    try:
        sets = ["status = ?"]
        params: list[Any] = [status]
        for key, value in extra.items():
            sets.append(f"{key} = ?")
            params.append(value)
        params.append(file_id)
        await db.execute(
            f"UPDATE knowledge_files SET {', '.join(sets)} WHERE id = ?",
            params,
        )
        await db.commit()
    finally:
        await db.close()


async def _extract_pdf_text_with_ocr_fallback(pdf_path: str) -> str:
    """提取 PDF 文本；当文字层为空时，对扫描页执行 Vision OCR。"""
    content_text = await extract_pdf_text(pdf_path)
    if content_text and len(content_text.strip()) >= 10:
        return content_text

    try:
        pages = await extract_pdf_with_pages(pdf_path)
        vision_pages = [int(p["page"]) for p in pages if p.get("parse_mode") == "vision"]
        if not vision_pages:
            return content_text or ""

        ocr_results = await ocr_vision_pages(pdf_path, vision_pages)
        text_parts: list[str] = []
        for page in pages:
            page_num = int(page["page"])
            page_text = page.get("content")
            if page_text:
                text_parts.append(f"[第{page_num}页]\n{page_text}")
                continue
            ocr_text = (ocr_results.get(page_num) or "").strip()
            if ocr_text:
                text_parts.append(f"[第{page_num}页]\n{ocr_text}")
        return "\n\n".join(text_parts)
    except Exception as e:
        logger.warning("PDF OCR 兜底失败: %s", str(e))
        return content_text or ""


async def _get_cached_extracted_text(file_id: int) -> Optional[str]:
    """读取知识库文件已缓存的 OCR/文本提取结果。"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT extracted_text FROM knowledge_files WHERE id = ?",
            (file_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        text = row["extracted_text"]
        if isinstance(text, str) and len(text.strip()) >= 10:
            return text
        return None
    finally:
        await db.close()


async def _save_extracted_text_cache(file_id: int, text: str) -> None:
    """保存知识库文件 OCR/文本提取结果，供后续重新解析复用。"""
    if not text or len(text.strip()) < 10:
        return
    db = await get_db()
    try:
        await db.execute(
            "UPDATE knowledge_files SET extracted_text = ?, extracted_at = ? WHERE id = ?",
            (text, _now_iso(), file_id),
        )
        await db.commit()
    finally:
        await db.close()


async def _get_or_extract_file_text(file_id: int, file_path: str, file_type: str) -> str:
    """优先复用缓存文本；缓存不存在时才执行 PDF 文本提取/OCR。"""
    cached = await _get_cached_extracted_text(file_id)
    if cached is not None:
        logger.info("复用知识库文件文本缓存: file_id=%s, chars=%d", file_id, len(cached))
        return cached

    if file_type in ("docx", "doc", "xlsx"):
        pdf_path = await file_convert.convert_to_pdf(file_path, os.path.dirname(file_path))
        text = await _extract_pdf_text_with_ocr_fallback(pdf_path)
    elif file_type == "pdf":
        text = await _extract_pdf_text_with_ocr_fallback(file_path)
    else:
        return ""

    await _save_extracted_text_cache(file_id, text)
    return text


async def _get_or_extract_image_text(file_id: int, image_path: str) -> str:
    """优先复用图片 OCR 文本；缓存不存在时调用 Vision 提取全文。"""
    cached = await _get_cached_extracted_text(file_id)
    if cached is not None:
        logger.info("复用知识库图片 OCR 缓存: file_id=%s, chars=%d", file_id, len(cached))
        return cached

    try:
        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode("utf-8")
        vision_func = await get_vision_func()
        text = await vision_func(image_base64, "请提取图片中的所有文字内容，保持原有格式。")
        text = text.strip() if text else ""
        await _save_extracted_text_cache(file_id, text)
        return text
    except Exception as e:
        logger.warning("图片 OCR 文本提取失败: file_id=%s, error=%s", file_id, str(e))
        return ""


async def _extract_qualification_with_llm(
    content_text: str,
    category: Optional[str] = None,
    filename: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """使用 LLM 从文本内容中提取资质信息。

    Args:
        content_text: 文件文本内容。

    Returns:
        资质信息字典，提取失败时返回 None。
    """
    if not content_text or len(content_text.strip()) < 10:
        return None

    llm_func = await get_llm_func()

    # 限制文本长度
    if len(content_text) > 8000:
        content_text = content_text[:8000] + "\n...(内容已截断)"

    prompt = _build_extract_qualification_prompt(content_text, category, filename)

    try:
        response = await llm_func(
            prompt,
            system_prompt=_EXTRACT_QUAL_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=2000,
        )

        # 解析 JSON
        json_str = response.strip()
        if "```" in json_str:
            import re
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", json_str)
            if match:
                json_str = match.group(1).strip()

        result = json.loads(json_str)
        if isinstance(result, list) and result:
            result = result[0]
        if not isinstance(result, dict):
            return None

        logger.info("LLM 提取资质信息成功: name=%s", result.get("name"))
        return result

    except json.JSONDecodeError as e:
        logger.error("LLM 返回 JSON 解析失败: %s", str(e))
        return None
    except Exception as e:
        logger.error("LLM 提取资质信息失败: %s", str(e))
        return None


async def _extract_qualification_with_vision(
    image_path: str,
    category: Optional[str] = None,
    filename: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """使用 Vision API 从图片中提取资质信息。

    Args:
        image_path: 图片文件路径。

    Returns:
        资质信息字典，提取失败时返回 None。
    """
    try:
        # 读取图片并编码为 base64
        with open(image_path, "rb") as f:
            image_data = f.read()
        image_base64 = base64.b64encode(image_data).decode("utf-8")

        vision_func = await get_vision_func()
        response = await vision_func(image_base64, _build_vision_prompt(category, filename))

        # 尝试从 Vision 响应中解析 JSON
        json_str = response.strip()
        if "```" in json_str:
            import re
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", json_str)
            if match:
                json_str = match.group(1).strip()

        # 尝试直接解析
        try:
            result = json.loads(json_str)
        except json.JSONDecodeError:
            # 如果 Vision 返回的不是 JSON，用 LLM 二次解析
            llm_func = await get_llm_func()
            result_str = await llm_func(
                f"请将以下证书识别结果转换为 JSON 格式（包含 name/number/issue_date/"
                f"expiry_date/issuing_authority/scope/level/holder 字段）：\n\n{response}",
                system_prompt="只输出 JSON 对象，不要输出其他内容。",
                temperature=0.1,
                max_tokens=1000,
            )
            if "```" in result_str:
                import re
                match = re.search(r"```(?:json)?\s*([\s\S]*?)```", result_str)
                if match:
                    result_str = match.group(1).strip()
            result = json.loads(result_str)

        if isinstance(result, list) and result:
            result = result[0]
        if not isinstance(result, dict):
            return None

        logger.info("Vision 提取资质信息成功: name=%s", result.get("name"))
        return result

    except Exception as e:
        logger.error("Vision 提取资质信息失败: %s", str(e))
        return None


async def _create_qualification_record(
    file_id: int, category: str, qual_data: dict[str, Any], raw_text: str = ""
) -> None:
    """创建 Qualification 数据库记录。

    Args:
        file_id: 关联的知识库文件 ID。
        category: 分类。
        qual_data: 资质信息字典。
        raw_text: 原始文本。
    """
    expiry_date = normalize_qualification_field(qual_data.get("expiry_date"))
    status = normalize_qualification_field(qual_data.get("status")) or _compute_status(expiry_date)
    now = _now_iso()

    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO qualifications
               (file_id, name, number, issue_date, expiry_date, issuing_authority,
                scope, level, holder, category, status, raw_text, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                file_id,
                normalize_qualification_field(qual_data.get("name")),
                normalize_qualification_field(qual_data.get("number")),
                normalize_qualification_field(qual_data.get("issue_date")),
                expiry_date,
                normalize_qualification_field(qual_data.get("issuing_authority")),
                normalize_qualification_field(qual_data.get("scope")),
                normalize_qualification_field(qual_data.get("level")),
                normalize_qualification_field(qual_data.get("holder")),
                category,
                status,
                raw_text[:500] if raw_text else None,
                now,
            ),
        )
        await db.commit()
    finally:
        await db.close()


async def parse_file(file_id: int) -> None:
    """异步解析知识库文件流程（通过 BackgroundTask 调用）。

    流程步骤：
    1. 更新 status=parsing
    2. 格式识别（用 filetype 库）
    3. 如果是 DOCX/XLSX → file_convert 转 PDF
    4. 如果是图片/扫描件 → Vision API 提取
    5. 纯文本提取（PyPDF2，不依赖 RAG-Anything/mineru）
    6. LLM 提取资质信息（7 个字段）
    7. 创建 Qualification 记录
    8. 更新 status=completed

    Args:
        file_id: 知识库文件 ID。
    """
    logger.info("开始解析知识库文件: file_id=%s", file_id)

    try:
        # 获取文件信息
        db = await get_db()
        try:
            cursor = await db.execute("SELECT * FROM knowledge_files WHERE id = ?", (file_id,))
            row = await cursor.fetchone()
        finally:
            await db.close()

        if row is None:
            logger.error("知识库文件不存在: file_id=%s", file_id)
            return

        kf = KnowledgeFile(**dict(row))
        file_path = kf.file_path
        file_type = kf.file_type or detect_file_type(file_path)

        # 步骤 1：更新状态为 parsing
        await _update_file_status(file_id, "parsing")

        if kf.category == "performance":
            content_text = ""
            if file_type == "image":
                content_text = await _get_or_extract_image_text(file_id, file_path)
            elif file_type in ("pdf", "docx", "doc", "xlsx"):
                content_text = await _get_or_extract_file_text(file_id, file_path, file_type)

            db = await get_db()
            try:
                await db.execute("DELETE FROM qualifications WHERE file_id = ?", (file_id,))
                await db.commit()
            finally:
                await db.close()

            projects = await performance_project_service.sync_projects_from_performance_file(
                file_id=file_id,
                filename=kf.filename,
                text=content_text,
            )
            await _update_file_status(file_id, "completed", parsed_at=_now_iso())
            logger.info(
                "业绩文件解析完成: file_id=%s, projects=%s",
                file_id,
                len(projects),
            )
            return

        qual_data: Optional[dict[str, Any]] = None
        placeholder_reason: Optional[str] = None
        extracted_text_for_record = ""

        # 步骤 2-5：根据文件类型选择解析策略
        if file_type == "image":
            # 图片：先 OCR 成文本并缓存，再走本地规则/LLM；失败时才用结构化 Vision 兜底
            logger.info("使用 Vision OCR 解析图片: file_id=%s", file_id)
            content_text = await _get_or_extract_image_text(file_id, file_path)
            extracted_text_for_record = content_text
            if content_text and len(content_text.strip()) >= 10:
                qual_data = _extract_qualification_from_text_locally(
                    content_text,
                    kf.category,
                    kf.filename,
                )
                if not has_meaningful_qualification_data(qual_data):
                    qual_data = await _extract_qualification_with_llm(
                        content_text,
                        kf.category,
                        kf.filename,
                    )
            if not has_meaningful_qualification_data(qual_data):
                qual_data = await _extract_qualification_with_vision(
                    file_path,
                    kf.category,
                    kf.filename,
                )
            if not has_meaningful_qualification_data(qual_data):
                placeholder_reason = "Vision 未提取到有效资质字段"

        elif file_type in ("docx", "doc", "xlsx"):
            # Office 文档：先转 PDF，再用纯文本提取（PyPDF2，不依赖 RAG-Anything/mineru）
            logger.info("转换 Office 文档为 PDF: file_id=%s, type=%s", file_id, file_type)
            try:
                content_text = await _get_or_extract_file_text(file_id, file_path, file_type)
                extracted_text_for_record = content_text
                if content_text and len(content_text.strip()) >= 10:
                    qual_data = _extract_qualification_from_text_locally(
                        content_text,
                        kf.category,
                        kf.filename,
                    )
                    if not has_meaningful_qualification_data(qual_data):
                        qual_data = await _extract_qualification_with_llm(
                            content_text,
                            kf.category,
                            kf.filename,
                        )
                else:
                    placeholder_reason = "Office 转 PDF 后未提取到可解析文本，OCR 也未识别到文字"
            except Exception as e:
                logger.error("Office 文档解析失败: file_id=%s, error=%s", file_id, str(e))
                # 尝试直接用 LLM 从文件名提取
                qual_data = await _extract_qualification_with_llm(
                    f"文件名: {kf.filename}",
                    kf.category,
                    kf.filename,
                )
                if not has_meaningful_qualification_data(qual_data):
                    placeholder_reason = f"Office 文档解析失败：{str(e)}"

        elif file_type == "pdf":
            # PDF：纯文本提取（PyPDF2，不依赖 RAG-Anything/mineru）
            logger.info("使用纯文本提取 PDF: file_id=%s", file_id)
            try:
                content_text = await _get_or_extract_file_text(file_id, file_path, file_type)
                extracted_text_for_record = content_text
                if content_text and len(content_text.strip()) >= 10:
                    qual_data = _extract_qualification_from_text_locally(
                        content_text,
                        kf.category,
                        kf.filename,
                    )
                    if not has_meaningful_qualification_data(qual_data):
                        qual_data = await _extract_qualification_with_llm(
                            content_text,
                            kf.category,
                            kf.filename,
                        )
                else:
                    placeholder_reason = "PDF 未提取到可解析文本，OCR 也未识别到文字"
            except Exception as e:
                logger.error("PDF 解析失败: file_id=%s, error=%s", file_id, str(e))
                placeholder_reason = f"PDF 解析失败：{str(e)}"

        else:
            logger.warning("未知文件类型: file_id=%s, type=%s", file_id, file_type)
            # 尝试用文件名提取
            qual_data = await _extract_qualification_with_llm(
                f"文件名: {kf.filename}",
                kf.category,
                kf.filename,
            )
            if not has_meaningful_qualification_data(qual_data):
                placeholder_reason = f"未知文件类型：{file_type}"

        # 步骤 6-7：创建 Qualification 记录
        # 重新解析时，先删除该文件关联的旧资质记录（避免重复数据）
        # 首次解析时 file_id 没有关联资质，DELETE 0 行，无副作用
        db = await get_db()
        try:
            await db.execute("DELETE FROM qualifications WHERE file_id = ?", (file_id,))
            await db.commit()
        finally:
            await db.close()

        if not has_meaningful_qualification_data(qual_data):
            qual_data = build_placeholder_qualification(
                kf.filename,
                placeholder_reason or "未提取到有效资质字段",
                kf.category,
            )

        if qual_data is not None:
            await _create_qualification_record(
                file_id=file_id,
                category=kf.category or "enterprise",
                qual_data=qual_data,
                raw_text=extracted_text_for_record or str(qual_data),
            )
            logger.info("资质记录创建成功: file_id=%s, name=%s", file_id, qual_data.get("name"))
        else:
            logger.warning("未能提取资质信息: file_id=%s", file_id)

        # 步骤 8：更新状态为 completed
        await _update_file_status(file_id, "completed", parsed_at=_now_iso())
        logger.info("知识库文件解析完成: file_id=%s", file_id)

    except Exception as e:
        logger.error(
            "知识库文件解析失败: file_id=%s, error=%s", file_id, str(e), exc_info=True
        )
        await _update_file_status(file_id, "failed")


async def get_qualifications(
    category: Optional[str] = None,
) -> list[Qualification]:
    """获取资质列表（可按分类筛选）。

    Args:
        category: 分类筛选，None 表示全部。

    Returns:
        Qualification 列表。
    """
    db = await get_db()
    try:
        if category:
            cursor = await db.execute(
                "SELECT * FROM qualifications WHERE category = ? ORDER BY id DESC",
                (category,),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM qualifications ORDER BY id DESC"
            )
        rows = await cursor.fetchall()
        return [Qualification(**dict(r)) for r in rows]
    finally:
        await db.close()


async def get_incomplete_qualification_file_ids(category: Optional[str] = None) -> list[int]:
    """获取待补全资质对应的源文件 ID，用于一键重新分析。"""
    db = await get_db()
    try:
        params: list[Any] = []
        where = [
            "q.file_id IS NOT NULL",
            "(q.status = 'needs_completion' OR q.scope LIKE '待人工补全：%')",
        ]
        if category:
            where.append("q.category = ?")
            params.append(category)
        cursor = await db.execute(
            f"""
            SELECT DISTINCT q.file_id
            FROM qualifications q
            JOIN knowledge_files f ON f.id = q.file_id
            WHERE {' AND '.join(where)}
              AND f.status NOT IN ('pending', 'parsing')
            ORDER BY q.file_id
            """,
            params,
        )
        rows = await cursor.fetchall()
        return [int(row["file_id"]) for row in rows]
    finally:
        await db.close()


async def get_qualification(qual_id: int) -> Optional[Qualification]:
    """获取单条资质信息。

    Args:
        qual_id: 资质 ID。

    Returns:
        Qualification 实例，不存在时返回 None。
    """
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM qualifications WHERE id = ?", (qual_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return Qualification(**dict(row))
    finally:
        await db.close()


async def create_qualification(data: dict[str, Any]) -> Qualification:
    """手动新增资质记录。

    Args:
        data: 资质信息字典。

    Returns:
        创建的 Qualification 实例。
    """
    expiry_date = normalize_qualification_field(data.get("expiry_date"))
    status = data.get("status") or _compute_status(expiry_date)
    now = _now_iso()

    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO qualifications
               (file_id, name, number, issue_date, expiry_date, issuing_authority,
                scope, level, holder, category, status, raw_text, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("file_id"),
                normalize_qualification_field(data.get("name")),
                normalize_qualification_field(data.get("number")),
                normalize_qualification_field(data.get("issue_date")),
                expiry_date,
                normalize_qualification_field(data.get("issuing_authority")),
                normalize_qualification_field(data.get("scope")),
                normalize_qualification_field(data.get("level")),
                normalize_qualification_field(data.get("holder")),
                normalize_qualification_field(data.get("category")),
                normalize_qualification_field(status),
                normalize_qualification_field(data.get("raw_text")),
                now,
            ),
        )
        await db.commit()
        qual_id = cursor.lastrowid
    finally:
        await db.close()

    return await get_qualification(qual_id)  # type: ignore


async def update_qualification(qual_id: int, data: dict[str, Any]) -> Optional[Qualification]:
    """更新资质信息。

    Args:
        qual_id: 资质 ID。
        data: 更新字段字典。

    Returns:
        更新后的 Qualification 实例，不存在时返回 None。
    """
    # 允许更新的字段
    allowed_fields = {
        "name", "number", "issue_date", "expiry_date", "issuing_authority",
        "scope", "level", "holder", "category", "status",
    }

    updates = {
        k: normalize_qualification_field(v)
        for k, v in data.items()
        if k in allowed_fields
    }

    # 如果更新了有效期，重新计算状态
    if "expiry_date" in updates and "status" not in updates:
        updates["status"] = _compute_status(updates["expiry_date"])

    if not updates:
        return await get_qualification(qual_id)

    db = await get_db()
    try:
        sets = [f"{k} = ?" for k in updates]
        params = list(updates.values())
        params.append(qual_id)
        await db.execute(
            f"UPDATE qualifications SET {', '.join(sets)} WHERE id = ?",
            params,
        )
        await db.commit()
    finally:
        await db.close()

    return await get_qualification(qual_id)


async def delete_qualification(qual_id: int) -> bool:
    """删除资质记录。

    Args:
        qual_id: 资质 ID。

    Returns:
        True 如果删除成功，False 如果记录不存在。
    """
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM qualifications WHERE id = ?", (qual_id,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def bulk_update_qualification_category(
    qualification_ids: list[int],
    category: str,
) -> dict[str, Any]:
    """批量修改资质分类，并同步修改关联源文件分类。

    Args:
        qualification_ids: 要修改的资质 ID 列表。
        category: 目标分类。

    Returns:
        操作统计，包括更新资质数、更新文件数、缺失资质 ID。
    """
    unique_ids = sorted({int(qid) for qid in qualification_ids if int(qid) > 0})
    if not unique_ids:
        return {
            "updated_qualification_count": 0,
            "updated_file_count": 0,
            "missing_qualification_ids": [],
        }

    placeholders = ",".join("?" for _ in unique_ids)
    db = await get_db()
    try:
        cursor = await db.execute(
            f"SELECT id, file_id FROM qualifications WHERE id IN ({placeholders})",
            unique_ids,
        )
        rows = await cursor.fetchall()
        found_ids = {int(row["id"]) for row in rows}
        missing_ids = [qid for qid in unique_ids if qid not in found_ids]
        file_ids = sorted(
            {
                int(row["file_id"])
                for row in rows
                if row["file_id"] is not None
            }
        )

        updated_qualification_count = 0
        updated_file_count = 0
        if found_ids:
            found_placeholders = ",".join("?" for _ in found_ids)
            cursor = await db.execute(
                f"UPDATE qualifications SET category = ? WHERE id IN ({found_placeholders})",
                [category, *sorted(found_ids)],
            )
            updated_qualification_count = cursor.rowcount

        if file_ids:
            file_placeholders = ",".join("?" for _ in file_ids)
            cursor = await db.execute(
                f"UPDATE knowledge_files SET category = ? WHERE id IN ({file_placeholders})",
                [category, *file_ids],
            )
            updated_file_count = cursor.rowcount

        await db.commit()
        return {
            "updated_qualification_count": updated_qualification_count,
            "updated_file_count": updated_file_count,
            "missing_qualification_ids": missing_ids,
        }
    finally:
        await db.close()


async def bulk_delete_qualifications_by_source(
    qualification_ids: list[int],
) -> dict[str, Any]:
    """按源文件语义批量删除资质。

    有 file_id 的资质会删除其源文件、该文件解析出的所有资质记录和物理文件；
    无 file_id 的手动资质仅删除该资质记录。

    Args:
        qualification_ids: 用户选中的资质 ID 列表。

    Returns:
        删除统计。
    """
    unique_ids = sorted({int(qid) for qid in qualification_ids if int(qid) > 0})
    if not unique_ids:
        return {
            "deleted_file_count": 0,
            "deleted_manual_qualification_count": 0,
            "deleted_related_qualification_count": 0,
            "missing_qualification_ids": [],
        }

    placeholders = ",".join("?" for _ in unique_ids)
    db = await get_db()
    try:
        cursor = await db.execute(
            f"SELECT id, file_id FROM qualifications WHERE id IN ({placeholders})",
            unique_ids,
        )
        rows = await cursor.fetchall()
        found_ids = {int(row["id"]) for row in rows}
        missing_ids = [qid for qid in unique_ids if qid not in found_ids]
        file_ids = sorted(
            {
                int(row["file_id"])
                for row in rows
                if row["file_id"] is not None
            }
        )
        manual_ids = sorted(
            int(row["id"])
            for row in rows
            if row["file_id"] is None
        )

        deleted_related_qualification_count = 0
        deleted_file_count = 0
        if file_ids:
            file_placeholders = ",".join("?" for _ in file_ids)
            cursor = await db.execute(
                f"SELECT id, file_path FROM knowledge_files WHERE id IN ({file_placeholders})",
                file_ids,
            )
            file_rows = await cursor.fetchall()

            cursor = await db.execute(
                f"SELECT COUNT(*) AS cnt FROM qualifications WHERE file_id IN ({file_placeholders})",
                file_ids,
            )
            count_row = await cursor.fetchone()
            deleted_related_qualification_count = int(count_row["cnt"] or 0)

            await db.execute(
                f"DELETE FROM qualifications WHERE file_id IN ({file_placeholders})",
                file_ids,
            )
            cursor = await db.execute(
                f"DELETE FROM knowledge_files WHERE id IN ({file_placeholders})",
                file_ids,
            )
            deleted_file_count = cursor.rowcount

            for file_row in file_rows:
                file_path = file_row["file_path"]
                try:
                    if file_path and os.path.exists(file_path):
                        os.remove(file_path)
                except OSError as e:
                    logger.warning(
                        "批量删除物理文件失败（已忽略）: file_path=%s, error=%s",
                        file_path,
                        str(e),
                    )

        deleted_manual_qualification_count = 0
        if manual_ids:
            manual_placeholders = ",".join("?" for _ in manual_ids)
            cursor = await db.execute(
                f"DELETE FROM qualifications WHERE id IN ({manual_placeholders})",
                manual_ids,
            )
            deleted_manual_qualification_count = cursor.rowcount

        await db.commit()
        return {
            "deleted_file_count": deleted_file_count,
            "deleted_manual_qualification_count": deleted_manual_qualification_count,
            "deleted_related_qualification_count": deleted_related_qualification_count,
            "missing_qualification_ids": missing_ids,
        }
    finally:
        await db.close()


async def list_files(category: Optional[str] = None) -> list[KnowledgeFile]:
    """获取知识库文件列表。

    Args:
        category: 分类筛选，None 表示全部。

    Returns:
        KnowledgeFile 列表。
    """
    db = await get_db()
    try:
        if category:
            cursor = await db.execute(
                "SELECT * FROM knowledge_files WHERE category = ? ORDER BY upload_time DESC, id DESC",
                (category,),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM knowledge_files ORDER BY upload_time DESC, id DESC"
            )
        rows = await cursor.fetchall()
        return [KnowledgeFile(**dict(r)) for r in rows]
    finally:
        await db.close()


async def get_file_status(file_id: int) -> Optional[dict[str, Any]]:
    """获取知识库文件解析状态。

    Args:
        file_id: 文件 ID。

    Returns:
        包含 file_id 和 status 的字典，不存在时返回 None。
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, status FROM knowledge_files WHERE id = ?",
            (file_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return {"file_id": row["id"], "status": row["status"]}
    finally:
        await db.close()


async def get_file(file_id: int) -> Optional[KnowledgeFile]:
    """按 ID 获取知识库文件元数据。"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM knowledge_files WHERE id = ?",
            (file_id,),
        )
        row = await cursor.fetchone()
        return KnowledgeFile(**dict(row)) if row else None
    finally:
        await db.close()


async def delete_file(file_id: int) -> bool:
    """删除知识库文件及其关联的资质记录和物理文件。

    删除顺序：
    1. 查询 knowledge_files 记录，不存在返回 False
    2. 删除关联的 qualifications 记录
    3. 删除物理文件（忽略文件不存在的异常）
    4. 删除 knowledge_files 记录
    5. 提交事务，返回 True

    Args:
        file_id: 知识库文件 ID。

    Returns:
        True 如果删除成功，False 如果文件记录不存在。
    """
    db = await get_db()
    try:
        # 1. 查询文件记录（需要 file_path 用于删除物理文件）
        cursor = await db.execute(
            "SELECT file_path FROM knowledge_files WHERE id = ?",
            (file_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return False
        file_path = row["file_path"]

        # 2. 删除关联的资质记录
        await db.execute(
            "DELETE FROM qualifications WHERE file_id = ?",
            (file_id,),
        )

        # 3. 删除物理文件（忽略文件不存在的异常）
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except OSError as e:
            logger.warning("删除物理文件失败（已忽略）: file_path=%s, error=%s", file_path, str(e))

        # 4. 删除 knowledge_files 记录
        await db.execute(
            "DELETE FROM knowledge_files WHERE id = ?",
            (file_id,),
        )

        # 5. 提交事务
        await db.commit()
        logger.info("知识库文件删除成功: file_id=%s", file_id)
        return True
    finally:
        await db.close()


async def prepare_reparse(file_id: int) -> None:
    """准备重新解析：校验文件存在性、状态，并重置为 pending。

    Args:
        file_id: 知识库文件 ID。

    Raises:
        ValueError: 文件不存在或正在解析中时抛出。
    """
    db = await get_db()
    try:
        # 1. 查询文件记录
        cursor = await db.execute(
            "SELECT status FROM knowledge_files WHERE id = ?",
            (file_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise ValueError(f"文件 {file_id} 不存在")

        # 2. 状态校验：pending/parsing 状态不允许重新解析
        current_status = row["status"]
        if current_status in ("pending", "parsing"):
            raise ValueError("文件正在解析中，请稍后再试")

        # 3. 重置状态为 pending
        await db.execute(
            "UPDATE knowledge_files SET status = 'pending' WHERE id = ?",
            (file_id,),
        )
        await db.commit()
        logger.info("知识库文件已重置为 pending，准备重新解析: file_id=%s", file_id)
    finally:
        await db.close()
