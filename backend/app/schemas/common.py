from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    message: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    username: str
    must_reauth: bool = False


class ActionRequest(BaseModel):
    confirm_password: str | None = None


class PackageActionRequest(BaseModel):
    package: str
    confirm_password: str | None = None


class FirewallPortRequest(BaseModel):
    port: int
    protocol: str = "tcp"
    confirm_password: str | None = None


class FirewallAppRequest(BaseModel):
    profile: str
    confirm_password: str | None = None


class HostnameRequest(BaseModel):
    hostname: str
    confirm_password: str | None = None


class NetplanWriteRequest(BaseModel):
    files: dict[str, str]
    confirm_password: str | None = None


class FileWriteRequest(BaseModel):
    path: str
    content: str
    create_backup: bool = True
    confirm_password: str | None = None


class FileDeleteRequest(BaseModel):
    path: str
    confirm_password: str | None = None


class MkdirRequest(BaseModel):
    path: str
    confirm_password: str | None = None


class UserCreateRequest(BaseModel):
    username: str
    shell: str = "/bin/bash"
    home: str | None = None
    sudo: bool = False
    password: str | None = None
    confirm_password: str | None = None


class UserActionRequest(BaseModel):
    username: str
    confirm_password: str | None = None


class ResetPasswordRequest(BaseModel):
    username: str
    new_password: str
    confirm_password: str | None = None


class SetSudoRequest(BaseModel):
    username: str
    enabled: bool
    confirm_password: str | None = None


class ProcessKillRequest(BaseModel):
    pid: int
    signal: str = "TERM"
    confirm_password: str | None = None


class TaskCreateRequest(BaseModel):
    name: str
    command: str
    schedule: str = "manual"


class TaskRunRequest(BaseModel):
    id: int
    confirm_password: str | None = None


class TaskDeleteRequest(BaseModel):
    id: int
    confirm_password: str | None = None


class SettingsUpdateRequest(BaseModel):
    server_port: int = 2511
    bind_address: str = "0.0.0.0"
    session_timeout_minutes: int = 30
    allow_terminal: bool = False
    docker_enabled: bool = True
    require_reauth_for_dangerous_actions: bool = True
    admin_email: str = ""
    monitoring_enabled: bool = True
    auto_update_enabled: bool = False
    confirm_password: str | None = None


class TerminalExecRequest(BaseModel):
    command: str
    confirm_password: str | None = None


class TerminalExecResponse(BaseModel):
    command: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int


class FileInfo(BaseModel):
    path: str
    type: str
    size: int
    owner: str | None = None
    group: str | None = None
    permissions: str
    modified_at: datetime | None = None


class GenericRecord(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class AssistantQueryRequest(BaseModel):
    prompt: str
    dry_run: bool = True


class AssistantExecuteRequest(BaseModel):
    prompt: str
    command: str
    confirm_password: str | None = None
    dry_run: bool = False


class IncidentRemediateRequest(BaseModel):
    confirm_password: str | None = None
    dry_run: bool = True


class DeploymentConfigRequest(BaseModel):
    app_name: str
    path: str
    repo_url: str = ""
    branch: str = "main"
    runtime: str = "auto"
    install_command: str = ""
    build_command: str = ""
    restart_command: str = ""
    service_name: str = ""
    port: int | None = None
    confirm_password: str | None = None


class DeploymentRunRequest(BaseModel):
    app_id: int
    confirm_password: str | None = None


class ExposurePreviewRequest(BaseModel):
    app_id: int
    domain: str
    port: int | None = None
    ssl_mode: str = "letsencrypt"
    open_firewall: bool = False
    confirm_password: str | None = None


class ExposureRemoveRequest(BaseModel):
    app_id: int
    confirm_password: str | None = None


class IntegrationUpsertRequest(BaseModel):
    name: str
    kind: str
    target_url: str
    enabled: bool = True
    events: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    confirm_password: str | None = None


class MemorySaveRequest(BaseModel):
    key: str
    scope: str = "server"
    value: dict[str, Any] = Field(default_factory=dict)


class CommandExplainRequest(BaseModel):
    command: str
