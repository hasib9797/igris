from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.services import applications, incidents
from backend.app.services.memory import list_memory
from backend.app.services.modules import firewall as firewall_service
from backend.app.services.modules import network as network_service
from backend.app.services.overview import get_system_overview


def explain_server(db: Session) -> dict:
    overview = get_system_overview()
    apps = applications.list_apps(db)
    incident_items = incidents.list_incidents(db)
    open_ports = network_service.get_ports()
    firewall = firewall_service.ufw_status()
    public_apps = [app for app in apps if app.get("exposure_status") == "public"]
    recommendations: list[str] = []
    if incident_items:
        recommendations.append(f"There are {len([item for item in incident_items if item['status'] == 'open'])} open incidents worth reviewing first.")
    if overview["pending_updates"]:
        recommendations.append(f"{len(overview['pending_updates'])} package updates are available.")
    if not public_apps:
        recommendations.append("No detected application is exposed publicly from Igris yet.")
    return {
        "summary": f"{overview['hostname']} is running {len(apps)} detected app(s), {len(open_ports)} open port entries, and {len(public_apps)} public exposure(s).",
        "overview": overview,
        "applications": apps,
        "incidents": incident_items,
        "open_ports": open_ports,
        "firewall": firewall,
        "memory": list_memory(db),
        "recommendations": recommendations,
    }


def scan_and_fix(db: Session, dry_run: bool = True) -> dict:
    incident_items = incidents.scan_incidents(db)
    suggested = []
    for item in incident_items:
        if item["status"] != "open":
            continue
        suggested.append(
            {
                "incident_id": item["id"],
                "severity": item["severity"],
                "title": item["title"],
                "suggested_fix": item["suggested_fix"],
            }
        )
    return {"dry_run": dry_run, "issues": suggested, "count": len(suggested)}
