from __future__ import annotations

import os
import secrets
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


def _default_config_path() -> Path:
    return Path(os.environ.get("IGRIS_CONFIG_PATH", "/etc/igris/config.yaml"))


def _default_data_dir() -> Path:
    return Path(os.environ.get("IGRIS_DATA_DIR", "/var/lib/igris"))


def _default_audit_log() -> Path:
    return Path(os.environ.get("IGRIS_AUDIT_LOG_PATH", "/var/log/igris/audit.log"))


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 2511
    https_enabled: bool = False


@dataclass
class AuthConfig:
    admin_username: str = "admin"
    password_hash: str = ""
    session_secret: str = ""
    session_timeout_minutes: int = 30
    admin_email: str = ""


@dataclass
class SystemConfig:
    managed_user: str = "ubuntu"
    allow_terminal: bool = False
    allow_package_install: bool = True
    allow_user_management: bool = True
    allow_network_management: bool = True
    allow_service_management: bool = True


@dataclass
class ModulesConfig:
    docker: bool = True
    alerts: bool = True
    tasks: bool = True
    files: bool = True


@dataclass
class SecurityConfig:
    trusted_subnets: list[str] = field(default_factory=list)
    require_reauth_for_dangerous_actions: bool = True
    audit_log_enabled: bool = True


@dataclass
class EmailConfig:
    enabled: bool = True
    recipient: str = ""


@dataclass
class MonitoringConfig:
    enabled: bool = True
    interval_seconds: int = 300
    cpu_threshold_percent: int = 85
    memory_threshold_percent: int = 90
    disk_threshold_percent: int = 90


@dataclass
class UpdatesConfig:
    enabled: bool = True
    auto_update: bool = False
    check_interval_seconds: int = 1800
    repo_url: str = "https://github.com/hasib9797/igris"
    branch: str = "main"


@dataclass
class AppConfig:
    server: ServerConfig = field(default_factory=ServerConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    system: SystemConfig = field(default_factory=SystemConfig)
    modules: ModulesConfig = field(default_factory=ModulesConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    updates: UpdatesConfig = field(default_factory=UpdatesConfig)
    config_path: Path = field(default_factory=_default_config_path)
    data_dir: Path = field(default_factory=_default_data_dir)
    audit_log_path: str = field(default_factory=lambda: str(_default_audit_log()))

    @property
    def resolved_database_url(self) -> str:
        database_path = self.data_dir / "database.db"
        return f"sqlite:///{database_path}"


_config_cache: AppConfig | None = None


def _merge_dataclass(instance: Any, values: dict[str, Any] | None) -> Any:
    if not values:
        return instance
    for key, value in values.items():
        if hasattr(instance, key):
            setattr(instance, key, value)
    return instance


def load_config(path: str | Path | None = None) -> AppConfig:
    config_path = Path(path or _default_config_path())
    config = AppConfig(config_path=config_path)
    config.data_dir = _default_data_dir()
    config.audit_log_path = str(_default_audit_log())
    if config_path.exists():
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        _merge_dataclass(config.server, payload.get("server"))
        _merge_dataclass(config.auth, payload.get("auth"))
        _merge_dataclass(config.system, payload.get("system"))
        _merge_dataclass(config.modules, payload.get("modules"))
        _merge_dataclass(config.security, payload.get("security"))
        _merge_dataclass(config.email, payload.get("email"))
        _merge_dataclass(config.monitoring, payload.get("monitoring"))
        _merge_dataclass(config.updates, payload.get("updates"))
    if not config.auth.session_secret:
        config.auth.session_secret = secrets.token_urlsafe(32)
    return config


def save_config(config: AppConfig, path: str | Path | None = None) -> None:
    config_path = Path(path or config.config_path or _default_config_path())
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "server": asdict(config.server),
        "auth": asdict(config.auth),
        "system": asdict(config.system),
        "modules": asdict(config.modules),
        "security": asdict(config.security),
        "email": asdict(config.email),
        "monitoring": asdict(config.monitoring),
        "updates": asdict(config.updates),
    }
    config_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def get_config() -> AppConfig:
    global _config_cache
    if _config_cache is None:
        _config_cache = load_config()
    return _config_cache


def clear_config_cache() -> None:
    global _config_cache
    _config_cache = None
