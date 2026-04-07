from __future__ import annotations

import re
from dataclasses import dataclass

from backend.app.services.command import run_command


UNIT_RE = re.compile(r"^[A-Za-z0-9@_.:-]+(?:\.service)?$")


@dataclass
class FailedServiceRecord:
    name: str
    status_line: str
    load_state: str
    active_state: str
    sub_state: str
    unit_file_state: str
    fragment_path: str
    deleted: bool = False


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


def inspect_service(name: str) -> FailedServiceRecord:
    result = run_command(
        [
            "systemctl",
            "show",
            "--property=Id,LoadState,ActiveState,SubState,UnitFileState,FragmentPath",
            "--",
            _validate_unit_name(name),
        ],
        timeout=10,
    )
    props: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        props[key] = value.strip()
    stderr = (result.stderr or "").lower()
    load_state = props.get("LoadState", "")
    unit_file_state = props.get("UnitFileState", "")
    fragment_path = props.get("FragmentPath", "")
    deleted = load_state == "not-found" or "could not be found" in stderr or (
        not fragment_path and unit_file_state == "not-found"
    )
    return FailedServiceRecord(
        name=props.get("Id") or name,
        status_line=name,
        load_state=load_state,
        active_state=props.get("ActiveState", ""),
        sub_state=props.get("SubState", ""),
        unit_file_state=unit_file_state,
        fragment_path=fragment_path,
        deleted=deleted,
    )


def list_failed_services(*, include_deleted: bool = True) -> list[FailedServiceRecord]:
    result = run_command(["systemctl", "--failed", "--no-legend", "--plain"], timeout=10)
    failed_services: list[FailedServiceRecord] = []
    for line in [item.strip() for item in result.stdout.splitlines() if item.strip()]:
        service_name = line.split()[0]
        record = inspect_service(service_name)
        record.status_line = line
        if record.deleted and not include_deleted:
            continue
        failed_services.append(record)
    return failed_services


def service_action(name: str, action: str) -> None:
    run_command(["systemctl", action, "--", _validate_unit_name(name)], timeout=30).ensure_success(f"Unable to {action} {name}")


def service_logs(name: str, lines: int = 200) -> str:
    return run_command(["journalctl", "--unit", _validate_unit_name(name), "-n", str(lines), "--no-pager"], timeout=20).stdout
