from __future__ import annotations

from backend.app.services.command import run_command


def ufw_status() -> str:
    return run_command(["ufw", "status", "verbose"], timeout=15).stdout


def ufw_action(action: str, target: str | None = None) -> str:
    command = ["ufw", action]
    if target:
        command.append(target)
    return run_command(command, timeout=30).ensure_success(f"Unable to run ufw {action}").stdout

