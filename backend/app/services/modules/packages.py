from __future__ import annotations

import os
import re

from backend.app.services.command import run_command


PACKAGE_RE = re.compile(r"^[a-z0-9][a-z0-9+._-]*$", re.IGNORECASE)


def _validate_package_name(package: str) -> str:
    if not PACKAGE_RE.fullmatch(package):
        raise ValueError("Invalid package name")
    return package


def search_packages(query: str) -> list[dict]:
    result = run_command(["apt-cache", "search", query], timeout=20).ensure_success("Unable to search packages")
    rows = []
    for line in result.stdout.splitlines()[:100]:
        if " - " in line:
            name, description = line.split(" - ", 1)
            rows.append({"name": name.strip(), "description": description.strip()})
    return rows


def package_action(package: str | None, action: str) -> str:
    env = dict(os.environ)
    env["DEBIAN_FRONTEND"] = "noninteractive"
    if action == "update-index":
        return run_command(["apt-get", "update"], timeout=600, env=env).ensure_success("Unable to update package index").stdout
    validated = _validate_package_name(package or "")
    commands = {
        "install": ["apt-get", "install", "-y", validated],
        "remove": ["apt-get", "remove", "-y", validated],
        "reinstall": ["apt-get", "install", "--reinstall", "-y", validated],
    }
    command = commands.get(action)
    if command is None:
        raise ValueError("Unsupported package action")
    return run_command(command, timeout=600, env=env).ensure_success(f"Unable to {action} package").stdout


def list_upgradable() -> list[str]:
    result = run_command(["apt", "list", "--upgradable"], timeout=30)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines()[1:] if line.strip()]
