from __future__ import annotations

import subprocess
from collections.abc import Iterator

from fastapi import APIRouter, Cookie, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.auth.session import REAUTH_COOKIE_NAME, clear_session_cookie, decode_reauth_token, set_reauth_cookie, set_session_cookie
from backend.app.config import get_config, save_config
from backend.app.db.session import get_db
from backend.app.models import AdminUser
from backend.app.schemas.common import (
    ActionRequest,
    FileDeleteRequest,
    FileWriteRequest,
    FirewallAppRequest,
    FirewallPortRequest,
    HostnameRequest,
    LoginRequest,
    MessageResponse,
    MkdirRequest,
    NetplanWriteRequest,
    PackageActionRequest,
    ProcessKillRequest,
    ResetPasswordRequest,
    SettingsUpdateRequest,
    SetSudoRequest,
    TaskCreateRequest,
    TaskDeleteRequest,
    TaskRunRequest,
    TerminalExecRequest,
    TerminalExecResponse,
    UserActionRequest,
    UserCreateRequest,
    UserResponse,
)
from backend.app.security.passwords import verify_password
from backend.app.services.authz import verify_reauth
from backend.app.services.modules import alerts as alert_service
from backend.app.services.modules import docker as docker_service
from backend.app.services.modules import files as file_service
from backend.app.services.modules import firewall as firewall_service
from backend.app.services.modules import logs as log_service
from backend.app.services.modules import network as network_service
from backend.app.services.modules import packages as package_service
from backend.app.services.modules import processes as process_service
from backend.app.services.modules import services as systemd_service
from backend.app.services.modules import tasks as task_service
from backend.app.services.modules import users as user_service
from backend.app.services.overview import get_system_health, get_system_overview
from backend.app.utils.audit import log_audit


router = APIRouter(prefix="/api")


def _dangerous(db: Session, actor: str, password: str | None, action: str, target: str = "") -> None:
    verify_reauth(db, actor, password)
    log_audit(db, actor=actor, action=action, target=target)


