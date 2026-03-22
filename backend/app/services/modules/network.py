from __future__ import annotations

import re
import socket
from pathlib import Path

import psutil

from backend.app.services.command import run_command


NETPLAN_PATH = Path("/etc/netplan")
HOSTNAME_RE = re.compile(r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$")


def get_interfaces() -> dict:
    interfaces = {}
    for name, addrs in psutil.net_if_addrs().items():
        interfaces[name] = [{"family": str(addr.family), "address": addr.address, "netmask": addr.netmask} for addr in addrs]
    return interfaces


def get_routes() -> list[str]:
    return [line for line in run_command(["ip", "route"], timeout=10).stdout.splitlines() if line.strip()]


def get_ports() -> list[str]:
    return [line for line in run_command(["ss", "-tulpn"], timeout=10).stdout.splitlines() if line.strip()]


def get_dns() -> dict:
    resolv = Path("/etc/resolv.conf").read_text(encoding="utf-8") if Path("/etc/resolv.conf").exists() else ""
    return {"hostname": socket.gethostname(), "resolv_conf": resolv}


def set_hostname(hostname: str) -> None:
    if not HOSTNAME_RE.fullmatch(hostname):
        raise ValueError("Invalid hostname")
    run_command(["hostnamectl", "set-hostname", hostname], timeout=20).ensure_success("Unable to update hostname")


def read_netplan() -> dict:
    files = {}
    for item in NETPLAN_PATH.glob("*.yaml"):
        files[str(item)] = item.read_text(encoding="utf-8")
    for item in NETPLAN_PATH.glob("*.yml"):
        files[str(item)] = item.read_text(encoding="utf-8")
    return files


def write_netplan(contents: dict[str, str]) -> None:
    for path_str, content in contents.items():
        target = Path(path_str).resolve(strict=False)
        if NETPLAN_PATH.resolve() not in target.parents:
            raise PermissionError(f"Netplan target must stay under {NETPLAN_PATH}")
        if target.suffix not in {".yaml", ".yml"}:
            raise ValueError("Netplan file must end with .yaml or .yml")
        backup = target.with_suffix(target.suffix + ".bak")
        if target.exists():
            backup.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
        target.write_text(content, encoding="utf-8")
    run_command(["netplan", "generate"], timeout=30).ensure_success("Netplan validation failed")
