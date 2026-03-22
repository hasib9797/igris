from __future__ import annotations

import os
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


DEFAULT_CONFIG_DIR = Path("/etc/igris")
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.yaml"
LEGACY_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.yml"
DEFAULT_DATA_DIR = Path("/var/lib/igris")
DEFAULT_AUDIT_LOG = DEFAULT_DATA_DIR / "audit.log"


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 2511
    https_enabled: bool = False


class AuthConfig(BaseModel):
    admin_username: str = "admin"
    password_hash: str = ""
    session_secret: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    session_timeout_minutes: int = 30


class SystemConfig(BaseModel):
    managed_user: str = "ubuntu"
    allow_terminal: bool = False
    allow_package_install: bool = True
    allow_user_management: bool = True
    allow_network_management: bool = True
    allow_service_management: bool = True


class ModuleConfig(BaseModel):
    docker: bool = True
    alerts: bool = True
    tasks: bool = True
    files: bool = True


class SecurityConfig(BaseModel):
    trusted_subnets: list[str] = Field(default_factory=list)
    require_reauth_for_dangerous_actions: bool = True
    audit_log_enabled: bool = True


class AppConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    system: SystemConfig = Field(default_factory=SystemConfig)
    modules: ModuleConfig = Field(default_factory=ModuleConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    data_dir: str = str(DEFAULT_DATA_DIR)
    audit_log_path: str = str(DEFAULT_AUDIT_LOG)
    database_url: str | None = None

    @property
    def resolved_data_dir(self) -> Path:
        return Path(self.data_dir)

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.resolved_data_dir / 'database.db'}"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _resolve_default_config_path() -> Path:
    configured = os.environ.get("IGRIS_CONFIG_PATH")
    if configured:
        return Path(configured)
    if DEFAULT_CONFIG_PATH.exists():
        return DEFAULT_CONFIG_PATH
    if LEGACY_CONFIG_PATH.exists():
        return LEGACY_CONFIG_PATH
    return DEFAULT_CONFIG_PATH


def default_config_dict() -> dict[str, Any]:
    return AppConfig().model_dump()


def clear_config_cache() -> None:
    get_config.cache_clear()


def load_config(config_path: str | Path | None = None) -> AppConfig:
    target = Path(config_path) if config_path else _resolve_default_config_path()
    data_dir_override = os.environ.get("IGRIS_DATA_DIR")
    if not target.exists():
        config = AppConfig()
    else:
        data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
        merged = _deep_merge(default_config_dict(), data)
        config = AppConfig.model_validate(merged)
    if data_dir_override:
        config.data_dir = data_dir_override
        config.audit_log_path = str(Path(data_dir_override) / "audit.log")
    config.resolved_data_dir.mkdir(parents=True, exist_ok=True)
    Path(config.audit_log_path).parent.mkdir(parents=True, exist_ok=True)
    return config


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return load_config()


def save_config(config: AppConfig, config_path: str | Path | None = None) -> Path:
    target = Path(config_path) if config_path else _resolve_default_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(config.model_dump(), sort_keys=False), encoding="utf-8")
    clear_config_cache()
    return target
