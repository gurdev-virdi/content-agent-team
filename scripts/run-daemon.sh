#!/bin/zsh
# Wrapper so launchd inherits the user's full environment and TCC permissions.
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="/usr/bin/python3"
fi

cd "$PROJECT_DIR"
source ~/.zshrc 2>/dev/null || true
exec "$PYTHON_BIN" "$PROJECT_DIR/scripts/telegram-daemon.py"
