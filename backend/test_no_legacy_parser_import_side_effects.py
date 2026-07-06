"""确保常规解析链路不会因导入 LLM/Vision 工具触发旧 RAG/MinerU 副作用。"""

import os
import subprocess
import sys


def test_importing_knowledge_service_does_not_probe_legacy_rag_parser() -> None:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import logging; logging.basicConfig(level=logging.WARNING); "
            "import app.services.knowledge_service; print('import-ok')",
        ],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )

    output = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, output
    assert "import-ok" in output
    assert "未找到 mineru.exe" not in output
    assert "RAG-Anything 未安装" not in output


if __name__ == "__main__":
    test_importing_knowledge_service_does_not_probe_legacy_rag_parser()
    print("legacy parser import side effect tests passed")
