from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psutil

from backend.app.config import AppConfig
from backend.app.services.command import run_command
from backend.app.services.modules.services import list_failed_services


@dataclass
class MonitorEvent:
    level: str
    message: str
    source: str
    subject: str
    fingerprint: str | None = None
    max_per_session: int = 3
    once_key: str | None = None
    audit_action: str | None = None
    audit_target: str = ""
    audit_details: dict[str, Any] | None = None


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
    failed_services = list_failed_services(include_deleted=True)
    active_failed_services = [item for item in failed_services if not item.deleted]
    deleted_failed_services = [item for item in failed_services if item.deleted]
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
                fingerprint="monitor:high-cpu",
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
                fingerprint="monitor:high-memory",
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
                fingerprint="monitor:high-disk",
            )
        )
    if active_failed_services:
        findings.append(f"{len(active_failed_services)} systemd service(s) are failed")
        sample = active_failed_services[0].status_line
        events.append(
            MonitorEvent(
                level="critical",
                message=f"AI monitor: detected failed systemd services. First failed unit: {sample}",
                source="ai-monitor",
                subject="Igris alert: failed services detected",
                fingerprint="monitor:failed-services:" + ",".join(sorted(item.name for item in active_failed_services)),
            )
        )
    if deleted_failed_services:
        findings.append(f"{len(deleted_failed_services)} deleted service unit(s) are still listed in systemd failed state")
        for item in deleted_failed_services:
            events.append(
                MonitorEvent(
                    level="info",
                    message=f"AI monitor: {item.name} was removed from the server but is still listed by systemd as failed. Igris recorded it once and will suppress repeat alerts for this deleted unit.",
                    source="ai-monitor",
                    subject="Igris notice: deleted service recorded",
                    fingerprint=f"monitor:deleted-service:{item.name}",
                    max_per_session=1,
                    once_key=f"deleted-service:{item.name}",
                    audit_action="service.deleted_unit_detected",
                    audit_target=item.name,
                    audit_details={
                        "status_line": item.status_line,
                        "load_state": item.load_state,
                        "active_state": item.active_state,
                        "sub_state": item.sub_state,
                        "unit_file_state": item.unit_file_state,
                    },
                )
            )

    if findings:
        summary = "AI monitor detected: " + "; ".join(findings) + "."
    else:
        summary = "AI monitor sees healthy CPU, memory, disk, and service status."
    return summary, events
