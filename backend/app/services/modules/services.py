from __future__ import annotations

import re

from backend.app.services.command import run_command


UNIT_RE = re.compile(r"^[A-Za-z0-9@_.:-]+(?:\.service)?$")


def _validate_unit_name(name: str) -> str:
    if not UNIT_RE.fullmatch(name):
        raise ValueError("Invalid systemd unit name")
    return name


def list_services() -> list[dict]:
    result = run_command(
        ["systemctl", "list-units", "--type=service", "--all", "--no-pager", "--no-legend"],
        timeout=20,
    ).ensure_success("Unable to list services")
    services = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        services.append(
            {
                "name": parts[0],
                "load": parts[1],
                "active": parts[2],
                "sub": parts[3],
                "description": " ".join(parts[4:]),
            }
        )
    return services


def service_action(name: str, action: str) -> None:
    run_command(["systemctl", action, "--", _validate_unit_name(name)], timeout=30).ensure_success(f"Unable to {action} {name}")


def service_logs(name: str, lines: int = 200) -> str:
    return run_command(["journalctl", "--unit", _validate_unit_name(name), "-n", str(lines), "--no-pager"], timeout=20).stdout
