from __future__ import annotations

import os
import signal
import time

import psutil


def list_processes(search: str | None = None) -> list[dict]:
    processes = list(psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent", "status"]))
    for proc in processes:
        try:
            proc.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    time.sleep(0.15)
    processes = []
    for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent", "status"]):
        try:
            info = proc.as_dict(attrs=["pid", "name", "username", "cpu_percent", "memory_percent", "status"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if search and search.lower() not in (info.get("name") or "").lower():
            continue
        processes.append(info)
    return sorted(processes, key=lambda item: item.get("cpu_percent", 0), reverse=True)[:200]


def kill_process(pid: int, sig: str) -> None:
    signum = signal.SIGKILL if sig.upper() == "KILL" else signal.SIGTERM
    os.kill(pid, signum)
