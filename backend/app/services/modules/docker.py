from __future__ import annotations

import re

from backend.app.services.command import run_command


CONTAINER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def _validate_container_name(container: str) -> str:
    if not CONTAINER_RE.fullmatch(container):
        raise ValueError("Invalid Docker container name")
    return container


def docker_installed() -> bool:
    return run_command(["docker", "version", "--format", "{{.Server.Version}}"], timeout=10).returncode == 0


def docker_status() -> dict:
    if not docker_installed():
        return {"installed": False, "running": False}
    info = run_command(["docker", "info", "--format", "{{json .}}"], timeout=20)
    running = info.returncode == 0
    return {"installed": True, "running": running, "details": info.stdout.strip()}


def list_containers(all_containers: bool = True) -> list[str]:
    args = ["docker", "ps"]
    if all_containers:
        args.append("-a")
    args.extend(["--format", "{{.ID}} {{.Names}} {{.Status}}"])
    return [line for line in run_command(args, timeout=20).stdout.splitlines() if line.strip()]


def container_action(container: str, action: str) -> None:
    run_command(["docker", action, _validate_container_name(container)], timeout=30).ensure_success(f"Unable to {action} container")


def container_logs(container: str, lines: int = 200) -> str:
    return run_command(["docker", "logs", "--tail", str(lines), _validate_container_name(container)], timeout=20).stdout


def list_images() -> list[str]:
    return [line for line in run_command(["docker", "images", "--format", "{{.Repository}}:{{.Tag}} {{.Size}}"], timeout=20).stdout.splitlines() if line.strip()]
