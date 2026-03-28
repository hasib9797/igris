from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import MemoryRecord


def remember(db: Session, key: str, value: dict[str, Any], scope: str = "server") -> MemoryRecord:
    record = db.scalar(select(MemoryRecord).where(MemoryRecord.key == key))
    payload = json.dumps(value, sort_keys=True)
    if record is None:
        record = MemoryRecord(key=key, scope=scope, value_json=payload, updated_at=datetime.utcnow())
        db.add(record)
    else:
        record.scope = scope
        record.value_json = payload
        record.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(record)
    return record


def recall(db: Session, key: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
    record = db.scalar(select(MemoryRecord).where(MemoryRecord.key == key))
    if record is None:
        return default or {}
    try:
        return json.loads(record.value_json or "{}")
    except json.JSONDecodeError:
        return default or {}


def list_memory(db: Session) -> list[dict[str, Any]]:
    records = db.scalars(select(MemoryRecord).order_by(MemoryRecord.key.asc())).all()
    items: list[dict[str, Any]] = []
    for record in records:
        try:
            value = json.loads(record.value_json or "{}")
        except json.JSONDecodeError:
            value = {}
        items.append(
            {
                "id": record.id,
                "key": record.key,
                "scope": record.scope,
                "value": value,
                "updated_at": record.updated_at.isoformat() if record.updated_at else None,
            }
        )
    return items
