#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
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
INSTALL_ROOT = Path("/usr/lib/igris")
BIN_PATH = Path("/usr/bin/igris")
SYSTEMD_SERVICE_PATH = Path("/etc/systemd/system/igris.service")
APP_VERSION = "2.0.0"


class CliError(RuntimeError):
    pass


def print_banner(title: str, subtitle: str = "") -> None:
    line = "=" * 68
    print(line)
    print(f"IGRIS v{APP_VERSION}  {title}")
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


def help_command() -> int:
    print_banner("HELP", "Showing available Igris commands")
    build_parser().print_help()
    return 0


def version_command() -> int:
    print(f"Igris v{APP_VERSION}")
    return 0


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


def config_show() -> int:
    print_banner("CONFIG", "Current runtime configuration summary")
    config = _import_callable("backend.app.config", "load_config")(CONFIG_PATH if CONFIG_PATH.exists() else None)
    summary = {
        "version": APP_VERSION,
        "config_path": str(CONFIG_PATH),
        "data_dir": str(DATA_DIR),
        "server": {"host": config.server.host, "port": config.server.port},
        "auth": {"admin_username": config.auth.admin_username, "admin_email": config.auth.admin_email, "email_alerts": config.email.enabled},
        "modules": {
            "docker": config.modules.docker,
            "files": config.modules.files,
            "alerts": config.modules.alerts,
            "tasks": config.modules.tasks,
            "terminal": config.system.allow_terminal,
        },
        "updates": {"auto_update": config.updates.auto_update, "repo_url": config.updates.repo_url, "branch": config.updates.branch},
    }
    print(json.dumps(summary, indent=2))
    return 0


def health() -> int:
    print_banner("HEALTH", "System health snapshot")
    get_health = _import_callable("backend.app.services.overview", "get_system_health")
    print(json.dumps(get_health(), indent=2))
    return 0


def overview() -> int:
    print_banner("OVERVIEW", "System overview snapshot")
    get_overview = _import_callable("backend.app.services.overview", "get_system_overview")
    print(json.dumps(get_overview(), indent=2))
    return 0


def users_list() -> int:
    print_banner("USERS", "Listing local Linux users")
    list_users = _import_callable("backend.app.services.modules.users", "list_users")
    print(json.dumps(list_users(), indent=2))
    return 0


def packages_upgradable() -> int:
    print_banner("PACKAGES", "Listing upgradable packages")
    list_upgradable = _import_callable("backend.app.services.modules.packages", "list_upgradable")
    print(json.dumps(list_upgradable(), indent=2))
    return 0


def services_failed() -> int:
    print_banner("FAILED SERVICES", "Listing failed systemd units")
    get_overview = _import_callable("backend.app.services.overview", "get_system_overview")
    print(json.dumps(get_overview().get("failed_services", []), indent=2))
    return 0


def files_roots() -> int:
    print_banner("FILE ROOTS", "Allowed file explorer roots")
    safe_roots = _import_callable("backend.app.services.modules.files", "SAFE_ROOTS")
    print(json.dumps([str(item) for item in safe_roots], indent=2))
    return 0


def file_read(path: str) -> int:
    print_banner("FILE READ", path)
    read_file = _import_callable("backend.app.services.modules.files", "read_file")
    result = read_file(path)
    print(result["content"])
    return 0


def tasks_list() -> int:
    print_banner("TASKS", "Listing saved Igris tasks")
    init_database = _import_callable("backend.app.db.session", "init_database")
    get_session_factory = _import_callable("backend.app.db.session", "get_session_factory")
    list_tasks_callable = _import_callable("backend.app.services.modules.tasks", "list_tasks")
    init_database()
    with get_session_factory()() as db:
        tasks = list_tasks_callable(db)
        payload = [{"id": task.id, "name": task.name, "command": task.command, "schedule": task.schedule, "enabled": task.enabled, "created_at": task.created_at.isoformat() if task.created_at else None} for task in tasks]
    print(json.dumps(payload, indent=2))
    return 0


def tasks_run(task_id: int) -> int:
    print_banner("TASK RUN", f"Running task {task_id}")
    _require_root("igris tasks run")
    init_database = _import_callable("backend.app.db.session", "init_database")
    get_session_factory = _import_callable("backend.app.db.session", "get_session_factory")
    run_task_callable = _import_callable("backend.app.services.modules.tasks", "run_task")
    init_database()
    with get_session_factory()() as db:
        output = run_task_callable(db, task_id)
    print(output)
    return 0


def logs(lines: int = 200, service: str = "igris.service") -> int:
    print_banner("LOGS", f"Showing the last {lines} lines for {service}")
    completed = subprocess.run(["journalctl", "-u", service, "-n", str(lines), "--no-pager"], check=False)
    return completed.returncode


def _parse_logs_args(subcommand: str | None, value: str | None) -> tuple[int, str]:
    if not subcommand:
        return 200, "igris.service"
    if subcommand.isdigit():
        return int(subcommand), value or "igris.service"
    return 200, subcommand


def update_check() -> int:
    print_banner("UPDATE CHECK", "Checking the remote repository for new Igris revisions")
    fetch_remote_revision = _import_callable("backend.app.services.updates", "fetch_remote_revision")
    load_runtime_state = _import_callable("backend.app.services.updates", "load_runtime_state")
    config = _import_callable("backend.app.config", "get_config")()
    remote_revision = fetch_remote_revision(config)
    if not remote_revision:
        print_error("Unable to fetch the remote revision.")
        return 1
    state = load_runtime_state(config)
    last_seen = state.get("last_seen_remote_revision")
    print(json.dumps({"version": APP_VERSION, "repo": config.updates.repo_url, "branch": config.updates.branch, "remote_revision": remote_revision, "last_seen_remote_revision": last_seen, "update_available": bool(last_seen and remote_revision != last_seen)}, indent=2))
    return 0


