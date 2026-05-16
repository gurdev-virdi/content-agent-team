# Animals Thriving

Animals Thriving is a small content automation system for a wildlife-focused Instagram account. It finds one positive conservation or animal story each day, drafts the caption, sources or generates an image, and sends the result to the owner for approval in Telegram. Approved drafts are archived for manual posting.

## What it does

- Finds one strong wildlife or conservation story for the day
- Writes an Instagram caption in the Animals Thriving voice
- Sources or generates a square image
- Sends the draft to Telegram for approval
- Archives approved content for later reference
- Exposes a local Mission Control dashboard for status, review, and manual actions

## How it works

The pipeline has four main stages:

- story selection
- caption generation
- image sourcing or generation
- approval and archive handoff

The local dashboard lives in Mission Control and runs from `scripts/mission-control.sh`.

## Quick start

1. Create a `.env` file from `.env.example` and fill in the values you need.
2. Bootstrap the local Python runtime:

```bash
scripts/bootstrap.sh
```

3. Check that the local setup is healthy:

```bash
.venv/bin/python scripts/doctor.py
```

4. Launch Mission Control:

```bash
scripts/mission-control.sh
```

5. Run the content pipeline manually:

```bash
scripts/pipeline.sh
```

## Test mode

Set `TEST_MODE=true` in `.env` to run the full pipeline without sending live Telegram notifications or publishing anywhere. In test mode, outputs are written to `output/pending/` so you can review the selection, caption, and image locally.

Useful test artifacts:

- `output/pending/today-selection.txt`
- `output/pending/today-draft.txt`
- `output/pending/test-run-summary.txt`

## Key environment variables

Required:

- `ANTHROPIC_API_KEY`
- `TEST_MODE`

Common optional settings:

- `LOCAL_INFERENCE`
- `MISSION_CONTROL_HOST`
- `MISSION_CONTROL_PORT`
- `MISSION_CONTROL_RELOAD`
- `OLLAMA_BASE`
- `VAULT_DIR`

Needed for live approval flow:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Optional image providers:

- `UNSPLASH_ACCESS_KEY`
- `REPLICATE_API_TOKEN`

## Scheduled runs

On macOS, the supported scheduler is `launchd`.

Install or reload the daily pipeline:

```bash
scripts/install-pipeline.sh
```

Install or reload the Telegram approval daemon:

```bash
scripts/install-daemon.sh
```

## Project structure

```text
scripts/                Runtime, pipeline, dashboard, and install scripts
scripts/mission_control FastAPI dashboard backend and static UI
logs/                   Runtime and scheduler logs
tests/                  Lightweight runtime tests
```

## Current status

Mission Control launches from the repo-owned `.venv` runtime and has a local doctor script for setup checks. The dashboard can run independently, while the full automation flow also depends on configured API keys, Telegram credentials, and optional local inference services.

Sensitive local state, generated content, and private operating prompts are intentionally excluded from version control.
