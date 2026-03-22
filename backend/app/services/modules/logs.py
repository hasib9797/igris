from __future__ import annotations

import re

from backend.app.services.command import run_command


UNIT_RE = re.compile(r"^[A-Za-z0-9@_.:-]+(?:\.service)?$")


def _validate_unit_name(name: str) -> str:
    if not UNIT_RE.fullmatch(name):
        raise ValueError("Invalid systemd unit name")
    return name


def system_logs(lines: int = 200, priority: str | None = None, query: str | None = None) -> str:
    command = ["journalctl", "-n", str(lines), "--no-pager"]
    if priority:
        command.extend(["-p", priority])
    output = run_command(command, timeout=20).stdout
    if query:
        output = "\n".join([line for line in output.splitlines() if query.lower() in line.lower()])
    return output


def service_logs(name: str, lines: int = 200) -> str:
    return run_command(["journalctl", "--unit", _validate_unit_name(name), "-n", str(lines), "--no-pager"], timeout=20).stdout
