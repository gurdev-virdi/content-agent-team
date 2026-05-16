#!/bin/bash
# install-daemon.sh
# Installs the Telegram approval daemon as a macOS launchd service.
# Runs automatically at login and restarts if it crashes.

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_NAME="com.animalsthriving.daemon"
PLIST_SRC="$PROJECT_DIR/scripts/$PLIST_NAME.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
PATH_VALUE="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin"

if [ ! -x "$PYTHON_BIN" ]; then
    echo "Repo Python runtime is missing. Run: $PROJECT_DIR/scripts/bootstrap.sh" >&2
    exit 1
fi

# Write the plist with resolved paths — run via zsh login shell so it
# inherits the user's TCC permissions and environment
cat > "$PLIST_SRC" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/zsh</string>
        <string>-l</string>
        <string>-c</string>
        <string>exec $PROJECT_DIR/scripts/run-daemon.sh</string>
    </array>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>$PATH_VALUE</string>
    </dict>

    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/logs/daemon.log</string>

    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/logs/daemon-error.log</string>

    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF

mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$HOME/Library/LaunchAgents"
cp "$PLIST_SRC" "$PLIST_DEST"

# Unload first if already running
launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"

echo "Daemon installed and started."
echo "Logs: $PROJECT_DIR/logs/daemon.log"
echo ""
echo "Useful commands:"
echo "  Stop:    launchctl unload ~/Library/LaunchAgents/$PLIST_NAME.plist"
echo "  Start:   launchctl load ~/Library/LaunchAgents/$PLIST_NAME.plist"
echo "  Status:  launchctl list | grep animalsthriving"
echo "  Logs:    tail -f $PROJECT_DIR/logs/daemon.log"
