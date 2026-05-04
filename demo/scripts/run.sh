#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
RUNTIME_DIR="$PROJECT_ROOT/runtime"
LOG_DIR="$RUNTIME_DIR/logs"
PID_DIR="$RUNTIME_DIR/pids"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
FRONTEND_MODE="${FRONTEND_MODE:-prod}"

start_detached() {
  local log_file="$1"
  shift

  if command -v setsid >/dev/null 2>&1; then
    setsid "$@" > "$log_file" 2>&1 < /dev/null &
  else
    nohup "$@" > "$log_file" 2>&1 < /dev/null &
  fi

  echo $!
}

assert_started() {
  local name="$1"
  local pid="$2"
  local log_file="$3"

  sleep 2
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "$name failed to start." >&2
    if [ -f "$log_file" ]; then
      echo "--- $name log ---" >&2
      tail -n 80 "$log_file" >&2
    fi
    exit 1
  fi
}

mkdir -p "$LOG_DIR" "$PID_DIR" "$BACKEND_DIR/runtime"

if [ ! -f "$PROJECT_ROOT/.env" ]; then
  cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
fi

if [ ! -f "$FRONTEND_DIR/.env.local" ]; then
  cp "$FRONTEND_DIR/.env.local.example" "$FRONTEND_DIR/.env.local"
fi

if [ -f "$PID_DIR/backend.pid" ] && kill -0 "$(cat "$PID_DIR/backend.pid")" 2>/dev/null; then
  echo "Backend already running on PID $(cat "$PID_DIR/backend.pid")"
else
  if [ ! -d "$BACKEND_DIR/.venv" ]; then
    python3 -m venv "$BACKEND_DIR/.venv"
  fi

  # shellcheck disable=SC1091
  source "$BACKEND_DIR/.venv/bin/activate"
  python -m pip install --upgrade pip
  python -m pip install -r "$PROJECT_ROOT/requirements.txt"

  (
    cd "$BACKEND_DIR"
    python - <<'PY'
import asyncio
from app.infra.persistence.database import init_db
asyncio.run(init_db())
PY
  )

  (
    cd "$BACKEND_DIR"
    # shellcheck disable=SC1091
    source "$BACKEND_DIR/.venv/bin/activate"
    backend_pid="$(start_detached "$LOG_DIR/backend.log" python -m uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT")"
    echo "$backend_pid" > "$PID_DIR/backend.pid"
    assert_started "Backend" "$backend_pid" "$LOG_DIR/backend.log"
  )
fi

if [ -f "$PID_DIR/frontend.pid" ] && kill -0 "$(cat "$PID_DIR/frontend.pid")" 2>/dev/null; then
  echo "Frontend already running on PID $(cat "$PID_DIR/frontend.pid")"
else
  (
    cd "$FRONTEND_DIR"
    if [ ! -d "node_modules" ]; then
      if [ -f "package-lock.json" ]; then
        npm ci
      else
        npm install
      fi
    fi

    if [ "$FRONTEND_MODE" = "dev" ]; then
      frontend_pid="$(start_detached "$LOG_DIR/frontend.log" npm run dev -- --hostname 0.0.0.0 --port "$FRONTEND_PORT")"
    else
      npm run build
      frontend_pid="$(start_detached "$LOG_DIR/frontend.log" npm run start -- --hostname 0.0.0.0 --port "$FRONTEND_PORT")"
    fi

    echo "$frontend_pid" > "$PID_DIR/frontend.pid"
    assert_started "Frontend" "$frontend_pid" "$LOG_DIR/frontend.log"
  )
fi

echo "Backend:  http://localhost:$BACKEND_PORT"
echo "Frontend: http://localhost:$FRONTEND_PORT"
echo "Mode:     frontend=$FRONTEND_MODE"
echo "Logs:     $LOG_DIR"
