# Animals Thriving — Instagram Automation Project

## What this project does
Runs a daily automated pipeline that finds one positive wildlife or conservation story, writes an Instagram caption, sources an image, and sends it to the owner for approval via Telegram. On approval, the draft is archived and the user posts manually to Instagram.

## How to trigger the daily pipeline
Say: "Run today's pipeline" or "Generate today's post"
This will invoke the `content-director` agent, which handles everything else.

From the shell, use:
```bash
scripts/pipeline.sh
```

## Agent overview
- **content-director** — Lead orchestrator. Start here always.
- **scout** — Finds and scores story candidates from conservation news sources
- **writer** — Writes Instagram captions in the Animals Thriving brand voice
- **visual** — Sources or generates a square image for the post
- **publisher** — Sends Telegram approval request, archives draft on approval (manual posting)

## Test mode

`TEST_MODE=true` in your `.env` runs the full pipeline safely:
- Scout searches real news sources and finds real stories
- Writer writes a real caption
- Visual finds or generates a real image
- Publisher saves everything to `output/pending/` but skips Telegram and Buffer entirely

Output files to review after a test run:
- `output/pending/today-selection.txt` — which story was chosen and why
- `output/pending/today-draft.txt` — the full caption and image path
- `output/pending/test-run-summary.txt` — what would have happened in live mode

Set `TEST_MODE=false` when you're satisfied with the output and ready to go live.

## Required environment variables
Set these before running:
```
ANTHROPIC_API_KEY=
TEST_MODE=true
LOCAL_INFERENCE=false

# Optional runtime overrides:
CLAUDE_BIN=
OLLAMA_BASE=http://localhost:11434
OLLAMA_ROUTER_MODEL=qwen3.5:4b
LOCAL_SCOUT_MODEL=qwen3.5:9b
LOCAL_WRITER_MODEL=qwen3:14b
MISSION_CONTROL_HOST=127.0.0.1
MISSION_CONTROL_PORT=8765
MISSION_CONTROL_RELOAD=false
VAULT_DIR=

# Only needed when TEST_MODE=false:
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
UNSPLASH_ACCESS_KEY=
REPLICATE_API_TOKEN=
```

Store in a `.env` file (already in .gitignore) and load with:
```bash
export $(cat .env | xargs)
```

## Runtime setup

This repo uses a local Python runtime at `.venv/` so Mission Control, the Telegram daemon, and the local pipeline all use the same dependencies.

Install or refresh it with:
```bash
scripts/bootstrap.sh
```

Check launch readiness with:
```bash
.venv/bin/python scripts/doctor.py
```

Start Mission Control with:
```bash
scripts/mission-control.sh
```

## File structure
```
.claude/agents/          ← all sub-agent definitions
scripts/                 ← helper scripts (bootstrap, launchd setup, env loader)
output/
  pending/               ← today's draft (image, caption, status)
  approved/              ← archived posts by date
```

## Running on a schedule (LaunchAgent)
The pipeline runs via a macOS LaunchAgent at 7:00 AM daily.
Plist: `~/Library/LaunchAgents/com.animalsthriving.pipeline.plist`
Logs: `logs/cron.log` (stdout) and `logs/cron-error.log` (stderr)
Pipeline run history: `logs/pipeline-runs.log`

Install or reload the scheduled pipeline:
```bash
scripts/install-pipeline.sh
```

Install or reload the Telegram approval daemon:
```bash
scripts/install-daemon.sh
```

To reload manually after editing a plist:
```bash
launchctl unload ~/Library/LaunchAgents/com.animalsthriving.pipeline.plist
launchctl load ~/Library/LaunchAgents/com.animalsthriving.pipeline.plist
```

`scripts/setup-cron.sh` is retained as a fallback only; `launchd` is the supported scheduler on macOS.

## Brand rules (quick reference)
- Post format: carousel or single image
- Tone: warm, specific, hopeful — never preachy
- CTA: always "Save this + tag someone who needs good news today 🌿"
- Hashtags: always 15, always include #AnimalsThriving #WildlifeWin #ConservationWin
