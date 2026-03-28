from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import IntegrationEndpoint


logger = logging.getLogger(__name__)


def _json_load(value: str, default: Any) -> Any:
    try:
        return json.loads(value or "")
    except json.JSONDecodeError:
        return default


def serialize_endpoint(endpoint: IntegrationEndpoint) -> dict[str, Any]:
    return {
        "id": endpoint.id,
        "name": endpoint.name,
        "kind": endpoint.kind,
        "target_url": endpoint.target_url,
        "enabled": endpoint.enabled,
        "events": _json_load(endpoint.events_json, []),
        "headers": _json_load(endpoint.headers_json, {}),
        "updated_at": endpoint.updated_at.isoformat() if endpoint.updated_at else None,
    }


def upsert_endpoint(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    endpoint = db.scalar(select(IntegrationEndpoint).where(IntegrationEndpoint.name == payload["name"]))
    if endpoint is None:
        endpoint = IntegrationEndpoint(name=payload["name"], kind=payload["kind"], target_url=payload["target_url"])
        db.add(endpoint)
    endpoint.kind = payload["kind"]
    endpoint.target_url = payload["target_url"]
    endpoint.enabled = bool(payload.get("enabled", True))
    endpoint.events_json = json.dumps(payload.get("events", []), sort_keys=True)
    endpoint.headers_json = json.dumps(payload.get("headers", {}), sort_keys=True)
    db.commit()
    db.refresh(endpoint)
    return serialize_endpoint(endpoint)


def list_endpoints(db: Session) -> list[dict[str, Any]]:
    items = db.scalars(select(IntegrationEndpoint).order_by(IntegrationEndpoint.kind.asc(), IntegrationEndpoint.name.asc())).all()
    return [serialize_endpoint(item) for item in items]


def dispatch_event(db: Session, event: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    endpoints = db.scalars(select(IntegrationEndpoint).where(IntegrationEndpoint.enabled.is_(True))).all()
    deliveries: list[dict[str, Any]] = []
    for endpoint in endpoints:
        events = _json_load(endpoint.events_json, [])
        if events and event not in events and "*" not in events:
            continue
        headers = _json_load(endpoint.headers_json, {})
        try:
            with httpx.Client(timeout=8) as client:
                if endpoint.kind == "discord":
                    body = {
                        "content": f"[Igris] {event}",
                        "embeds": [
                            {
                                "title": payload.get("title", event),
                                "description": payload.get("message", ""),
                                "color": 15158332 if payload.get("severity") == "critical" else 3447003,
                                "fields": [{"name": key, "value": str(value), "inline": False} for key, value in payload.items() if key not in {"title", "message"}][:6],
                            }
                        ],
                    }
                    response = client.post(endpoint.target_url, json=body, headers=headers)
                else:
                    response = client.post(endpoint.target_url, json={"event": event, "payload": payload}, headers=headers)
                deliveries.append({"name": endpoint.name, "status": response.status_code})
                response.raise_for_status()
        except Exception as exc:
            logger.warning("Integration delivery failed for %s: %s", endpoint.name, exc)
            deliveries.append({"name": endpoint.name, "status": "failed", "error": str(exc)})
    return deliveries
