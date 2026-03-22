from __future__ import annotations

import os
import signal

import psutil


def list_processes(search: str | None = None) -> list[dict]:
    processes = []
    for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent", "status"]):
        info = proc.info
        if search and search.lower() not in (info.get("name") or "").lower():
            continue
        processes.append(info)
    return sorted(processes, key=lambda item: item.get("cpu_percent", 0), reverse=True)[:200]


def kill_process(pid: int, sig: str) -> None:
    signum = signal.SIGKILL if sig.upper() == "KILL" else signal.SIGTERM
    os.kill(pid, signum)
