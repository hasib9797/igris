#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONFIG_PATH = Path("/etc/igris/config.yaml")
DATA_DIR = Path("/var/lib/igris")
DEFAULT_UPDATE_REPO = "https://github.com/hasib9797/igris"
DEFAULT_UPDATE_BRANCH = "main"


class CliError(RuntimeError):
    pass


def print_banner(title: str, subtitle: str = "") -> None:
    line = "=" * 68
    print(line)
    print(f"IGRIS  {title}")
    if subtitle:
        print(subtitle)
    print(line)


def print_step(message: str) -> None:
    print(f"[IGRIS] {message}")


def print_success(message: str) -> None:
    print(f"[IGRIS] {message}")


def print_error(message: str) -> None:
    print(f"[IGRIS] {message}", file=sys.stderr)


def _require_root(action: str) -> None:
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        raise PermissionError(f"Root required: {action}")


def _run(command: list[str], *, cwd: Path | None = None, timeout: int | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        env=env,
        check=False,
        timeout=timeout,
        text=True,
        capture_output=True,
    )


def _run_checked(command: list[str], *, cwd: Path | None = None, timeout: int | None = None, env: dict[str, str] | None = None, error_message: str = "Command failed") -> subprocess.CompletedProcess[str]:
    completed = _run(command, cwd=cwd, timeout=timeout, env=env)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise CliError(f"{error_message}{': ' + detail if detail else ''}")
    return completed


def _import_callable(module_name: str, attribute: str):
    module = importlib.import_module(module_name)
    return getattr(module, attribute)


def status() -> int:
    print_banner("SERVICE STATUS", "Inspecting igris.service")
    completed = subprocess.run(["systemctl", "status", "igris.service", "--no-pager"], check=False)
    return completed.returncode


def doctor() -> int:
    print_banner("DOCTOR", "Checking critical runtime dependencies")
    checks = {
        "python3": shutil.which("python3") is not None,
        "systemctl": shutil.which("systemctl") is not None,
        "ufw": shutil.which("ufw") is not None,
        "git": shutil.which("git") is not None,
        "config": CONFIG_PATH.exists(),
        "data_dir": DATA_DIR.exists(),
    }
    for name, ok in checks.items():
        state = "ok" if ok else "missing"
        print(f" - {name:<10} {state}")
    if all(checks.values()):
        print_success("Doctor checks passed.")
        return 0
    print_error("Doctor found missing requirements.")
    return 1


def reset_admin() -> int:
    print_banner("RESET ADMIN", "Updating the dashboard admin password")
    _require_root("igris reset-admin")
    run_reset = _import_callable("scripts.setup_wizard", "reset_admin_password")
    run_reset()
    print_success("Admin password updated.")
    return 0


def backup(target: str) -> int:
    print_banner("BACKUP", "Copying Igris config and metadata")
    _require_root("igris backup")
    target_path = Path(target)
    target_path.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        shutil.copy2(CONFIG_PATH, target_path / "config.yaml")
    if DATA_DIR.exists():
        destination = target_path / "data"
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(DATA_DIR, destination)
    print_success(f"Backup written to {target_path}")
    return 0


def restore(source: str) -> int:
    print_banner("RESTORE", "Restoring Igris config and metadata")
    _require_root("igris restore")
    source_path = Path(source)
    if (source_path / "config.yaml").exists():
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path / "config.yaml", CONFIG_PATH)
    if (source_path / "data").exists():
        if DATA_DIR.exists():
            shutil.rmtree(DATA_DIR)
        shutil.copytree(source_path / "data", DATA_DIR)
    print_success(f"Restore completed from {source_path}")
    return 0


def _ensure_git() -> None:
    if shutil.which("git"):
        return
    print_step("Installing git")
    _run_checked(["apt-get", "update"], error_message="Unable to update apt package metadata")
    _run_checked(["apt-get", "install", "-y", "git"], error_message="Unable to install git")


def restart() -> int:
    print_banner("RESTART", "Restarting igris.service")
    _require_root("igris --restart")
    _run_checked(["systemctl", "restart", "igris.service"], error_message="Unable to restart igris.service")
    _run_checked(["systemctl", "is-active", "--quiet", "igris.service"], error_message="igris.service did not come back up")
    print_success("igris.service restarted successfully.")
    return 0


