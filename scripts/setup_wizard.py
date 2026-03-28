from __future__ import annotations

import getpass
import re
import secrets
import shutil
import socket
from datetime import datetime
from pathlib import Path

from backend.app.config import AppConfig, clear_config_cache, load_config, save_config
from backend.app.db.session import Base, get_engine, get_session_factory, init_database
from backend.app.models import AdminUser
from backend.app.security.passwords import hash_password
from scripts.install_service import install_service, start_service
from scripts.open_firewall import install_ufw_profile, allow_port


CONFIG_PATH = Path("/etc/igris/config.yaml")
DATA_DIR = Path("/var/lib/igris")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or (default or "")


def _ask_required(prompt: str, default: str | None = None) -> str:
    while True:
        value = _ask(prompt, default)
        if value:
            return value
        print("[Igris] A value is required.")


def _ask_bool(prompt: str, default: bool) -> bool:
    suffix = "Y/n" if default else "y/N"
    value = input(f"{prompt} [{suffix}]: ").strip().lower()
    if not value:
        return default
    return value in {"y", "yes"}


def _ask_email(prompt: str, default: str | None = None) -> str:
    while True:
        value = _ask_required(prompt, default)
        if EMAIL_RE.match(value):
            return value
        print("[Igris] Enter a valid email address.")


def _detect_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def _backup_existing_config() -> None:
    if not CONFIG_PATH.exists():
        return
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = CONFIG_PATH.with_suffix(CONFIG_PATH.suffix + f".bak.{timestamp}")
    shutil.copy2(CONFIG_PATH, backup)
    print(f"[Igris] Backed up existing config to {backup}")


def _write_admin_to_db(config: AppConfig) -> None:
    init_database()
    Base.metadata.create_all(bind=get_engine())
    with get_session_factory()() as session:
        admin = session.query(AdminUser).filter(AdminUser.username == config.auth.admin_username).one_or_none()
        if admin:
            admin.password_hash = config.auth.password_hash
        else:
            session.add(AdminUser(username=config.auth.admin_username, password_hash=config.auth.password_hash))
        session.commit()


def reset_admin_password() -> None:
    config = load_config(CONFIG_PATH)
    new_password = getpass.getpass("New admin password: ")
    confirm = getpass.getpass("Confirm new admin password: ")
    if new_password != confirm:
        raise RuntimeError("Password confirmation does not match")
    config.auth.password_hash = hash_password(new_password)
    save_config(config, CONFIG_PATH)
    clear_config_cache()
    _write_admin_to_db(config)


def run_setup() -> None:
    print("Igris setup wizard")
    admin_username = _ask("Dashboard admin username", "admin")
    enable_email_alerts = _ask_bool("Enable email alerts", True)
    admin_email = _ask_email("Alert email address") if enable_email_alerts else ""
    password = getpass.getpass("Dashboard password: ")
    confirm = getpass.getpass("Confirm dashboard password: ")
    if password != confirm:
        raise RuntimeError("Dashboard passwords do not match")
    port = int(_ask("Dashboard port", "2511"))
    bind_address = _ask("Bind address", "0.0.0.0")
    managed_user = _ask("Primary managed Linux username", "ubuntu")
    open_ufw = _ask_bool("Open UFW automatically", True)
    enable_terminal = _ask_bool("Enable terminal module", False)
    enable_docker = _ask_bool("Enable Docker module", True)
    enable_monitoring = _ask_bool("Enable server monitor and alerts", True)
    auto_update = _ask_bool("Enable automatic updates when the GitHub repo changes", False)

    print("[Igris] Preparing configuration directories")
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    Path("/var/log/igris").mkdir(parents=True, exist_ok=True)

    _backup_existing_config()
    config = load_config(CONFIG_PATH if CONFIG_PATH.exists() else None)
    config.server.port = port
    config.server.host = bind_address
    config.auth.admin_username = admin_username
    config.auth.admin_email = admin_email
    config.auth.password_hash = hash_password(password)
    config.auth.session_secret = secrets.token_urlsafe(32)
    config.system.managed_user = managed_user
    config.system.allow_terminal = enable_terminal
    config.modules.docker = enable_docker
    config.email.enabled = enable_email_alerts
    config.email.recipient = admin_email
    config.monitoring.enabled = enable_monitoring
    config.updates.enabled = True
    config.updates.auto_update = auto_update
    config.updates.check_interval_seconds = 120
    config.config_path = CONFIG_PATH
    config.data_dir = DATA_DIR
    save_config(config, CONFIG_PATH)
    clear_config_cache()
    print(f"[Igris] Wrote configuration to {CONFIG_PATH}")

    print("[Igris] Initializing SQLite metadata database")
    _write_admin_to_db(config)

    print("[Igris] Installing systemd service")
    install_service()

    print("[Igris] Starting Igris service")
    start_service()

    print("[Igris] Installing UFW application profile")
    install_ufw_profile()

    if open_ufw:
        print(f"[Igris] Opening TCP port {port} in UFW")
        allow_port(port)

    access_ip = _detect_ip()
    print("\nIgris is ready.")
    print(f"Dashboard URL: http://{access_ip}:{port}")
