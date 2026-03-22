#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


SERVICE_DEST = Path("/etc/systemd/system/igris.service")


def _run_systemctl(*args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["systemctl", *args], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"systemctl {' '.join(args)} failed"
        raise RuntimeError(detail)
    return result


def install_service(service_source: Path) -> None:
    if not service_source.exists():
        raise FileNotFoundError(f"Service template not found: {service_source}")
    SERVICE_DEST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(service_source, SERVICE_DEST)
    _run_systemctl("daemon-reload")
    _run_systemctl("enable", "igris.service")


def start_service() -> None:
    try:
        _run_systemctl("restart", "igris.service")
        _run_systemctl("is-active", "--quiet", "igris.service")
    except RuntimeError as exc:
        logs = subprocess.run(
            ["journalctl", "-u", "igris.service", "-n", "40", "--no-pager"],
            check=False,
            capture_output=True,
            text=True,
        )
        detail = logs.stdout.strip() or logs.stderr.strip()
        if detail:
            raise RuntimeError(f"{exc}\n\nRecent igris.service logs:\n{detail}") from exc
        raise


def uninstall_service() -> None:
    subprocess.run(["systemctl", "disable", "--now", "igris.service"], check=False)
    if SERVICE_DEST.exists():
        SERVICE_DEST.unlink()
    _run_systemctl("daemon-reload")


if __name__ == "__main__":
    install_service(Path(__file__).resolve().parents[1] / "packaging" / "debian" / "igris.service")
