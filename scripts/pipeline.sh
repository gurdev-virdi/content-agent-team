#!/bin/zsh
# Pipeline wrapper — loads env, runs the daily pipeline, notifies on failure.
# Called by the LaunchAgent. Logs go to logs/cron.log and logs/cron-error.log.

set -u

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN="/usr/bin/python3"
fi

if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

NOTIFY="$PROJECT_DIR/scripts/notify.py"
LOG="$PROJECT_DIR/logs/pipeline-runs.log"
KILL_SWITCH="$PROJECT_DIR/output/KILL_SWITCH"
CLAUDE_BIN="${CLAUDE_BIN:-}"

mkdir -p "$PROJECT_DIR/logs" "$PROJECT_DIR/output/pending" "$PROJECT_DIR/output/approved"

# ── Kill switch check ────────────────────────────────────────────────────────
# If output/KILL_SWITCH exists, abort immediately and log it.
if [ -f "$KILL_SWITCH" ]; then
    REASON="$(cat "$KILL_SWITCH" 2>/dev/null | head -1)"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] KILL_SWITCH STATUS=blocked REASON=\"${REASON:-Kill switch active}\"" >> "$LOG"
    echo "🚫 Pipeline blocked — kill switch is active. Reason: ${REASON:-Kill switch active}"
    echo "   To resume: delete output/KILL_SWITCH or use Mission Control to deactivate."
    "$PYTHON_BIN" "$NOTIFY" "🚫 *Pipeline blocked* — Kill switch is active. Deactivate in Mission Control to resume." 2>/dev/null
    exit 0
fi

RUN_ID="${RUN_ID:-RUN_$(date +%Y%m%d-%H%M%S)}"
export RUN_ID
echo "[$(date '+%Y-%m-%d %H:%M:%S')] RUN_ID=$RUN_ID STATUS=started" >> "$LOG"

"$PYTHON_BIN" "$NOTIFY" "🌿 *Daily pipeline starting* ($RUN_ID)" 2>/dev/null

if [ "${LOCAL_INFERENCE:-false}" = "true" ]; then
    "$PYTHON_BIN" "$PROJECT_DIR/scripts/pipeline_local.py"
else
    if [ -z "$CLAUDE_BIN" ]; then
        CLAUDE_BIN="$(command -v claude 2>/dev/null || true)"
    fi
    if [ -z "$CLAUDE_BIN" ] && [ -x "$HOME/.local/bin/claude" ]; then
        CLAUDE_BIN="$HOME/.local/bin/claude"
    fi
    if [ -z "$CLAUDE_BIN" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] RUN_ID=$RUN_ID STATUS=failed ERROR=\"Claude binary not found\"" >> "$LOG"
        echo "Claude binary not found. Set CLAUDE_BIN in .env or install claude on PATH." >&2
        exit 127
    fi
    "$CLAUDE_BIN" --print "Run today's pipeline"
fi
EXIT_CODE=$?

if [ "$EXIT_CODE" -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] RUN_ID=$RUN_ID STATUS=launcher_exited_ok" >> "$LOG"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] RUN_ID=$RUN_ID STATUS=failed EXIT_CODE=$EXIT_CODE" >> "$LOG"
    "$PYTHON_BIN" "$NOTIFY" \
        "⚠️ *Pipeline failed* ($RUN_ID)

Exit code: \`$EXIT_CODE\`

Check \`logs/cron-error.log\` for details." 2>/dev/null
fi
