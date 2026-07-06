"""LibreOffice 转换回归测试。"""

import asyncio
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services import file_convert


class LibreOfficeConversionTests(unittest.TestCase):
    def test_conversion_does_not_require_async_subprocess_support(self) -> None:
        """Uvicorn 热重载的事件循环不支持异步子进程时仍能转换。"""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            input_path = Path(temp_dir) / "sample.doc"
            output_dir = Path(temp_dir) / "output"
            fake_soffice = Path(temp_dir) / "soffice.exe"
            input_path.write_bytes(b"sample")
            fake_soffice.write_bytes(b"fake")

            def fake_run(args, **kwargs):
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / "sample.pdf").write_bytes(b"%PDF-1.4\n%%EOF")
                return subprocess.CompletedProcess(args, 0, b"converted", b"")

            original_path = file_convert.LIBREOFFICE_PATH
            file_convert.LIBREOFFICE_PATH = str(fake_soffice)
            file_convert.subprocess = subprocess
            try:
                with (
                    patch.object(
                        asyncio,
                        "create_subprocess_exec",
                        side_effect=NotImplementedError,
                    ),
                    patch.object(subprocess, "run", side_effect=fake_run),
                ):
                    result = asyncio.run(
                        file_convert.convert_to_pdf(
                            str(input_path),
                            str(output_dir),
                        )
                    )
            finally:
                file_convert.LIBREOFFICE_PATH = original_path

            self.assertEqual(str(output_dir / "sample.pdf"), result)


if __name__ == "__main__":
    unittest.main()
