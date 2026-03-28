from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.models import AdminUser
from backend.app.schemas.common import (
    ActionRequest,
    AssistantExecuteRequest,
    AssistantQueryRequest,
    CommandExplainRequest,
    DeploymentConfigRequest,
    DeploymentRunRequest,
    ExposurePreviewRequest,
    ExposureRemoveRequest,
    IncidentRemediateRequest,
    IntegrationUpsertRequest,
    MemorySaveRequest,
    MessageResponse,
)
from backend.app.services import applications as application_service
from backend.app.services import assistant as assistant_service
from backend.app.services import deployments as deployment_service
from backend.app.services import explain as explain_service
from backend.app.services import incidents as incident_service
from backend.app.services import integrations as integration_service
from backend.app.services import memory as memory_service
from backend.app.services import plugins as plugin_service
from backend.app.services import system_map as system_map_service
from backend.app.utils.audit import log_audit
from backend.app.db.session import get_db
from backend.app.services.authz import verify_reauth


router = APIRouter(prefix="/api/premium")


def _dangerous(db: Session, actor: str, password: str | None, action: str, target: str = "") -> None:
    verify_reauth(db, actor, password)
    log_audit(db, actor=actor, action=action, target=target)


@router.get("/assistant/context")
def assistant_context(_: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return assistant_service.build_server_context(db)


@router.get("/assistant/history")
def assistant_history(_: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return assistant_service.list_history(db)


@router.post("/assistant/query")
def assistant_query(payload: AssistantQueryRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    response = assistant_service.ask_assistant(db, payload.prompt, dry_run=payload.dry_run)
    log_audit(db, actor=user.username, action="assistant.query", target=payload.prompt[:120], details={"dry_run": payload.dry_run})
    return response


@router.post("/assistant/execute")
def assistant_execute(payload: AssistantExecuteRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _dangerous(db, user.username, payload.confirm_password, "assistant.execute", payload.command)
    response = assistant_service.execute_assistant_command(db, payload.prompt, payload.command, dry_run=payload.dry_run)
    log_audit(db, actor=user.username, action="assistant.action", target=payload.command, details={"dry_run": payload.dry_run})
    return response


@router.post("/terminal/explain")
def terminal_explain(payload: CommandExplainRequest, _: AdminUser = Depends(get_current_user)) -> dict:
    return assistant_service.explain_command(payload.command)


@router.get("/applications")
def applications(_: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return application_service.list_apps(db)


@router.post("/applications/refresh")
def refresh_applications(user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    apps = application_service.refresh_inventory(db)
    log_audit(db, actor=user.username, action="applications.refresh", target=str(len(apps)))
    return apps


@router.get("/incidents")
def incidents(_: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return incident_service.list_incidents(db)


@router.post("/incidents/scan")
def scan_incidents(user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    items = incident_service.scan_incidents(db)
    log_audit(db, actor=user.username, action="incidents.scan", target=str(len(items)))
    return items


@router.post("/incidents/{incident_id}/remediate")
def remediate_incident(incident_id: int, payload: IncidentRemediateRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if not payload.dry_run:
        _dangerous(db, user.username, payload.confirm_password, "incidents.remediate", str(incident_id))
    response = incident_service.remediate_incident(db, incident_id, dry_run=payload.dry_run)
    log_audit(db, actor=user.username, action="incidents.remediate.preview" if payload.dry_run else "incidents.remediate", target=str(incident_id))
    return response


@router.get("/explain")
def explain_server(_: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return explain_service.explain_server(db)


@router.post("/scan-fix")
def scan_fix(_: ActionRequest | None = None, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    response = explain_service.scan_and_fix(db, dry_run=True)
    log_audit(db, actor=user.username, action="scan-fix.run", target=str(response["count"]))
    return response


@router.get("/system-map")
def system_map(_: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return system_map_service.build_system_map(db)


@router.get("/deployments")
def deployments(_: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return deployment_service.list_deployments(db)


@router.post("/deployments/configure")
def configure_deployment(payload: DeploymentConfigRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _dangerous(db, user.username, payload.confirm_password, "deployments.configure", payload.path)
    response = deployment_service.save_deployment_config(db, payload.model_dump(exclude={"confirm_password"}))
    log_audit(db, actor=user.username, action="deployments.configure", target=payload.path)
    return response


@router.post("/deployments/run")
def run_deployment(payload: DeploymentRunRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _dangerous(db, user.username, payload.confirm_password, "deployments.run", str(payload.app_id))
    response = deployment_service.run_deployment(db, payload.app_id)
    integration_service.dispatch_event(db, f"deployment.{response['status']}", {"title": "Deployment finished", "message": f"Deployment for app #{payload.app_id} ended with status {response['status']}.", "severity": "critical" if response["status"] == "failed" else "info"})
    return response


@router.post("/exposure/preview")
def exposure_preview(payload: ExposurePreviewRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    log_audit(db, actor=user.username, action="exposure.preview", target=payload.domain)
    return deployment_service.build_exposure_preview(db, payload.app_id, payload.domain, payload.port, payload.ssl_mode, payload.open_firewall)


@router.post("/exposure/apply")
def exposure_apply(payload: ExposurePreviewRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _dangerous(db, user.username, payload.confirm_password, "exposure.apply", payload.domain)
    response = deployment_service.apply_exposure(db, payload.app_id, payload.domain, payload.port, payload.ssl_mode, payload.open_firewall)
    integration_service.dispatch_event(db, "exposure.applied", {"title": "Public exposure applied", "message": f"{response['app_name']} is now exposed on {response['domain']}.", "severity": "info"})
    return response


@router.post("/exposure/remove")
def exposure_remove(payload: ExposureRemoveRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _dangerous(db, user.username, payload.confirm_password, "exposure.remove", str(payload.app_id))
    response = deployment_service.remove_exposure(db, payload.app_id)
    integration_service.dispatch_event(db, "exposure.removed", {"title": "Public exposure removed", "message": response.get("domain", "domain removed"), "severity": "info"})
    return response


@router.get("/integrations")
def integrations(_: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return integration_service.list_endpoints(db)


@router.post("/integrations")
def save_integration(payload: IntegrationUpsertRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _dangerous(db, user.username, payload.confirm_password, "integrations.save", payload.name)
    response = integration_service.upsert_endpoint(db, payload.model_dump(exclude={"confirm_password"}))
    log_audit(db, actor=user.username, action="integrations.save", target=payload.name)
    return response


@router.get("/memory")
def list_memory(_: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return memory_service.list_memory(db)


@router.post("/memory")
def save_memory(payload: MemorySaveRequest, user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> MessageResponse:
    memory_service.remember(db, payload.key, payload.value, payload.scope)
    log_audit(db, actor=user.username, action="memory.save", target=payload.key)
    return MessageResponse(message=f"Saved memory key {payload.key}")


@router.get("/plugins")
def plugins(_: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return plugin_service.list_plugins(db)


@router.post("/plugins/refresh")
def refresh_plugins(user: AdminUser = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    items = plugin_service.refresh_plugins(db)
    log_audit(db, actor=user.username, action="plugins.refresh", target=str(len(items)))
    return items
