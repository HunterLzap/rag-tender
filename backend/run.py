"""RAG-Tender Assistant 后端启动入口。

使用 uvicorn 启动 FastAPI 应用，监听 127.0.0.1:8000。
"""

import uvicorn


def main() -> None:
    """启动 uvicorn 服务器。"""
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
