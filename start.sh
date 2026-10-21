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

is_running() {
  local pid_file="$PID_DIR/$1.pid"
  [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null
}

start_service() {
  local name="$1"
  shift
  if is_running "$name"; then
    return
  fi
  TENDER_LIVE_MODEL_CALLS="${TENDER_LIVE_MODEL_CALLS:-false}" \
    "$ROOT/backend/.venv/bin/python" - "$LOG_DIR/$name.log" "$PID_DIR/$name.pid" "$@" <<'PY'
import subprocess
import sys
from pathlib import Path

with open(sys.argv[1], "ab", buffering=0) as log:
    process = subprocess.Popen(
        sys.argv[3:],
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
Path(sys.argv[2]).write_text(str(process.pid))
PY
}

(
  cd "$ROOT/backend"
  .venv/bin/python -m app.db_bootstrap
  start_service api "$ROOT/backend/.venv/bin/uvicorn" \
    app.main:app --host 127.0.0.1 --port 8000
  start_service worker "$ROOT/backend/.venv/bin/python" -m app.worker
)
(
  cd "$ROOT/frontend"
  start_service frontend "$ROOT/frontend/node_modules/.bin/vite" \
    --host 127.0.0.1 --strictPort
)

echo "API:      http://127.0.0.1:8000/docs"
echo "Frontend: http://127.0.0.1:5173"
echo "Logs:     $LOG_DIR"
echo "Live model calls: ${TENDER_LIVE_MODEL_CALLS:-false}"
