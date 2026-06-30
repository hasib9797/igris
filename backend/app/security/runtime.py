from __future__ import annotations

import json
import ipaddress
import re
import time
from collections.abc import Iterable
from pathlib import Path

from fastapi import Request

from backend.app.config import AppConfig


_DANGEROUS_TERMINAL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(^|\s)rm\s+-rf\s+/(?:\s|$)"), "Refusing recursive deletion of the filesystem root."),
    (re.compile(r"(^|\s)mkfs(\.[a-z0-9]+)?\s", re.IGNORECASE), "Refusing filesystem formatting command."),
    (re.compile(r"(^|\s)(shutdown|reboot|poweroff|halt)(\s|$)"), "Refusing host power control from the dashboard console."),
    (re.compile(r"(^|\s)dd\s+.*of=/dev/", re.IGNORECASE), "Refusing direct block-device overwrite command."),
    (re.compile(r":\(\)\s*\{"), "Refusing shell fork bomb pattern."),
]


def _login_state_path(config: AppConfig) -> Path:
    return config.data_dir / "security" / "login-failures.json"


def _load_login_failures(config: AppConfig) -> dict[str, dict[str, float]]:
    path = _login_state_path(config)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    cleaned: dict[str, dict[str, float]] = {}
    for ip, details in payload.items():
        if not isinstance(ip, str) or not isinstance(details, dict):
            continue
        cleaned[ip] = {
            "count": float(details.get("count", 0)),
            "last_failure": float(details.get("last_failure", 0.0)),
        }
    return cleaned


def _save_login_failures(config: AppConfig, payload: dict[str, dict[str, float]]) -> None:
    path = _login_state_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def client_ip_from_request(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


def ip_allowed(ip: str, trusted_subnets: Iterable[str]) -> bool:
    networks = [item for item in trusted_subnets if str(item).strip()]
    if not networks:
        return True
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for item in networks:
        try:
            if address in ipaddress.ip_network(item, strict=False):
                return True
        except ValueError:
            continue
    return False


def login_is_blocked(ip: str, config: AppConfig) -> tuple[bool, int]:
    failures = _load_login_failures(config)
    attempts = failures.get(ip)
    if not attempts:
        return False, 0
    last_failure = attempts.get("last_failure", 0.0)
    count = int(attempts.get("count", 0))
    window = max(1, config.security.login_lockout_minutes) * 60
    if count < max(1, config.security.login_max_attempts):
        return False, 0
    elapsed = time.time() - last_failure
    if elapsed >= window:
        failures.pop(ip, None)
        _save_login_failures(config, failures)
        return False, 0
    remaining = max(1, int(window - elapsed))
    return True, remaining


def register_login_failure(ip: str, config: AppConfig) -> int:
    failures = _load_login_failures(config)
    state = failures.setdefault(ip, {"count": 0.0, "last_failure": 0.0})
    state["count"] = int(state.get("count", 0)) + 1
    state["last_failure"] = time.time()
    _save_login_failures(config, failures)
    return int(state["count"])


def clear_login_failures(ip: str, config: AppConfig) -> None:
    failures = _load_login_failures(config)
    if ip in failures:
        failures.pop(ip, None)
        _save_login_failures(config, failures)


def blocked_terminal_reason(command: str, config: AppConfig) -> str | None:
    if not config.security.block_dangerous_terminal_commands:
        return None
    for pattern, reason in _DANGEROUS_TERMINAL_PATTERNS:
        if pattern.search(command):
            return reason
    return None
