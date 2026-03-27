from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from backend.app.config import AppConfig
from backend.app.services.command import run_command


def _state_path(config: AppConfig) -> Path:
    return config.data_dir / "runtime-state.json"


def load_runtime_state(config: AppConfig) -> dict:
    path = _state_path(config)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_runtime_state(config: AppConfig, state: dict) -> None:
    path = _state_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def fetch_remote_revision(config: AppConfig) -> str | None:
    result = run_command(["git", "ls-remote", config.updates.repo_url, f"refs/heads/{config.updates.branch}"], timeout=30)
    if result.returncode != 0:
        return None
    line = next((item for item in result.stdout.splitlines() if item.strip()), "")
    if not line:
        return None
    return line.split()[0]


def build_update_command() -> list[str]:
    system_cli = Path("/usr/bin/igris")
    if system_cli.exists():
        return [str(system_cli), "--update"]
    cli_script = Path(__file__).resolve().parents[3] / "cli" / "igris_cli.py"
    return [sys.executable, str(cli_script), "--update"]


def trigger_auto_update() -> None:
    subprocess.Popen(
        build_update_command(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
