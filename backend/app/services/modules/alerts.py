from __future__ import annotations

from datetime import datetime, timedelta

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


def find_recent_alert(db: Session, *, source: str, message: str, within_minutes: int = 60) -> AlertRecord | None:
    cutoff = datetime.utcnow() - timedelta(minutes=within_minutes)
    stmt = (
        select(AlertRecord)
        .where(AlertRecord.source == source, AlertRecord.message == message, AlertRecord.created_at >= cutoff)
        .order_by(AlertRecord.created_at.desc())
        .limit(1)
    )
    return db.scalar(stmt)


def create_alert_once(
    db: Session,
    *,
    level: str,
    message: str,
    source: str = "system",
    within_minutes: int = 60,
) -> AlertRecord | None:
    existing = find_recent_alert(db, source=source, message=message, within_minutes=within_minutes)
    if existing:
        return None
    return create_alert(db, level=level, message=message, source=source)


def resolve_alert(db: Session, alert_id: int) -> AlertRecord:
    alert = db.get(AlertRecord, alert_id)
    if not alert:
        raise ValueError("Alert not found")
    alert.resolved = True
    db.commit()
    db.refresh(alert)
    return alert


def clear_resolved_alerts(db: Session) -> int:
    resolved_alerts = list(db.scalars(select(AlertRecord).where(AlertRecord.resolved.is_(True))).all())
    count = len(resolved_alerts)
    for alert in resolved_alerts:
        db.delete(alert)
    db.commit()
    return count

