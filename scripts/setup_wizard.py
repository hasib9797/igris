#!/usr/bin/env python3
from __future__ import annotations

import getpass
import os
import secrets
import shutil
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.config import AppConfig, DEFAULT_CONFIG_PATH, clear_config_cache, save_config
from backend.app.db.session import Base, get_engine, init_database
from backend.app.security.passwords import hash_password
from scripts.install_service import install_service, start_service
from scripts.open_firewall import allow_port


CONFIG_PATH = DEFAULT_CONFIG_PATH
DATA_DIR = Path("/var/lib/igris")
SERVICE_SOURCE = ROOT / "packaging" / "debian" / "igris.service"
UFW_PROFILE_SOURCE = ROOT / "packaging" / "ufw" / "igris.profile"
UFW_PROFILE_DEST = Path("/etc/ufw/applications.d/igris")


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or (default or "")


def ask_bool(prompt: str, default: bool = True) -> bool:
    default_label = "Y/n" if default else "y/N"
    value = input(f"{prompt} [{default_label}]: ").strip().lower()
    if not value:
        return default
    return value in {"y", "yes"}


def local_ip() -> str:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"
    finally:
        probe.close()


def install_ufw_profile() -> None:
    if not UFW_PROFILE_SOURCE.exists():
        raise FileNotFoundError(f"UFW profile not found: {UFW_PROFILE_SOURCE}")
    UFW_PROFILE_DEST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(UFW_PROFILE_SOURCE, UFW_PROFILE_DEST)
    subprocess.run(["ufw", "app", "update", "Igris"], check=False)


def initialize_database() -> None:
    clear_config_cache()
    init_database()
    Base.metadata.create_all(bind=get_engine())


def backup_existing_config() -> Path | None:
    if not CONFIG_PATH.exists():
        return None
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    backup_path = CONFIG_PATH.with_name(f"{CONFIG_PATH.name}.bak.{stamp}")
    shutil.copy2(CONFIG_PATH, backup_path)
    return backup_path


def step(message: str) -> None:
    print(f"[Igris] {message}")


def run_setup() -> None:
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        raise PermissionError("igris --setup must be run as root")
    print("Igris setup wizard")
    admin_username = ask("Dashboard admin username", "admin")
    while True:
        password = getpass.getpass("Dashboard password: ")
        confirm = getpass.getpass("Confirm dashboard password: ")
        if password and password == confirm:
            break
        print("Passwords did not match. Please try again.")
    port = int(ask("Dashboard port", "2511"))
    bind = ask("Bind address", "0.0.0.0")
    managed_user = ask("Primary managed Linux username", "ubuntu")
    open_ufw = ask_bool("Open UFW automatically", True)
    allow_terminal = ask_bool("Enable terminal module", False)
    docker_enabled = ask_bool("Enable Docker module", True)

    step("Preparing configuration directories")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    backup_path = backup_existing_config()
    if backup_path:
        step(f"Backed up existing config to {backup_path}")

    config = AppConfig()
    config.server.host = bind
    config.server.port = port
    config.auth.admin_username = admin_username
    config.auth.password_hash = hash_password(password)
    config.auth.session_secret = secrets.token_urlsafe(48)
    config.system.managed_user = managed_user
    config.system.allow_terminal = allow_terminal
    config.modules.docker = docker_enabled
    config.data_dir = str(DATA_DIR)
    config.audit_log_path = str(DATA_DIR / "audit.log")
    config.database_url = f"sqlite:///{DATA_DIR / 'database.db'}"
    save_config(config, CONFIG_PATH)
    step(f"Wrote configuration to {CONFIG_PATH}")

    step("Initializing SQLite metadata database")
    initialize_database()
    step("Installing systemd service")
    install_service(SERVICE_SOURCE)
    step("Starting Igris service")
    start_service()
    step("Installing UFW application profile")
    install_ufw_profile()
    if open_ufw:
        step(f"Opening TCP port {port} in UFW")
        allow_port(port)
    else:
        step("Skipping UFW port change")

    print("")
    print("Igris is ready.")
    print(f"Dashboard URL: http://{local_ip()}:{port}")


if __name__ == "__main__":
    run_setup()
