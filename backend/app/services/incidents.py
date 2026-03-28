from __future__ import annotations

import json
from datetime import datetime

import httpx
import psutil
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import get_config
from backend.app.models import DeploymentRecord, IncidentRecord, ManagedApp
from backend.app.services.command import run_command


def _incident_payload(rule_key: str, severity: str, title: str, summary: str, resource_key: str, suggested_fix: str, auto_remediation_enabled: bool = False) -> dict:
    return {
        "rule_key": rule_key,
        "severity": severity,
        "title": title,
        "summary": summary,
        "resource_key": resource_key,
        "suggested_fix": suggested_fix,
        "auto_remediation_enabled": auto_remediation_enabled,
    }


def _upsert_incident(db: Session, payload: dict) -> IncidentRecord:
    incident = db.scalar(
        select(IncidentRecord).where(
            IncidentRecord.rule_key == payload["rule_key"],
            IncidentRecord.resource_key == payload["resource_key"],
            IncidentRecord.status == "open",
        )
    )
    if incident is None:
        incident = IncidentRecord(
            rule_key=payload["rule_key"],
            severity=payload["severity"],
            title=payload["title"],
            summary=payload["summary"],
            resource_key=payload["resource_key"],
            suggested_fix=payload["suggested_fix"],
            auto_remediation_enabled=payload.get("auto_remediation_enabled", False),
        )
        db.add(incident)
    else:
        incident.severity = payload["severity"]
        incident.title = payload["title"]
        incident.summary = payload["summary"]
        incident.suggested_fix = payload["suggested_fix"]
        incident.auto_remediation_enabled = payload.get("auto_remediation_enabled", False)
        incident.updated_at = datetime.utcnow()
    db.flush()
    return incident


def _resolve_missing(db: Session, active_keys: set[tuple[str, str]]) -> None:
    for incident in db.scalars(select(IncidentRecord).where(IncidentRecord.status == "open")).all():
        key = (incident.rule_key, incident.resource_key)
        if key in active_keys:
            continue
        incident.status = "resolved"
        incident.resolved_at = datetime.utcnow()
        incident.updated_at = datetime.utcnow()
    db.commit()


def _service_restart_count(service_name: str) -> int:
    result = run_command(["systemctl", "show", service_name, "--property=NRestarts"], timeout=10)
    for line in result.stdout.splitlines():
        if line.startswith("NRestarts="):
            try:
                return int(line.split("=", 1)[1] or "0")
            except ValueError:
                return 0
    return 0


