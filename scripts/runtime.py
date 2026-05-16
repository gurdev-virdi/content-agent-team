#!/usr/bin/env python3
"""Shared runtime/config helpers for Animals Thriving services."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_CLAUDE_PATHS = (
    Path.home() / ".local" / "bin" / "claude",
    Path("/opt/homebrew/bin/claude"),
    Path("/usr/local/bin/claude"),
)

DEFAULT_OLLAMA_BASE = "http://localhost:11434"


def find_project_root(start: Path | None = None) -> Path:
    """Find the repo root by walking up from a script path."""
    here = (start or Path(__file__)).resolve()
    if here.is_file():
        here = here.parent
    for candidate in (here, *here.parents):
        if (candidate / "scripts").is_dir() and (candidate / ".env.example").exists():
            return candidate
    return Path(__file__).resolve().parent.parent


PROJECT_DIR = find_project_root()


def parse_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        env[key.strip()] = value
    return env


def load_env(project_dir: Path | None = None) -> dict[str, str]:
    project = Path(project_dir or PROJECT_DIR)
    env = parse_env_file(project / ".env")
    merged = {**env}
    for key, value in os.environ.items():
        if key not in merged:
            merged[key] = value
    return merged


def env_bool(env: dict[str, str], key: str, default: bool = False) -> bool:
    value = env.get(key)
    if value is None or value == "":
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def configured_path(env: dict[str, str], key: str, default: Path | None = None) -> Path | None:
    value = env.get(key, "").strip()
    if value:
        return Path(value).expanduser()
    return default


def claude_bin(env: dict[str, str] | None = None) -> str:
    env = env or load_env()
    configured = configured_path(env, "CLAUDE_BIN")
    if configured:
        return str(configured)
    found = shutil.which("claude")
    if found:
        return found
    for path in DEFAULT_CLAUDE_PATHS:
        if path.exists():
            return str(path)
    return "claude"


def ollama_base(env: dict[str, str] | None = None) -> str:
    env = env or load_env()
    return env.get("OLLAMA_BASE", DEFAULT_OLLAMA_BASE).rstrip("/")


def vault_dir(env: dict[str, str] | None = None) -> Path:
    env = env or load_env()
    configured = configured_path(env, "VAULT_DIR")
    if configured:
        return configured
    return Path.home() / "claude" / "animals_thriving_vault"


def ensure_runtime_dirs(project_dir: Path | None = None) -> None:
    project = Path(project_dir or PROJECT_DIR)
    for rel in ("logs", "output", "output/pending", "output/approved"):
        (project / rel).mkdir(parents=True, exist_ok=True)


def redact_env(env: dict[str, str]) -> dict[str, str]:
    redacted = {}
    for key, value in env.items():
        if any(token in key.upper() for token in ("KEY", "TOKEN", "SECRET")):
            redacted[key] = "<set>" if value else ""
        else:
            redacted[key] = value
    return redacted


@dataclass(frozen=True)
class TeamPaths:
    id: str
    name: str
    icon: str
    description: str
    project: Path
    agents: Path
    pending: Path
    approved: Path
    logs: Path

    @property
    def env(self) -> dict[str, str]:
        return load_env(self.project)


def team_paths(team: dict, fallback_project: Path | None = None) -> TeamPaths:
    project = Path(team.get("project_dir") or fallback_project or PROJECT_DIR).expanduser()
    return TeamPaths(
        id=team.get("id", "animals-thriving"),
        name=team.get("name", team.get("id", "Animals Thriving")),
        icon=team.get("icon", ""),
        description=team.get("description", ""),
        project=project,
        agents=project / ".claude" / "agents",
        pending=project / "output" / "pending",
        approved=project / "output" / "approved",
        logs=project / "logs",
    )


def missing_required(env: dict[str, str], keys: Iterable[str]) -> list[str]:
    return [key for key in keys if not env.get(key, "").strip()]

