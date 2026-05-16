#!/bin/bash
# setup-cron.sh
# Deprecated fallback. launchd is the supported scheduler.

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CRON_CMD="0 7 * * * cd $PROJECT_DIR && scripts/pipeline.sh >> logs/cron.log 2>> logs/cron-error.log"

echo "WARNING: cron is a fallback only. Prefer launchd on macOS."

# Add to crontab
(crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -

echo "Cron fallback installed. Pipeline will run daily at 7 AM."
echo "Logs will appear in $PROJECT_DIR/logs/cron.log"
mkdir -p "$PROJECT_DIR/logs"
