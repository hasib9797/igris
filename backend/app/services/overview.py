from __future__ import annotations

import platform
import socket
import time
from pathlib import Path

import httpx
import psutil

from backend.app.services.command import run_command


def _public_ip() -> str | None:
    try:
        with httpx.Client(timeout=2.5) as client:
            response = client.get("https://api.ipify.org")
            response.raise_for_status()
            return response.text.strip()
    except Exception:
        return None


def _os_release() -> str:
    release_file = Path("/etc/os-release")
    if not release_file.exists():
        return platform.platform()
    data = {}
    for line in release_file.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            data[key] = value.strip('"')
    return data.get("PRETTY_NAME", platform.platform())


def get_system_overview() -> dict:
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    boot = psutil.boot_time()
    uptime = int(time.time() - boot)
    psutil.cpu_percent(interval=None)
    processes = list(psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]))
    for proc in processes:
        try:
            proc.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    time.sleep(0.15)
    cpu_usage = psutil.cpu_percent(interval=None)
    top = []
    for proc in processes:
        try:
            info = proc.as_dict(attrs=["pid", "name", "cpu_percent", "memory_percent"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        top.append(info)
    top.sort(key=lambda item: item.get("cpu_percent", 0), reverse=True)
    interfaces = psutil.net_if_addrs()
    local_ips = []
    for _, entries in interfaces.items():
        local_ips.extend([entry.address for entry in entries if "." in entry.address])
    failed_services = run_command(["systemctl", "--failed", "--no-legend", "--plain"], timeout=10)
    updates = run_command(["apt", "list", "--upgradable"], timeout=20)
    return {
        "hostname": socket.gethostname(),
        "os_version": _os_release(),
        "kernel_version": platform.release(),
        "uptime_seconds": uptime,
        "cpu_usage_percent": cpu_usage,
        "ram_usage_percent": vm.percent,
        "disk_usage_percent": disk.percent,
        "network_interfaces": list(interfaces.keys()),
        "local_ip": local_ips[0] if local_ips else None,
        "public_ip": _public_ip(),
        "failed_services": [line.strip() for line in failed_services.stdout.splitlines() if line.strip()][:10],
        "top_processes": top[:5],
        "pending_updates": [line.strip() for line in updates.stdout.splitlines()[1:] if line.strip()][:20],
    }


def get_system_health() -> dict:
    load_avg = getattr(psutil, "getloadavg", lambda: (0.0, 0.0, 0.0))()
    psutil.cpu_percent(interval=None)
    time.sleep(0.1)
    return {
        "status": "ok",
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
        "load_average": load_avg,
    }

