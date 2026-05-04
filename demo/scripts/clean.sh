#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

bash "$SCRIPT_DIR/stop.sh" || true

rm -rf \
  "$PROJECT_ROOT/runtime" \
  "$BACKEND_DIR/runtime" \
  "$FRONTEND_DIR/.next"

rm -f \
  "$PROJECT_ROOT/.env" \
  "$FRONTEND_DIR/.env.local"

find "$BACKEND_DIR" -type d -name "__pycache__" -prune -exec rm -rf {} +

if [ "${1:-}" = "--all" ]; then
  rm -rf \
    "$BACKEND_DIR/.venv" \
    "$FRONTEND_DIR/node_modules"
fi

echo "Cleaned generated runtime files."
if [ "${1:-}" = "--all" ]; then
  echo "Also removed backend/.venv and frontend/node_modules."
fi
