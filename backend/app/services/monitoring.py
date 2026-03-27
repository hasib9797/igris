from __future__ import annotations

from dataclasses import dataclass

import psutil

from backend.app.config import AppConfig
from backend.app.services.command import run_command


@dataclass
class MonitorEvent:
    level: str
    message: str
    source: str
    subject: str


def _top_process_summary() -> str:
    processes: list[tuple[float, str, int]] = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent"]):
        try:
            info = proc.info
            processes.append((float(info.get("cpu_percent") or 0), str(info.get("name") or "unknown"), int(info.get("pid") or 0)))
        except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
            continue
    processes.sort(reverse=True)
    if not processes:
        return "No busy process identified."
    cpu, name, pid = processes[0]
    return f"Top process is {name} (PID {pid}) at {cpu:.0f}% CPU."


def build_monitor_summary(config: AppConfig) -> tuple[str, list[MonitorEvent]]:
    psutil.cpu_percent(interval=None)
    cpu_percent = psutil.cpu_percent(interval=0.15)
    memory_percent = psutil.virtual_memory().percent
    disk_percent = psutil.disk_usage("/").percent
    failed_services = run_command(["systemctl", "--failed", "--no-legend", "--plain"], timeout=10)
    failed_service_lines = [line.strip() for line in failed_services.stdout.splitlines() if line.strip()]
    events: list[MonitorEvent] = []
    findings: list[str] = []

    if cpu_percent >= config.monitoring.cpu_threshold_percent:
        findings.append(f"CPU is elevated at {cpu_percent:.0f}%")
        events.append(
            MonitorEvent(
                level="warning",
                message=f"AI monitor: CPU usage is {cpu_percent:.0f}% and may require attention. {_top_process_summary()}",
                source="ai-monitor",
                subject="Igris alert: high CPU usage",
            )
        )
    if memory_percent >= config.monitoring.memory_threshold_percent:
        findings.append(f"Memory is elevated at {memory_percent:.0f}%")
        events.append(
            MonitorEvent(
                level="warning",
                message=f"AI monitor: memory usage is {memory_percent:.0f}%. Review running services and recent deployments.",
                source="ai-monitor",
                subject="Igris alert: high memory usage",
            )
        )
    if disk_percent >= config.monitoring.disk_threshold_percent:
        findings.append(f"Disk usage reached {disk_percent:.0f}%")
        events.append(
            MonitorEvent(
                level="critical" if disk_percent >= 95 else "warning",
                message=f"AI monitor: root filesystem usage is {disk_percent:.0f}%. Clean logs, caches, or unused packages before writes fail.",
                source="ai-monitor",
                subject="Igris alert: low disk space",
            )
        )
    if failed_service_lines:
        findings.append(f"{len(failed_service_lines)} systemd service(s) are failed")
        sample = failed_service_lines[0]
        events.append(
            MonitorEvent(
                level="critical",
                message=f"AI monitor: detected failed systemd services. First failed unit: {sample}",
                source="ai-monitor",
                subject="Igris alert: failed services detected",
            )
        )

    if findings:
        summary = "AI monitor detected: " + "; ".join(findings) + "."
    else:
        summary = "AI monitor sees healthy CPU, memory, disk, and service status."
    return summary, events
