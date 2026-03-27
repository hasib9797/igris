from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


SERVICE_TEMPLATE = Path("/usr/lib/igris/packaging/debian/igris.service")
SYSTEMD_PATH = Path("/etc/systemd/system/igris.service")


def _run_checked(command: list[str], error_message: str) -> None:
    completed = subprocess.run(command, check=False, text=True, capture_output=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"{error_message}{': ' + detail if detail else ''}")


def install_service(source: Path | None = None) -> None:
    template = Path(source or SERVICE_TEMPLATE)
    if not template.exists():
        raise FileNotFoundError(f"Service template not found: {template}")
    SYSTEMD_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template, SYSTEMD_PATH)
    _run_checked(["systemctl", "daemon-reload"], "Unable to reload systemd")
    _run_checked(["systemctl", "enable", "igris.service"], "Unable to enable igris.service")


def start_service() -> None:
    _run_checked(["systemctl", "start", "igris.service"], "Unable to start igris.service")


def uninstall_service() -> None:
    subprocess.run(["systemctl", "disable", "--now", "igris.service"], check=False)
    if SYSTEMD_PATH.exists():
        SYSTEMD_PATH.unlink()
    _run_checked(["systemctl", "daemon-reload"], "Unable to reload systemd")
