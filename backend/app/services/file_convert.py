"""LibreOffice 文件转换封装。

使用 LibreOffice headless 模式将 Office 文档（DOCX/DOC/XLSX/PPTX）
转换为 PDF 格式，供后续统一 PDF 文本提取 / OCR 流程使用。
"""

import asyncio
import logging
import os
import subprocess
import tempfile

from app.config import LIBREOFFICE_PATH
from app.utils.api_response import ErrorCode

logger = logging.getLogger(__name__)


def is_libreoffice_available() -> bool:
    """检查 LibreOffice 可执行文件是否存在。

    Returns:
        True 如果 soffice.exe 存在于配置路径中。
    """
    return os.path.isfile(LIBREOFFICE_PATH)


async def convert_to_pdf(input_path: str, output_dir: str) -> str:
    """使用 LibreOffice headless 将 Office 文档转换为 PDF。

    在线程中通过 subprocess.run 执行 soffice.exe，避免阻塞事件循环，
    同时兼容 Windows 下 Uvicorn 热重载使用的 SelectorEventLoop。

    Args:
        input_path: 输入文件路径（DOCX/DOC/XLSX/PPTX 等）。
        output_dir: PDF 输出目录。

    Returns:
        转换后的 PDF 文件绝对路径。

    Raises:
        RuntimeError: LibreOffice 不可用或转换失败时抛出，包含 ErrorCode 信息。
    """
    if not is_libreoffice_available():
        logger.error("LibreOffice 不可用: %s", LIBREOFFICE_PATH)
        raise RuntimeError(
            f"LibreOffice 不可用（错误码 {ErrorCode.LIBREOFFICE_CONVERT_FAILED}）: "
            f"未找到 {LIBREOFFICE_PATH}"
        )

    if not os.path.isfile(input_path):
        raise RuntimeError(f"输入文件不存在: {input_path}")

    os.makedirs(output_dir, exist_ok=True)

    # 为 LibreOffice 创建独立的用户配置目录，避免并发冲突
    user_install_dir = tempfile.mkdtemp(prefix="lo_profile_")
    user_install_uri = f"file:///{user_install_dir.replace(os.sep, '/')}"

    cmd_args = [
        LIBREOFFICE_PATH,
        f"-env:UserInstallation={user_install_uri}",
        "--headless",
        "--norestore",
        "--convert-to", "pdf",
        "--outdir", output_dir,
        input_path,
    ]

    logger.info("LibreOffice 转换: %s -> %s", input_path, output_dir)

    try:
        process = await asyncio.to_thread(
            subprocess.run,
            cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            check=False,
        )

        stdout_text = process.stdout.decode("utf-8", errors="replace") if process.stdout else ""
        stderr_text = process.stderr.decode("utf-8", errors="replace") if process.stderr else ""

        if process.returncode != 0:
            logger.error(
                "LibreOffice 转换失败 (returncode=%d): stdout=%s, stderr=%s",
                process.returncode,
                stdout_text,
                stderr_text,
            )
            raise RuntimeError(
                f"LibreOffice 转换失败（错误码 {ErrorCode.LIBREOFFICE_CONVERT_FAILED}）: "
                f"{stderr_text or stdout_text}"
            )

        # 构造输出 PDF 路径
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        pdf_path = os.path.join(output_dir, f"{base_name}.pdf")

        if not os.path.isfile(pdf_path):
            # 尝试在输出目录中查找刚生成的 PDF
            generated_pdfs = [
                f for f in os.listdir(output_dir)
                if f.endswith(".pdf") and base_name in f
            ]
            if generated_pdfs:
                pdf_path = os.path.join(output_dir, generated_pdfs[0])
            else:
                raise RuntimeError(
                    f"LibreOffice 转换后未找到 PDF 文件（错误码 "
                    f"{ErrorCode.LIBREOFFICE_CONVERT_FAILED}）"
                )

        logger.info("LibreOffice 转换成功: %s", pdf_path)
        return pdf_path

    except subprocess.TimeoutExpired:
        logger.error("LibreOffice 转换超时（120秒）: %s", input_path)
        raise RuntimeError(
            f"LibreOffice 转换超时（错误码 {ErrorCode.LIBREOFFICE_CONVERT_FAILED}）"
        )
    except RuntimeError:
        raise
    except Exception as e:
        logger.error("LibreOffice 转换异常: %s, error=%s", input_path, str(e))
        raise RuntimeError(
            f"LibreOffice 转换异常（错误码 {ErrorCode.LIBREOFFICE_CONVERT_FAILED}）: {str(e)}"
        )
