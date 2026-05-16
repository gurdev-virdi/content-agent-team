#!/bin/bash
# Installs the daily pipeline as the supported macOS launchd schedule.

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_NAME="com.animalsthriving.pipeline"
PLIST_SRC="$PROJECT_DIR/scripts/$PLIST_NAME.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

if [ ! -x "$PROJECT_DIR/scripts/pipeline.sh" ]; then
    echo "Pipeline launcher is not executable: $PROJECT_DIR/scripts/pipeline.sh" >&2
    exit 1
fi

cat > "$PLIST_SRC" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>

    <key>ProgramArguments</key>
    <array>
        <string>$PROJECT_DIR/scripts/pipeline.sh</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>7</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/logs/cron.log</string>

    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/logs/cron-error.log</string>
</dict>
</plist>
EOF

mkdir -p "$PROJECT_DIR/logs" "$HOME/Library/LaunchAgents"
cp "$PLIST_SRC" "$PLIST_DEST"

launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"

echo "Pipeline LaunchAgent installed for 7:00 AM daily."
echo "Logs: $PROJECT_DIR/logs/cron.log and $PROJECT_DIR/logs/cron-error.log"
