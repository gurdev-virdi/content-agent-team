#!/bin/zsh
set -e
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  echo "Missing repo runtime. Run: ${PROJECT_DIR}/scripts/bootstrap.sh" >&2
  exit 1
fi

cd "$PROJECT_DIR"

if [ -f "$PROJECT_DIR/.env" ]; then
  set -a
  source "$PROJECT_DIR/.env"
  set +a
fi

HOST="${MISSION_CONTROL_HOST:-127.0.0.1}"
PORT="${MISSION_CONTROL_PORT:-8765}"
RELOAD="${MISSION_CONTROL_RELOAD:-false}"

echo "Starting Mission Control on http://${HOST}:${PORT} ..."
UVICORN_ARGS=(scripts.mission_control.app:app --host "$HOST" --port "$PORT")
if [[ "$RELOAD" == "1" || "$RELOAD" == "true" || "$RELOAD" == "yes" || "$RELOAD" == "on" ]]; then
  UVICORN_ARGS+=(--reload)
fi

"$PYTHON_BIN" -m uvicorn "${UVICORN_ARGS[@]}" &
SERVER_PID=$!

sleep 1
open "http://${HOST}:${PORT}" 2>/dev/null || true

echo "Mission Control running (PID $SERVER_PID). Press Ctrl+C to stop."
wait $SERVER_PID
