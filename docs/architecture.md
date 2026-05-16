# Architecture Overview

## Goal

Animals Thriving automates the draft creation side of a daily social content workflow while keeping the final publish decision with a human operator.

## Main components

### Pipeline runtime

The pipeline entrypoint is `scripts/pipeline.sh`, which uses the repo-owned Python environment and delegates the main workflow to the local pipeline code.

Primary responsibilities:

- load environment and runtime configuration
- check kill-switch and execution preconditions
- coordinate story selection, captioning, and image handling
- write draft artifacts for review
- trigger the approval flow

### Mission Control

Mission Control is a local FastAPI application exposed by `scripts/mission_control/app.py`.

Primary responsibilities:

- surface system status and recent runs
- show draft and archive data
- expose manual controls such as rerun, approve, revise, and daemon operations
- provide a simple operator-facing control plane for the workflow

### Telegram approval flow

The Telegram pieces are handled by `scripts/telegram-daemon.py` and `scripts/notify.py`.

Primary responsibilities:

- send draft approval prompts
- receive or poll for approval commands
- route approved or revised outcomes back into the local workflow

### Runtime utilities

Shared runtime helpers live in `scripts/runtime.py` and operational checks live in `scripts/doctor.py`.

Primary responsibilities:

- normalize environment loading
- resolve workspace paths
- verify local dependencies and expected services

## Workflow

1. A scheduled task or manual action triggers the pipeline.
2. The runtime selects a candidate wildlife or conservation story.
3. The system drafts caption and image outputs.
4. A draft package is assembled locally.
5. Telegram is used as the human approval gate.
6. Approved results are archived for manual posting.
7. Mission Control provides visibility and manual intervention throughout.

## Why this is interesting

This project sits in the middle ground between a toy LLM demo and a full production platform. It shows:

- operational thinking, not just generation
- human review as a first-class product constraint
- local developer tooling for reliability and observability
- pragmatic automation around a real editorial workflow