def alerts_test() -> int:
    print_banner("ALERT TEST", "Creating and emailing a test alert")
    _require_root("igris alerts test")
    get_config = _import_callable("backend.app.config", "get_config")
    init_database = _import_callable("backend.app.db.session", "init_database")
    get_session_factory = _import_callable("backend.app.db.session", "get_session_factory")
    create_alert = _import_callable("backend.app.services.modules.alerts", "create_alert")
    build_alert_html = _import_callable("backend.app.services.notifications", "build_alert_html")
    send_email_notification = _import_callable("backend.app.services.notifications", "send_email_notification")
    init_database()
    config = get_config()
    message = "Igris CLI test alert"
    with get_session_factory()() as db:
        create_alert(db, level="warning", message=message, source="cli")
    send_email_notification(
        config,
        subject="Igris alert: CLI test email",
        text_body=message,
        html_body=build_alert_html(title="CLI test alert", summary=message, details="This test email was triggered from the Igris CLI."),
        require_ready=True,
    )
    print_success("Test alert created and email sent.")
    return 0


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


def _backup_path(source: Path, backup_root: Path, name: str) -> Path | None:
    if not source.exists():
        return None
    destination = backup_root / name
    if source.is_dir():
        shutil.copytree(source, destination, symlinks=True)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return destination


def _restore_path(backup: Path | None, destination: Path) -> None:
    if destination.exists():
        if destination.is_dir():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    if backup is None or not backup.exists():
        return
    if backup.is_dir():
        shutil.copytree(backup, destination, symlinks=True)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, destination)


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
    backup_root = temp_root / "backup"
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["DEBIAN_FRONTEND"] = "noninteractive"
    install_backup: Path | None = None
    bin_backup: Path | None = None
    service_backup: Path | None = None

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

        print_step("Creating rollback snapshot of the current install")
        backup_root.mkdir(parents=True, exist_ok=True)
        install_backup = _backup_path(INSTALL_ROOT, backup_root, "usr-lib-igris")
        bin_backup = _backup_path(BIN_PATH, backup_root, "usr-bin-igris")
        service_backup = _backup_path(SYSTEMD_SERVICE_PATH, backup_root, "igris.service")

        print_step("Stopping igris.service")
        subprocess.run(["systemctl", "stop", "igris.service"], check=False)

        try:
            print_step("Running the installer from the fetched build")
            _run_checked(["bash", str(install_script)], cwd=checkout, timeout=1800, env=env, error_message="Update installer failed")

            print_step("Reloading systemd and starting igris.service")
            _run_checked(["systemctl", "daemon-reload"], error_message="Unable to reload systemd")
            _run_checked(["systemctl", "start", "igris.service"], error_message="Unable to start igris.service")
            _run_checked(["systemctl", "is-active", "--quiet", "igris.service"], error_message="igris.service is not active after update")
            print_success("Igris updated successfully.")
            _run_checked(["systemctl", "restart", "igris.service"], error_message="Unable to restart igris.service after update")
            print_success("igris.service restarted successfully after update.")
            return 0
        except Exception as exc:
            print_error(f"Update failed, restoring previous install: {exc}")
            _restore_path(install_backup, INSTALL_ROOT)
            _restore_path(bin_backup, BIN_PATH)
            _restore_path(service_backup, SYSTEMD_SERVICE_PATH)
            _run_checked(["systemctl", "daemon-reload"], error_message="Unable to reload systemd after rollback")
            _run_checked(["systemctl", "start", "igris.service"], error_message="Unable to restart igris.service after rollback")
            _run_checked(["systemctl", "is-active", "--quiet", "igris.service"], error_message="igris.service did not recover after rollback")
            raise CliError(f"Update failed and the previous version was restored: {exc}") from exc
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="igris", description="Igris v2 Ubuntu server manager")
    parser.add_argument("--setup", action="store_true", help="run the initial setup wizard")
    parser.add_argument("--update", action="store_true", help="fetch and install the latest Igris build")
    parser.add_argument("--restart", action="store_true", help="restart igris.service")
    parser.add_argument("command", nargs="?", help="help | version | status | doctor | config | health | overview | users | tasks | packages | services | files | logs | alerts | update-check | reset-admin | service | open-port | close-port | backup | restore | update | restart | server")
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
        if args.command == "help":
            return help_command()
        if args.command == "version":
            return version_command()
        if args.command == "status":
            return status()
        if args.command == "doctor":
            return doctor()
        if args.command == "config":
            return config_show()
        if args.command == "health":
            return health()
        if args.command == "overview":
            return overview()
        if args.command == "users" and args.subcommand == "list":
            return users_list()
        if args.command == "tasks" and args.subcommand == "list":
            return tasks_list()
        if args.command == "tasks" and args.subcommand and args.value is None and args.subcommand.isdigit():
            return tasks_run(int(args.subcommand))
        if args.command == "tasks" and args.subcommand == "run" and args.value and args.value.isdigit():
            return tasks_run(int(args.value))
        if args.command == "packages" and args.subcommand == "upgradable":
            return packages_upgradable()
        if args.command == "services" and args.subcommand == "failed":
            return services_failed()
        if args.command == "files" and args.subcommand == "roots":
            return files_roots()
        if args.command == "files" and args.subcommand == "read" and args.value:
            return file_read(args.value)
        if args.command == "logs":
            lines, service = _parse_logs_args(args.subcommand, args.value)
            return logs(lines, service)
        if args.command == "update-check":
            return update_check()
        if args.command == "alerts" and args.subcommand == "test":
            return alerts_test()
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
