#!/usr/bin/env python3
"""
Animals Thriving — Mission Control dashboard (FastAPI backend).
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from scripts.runtime import (
    PROJECT_DIR,
    claude_bin,
    ensure_runtime_dirs,
    load_env as runtime_load_env,
    team_paths,
)

AGENTS_DIR    = PROJECT_DIR / ".claude" / "agents"
PENDING_DIR   = PROJECT_DIR / "output" / "pending"
APPROVED_DIR  = PROJECT_DIR / "output" / "approved"
LOGS_DIR      = PROJECT_DIR / "logs"
STATIC_DIR    = Path(__file__).parent / "static"
TEAMS_FILE    = Path.home() / ".claude" / "mission-control-teams.json"
KILL_SWITCH   = PROJECT_DIR / "output" / "KILL_SWITCH"

_DEFAULT_TEAMS = [
    {
        "id": "animals-thriving",
        "name": "Animals Thriving",
        "icon": "🦁",
        "description": "Daily wildlife Instagram content pipeline",
        "project_dir": str(PROJECT_DIR),
    },
    {
        "id": "health-analysis",
        "name": "Health Analysis",
        "icon": "🏃",
        "description": "Personal health data synthesis and insights",
        "project_dir": str(Path.home() / "claude" / "health-analysis"),
    },
    {
        "id": "product-management",
        "name": "Product Management",
        "icon": "📋",
        "description": "Product management support and analysis",
        "project_dir": str(Path.home() / "claude" / "product-management"),
    },
]


def load_teams() -> list:
    if TEAMS_FILE.exists():
        try:
            return json.loads(TEAMS_FILE.read_text())
        except Exception:
            pass
    TEAMS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TEAMS_FILE.write_text(json.dumps(_DEFAULT_TEAMS, indent=2))
    return [dict(t) for t in _DEFAULT_TEAMS]


def save_teams(teams: list):
    TEAMS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TEAMS_FILE.write_text(json.dumps(teams, indent=2))


def resolve_team(team_id: str) -> dict:
    """Return team config + resolved paths dict."""
    teams = load_teams()
    team = next((t for t in teams if t["id"] == team_id), None)
    if not team:
        team = {"id": team_id, "name": team_id, "icon": "⬡", "description": "", "project_dir": str(PROJECT_DIR)}
    paths = team_paths(team, PROJECT_DIR)
    return {
        **team,
        "project_dir": str(paths.project),
        "_project": paths.project,
        "_agents": paths.agents,
        "_pending": paths.pending,
        "_approved": paths.approved,
        "_logs": paths.logs,
    }

app = FastAPI(title="Animals Thriving — Mission Control")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Env ───────────────────────────────────────────────────────────────────────

def load_env(project_dir: Path | None = None) -> dict:
    return runtime_load_env(project_dir or PROJECT_DIR)


# ── Parsers ───────────────────────────────────────────────────────────────────

def parse_agents(team_id: str = "animals-thriving") -> list:
    agents = []
    agents_dir = resolve_team(team_id)["_agents"]
    if not agents_dir.exists():
        return agents
    for md_file in sorted(agents_dir.glob("*.md")):
        text = md_file.read_text()
        parts = text.split("---", 2)
        meta = {}
        body = text
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip()
            body = parts[2].strip()
        agents.append({
            "name": meta.get("name", md_file.stem),
            "model": meta.get("model", "unknown"),
            "description": meta.get("description", ""),
            "tools": [t.strip() for t in meta.get("tools", "").split(",") if t.strip()],
            "body": body,
            "raw": text,
        })
    return agents


def parse_runs(team_id: str = "animals-thriving") -> list:
    log_file = resolve_team(team_id)["_logs"] / "pipeline-runs.log"
    if not log_file.exists():
        return []
    runs: dict = {}
    pattern = re.compile(r"\[([^\]]+)\]\s+(.*)")
    for line in log_file.read_text().splitlines():
        m = pattern.match(line)
        if not m:
            continue
        timestamp, rest = m.group(1), m.group(2)
        fields: dict = {}
        for token in re.findall(r'(\w+)=([^\s]+)', rest):
            fields[token[0]] = token[1]
        run_id = fields.get("RUN_ID", "")
        if not run_id:
            continue
        if run_id not in runs:
            runs[run_id] = {
                "run_id": run_id,
                "started_at": timestamp,
                "status": "started",
                "story": "",
                "steps": [],
                "error": "",
            }
        status = fields.get("STATUS", "")
        if status:
            runs[run_id]["status"] = status
        story = fields.get("STORY", "")
        if story:
            runs[run_id]["story"] = story.replace("_", " ")
        error = fields.get("ERROR", "")
        if error:
            runs[run_id]["error"] = error
        step = fields.get("STEP", "")
        if step:
            runs[run_id]["steps"].append({"time": timestamp, "step": step})
        runs[run_id]["steps"].append({"time": timestamp, "raw": rest})
    return sorted(runs.values(), key=lambda r: r["started_at"], reverse=True)


def parse_draft(team_id: str = "animals-thriving") -> Optional[dict]:
    pending = resolve_team(team_id)["_pending"]
    draft_file = pending / "today-draft.txt"
    if not draft_file.exists():
        return None
    raw = draft_file.read_text()
    draft: dict = {}
    for line in raw.split("\n"):
        for key in ("IMAGE", "SOURCE", "IMAGE_CREDIT"):
            if line.startswith(f"{key}:"):
                draft[key.lower()] = line.split(":", 1)[1].strip()
    if "CAPTION:\n" in raw:
        draft["caption"] = raw.split("CAPTION:\n", 1)[1].strip()

    sel_file = pending / "today-selection.txt"
    if sel_file.exists():
        draft["selection"] = sel_file.read_text().strip()

    status_file = pending / "approval-status.txt"
    if status_file.exists():
        draft["approval_status"] = status_file.read_text().strip()

    return draft


def parse_approved(team_id: str = "animals-thriving") -> list:
    posts = []
    approved_dir = resolve_team(team_id)["_approved"]
    if not approved_dir.exists():
        return posts
    for d in sorted(approved_dir.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        is_test = d.name.startswith("TEST")
        post: dict = {"date": d.name, "is_test": is_test}
        draft_file = d / "today-draft.txt"
        if draft_file.exists():
            raw = draft_file.read_text()
            for line in raw.split("\n"):
                for key in ("IMAGE", "SOURCE"):
                    if line.startswith(f"{key}:"):
                        post[key.lower()] = line.split(":", 1)[1].strip()
            if "CAPTION:\n" in raw:
                caption = raw.split("CAPTION:\n", 1)[1].strip()
                post["hook"] = caption.split("\n")[0]
                post["caption"] = caption
        status_file = d / "status.txt"
        if status_file.exists():
            post["status"] = status_file.read_text().strip()
        posts.append(post)
    return posts


def parse_audit(team_id: str = "animals-thriving") -> dict:
    conv_dir = resolve_team(team_id)["_logs"] / "conversations"
    env = load_env(resolve_team(team_id)["_project"])
    authorized_id = int(env.get("TELEGRAM_CHAT_ID", 0))
    all_entries = []
    unknown_count = 0
    injection_count = 0

    if conv_dir.exists():
        for f in sorted(conv_dir.glob("*.jsonl")):
            date = f.stem
            for line in f.read_text().splitlines():
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                chat_id = entry.get("chat_id")
                tools = entry.get("tools_called", [])
                flagged_unknown = chat_id != authorized_id
                flagged_injection = "[INJECTION_DETECTED]" in tools
                if flagged_unknown:
                    unknown_count += 1
                if flagged_injection:
                    injection_count += 1
                all_entries.append({
                    "date": date,
                    "timestamp": entry.get("timestamp", ""),
                    "chat_id": chat_id,
                    "user_text": entry.get("user_text", ""),
                    "bot_response": entry.get("bot_response", ""),
                    "tools_called": tools,
                    "flagged_unknown": flagged_unknown,
                    "flagged_injection": flagged_injection,
                })

    return {
        "authorized_chat_id": authorized_id,
        "total_messages": len(all_entries),
        "unknown_chat_ids": unknown_count,
        "injection_attempts": injection_count,
        "entries": sorted(all_entries, key=lambda e: e["timestamp"], reverse=True),
    }


def get_process_status(team_id: str = "animals-thriving") -> dict:
    daemon_pid = None
    pipeline_pid = None
    project_dir = str(resolve_team(team_id)["_project"])

    def pgrep(pattern: str) -> list[str]:
        try:
            result = subprocess.run(["pgrep", "-fl", pattern], capture_output=True, text=True, timeout=2)
        except Exception:
            return []
        return result.stdout.splitlines()

    # Daemon: for animals-thriving, look for telegram-daemon.py
    if team_id == "animals-thriving":
        for line in pgrep("telegram-daemon"):
            parts = line.split(None, 1)
            if len(parts) == 2 and "telegram-daemon.py" in parts[1] and project_dir in parts[1]:
                try:
                    daemon_pid = int(parts[0])
                except ValueError:
                    pass
    # Pipeline: look for pipeline process running from this team's project dir
    for line in pgrep(re.escape(project_dir)):
        parts = line.split(None, 1)
        if len(parts) == 2 and project_dir in parts[1] and ("pipeline" in parts[1].lower() or "--print" in parts[1]):
            try:
                pipeline_pid = int(parts[0])
            except ValueError:
                pass
    return {"daemon_pid": daemon_pid, "pipeline_pid": pipeline_pid}


def get_kill_switch_status(team_id: str = "animals-thriving") -> dict:
    ks_file = resolve_team(team_id)["_project"] / "output" / "KILL_SWITCH"
    if ks_file.exists():
        try:
            content = ks_file.read_text().strip()
        except Exception:
            content = ""
        lines = content.splitlines()
        reason = lines[0] if lines else ""
        activated_at = lines[1] if len(lines) > 1 else ""
        activated_by = lines[2] if len(lines) > 2 else "Mission Control"
        return {"active": True, "reason": reason, "activated_at": activated_at, "activated_by": activated_by}
    return {"active": False, "reason": "", "activated_at": "", "activated_by": ""}


def get_system_status(team_id: str = "animals-thriving") -> dict:
    team = resolve_team(team_id)
    runs = parse_runs(team_id)
    last_run = runs[0] if runs else None
    draft = parse_draft(team_id)
    approved = parse_approved(team_id)
    last_approved = next((p for p in approved if not p.get("is_test")), None)

    daemon_log = team["_logs"] / "daemon.log"
    daemon_up = False
    daemon_since = ""
    if daemon_log.exists():
        lines = daemon_log.read_text().splitlines()
        for line in reversed(lines):
            if "Daemon started" in line:
                daemon_since = line.split("]")[0].lstrip("[")
                daemon_up = True
                break
            if "Daemon stopped" in line:
                break

    env = load_env(team["_project"])
    procs = get_process_status(team_id)
    daemon_up = daemon_up and procs["daemon_pid"] is not None
    agents = parse_agents(team_id)
    kill_switch = get_kill_switch_status(team_id)
    return {
        "team": {k: team[k] for k in ("id", "name", "icon", "description") if k in team},
        "agent_count": len(agents),
        "daemon": {"up": daemon_up, "since": daemon_since, "pid": procs["daemon_pid"]},
        "pipeline_running": procs["pipeline_pid"] is not None,
        "pipeline_pid": procs["pipeline_pid"],
        "last_run": last_run,
        "pending_draft": bool(draft),
        "draft_preview": (draft.get("caption", "")[:120] + "…") if draft else None,
        "last_approved": last_approved,
        "test_mode": env.get("TEST_MODE", "false").lower() == "true",
        "kill_switch": kill_switch,
        "current_time": datetime.now().isoformat(),
    }


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/status")
async def status(team: str = "animals-thriving"):
    return get_system_status(team)


@app.get("/api/health")
async def health(team: str = "animals-thriving"):
    t = resolve_team(team)
    env = load_env(t["_project"])
    ensure_runtime_dirs(t["_project"])
    required = ["ANTHROPIC_API_KEY"]
    if env.get("TEST_MODE", "true").lower() not in {"1", "true", "yes", "on"}:
        required.extend(["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"])
    missing = [key for key in required if not env.get(key)]
    checks = {
        "project_dir": str(t["_project"]),
        "project_exists": t["_project"].exists(),
        "fastapi": importlib.util.find_spec("fastapi") is not None,
        "uvicorn": importlib.util.find_spec("uvicorn") is not None,
        "claude_bin": claude_bin(env),
        "missing_required_env": missing,
        "logs_dir": str(t["_logs"]),
        "output_dir": str(t["_project"] / "output"),
    }
    return {"ok": checks["project_exists"] and checks["fastapi"] and checks["uvicorn"] and not missing, "checks": checks}


@app.get("/api/teams")
async def list_teams_route():
    return load_teams()


@app.post("/api/teams")
async def create_team_route(payload: dict = Body(...)):
    teams = load_teams()
    name = (payload.get("name") or "New Team").strip()
    tid = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    existing = {t["id"] for t in teams}
    base, n = tid, 2
    while tid in existing:
        tid = f"{base}-{n}"
        n += 1
    new_team = {
        "id": tid,
        "name": name,
        "icon": payload.get("icon", "⬡"),
        "description": payload.get("description", ""),
        "project_dir": payload.get("project_dir", ""),
    }
    teams.append(new_team)
    save_teams(teams)
    return new_team


@app.put("/api/teams/{tid}")
async def update_team_route(tid: str, payload: dict = Body(...)):
    teams = load_teams()
    idx = next((i for i, t in enumerate(teams) if t["id"] == tid), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Team not found")
    for k, v in payload.items():
        if k != "id":
            teams[idx][k] = v
    save_teams(teams)
    return teams[idx]


@app.delete("/api/teams/{tid}")
async def delete_team_route(tid: str):
    if tid == "animals-thriving":
        raise HTTPException(status_code=400, detail="Cannot delete the default team")
    teams = [t for t in load_teams() if t["id"] != tid]
    save_teams(teams)
    return {"status": "deleted", "id": tid}


@app.get("/api/agents")
async def agents(team: str = "animals-thriving"):
    return parse_agents(team)


@app.post("/api/agents")
async def create_agent_route(payload: dict = Body(...), team: str = "animals-thriving"):
    t = resolve_team(team)
    agents_dir = t["_agents"]
    agents_dir.mkdir(parents=True, exist_ok=True)
    name = (payload.get("name") or "").strip()
    content = (payload.get("content") or "").strip()
    if not name or not content:
        raise HTTPException(status_code=400, detail="name and content are required")
    safe_name = re.sub(r"[^a-z0-9\-]", "", name.lower())
    path = agents_dir / f"{safe_name}.md"
    if path.exists():
        raise HTTPException(status_code=409, detail=f"Agent '{safe_name}' already exists")
    path.write_text(content)
    return {"status": "created", "name": safe_name}


@app.get("/api/agents/{name}")
async def agent(name: str, team: str = "animals-thriving"):
    for a in parse_agents(team):
        if a["name"] == name:
            return a
    raise HTTPException(status_code=404, detail="Agent not found")


@app.put("/api/agents/{name}")
async def update_agent(name: str, payload: dict = Body(...), team: str = "animals-thriving"):
    content = payload.get("content", "")
    if not content.strip():
        raise HTTPException(status_code=400, detail="Content cannot be empty")
    safe_name = re.sub(r"[^a-z0-9\-]", "", name.lower())
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid agent name")
    path = resolve_team(team)["_agents"] / f"{safe_name}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Agent not found")
    path.write_text(content)
    return {"status": "saved", "name": safe_name, "size": len(content)}


@app.delete("/api/agents/{name}")
async def delete_agent_route(name: str, team: str = "animals-thriving"):
    safe_name = re.sub(r"[^a-z0-9\-]", "", name.lower())
    path = resolve_team(team)["_agents"] / f"{safe_name}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Agent not found")
    path.unlink()
    return {"status": "deleted", "name": safe_name}


@app.get("/api/runs")
async def runs(team: str = "animals-thriving"):
    return parse_runs(team)


@app.get("/api/draft")
async def draft(team: str = "animals-thriving"):
    d = parse_draft(team)
    if not d:
        return {"pending": False}
    d["pending"] = True
    return d


@app.get("/api/approved")
async def approved(team: str = "animals-thriving"):
    return parse_approved(team)


@app.get("/api/audit")
async def audit(team: str = "animals-thriving"):
    return parse_audit(team)


@app.get("/api/logs/daemon")
async def daemon_log(team: str = "animals-thriving"):
    log_file = resolve_team(team)["_logs"] / "daemon.log"
    if not log_file.exists():
        return {"lines": []}
    lines = log_file.read_text().splitlines()
    return {"lines": lines[-200:]}


@app.get("/output/pending/{filename}")
async def serve_pending_file(filename: str, team: str = "animals-thriving"):
    path = resolve_team(team)["_pending"] / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(str(path))


@app.get("/output/approved/{date}/{filename}")
async def serve_approved_file(date: str, filename: str, team: str = "animals-thriving"):
    path = resolve_team(team)["_approved"] / date / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(str(path))


# ── Chat SSE ──────────────────────────────────────────────────────────────────

@app.get("/api/chat/stream")
async def chat_stream(message: str, agent: str = "content-director", team: str = "animals-thriving"):
    t = resolve_team(team)
    env = load_env(t["_project"])
    if agent and agent != "content-director" and agent != "full-pipeline":
        prompt = f"You are acting as the {agent} agent. {message}"
    else:
        prompt = message

    full_env = {**os.environ, **env}

    async def generate():
        try:
            process = await asyncio.create_subprocess_exec(
                claude_bin(env), "--print", prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(t["_project"]),
                env=full_env,
            )
            async for line in process.stdout:
                text = line.decode("utf-8", errors="replace")
                yield f"data: {json.dumps({'text': text})}\n\n"
            await process.wait()
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                              headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Actions ───────────────────────────────────────────────────────────────────

@app.get("/api/kill-switch")
async def kill_switch_status(team: str = "animals-thriving"):
    return get_kill_switch_status(team)


@app.post("/api/kill-switch/activate")
async def kill_switch_activate(payload: dict = Body(default={}), team: str = "animals-thriving"):
    import signal
    reason = (payload.get("reason") or "Manually activated via Mission Control").strip()
    ks_file = resolve_team(team)["_project"] / "output" / "KILL_SWITCH"
    ks_file.parent.mkdir(parents=True, exist_ok=True)
    ks_file.write_text(f"{reason}\n{datetime.now().isoformat()}\nMission Control\n")

    # Log to pipeline-runs.log
    log_file = resolve_team(team)["_logs"] / "pipeline-runs.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(str(log_file), "a") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] KILL_SWITCH STATUS=activated REASON=\"{reason}\"\n")

    # Stop any running pipeline
    procs = get_process_status(team)
    if procs["pipeline_pid"]:
        try:
            os.kill(procs["pipeline_pid"], signal.SIGTERM)
        except ProcessLookupError:
            pass

    return {"status": "activated", "reason": reason, "message": "Kill switch activated. All agent flows are blocked."}


@app.post("/api/kill-switch/deactivate")
async def kill_switch_deactivate(team: str = "animals-thriving"):
    ks_file = resolve_team(team)["_project"] / "output" / "KILL_SWITCH"
    if not ks_file.exists():
        return {"status": "already_inactive", "message": "Kill switch was not active."}
    ks_file.unlink()

    # Log to pipeline-runs.log
    log_file = resolve_team(team)["_logs"] / "pipeline-runs.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(str(log_file), "a") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] KILL_SWITCH STATUS=deactivated\n")

    return {"status": "deactivated", "message": "Kill switch cleared. Agent flows are unblocked."}


@app.post("/api/actions/run-pipeline")
async def action_run_pipeline(team: str = "animals-thriving"):
    ks = get_kill_switch_status(team)
    if ks["active"]:
        raise HTTPException(status_code=403, detail=f"Kill switch is active: {ks['reason']}. Deactivate it in Mission Control first.")
    t = resolve_team(team)
    env = load_env(t["_project"])
    pipeline = t["_project"] / "scripts" / "pipeline.sh"
    if not pipeline.exists():
        raise HTTPException(status_code=404, detail="Pipeline script not found for this team")
    subprocess.Popen(
        [str(pipeline)],
        cwd=str(t["_project"]),
        env={**os.environ, **env},
    )
    return {"status": "started", "message": "Pipeline launched."}


@app.post("/api/actions/find-stories")
async def action_find_stories(team: str = "animals-thriving"):
    t = resolve_team(team)
    env = load_env(t["_project"])
    subprocess.Popen(
        [claude_bin(env), "--print",
         "Use the scout sub-agent to find today's top 3 wildlife/conservation story candidates "
         "and return their headlines, scores, and summaries. Do not proceed further."],
        cwd=str(t["_project"]),
        env={**os.environ, **env},
    )
    return {"status": "started", "message": "Scout launched."}


@app.post("/api/actions/approve")
async def action_approve(team: str = "animals-thriving"):
    import urllib.request
    t = resolve_team(team)
    draft = parse_draft(team)
    if not draft:
        raise HTTPException(status_code=400, detail="No pending draft")
    env = load_env(t["_project"])
    date_str = datetime.now().strftime("%Y-%m-%d")
    archive = t["_approved"] / date_str
    archive.mkdir(parents=True, exist_ok=True)
    for f in t["_pending"].iterdir():
        if f.is_file():
            shutil.move(str(f), str(archive / f.name))
    (archive / "status.txt").write_text(f"APPROVED\n{datetime.now().isoformat()}\n")

    # Notify via Telegram
    caption = draft.get("caption", "")
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = env.get("TELEGRAM_CHAT_ID", "")
    if token and chat_id:
        msg = (
            f"✅ *Approved via Mission Control!*\n\n"
            f"Image: `output/approved/{date_str}/today-image.jpg`\n\n"
            f"Caption:\n```\n{caption[:800]}\n```\n\n"
            f"Open Instagram, post the image, paste the caption. 🌿"
        )
        try:
            data = json.dumps({
                "chat_id": int(chat_id),
                "text": msg,
                "parse_mode": "Markdown",
            }).encode()
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass

    return {"status": "approved", "date": date_str}


@app.post("/api/actions/revise")
async def action_revise(team: str = "animals-thriving"):
    t = resolve_team(team)
    env = load_env(t["_project"])
    t["_pending"].mkdir(parents=True, exist_ok=True)
    (t["_pending"] / "approval-status.txt").write_text(f"REJECTED\n{datetime.now().isoformat()}\n")
    pipeline = t["_project"] / "scripts" / "pipeline.sh"
    if pipeline.exists():
        cmd = [str(pipeline)]
    else:
        cmd = [claude_bin(env), "--print", "Run today's pipeline"]
    subprocess.Popen(
        cmd,
        cwd=str(t["_project"]),
        env={**os.environ, **env},
    )
    return {"status": "revising", "message": "Pipeline relaunched for a new story."}


@app.post("/api/actions/stop-daemon")
async def action_stop_daemon(team: str = "animals-thriving"):
    import signal
    procs = get_process_status(team)
    if not procs["daemon_pid"]:
        return {"status": "not_running", "message": "Daemon is not running."}
    os.kill(procs["daemon_pid"], signal.SIGTERM)
    return {"status": "stopped", "message": f"Daemon (PID {procs['daemon_pid']}) stopped."}


@app.post("/api/actions/start-daemon")
async def action_start_daemon(team: str = "animals-thriving"):
    t = resolve_team(team)
    procs = get_process_status(team)
    if procs["daemon_pid"]:
        return {"status": "already_running", "message": f"Daemon already running (PID {procs['daemon_pid']})."}
    env = load_env(t["_project"])
    daemon_script = t["_project"] / "scripts" / "run-daemon.sh"
    if not daemon_script.exists():
        raise HTTPException(status_code=404, detail="Daemon launcher not found for this team")
    t["_logs"].mkdir(parents=True, exist_ok=True)
    log_file = open(str(t["_logs"] / "daemon.log"), "a")
    err_file = open(str(t["_logs"] / "daemon-error.log"), "a")
    subprocess.Popen(
        ["zsh", str(daemon_script)],
        cwd=str(t["_project"]),
        env={**os.environ, **env},
        stdout=log_file,
        stderr=err_file,
    )
    return {"status": "started", "message": "Daemon started."}


@app.post("/api/actions/restart-daemon")
async def action_restart_daemon(team: str = "animals-thriving"):
    import signal
    t = resolve_team(team)
    procs = get_process_status(team)
    if procs["daemon_pid"]:
        os.kill(procs["daemon_pid"], signal.SIGTERM)
        await asyncio.sleep(1.5)
    env = load_env(t["_project"])
    daemon_script = t["_project"] / "scripts" / "run-daemon.sh"
    if not daemon_script.exists():
        raise HTTPException(status_code=404, detail="Daemon launcher not found for this team")
    t["_logs"].mkdir(parents=True, exist_ok=True)
    log_file = open(str(t["_logs"] / "daemon.log"), "a")
    err_file = open(str(t["_logs"] / "daemon-error.log"), "a")
    subprocess.Popen(
        ["zsh", str(daemon_script)],
        cwd=str(t["_project"]),
        env={**os.environ, **env},
        stdout=log_file,
        stderr=err_file,
    )
    return {"status": "restarted", "message": "Daemon restarted."}


@app.post("/api/actions/stop-pipeline")
async def action_stop_pipeline(team: str = "animals-thriving"):
    import signal
    procs = get_process_status(team)
    if not procs["pipeline_pid"]:
        return {"status": "not_running", "message": "No pipeline is currently running."}
    os.kill(procs["pipeline_pid"], signal.SIGTERM)
    return {"status": "stopped", "message": f"Pipeline (PID {procs['pipeline_pid']}) stopped."}


if __name__ == "__main__":
    import uvicorn
    env = load_env(PROJECT_DIR)
    uvicorn.run(
        "scripts.mission_control.app:app",
        host=env.get("MISSION_CONTROL_HOST", "127.0.0.1"),
        port=int(env.get("MISSION_CONTROL_PORT", "8765")),
        reload=True,
    )
