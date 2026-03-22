from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.config import get_config
from backend.app.models import AuditLog


def log_audit(db: Session, actor: str, action: str, target: str = "", details: dict | str | None = None) -> None:
    payload = details if isinstance(details, str) else json.dumps(details or {}, sort_keys=True)
    entry = AuditLog(actor=actor, action=action, target=target, details=payload)
    db.add(entry)
    db.commit()
    if get_config().security.audit_log_enabled:
        audit_path = Path(get_config().audit_log_path)
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "actor": actor,
                "action": action,
                "target": target,
                "details": details or {},
            }
        )
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

