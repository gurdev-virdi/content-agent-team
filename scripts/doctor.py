#!/usr/bin/env python3
"""Validate launch/runtime prerequisites without starting long-running services."""

from __future__ import annotations

import importlib.util
import json
import os
import plistlib
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.runtime import (  # noqa: E402
    PROJECT_DIR,
    claude_bin,
    ensure_runtime_dirs,
    env_bool,
    load_env,
    missing_required,
    ollama_base,
    vault_dir,
)


def check(name: str, ok: bool, detail: str = "") -> dict:
    status = "ok" if ok else "fail"
    print(f"[{status}] {name}{': ' + detail if detail else ''}")
    return {"name": name, "ok": ok, "detail": detail}


def python_dep(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def ollama_available(base: str) -> bool:
    try:
        urllib.request.urlopen(f"{base}/api/tags", timeout=2).read()
        return True
    except Exception:
        return False


def launchd_status() -> tuple[bool, str]:
    plist = Path.home() / "Library" / "LaunchAgents" / "com.animalsthriving.daemon.plist"
    if not plist.exists():
        return False, f"not installed at {plist}"
    try:
        with plist.open("rb") as f:
            data = plistlib.load(f)
        args = " ".join(data.get("ProgramArguments", []))
        if str(PROJECT_DIR) not in args and str(PROJECT_DIR) != data.get("WorkingDirectory", ""):
            return False, "installed plist points at a different workspace"
        return True, str(plist)
    except Exception as exc:
        return False, f"could not read plist: {exc}"


def main() -> int:
    env = load_env()
    ensure_runtime_dirs()
    results = []

    results.append(check("project root", PROJECT_DIR.exists(), str(PROJECT_DIR)))
    results.append(check("logs/output dirs", (PROJECT_DIR / "logs").is_dir() and (PROJECT_DIR / "output").is_dir()))
    results.append(check("FastAPI dependency", python_dep("fastapi")))
    results.append(check("Uvicorn dependency", python_dep("uvicorn")))

    bin_path = claude_bin(env)
    if Path(bin_path).is_absolute():
        claude_ok = Path(bin_path).exists() and os.access(bin_path, os.X_OK)
    else:
        claude_ok = subprocess.run(["/usr/bin/env", "sh", "-lc", f"command -v {bin_path}"], capture_output=True).returncode == 0
    results.append(check("Claude binary", claude_ok, bin_path))

    required = ["ANTHROPIC_API_KEY"]
    if not env_bool(env, "TEST_MODE", True):
        required.extend(["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"])
    missing = missing_required(env, required)
    results.append(check("required env", not missing, ", ".join(missing) if missing else "present"))

    optional_missing = missing_required(env, ["UNSPLASH_ACCESS_KEY", "REPLICATE_API_TOKEN"])
    results.append(check("image provider env", True, "missing optional: " + ", ".join(optional_missing) if optional_missing else "present"))

    base = ollama_base(env)
    results.append(check("Ollama API", ollama_available(base), base))
    port = int(env.get("MISSION_CONTROL_PORT", "8765"))
    port_busy = port_open("127.0.0.1", port)
    results.append(check("Mission Control port", True, f"{port} {'in use' if port_busy else 'free'}"))

    launchd_ok, launchd_detail = launchd_status()
    results.append(check("launchd daemon plist", launchd_ok, launchd_detail))

    vdir = vault_dir(env)
    results.append(check("vault path", True, str(vdir)))

    if "--json" in sys.argv:
        print(json.dumps({"ok": all(item["ok"] for item in results), "checks": results}, indent=2))
    return 0 if all(item["ok"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
