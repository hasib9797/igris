#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.entrypoint import main as run_server
from scripts.install_service import install_service, start_service, uninstall_service
from scripts.open_firewall import allow_port, deny_port
from scripts.setup_wizard import run_setup

SERVICE_FILE = ROOT / "packaging" / "debian" / "igris.service"
CONFIG_PATH = Path("/etc/igris/config.yaml")
DATA_DIR = Path("/var/lib/igris")


def status() -> int:
    return subprocess.run(["systemctl", "status", "igris.service"], check=False).returncode


def doctor() -> int:
    checks = {
        "python3": shutil.which("python3") is not None,
        "systemctl": shutil.which("systemctl") is not None,
        "ufw": shutil.which("ufw") is not None,
        "config": CONFIG_PATH.exists(),
        "data_dir": DATA_DIR.exists(),
    }
    for name, ok in checks.items():
        print(f"{name}: {'ok' if ok else 'missing'}")
    return 0 if all(checks.values()) else 1


def reset_admin() -> int:
    from backend.app.config import clear_config_cache, load_config, save_config
    from backend.app.db.session import get_session_factory, init_database
    from backend.app.models import AdminUser
    from backend.app.security.passwords import hash_password

    import getpass

    config = load_config(CONFIG_PATH)
    new_hash = hash_password(getpass.getpass("New admin password: "))
    config.auth.password_hash = new_hash
    save_config(config, CONFIG_PATH)
    clear_config_cache()
    init_database()
    with get_session_factory()() as session:
        admin = session.query(AdminUser).filter(AdminUser.username == config.auth.admin_username).one_or_none()
        if admin:
            admin.password_hash = new_hash
            session.commit()
    print("Admin password updated.")
    return 0


def backup(target: str) -> int:
    target_path = Path(target)
    target_path.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        shutil.copy2(CONFIG_PATH, target_path / "config.yaml")
    if DATA_DIR.exists():
        destination = target_path / "data"
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(DATA_DIR, destination)
    print(f"Backup written to {target_path}")
    return 0


def restore(source: str) -> int:
    source_path = Path(source)
    if (source_path / "config.yaml").exists():
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path / "config.yaml", CONFIG_PATH)
    if (source_path / "data").exists():
        if DATA_DIR.exists():
            shutil.rmtree(DATA_DIR)
        shutil.copytree(source_path / "data", DATA_DIR)
    print(f"Restore completed from {source_path}")
    return 0


def update() -> int:
    subprocess.run(["apt-get", "update"], check=True)
    subprocess.run(["systemctl", "restart", "igris.service"], check=False)
    print("Package index refreshed and service restart requested.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="igris")
    parser.add_argument("--setup", action="store_true")
    parser.add_argument("command", nargs="?")
    parser.add_argument("subcommand", nargs="?")
    parser.add_argument("value", nargs="?")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.setup:
        run_setup()
        return 0
    if args.command == "server":
        run_server()
        return 0
    if args.command == "status":
        return status()
    if args.command == "doctor":
        return doctor()
    if args.command == "reset-admin":
        return reset_admin()
    if args.command == "service" and args.subcommand == "install":
        install_service(SERVICE_FILE)
        start_service()
        return 0
    if args.command == "service" and args.subcommand == "uninstall":
        uninstall_service()
        return 0
    if args.command == "open-port":
        allow_port(int(args.subcommand or 2511))
        return 0
    if args.command == "close-port":
        deny_port(int(args.subcommand or 2511))
        return 0
    if args.command == "backup":
        return backup(args.subcommand or "./igris-backup")
    if args.command == "restore":
        return restore(args.subcommand or "./igris-backup")
    if args.command == "update":
        return update()
    print("Unsupported command")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
