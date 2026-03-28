from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.services import applications, deployments, explain


def build_system_map(db: Session) -> dict:
    apps = applications.list_apps(db)
    deployment_items = deployments.list_deployments(db)
    explained = explain.explain_server(db)
    nodes = []
    edges = []
    nodes.append({"id": "server", "label": explained["overview"]["hostname"], "kind": "server"})
    for app in apps:
        app_id = f"app:{app['id']}"
        nodes.append({"id": app_id, "label": app["name"], "kind": "application", "status": app["status"], "path": app["path"]})
        edges.append({"from": "server", "to": app_id, "label": app["app_type"]})
        for port in app.get("ports", []):
            port_id = f"port:{app['id']}:{port}"
            nodes.append({"id": port_id, "label": str(port), "kind": "port"})
            edges.append({"from": app_id, "to": port_id, "label": "listens"})
        if app.get("public_domain"):
            domain_id = f"domain:{app['public_domain']}"
            nodes.append({"id": domain_id, "label": app["public_domain"], "kind": "domain"})
            edges.append({"from": domain_id, "to": app_id, "label": "routes to"})
    for deployment in deployment_items[:20]:
        deployment_id = f"deploy:{deployment['id']}"
        nodes.append({"id": deployment_id, "label": deployment["app_name"], "kind": "deployment", "status": deployment["status"]})
        matching = next((app for app in apps if app["name"] == deployment["app_name"]), None)
        if matching:
            edges.append({"from": deployment_id, "to": f"app:{matching['id']}", "label": deployment["status"]})
    return {"nodes": nodes, "edges": edges, "summary": explained["summary"]}
