#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PID_DIR="$PROJECT_ROOT/runtime/pids"

stop_pid() {
  local name="$1"
  local pid_file="$PID_DIR/$name.pid"

  if [ ! -f "$pid_file" ]; then
    echo "$name not running"
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    echo "Stopped $name ($pid)"
  else
    echo "$name PID file exists but process is not running"
  fi
  rm -f "$pid_file"
}

stop_pid backend
stop_pid frontend
