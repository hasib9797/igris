from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import AlertRecord


def list_alerts(db: Session) -> list[AlertRecord]:
    return list(db.scalars(select(AlertRecord).order_by(AlertRecord.created_at.desc()).limit(100)).all())


def create_alert(db: Session, level: str, message: str, source: str = "manual") -> AlertRecord:
    alert = AlertRecord(level=level, message=message, source=source)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert

