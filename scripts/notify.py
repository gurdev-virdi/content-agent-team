#!/usr/bin/env python3
"""Send a Telegram message to the owner. Called by pipeline scripts on failure/success."""
import json
import sys
import urllib.request
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.runtime import load_env  # noqa: E402


def send_telegram(message):
    env = load_env()
    token = env.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = env.get("TELEGRAM_CHAT_ID") or os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        print("notify.py: missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID", file=sys.stderr)
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({
        "chat_id": int(chat_id),
        "text": message,
        "parse_mode": "Markdown",
    }).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            result = json.loads(r.read())
            return result.get("ok", False)
    except Exception as e:
        print(f"notify.py: Telegram send failed: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: notify.py <message>")
        sys.exit(1)
    ok = send_telegram(sys.argv[1])
    sys.exit(0 if ok else 1)
