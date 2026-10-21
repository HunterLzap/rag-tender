FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    libreoffice-writer \
    libreoffice-calc \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

ENV TENDER_DATA_DIR=/data \
    TENDER_LIBREOFFICE_PATH=/usr/bin/libreoffice \
    TENDER_AUTO_CREATE_SCHEMA=false

EXPOSE 8000
CMD ["sh", "-c", ".venv/bin/python -m app.db_bootstrap && exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000"]
