from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


UFW_PROFILE_SOURCE = Path("/usr/lib/igris/packaging/ufw/igris.profile")
UFW_PROFILE_TARGET = Path("/etc/ufw/applications.d/igris")


def _run_checked(command: list[str], error_message: str) -> None:
    completed = subprocess.run(command, check=False, text=True, capture_output=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"{error_message}{': ' + detail if detail else ''}")


def install_ufw_profile(source: Path | None = None) -> None:
    profile = Path(source or UFW_PROFILE_SOURCE)
    if not profile.exists():
        raise FileNotFoundError(f"UFW profile not found: {profile}")
    UFW_PROFILE_TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(profile, UFW_PROFILE_TARGET)
    _run_checked(["ufw", "app", "update", "Igris"], "Unable to refresh the UFW app profile")


def allow_port(port: int) -> None:
    _run_checked(["ufw", "allow", f"{port}/tcp"], f"Unable to allow TCP port {port}")


def deny_port(port: int) -> None:
    _run_checked(["ufw", "--force", "delete", "allow", f"{port}/tcp"], f"Unable to remove allow rule for TCP port {port}")
