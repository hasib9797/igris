from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import get_config
from backend.app.models import AlertRecord
from backend.app.services.updates import load_runtime_state, save_runtime_state


def format_alert_code(alert_id: int) -> str:
    return f"ALT-{alert_id:06d}"


def _boot_session_id() -> str:
    boot_id_path = Path("/proc/sys/kernel/random/boot_id")
    try:
        if boot_id_path.exists():
            boot_id = boot_id_path.read_text(encoding="utf-8").strip()
            if boot_id:
                return boot_id
    except OSError:
        pass
    return "unknown-boot"


def _ensure_runtime_sessions(*, reset_igris_session: bool = False) -> tuple[dict, str]:
    config = get_config()
    state = load_runtime_state(config)
    boot_id = _boot_session_id()
    if reset_igris_session or not state.get("igris_session_id"):
        state["igris_session_id"] = uuid.uuid4().hex
    if state.get("host_boot_id") != boot_id:
        state["host_boot_id"] = boot_id
        state.pop("alert_delivery", None)
    session_key = f"{boot_id}:{state['igris_session_id']}"
    if state.get("alert_delivery_session_key") != session_key:
        state["alert_delivery_session_key"] = session_key
        state["alert_delivery"] = {}
    save_runtime_state(config, state)
    return state, session_key


def initialize_alert_sessions() -> None:
    _ensure_runtime_sessions(reset_igris_session=True)


def _alert_fingerprint(*, source: str, message: str, fingerprint: str | None = None) -> str:
    raw = fingerprint or f"{source}:{message}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def list_alerts(db: Session) -> list[AlertRecord]:
    return list(db.scalars(select(AlertRecord).order_by(AlertRecord.created_at.desc()).limit(100)).all())


def create_alert(db: Session, level: str, message: str, source: str = "manual") -> AlertRecord:
    alert = AlertRecord(level=level, message=message, source=source)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def create_session_limited_alert(
    db: Session,
    *,
    level: str,
    message: str,
    source: str = "system",
    fingerprint: str | None = None,
    max_per_session: int = 3,
) -> AlertRecord | None:
    if max_per_session <= 0:
        return None
    state, session_key = _ensure_runtime_sessions()
    delivery = state.setdefault("alert_delivery", {})
    session_delivery = delivery.setdefault(session_key, {})
    key = _alert_fingerprint(source=source, message=message, fingerprint=fingerprint)
    count = int(session_delivery.get(key, 0) or 0)
    if count >= max_per_session:
        return None
    alert = create_alert(db, level=level, message=message, source=source)
    session_delivery[key] = count + 1
    state["alert_delivery"] = {session_key: session_delivery}
    save_runtime_state(get_config(), state)
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