def scan_incidents(db: Session) -> list[dict]:
    config = get_config()
    if not config.incidents.enabled:
        return list_incidents(db)
    findings: list[dict] = []
    cpu = psutil.cpu_percent(interval=0.2)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    if cpu >= config.monitoring.cpu_threshold_percent:
        findings.append(_incident_payload("high-cpu", "warning", "CPU pressure detected", f"CPU usage is holding at {cpu:.0f}% across the server.", "host:cpu", "Inspect top processes and consider restarting the hottest service."))
    if memory >= config.monitoring.memory_threshold_percent:
        findings.append(_incident_payload("high-memory", "warning", "Memory pressure detected", f"Memory usage is holding at {memory:.0f}%.", "host:memory", "Inspect resident processes and recycle the biggest worker group."))
    if disk >= config.monitoring.disk_threshold_percent:
        findings.append(_incident_payload("high-disk", "critical" if disk >= 95 else "warning", "Disk pressure detected", f"Root disk usage is {disk:.0f}%.", "host:disk", "Purge logs, package caches, or old deployments before writes start failing."))

    failed = run_command(["systemctl", "--failed", "--no-legend", "--plain"], timeout=10)
    for line in [item.strip() for item in failed.stdout.splitlines() if item.strip()]:
        service_name = line.split()[0]
        findings.append(
            _incident_payload(
                "failed-service",
                "critical",
                f"{service_name} is failed",
                f"The systemd unit {service_name} is currently failed or inactive.",
                service_name,
                f"Inspect logs with journalctl -u {service_name} -n 200 and restart the service if the failure is transient.",
                auto_remediation_enabled="failed-service" in config.incidents.auto_remediation_rules,
            )
        )
        restarts = _service_restart_count(service_name)
        if restarts >= 3:
            findings.append(
                _incident_payload(
                    "crash-loop",
                    "critical",
                    f"{service_name} looks unstable",
                    f"{service_name} restarted {restarts} times recently, which suggests a crash loop.",
                    service_name,
                    "Review the last deployment or environment change before forcing another restart.",
                )
            )

    nginx_test = run_command(["/bin/bash", "-lc", "command -v nginx >/dev/null 2>&1 && nginx -t"], timeout=20)
    if nginx_test.returncode != 0 and "not found" not in (nginx_test.stderr or "").lower():
        findings.append(
            _incident_payload(
                "nginx-config",
                "critical",
                "Reverse proxy validation failed",
                nginx_test.stderr.strip() or nginx_test.stdout.strip() or "nginx -t failed",
                "nginx",
                "Fix the generated site config and re-test with nginx -t before reload.",
            )
        )

    deployments = db.scalars(select(DeploymentRecord).order_by(DeploymentRecord.created_at.desc())).all()
    failed_by_app: dict[str, int] = {}
    for item in deployments[:20]:
        if item.status == "failed":
            failed_by_app[item.app_name] = failed_by_app.get(item.app_name, 0) + 1
    for app_name, count in failed_by_app.items():
        if count >= 2:
            findings.append(
                _incident_payload(
                    "deployment-failures",
                    "warning",
                    f"{app_name} deployment is unstable",
                    f"{app_name} has {count} recent failed deployments.",
                    app_name,
                    "Review build logs and restore the last good revision before retrying.",
                )
            )

    for app in db.scalars(select(ManagedApp).where(ManagedApp.exposure_status == "public")).all():
        try:
            ports = json.loads(app.ports_json or "[]")
        except json.JSONDecodeError:
            ports = []
        if not ports:
            continue
        port = ports[0]
        try:
            with httpx.Client(timeout=3, follow_redirects=True) as client:
                response = client.get(f"http://127.0.0.1:{port}")
            if response.status_code >= 500:
                findings.append(
                    _incident_payload(
                        "unreachable-app",
                        "warning",
                        f"{app.name} returned server errors",
                        f"{app.name} is listening on {port} but returned HTTP {response.status_code}.",
                        app.name,
                        "Inspect the app logs and upstream reverse proxy configuration.",
                    )
                )
        except Exception:
            findings.append(
                _incident_payload(
                    "unreachable-app",
                    "warning",
                    f"{app.name} is not answering locally",
                    f"{app.name} should be reachable on port {port} but the health probe failed.",
                    app.name,
                    "Check the process, service unit, and firewall or reverse proxy binding.",
                )
            )

    active_keys: set[tuple[str, str]] = set()
    for payload in findings:
        incident = _upsert_incident(db, payload)
        active_keys.add((incident.rule_key, incident.resource_key))
        if incident.auto_remediation_enabled and incident.rule_key == "failed-service":
            result = run_command(["systemctl", "restart", incident.resource_key], timeout=30)
            incident.action_summary = "Auto-remediation restarted the service." if result.returncode == 0 else result.stderr.strip() or result.stdout.strip()
    db.commit()
    _resolve_missing(db, active_keys)
    return list_incidents(db)


def list_incidents(db: Session) -> list[dict]:
    items = db.scalars(select(IncidentRecord).order_by(IncidentRecord.created_at.desc())).all()
    return [
        {
            "id": item.id,
            "rule_key": item.rule_key,
            "severity": item.severity,
            "title": item.title,
            "summary": item.summary,
            "resource_key": item.resource_key,
            "status": item.status,
            "suggested_fix": item.suggested_fix,
            "auto_remediation_enabled": item.auto_remediation_enabled,
            "action_summary": item.action_summary,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
        }
        for item in items
    ]


def remediate_incident(db: Session, incident_id: int, dry_run: bool = True) -> dict:
    incident = db.scalar(select(IncidentRecord).where(IncidentRecord.id == incident_id))
    if incident is None:
        raise FileNotFoundError(f"Incident {incident_id} was not found")
    commands: list[str]
    if incident.rule_key in {"failed-service", "crash-loop"}:
        commands = [f"systemctl restart {incident.resource_key}", f"journalctl -u {incident.resource_key} -n 120 --no-pager"]
    elif incident.rule_key == "nginx-config":
        commands = ["nginx -t", "systemctl reload nginx"]
    elif incident.rule_key == "high-disk":
        commands = ["journalctl --vacuum-time=7d", "apt autoremove -y", "apt clean"]
    elif incident.rule_key == "high-cpu":
        commands = ["ps -eo pid,pcpu,pmem,cmd --sort=-pcpu | head -n 10"]
    elif incident.rule_key == "high-memory":
        commands = ["ps -eo pid,pcpu,pmem,cmd --sort=-pmem | head -n 10"]
    else:
        commands = [incident.suggested_fix]

    if dry_run:
        return {"status": "dry-run", "commands": commands, "incident": incident.title}

    results = []
    for command in commands:
        result = run_command(["/bin/bash", "-lc", command], timeout=60)
        results.append({"command": command, "stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode})
    incident.action_summary = "\n".join([f"{item['command']} => {item['returncode']}" for item in results])
    incident.updated_at = datetime.utcnow()
    db.commit()
    return {"status": "executed", "results": results}