@router.post("/auth/login", response_model=UserResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> UserResponse:
    user = db.scalar(select(AdminUser).where(AdminUser.username == payload.username))
    if not user or not verify_password(payload.password, user.password_hash):
        log_audit(db, actor=payload.username or "unknown", action="auth.login_failed")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    set_session_cookie(response, user.username)
    log_audit(db, actor=user.username, action="auth.login")
    return UserResponse(username=user.username, must_reauth=user.must_reauth)


@router.post("/auth/logout", response_model=MessageResponse)
def logout(response: Response, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    clear_session_cookie(response)
    log_audit(db, actor=user.username, action="auth.logout")
    return MessageResponse(message="Logged out")


@router.get("/auth/me", response_model=UserResponse)
def me(user: AdminUser = Depends(get_current_user)) -> UserResponse:
    return UserResponse(username=user.username, must_reauth=user.must_reauth)


@router.get("/system/overview")
def system_overview(_: AdminUser = Depends(get_current_user)) -> dict:
    return get_system_overview()


@router.get("/system/health")
def system_health(_: AdminUser = Depends(get_current_user)) -> dict:
    return get_system_health()


@router.get("/services")
def services(_: AdminUser = Depends(get_current_user)) -> list[dict]:
    return systemd_service.list_services()


@router.post("/services/{name}/start", response_model=MessageResponse)
def service_start(name: str, payload: ActionRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "services.start", name)
    systemd_service.service_action(name, "start")
    return MessageResponse(message=f"Started {name}")


@router.post("/services/{name}/stop", response_model=MessageResponse)
def service_stop(name: str, payload: ActionRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "services.stop", name)
    systemd_service.service_action(name, "stop")
    return MessageResponse(message=f"Stopped {name}")


@router.post("/services/{name}/restart", response_model=MessageResponse)
def service_restart(name: str, payload: ActionRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "services.restart", name)
    systemd_service.service_action(name, "restart")
    return MessageResponse(message=f"Restarted {name}")


@router.post("/services/{name}/enable", response_model=MessageResponse)
def service_enable(name: str, payload: ActionRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "services.enable", name)
    systemd_service.service_action(name, "enable")
    return MessageResponse(message=f"Enabled {name}")


@router.post("/services/{name}/disable", response_model=MessageResponse)
def service_disable(name: str, payload: ActionRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "services.disable", name)
    systemd_service.service_action(name, "disable")
    return MessageResponse(message=f"Disabled {name}")


@router.get("/services/{name}/logs")
def service_logs(name: str, _: AdminUser = Depends(get_current_user)) -> dict:
    return {"logs": systemd_service.service_logs(name)}


@router.get("/packages/search")
def package_search(query: str = Query(..., min_length=2), _: AdminUser = Depends(get_current_user)) -> list[dict]:
    return package_service.search_packages(query)


@router.post("/packages/install", response_model=MessageResponse)
def package_install(payload: PackageActionRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "packages.install", payload.package)
    package_service.package_action(payload.package, "install")
    return MessageResponse(message=f"Installed {payload.package}")


@router.post("/packages/remove", response_model=MessageResponse)
def package_remove(payload: PackageActionRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "packages.remove", payload.package)
    package_service.package_action(payload.package, "remove")
    return MessageResponse(message=f"Removed {payload.package}")


@router.post("/packages/reinstall", response_model=MessageResponse)
def package_reinstall(payload: PackageActionRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "packages.reinstall", payload.package)
    package_service.package_action(payload.package, "reinstall")
    return MessageResponse(message=f"Reinstalled {payload.package}")


@router.post("/packages/update-index", response_model=MessageResponse)
def package_update_index(payload: ActionRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "packages.update-index")
    package_service.package_action("", "update-index")
    return MessageResponse(message="Package index updated")


@router.get("/packages/upgradable")
def package_upgradable(_: AdminUser = Depends(get_current_user)) -> list[str]:
    return package_service.list_upgradable()


@router.get("/packages/installed")
def package_installed(_: AdminUser = Depends(get_current_user)) -> list[dict]:
    return package_service.list_installed()


@router.get("/network/interfaces")
def network_interfaces(_: AdminUser = Depends(get_current_user)) -> dict:
    return network_service.get_interfaces()


@router.get("/network/routes")
def network_routes(_: AdminUser = Depends(get_current_user)) -> list[str]:
    return network_service.get_routes()


@router.get("/network/ports")
def network_ports(_: AdminUser = Depends(get_current_user)) -> list[str]:
    return network_service.get_ports()


@router.get("/network/dns")
def network_dns(_: AdminUser = Depends(get_current_user)) -> dict:
    return network_service.get_dns()


@router.post("/network/hostname", response_model=MessageResponse)
def network_hostname(payload: HostnameRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "network.hostname", payload.hostname)
    network_service.set_hostname(payload.hostname)
    return MessageResponse(message=f"Hostname updated to {payload.hostname}")


@router.get("/network/netplan")
def network_netplan(_: AdminUser = Depends(get_current_user)) -> dict:
    return network_service.read_netplan()


@router.post("/network/netplan", response_model=MessageResponse)
def update_netplan(payload: NetplanWriteRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "network.netplan.write")
    network_service.write_netplan(payload.files)
    return MessageResponse(message="Netplan updated")


@router.get("/firewall/status")
def firewall_status(_: AdminUser = Depends(get_current_user)) -> dict:
    return {"status": firewall_service.ufw_status()}


@router.post("/firewall/enable", response_model=MessageResponse)
def firewall_enable(payload: ActionRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "firewall.enable")
    firewall_service.ufw_action("enable")
    return MessageResponse(message="UFW enabled")


@router.post("/firewall/disable", response_model=MessageResponse)
def firewall_disable(payload: ActionRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "firewall.disable")
    firewall_service.ufw_action("disable")
    return MessageResponse(message="UFW disabled")


@router.post("/firewall/allow-port", response_model=MessageResponse)
def firewall_allow_port(payload: FirewallPortRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    target = f"{payload.port}/{payload.protocol}"
    _dangerous(db, user.username, payload.confirm_password, "firewall.allow-port", target)
    firewall_service.ufw_action("allow", target)
    return MessageResponse(message=f"Allowed {target}")


@router.post("/firewall/deny-port", response_model=MessageResponse)
def firewall_deny_port(payload: FirewallPortRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    target = f"{payload.port}/{payload.protocol}"
    _dangerous(db, user.username, payload.confirm_password, "firewall.deny-port", target)
    firewall_service.ufw_action("deny", target)
    return MessageResponse(message=f"Denied {target}")


@router.post("/firewall/allow-app", response_model=MessageResponse)
def firewall_allow_app(payload: FirewallAppRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "firewall.allow-app", payload.profile)
    firewall_service.ufw_action("allow", payload.profile)
    return MessageResponse(message=f"Allowed app profile {payload.profile}")


@router.get("/firewall/rules")
def firewall_rules(_: AdminUser = Depends(get_current_user)) -> dict:
    return {"rules": firewall_service.ufw_status()}


@router.get("/users")
def users(_: AdminUser = Depends(get_current_user)) -> list[dict]:
    return user_service.list_users()


@router.post("/users/create", response_model=MessageResponse)
def users_create(payload: UserCreateRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "users.create", payload.username)
    user_service.create_user(payload.username, payload.shell, payload.home)
    if payload.password:
        user_service.set_password(payload.username, payload.password)
    if payload.sudo:
        user_service.set_sudo(payload.username, True)
    return MessageResponse(message=f"Created user {payload.username}")


@router.post("/users/delete", response_model=MessageResponse)
def users_delete(payload: UserActionRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "users.delete", payload.username)
    user_service.delete_user(payload.username)
    return MessageResponse(message=f"Deleted user {payload.username}")


@router.post("/users/lock", response_model=MessageResponse)
def users_lock(payload: UserActionRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "users.lock", payload.username)
    user_service.lock_user(payload.username)
    return MessageResponse(message=f"Locked user {payload.username}")


@router.post("/users/unlock", response_model=MessageResponse)
def users_unlock(payload: UserActionRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "users.unlock", payload.username)
    user_service.unlock_user(payload.username)
    return MessageResponse(message=f"Unlocked user {payload.username}")


@router.post("/users/reset-password", response_model=MessageResponse)
def users_reset_password(payload: ResetPasswordRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "users.reset-password", payload.username)
    user_service.set_password(payload.username, payload.new_password)
    return MessageResponse(message=f"Password reset for {payload.username}")


@router.post("/users/set-sudo", response_model=MessageResponse)
def users_set_sudo(payload: SetSudoRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "users.set-sudo", payload.username)
    user_service.set_sudo(payload.username, payload.enabled)
    state = "granted" if payload.enabled else "revoked"
    return MessageResponse(message=f"Sudo {state} for {payload.username}")


@router.get("/files/list")
def files_list(path: str = Query("/etc"), _: AdminUser = Depends(get_current_user)) -> list[dict]:
    return file_service.list_path(path)


@router.get("/files/read")
def files_read(path: str = Query(...), _: AdminUser = Depends(get_current_user)) -> dict:
    return file_service.read_file(path)


@router.post("/files/write", response_model=MessageResponse)
def files_write(payload: FileWriteRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "files.write", payload.path)
    file_service.write_file(payload.path, payload.content, payload.create_backup)
    return MessageResponse(message=f"Updated {payload.path}")


@router.post("/files/upload", response_model=MessageResponse)
def files_upload(
    path: str = Query(...),
    confirm_password: str | None = Query(None),
    upload: UploadFile = File(...),
    user: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    _dangerous(db, user.username, confirm_password, "files.upload", path)
    content = upload.file.read().decode("utf-8")
    file_service.write_file(path, content, create_backup=True)
    return MessageResponse(message=f"Uploaded {upload.filename} to {path}")


@router.post("/files/delete", response_model=MessageResponse)
def files_delete(payload: FileDeleteRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "files.delete", payload.path)
    file_service.delete_path(payload.path)
    return MessageResponse(message=f"Deleted {payload.path}")


@router.post("/files/mkdir", response_model=MessageResponse)
def files_mkdir(payload: MkdirRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "files.mkdir", payload.path)
    file_service.make_directory(payload.path)
    return MessageResponse(message=f"Created directory {payload.path}")


@router.get("/processes")
def processes(search: str | None = None, _: AdminUser = Depends(get_current_user)) -> list[dict]:
    return process_service.list_processes(search)


@router.post("/processes/kill", response_model=MessageResponse)
def process_kill(payload: ProcessKillRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "processes.kill", str(payload.pid))
    process_service.kill_process(payload.pid, payload.signal)
    return MessageResponse(message=f"Signal {payload.signal} sent to {payload.pid}")


@router.get("/logs/system")
def logs_system(lines: int = 200, severity: str | None = None, query: str | None = None, _: AdminUser = Depends(get_current_user)) -> dict:
    return {"logs": log_service.system_logs(lines=lines, priority=severity, query=query)}


@router.get("/logs/service/{name}")
def logs_service(name: str, lines: int = 200, _: AdminUser = Depends(get_current_user)) -> dict:
    return {"logs": log_service.service_logs(name, lines=lines)}


@router.get("/logs/live")
def logs_live(service: str | None = None, lines: int = 20, _: AdminUser = Depends(get_current_user)) -> StreamingResponse:
    command = ["journalctl", "-f", "-n", str(lines), "--no-pager"]
    if service:
        command.extend(["--unit", log_service._validate_unit_name(service)])

    def generate() -> Iterator[bytes]:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            assert process.stdout is not None
            for line in iter(process.stdout.readline, b""):
                if not line:
                    break
                yield line
        finally:
            process.terminate()
            try:
                process.wait(timeout=2)
            except Exception:
                pass

    return StreamingResponse(generate(), media_type="text/plain")


@router.get("/docker/status")
def docker_status(_: AdminUser = Depends(get_current_user)) -> dict:
    return docker_service.docker_status()


@router.get("/docker/containers")
def docker_containers(_: AdminUser = Depends(get_current_user)) -> list[str]:
    return docker_service.list_containers()


@router.post("/docker/container/start", response_model=MessageResponse)
def docker_start(container: str = Query(...), payload: ActionRequest | None = None, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password if payload else None, "docker.container.start", container)
    docker_service.container_action(container, "start")
    return MessageResponse(message=f"Started container {container}")


@router.post("/docker/container/stop", response_model=MessageResponse)
def docker_stop(container: str = Query(...), payload: ActionRequest | None = None, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password if payload else None, "docker.container.stop", container)
    docker_service.container_action(container, "stop")
    return MessageResponse(message=f"Stopped container {container}")


@router.post("/docker/container/restart", response_model=MessageResponse)
def docker_restart(container: str = Query(...), payload: ActionRequest | None = None, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password if payload else None, "docker.container.restart", container)
    docker_service.container_action(container, "restart")
    return MessageResponse(message=f"Restarted container {container}")


@router.get("/docker/container/logs")
def docker_container_logs(container: str = Query(...), _: AdminUser = Depends(get_current_user)) -> dict:
    return {"logs": docker_service.container_logs(container)}


@router.get("/docker/images")
def docker_images(_: AdminUser = Depends(get_current_user)) -> list[str]:
    return docker_service.list_images()


@router.post("/terminal/exec", response_model=TerminalExecResponse)
def terminal_exec(
    payload: TerminalExecRequest,
    response: Response,
    reauth_token: str | None = Cookie(default=None, alias=REAUTH_COOKIE_NAME),
    user: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TerminalExecResponse:
    if not get_config().system.allow_terminal:
        raise HTTPException(status_code=403, detail="Terminal module is disabled")
    if payload.confirm_password:
        _dangerous(db, user.username, payload.confirm_password, "terminal.exec")
        set_reauth_cookie(response, user.username, "terminal.exec")
    elif get_config().security.require_reauth_for_dangerous_actions and not decode_reauth_token(reauth_token, user.username, "terminal.exec"):
        raise HTTPException(status_code=401, detail="Console confirmation expired. Confirm your dashboard password again.")
    try:
        completed = subprocess.run(
            ["/bin/bash", "-lc", payload.command],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        log_audit(db, actor=user.username, action="terminal.exec.timeout", target=payload.command[:120])
        raise HTTPException(
            status_code=408,
            detail=f"Command timed out after 30 seconds: {exc.cmd}",
        ) from exc
    log_audit(db, actor=user.username, action="terminal.exec.completed", target=payload.command[:120])
    return TerminalExecResponse(
        command=payload.command,
        stdout=completed.stdout,
        stderr=completed.stderr,
        exit_code=completed.returncode,
    )


@router.get("/tasks")
def tasks(_: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return [
        {"id": task.id, "name": task.name, "command": task.command, "schedule": task.schedule, "enabled": task.enabled}
        for task in task_service.list_tasks(db)
    ]


@router.post("/tasks/create", response_model=MessageResponse)
def tasks_create(payload: TaskCreateRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    task_service.create_task(db, payload.name, payload.command, payload.schedule)
    log_audit(db, actor=user.username, action="tasks.create", target=payload.name)
    return MessageResponse(message=f"Created task {payload.name}")


@router.post("/tasks/run", response_model=MessageResponse)
def tasks_run(payload: TaskRunRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "tasks.run", str(payload.id))
    task_service.run_task(db, payload.id)
    return MessageResponse(message=f"Task {payload.id} executed")


@router.post("/tasks/delete", response_model=MessageResponse)
def tasks_delete(payload: TaskDeleteRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "tasks.delete", str(payload.id))
    task_service.delete_task(db, payload.id)
    return MessageResponse(message=f"Task {payload.id} deleted")


@router.get("/alerts")
def alerts(_: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return [
        {"id": item.id, "level": item.level, "message": item.message, "source": item.source, "resolved": item.resolved}
        for item in alert_service.list_alerts(db)
    ]


@router.post("/alerts/test", response_model=MessageResponse)
def alerts_test(user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    alert_service.create_alert(db, level="warning", message="Igris test alert", source="manual")
    log_audit(db, actor=user.username, action="alerts.test")
    return MessageResponse(message="Test alert created")


@router.get("/settings")
def settings(_: AdminUser = Depends(get_current_user)) -> dict:
    config = get_config()
    return {
        "server_port": config.server.port,
        "bind_address": config.server.host,
        "session_timeout_minutes": config.auth.session_timeout_minutes,
        "allow_terminal": config.system.allow_terminal,
        "docker_enabled": config.modules.docker,
        "require_reauth_for_dangerous_actions": config.security.require_reauth_for_dangerous_actions,
    }


@router.post("/settings/update", response_model=MessageResponse)
def settings_update(payload: SettingsUpdateRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    _dangerous(db, user.username, payload.confirm_password, "settings.update")
    config = get_config()
    config.server.port = payload.server_port
    config.server.host = payload.bind_address
    config.auth.session_timeout_minutes = payload.session_timeout_minutes
    config.system.allow_terminal = payload.allow_terminal
    config.modules.docker = payload.docker_enabled
    config.security.require_reauth_for_dangerous_actions = payload.require_reauth_for_dangerous_actions
    save_config(config)
    return MessageResponse(message="Settings updated")
