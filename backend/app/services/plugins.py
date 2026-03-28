from __future__ import annotations

import json
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import PluginRecord


def _plugin_roots() -> list[Path]:
    root = Path(__file__).resolve().parents[3] / "plugins"
    return [path for path in root.iterdir() if path.is_dir()] if root.exists() else []


def refresh_plugins(db: Session) -> list[dict]:
    manifests: list[dict] = []
    for root in _plugin_roots():
        manifest_path = root / "igris-plugin.yaml"
        if not manifest_path.exists():
            continue
        payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        plugin_id = payload.get("id") or root.name
        record = db.scalar(select(PluginRecord).where(PluginRecord.plugin_id == plugin_id))
        if record is None:
            record = PluginRecord(plugin_id=plugin_id, name=payload.get("name") or plugin_id)
            db.add(record)
        record.name = payload.get("name") or plugin_id
        record.version = str(payload.get("version") or "0.0.0")
        record.enabled = bool(payload.get("enabled", True))
        record.manifest_json = json.dumps(payload, sort_keys=True)
        manifests.append(
            {
                "plugin_id": plugin_id,
                "name": record.name,
                "version": record.version,
                "enabled": record.enabled,
                "manifest": payload,
            }
        )
    db.commit()
    return manifests or list_plugins(db)


def list_plugins(db: Session) -> list[dict]:
    items = db.scalars(select(PluginRecord).order_by(PluginRecord.name.asc())).all()
    output: list[dict] = []
    for item in items:
        try:
            manifest = json.loads(item.manifest_json or "{}")
        except json.JSONDecodeError:
            manifest = {}
        output.append(
            {
                "id": item.id,
                "plugin_id": item.plugin_id,
                "name": item.name,
                "version": item.version,
                "enabled": item.enabled,
                "manifest": manifest,
                "extension_points": manifest.get("extension_points", {}),
            }
        )
    return output