def update() -> int:
    print_banner("UPDATE", "Fetching and applying the latest Igris build")
    _require_root("igris --update")
    _ensure_git()

    repo_url = DEFAULT_UPDATE_REPO
    branch = DEFAULT_UPDATE_BRANCH
    temp_root = Path(tempfile.mkdtemp(prefix="igris-update-"))
    checkout = temp_root / "repo"
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["DEBIAN_FRONTEND"] = "noninteractive"

    try:
        print_step(f"Cloning {repo_url} ({branch})")
        _run_checked(
            ["git", "clone", "--depth", "1", "--single-branch", "--branch", branch, repo_url, str(checkout)],
            timeout=180,
            env=env,
            error_message="Unable to fetch the update repository",
        )
        install_script = checkout / "install.sh"
        if not install_script.exists():
            raise CliError(f"install.sh not found in update repository: {install_script}")

        print_step("Stopping igris.service")
        subprocess.run(["systemctl", "stop", "igris.service"], check=False)

        print_step("Running the installer from the fetched build")
        _run_checked(["bash", str(install_script)], cwd=checkout, timeout=1800, env=env, error_message="Update installer failed")

        print_step("Reloading systemd and starting igris.service")
        _run_checked(["systemctl", "daemon-reload"], error_message="Unable to reload systemd")
        _run_checked(["systemctl", "start", "igris.service"], error_message="Unable to start igris.service")
        _run_checked(["systemctl", "is-active", "--quiet", "igris.service"], error_message="igris.service is not active after update")
        print_success("Igris updated successfully.")
        return 0
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="igris", description="Igris Ubuntu server manager")
    parser.add_argument("--setup", action="store_true", help="run the initial setup wizard")
    parser.add_argument("--update", action="store_true", help="fetch and install the latest Igris build")
    parser.add_argument("--restart", action="store_true", help="restart igris.service")
    parser.add_argument("command", nargs="?", help="status | doctor | reset-admin | service | open-port | close-port | backup | restore | update | restart | server")
    parser.add_argument("subcommand", nargs="?")
    parser.add_argument("value", nargs="?")
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        if args.setup:
            print_banner("SETUP", "Launching the Igris setup wizard")
            _require_root("igris --setup")
            run_setup = _import_callable("scripts.setup_wizard", "run_setup")
            run_setup()
            return 0
        if args.update:
            return update()
        if args.restart:
            return restart()
        if args.command == "server":
            run_server = _import_callable("backend.entrypoint", "main")
            run_server()
            return 0
        if args.command == "status":
            return status()
        if args.command == "doctor":
            return doctor()
        if args.command == "reset-admin":
            return reset_admin()
        if args.command == "service" and args.subcommand == "install":
            print_banner("SERVICE INSTALL", "Installing igris.service into systemd")
            _require_root("igris service install")
            install_service = _import_callable("scripts.install_service", "install_service")
            start_service = _import_callable("scripts.install_service", "start_service")
            install_service()
            start_service()
            print_success("igris.service installed and started.")
            return 0
        if args.command == "service" and args.subcommand == "uninstall":
            print_banner("SERVICE UNINSTALL", "Removing igris.service from systemd")
            _require_root("igris service uninstall")
            uninstall_service = _import_callable("scripts.install_service", "uninstall_service")
            uninstall_service()
            print_success("igris.service removed.")
            return 0
        if args.command == "open-port":
            print_banner("OPEN PORT", "Allowing an inbound TCP port with UFW")
            _require_root("igris open-port")
            allow_port = _import_callable("scripts.open_firewall", "allow_port")
            allow_port(int(args.subcommand or 2511))
            print_success(f"Port {int(args.subcommand or 2511)} allowed.")
            return 0
        if args.command == "close-port":
            print_banner("CLOSE PORT", "Closing an inbound TCP port with UFW")
            _require_root("igris close-port")
            deny_port = _import_callable("scripts.open_firewall", "deny_port")
            deny_port(int(args.subcommand or 2511))
            print_success(f"Port {int(args.subcommand or 2511)} closed.")
            return 0
        if args.command == "backup":
            return backup(args.subcommand or "./igris-backup")
        if args.command == "restore":
            return restore(args.subcommand or "./igris-backup")
        if args.command == "update":
            return update()
        if args.command == "restart":
            return restart()
        build_parser().print_help()
        return 1
    except PermissionError as exc:
        print_error(str(exc))
        return 1
    except CliError as exc:
        print_error(str(exc))
        return 1
    except KeyboardInterrupt:
        print_error("Operation cancelled.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
