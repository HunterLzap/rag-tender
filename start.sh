#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$ROOT/data/logs"
PID_DIR="$ROOT/data/pids"
mkdir -p "$LOG_DIR" "$PID_DIR"

if [[ ! -x "$ROOT/backend/.venv/bin/uvicorn" ]]; then
  echo "missing backend virtualenv; run: cd backend && uv sync"
  exit 1
fi
if [[ ! -x "$ROOT/frontend/node_modules/.bin/vite" ]]; then
  echo "missing frontend dependencies; run: cd frontend && pnpm install"
  exit 1
fi

(
  cd "$ROOT/backend"
  .venv/bin/python -m app.db_bootstrap
  .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 \
    >"$LOG_DIR/api.log" 2>&1 &
  echo $! >"$PID_DIR/api.pid"
  .venv/bin/python -m app.worker >"$LOG_DIR/worker.log" 2>&1 &
  echo $! >"$PID_DIR/worker.pid"
)
(
  cd "$ROOT/frontend"
  pnpm dev --host 127.0.0.1 >"$LOG_DIR/frontend.log" 2>&1 &
  echo $! >"$PID_DIR/frontend.pid"
)

echo "API:      http://127.0.0.1:8000/docs"
echo "Frontend: http://127.0.0.1:5173"
echo "Logs:     $LOG_DIR"
