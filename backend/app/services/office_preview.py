"""Render Office documents locally using their print layout."""

import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from app.config import get_settings
from app.domain.document_ir import DocumentParseError


def office_executable() -> str | None:
    configured = get_settings().libreoffice_path
    if configured:
        executable = shutil.which(configured)
        if executable:
            return executable
    for candidate in (
        "soffice", "libreoffice", "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ):
        executable = shutil.which(candidate)
        if executable:
            return executable
    return None


def render_office_pdf(path: Path) -> Path:
    executable = office_executable()
    if executable is None:
        raise DocumentParseError("原页预览需要安装 LibreOffice（Writer 和 Calc）后重新解析")
    target = path.with_suffix(".preview.pdf")
    with tempfile.TemporaryDirectory(prefix="tender-office-") as temporary:
        directory = Path(temporary)
        profile = directory / "profile"
        environment = os.environ.copy()
        if sys.platform == "darwin" and not environment.get("FONTCONFIG_FILE"):
            # Headless macOS builds may not discover system CJK fonts themselves.
            fonts = ET.Element("fontconfig")
            for font_dir in (
                "/System/Library/Fonts", "/Library/Fonts",
                str(Path.home() / "Library/Fonts"), "/System/Library/AssetsV2",
            ):
                ET.SubElement(fonts, "dir").text = font_dir
            ET.SubElement(fonts, "cachedir").text = str(
                get_settings().resolved_data_dir / "font-cache"
            )
            font_config = directory / "fonts.conf"
            ET.ElementTree(fonts).write(font_config, encoding="utf-8", xml_declaration=True)
            environment["FONTCONFIG_FILE"] = str(font_config)
        export_filter = "calc_pdf_Export" if path.suffix.lower() == ".xlsx" else "writer_pdf_Export"
        result = subprocess.run(
            [
                executable, f"-env:UserInstallation={profile.as_uri()}",
                "--headless", "--nologo", "--nodefault", "--norestore",
                "--convert-to", f"pdf:{export_filter}", "--outdir", str(directory), str(path),
            ],
            env=environment, capture_output=True, text=True, timeout=120, check=False,
        )
        converted = directory / f"{path.stem}.pdf"
        if result.returncode != 0 or not converted.exists():
            raise DocumentParseError(
                f"原页渲染失败：{(result.stderr or result.stdout)[-400:].strip()}"
            )
        shutil.copyfile(converted, target)
    return target
