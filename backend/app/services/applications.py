from __future__ import annotations

import json
from pathlib import Path

import psutil
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import ManagedApp
from backend.app.services.command import run_command


APP_ROOTS = ("/srv", "/var/www", "/opt", "/home", "/usr/local")


def _load_json(value: str, fallback):
    try:
        return json.loads(value or "")
    except json.JSONDecodeError:
        return fallback


def _classify_path(path: Path) -> tuple[str, str, dict]:
    metadata: dict[str, str | bool] = {}
    if (path / "package.json").exists():
        package_payload = (path / "package.json").read_text(encoding="utf-8", errors="ignore").lower()
        if "nestjs" in package_payload:
            return "nestjs", "node", metadata
        if "\"express\"" in package_payload:
            return "express", "node", metadata
        if "\"vite\"" in package_payload or "\"react\"" in package_payload:
            return "react-vite", "node", metadata
        return "node", "node", metadata
    if (path / "manage.py").exists():
        return "django", "python", metadata
    if (path / "requirements.txt").exists() or (path / "pyproject.toml").exists():
        content = ""
        for file_name in ("requirements.txt", "pyproject.toml"):
            candidate = path / file_name
            if candidate.exists():
                content += candidate.read_text(encoding="utf-8", errors="ignore").lower()
        if "fastapi" in content:
            return "fastapi", "python", metadata
        if "django" in content:
            return "django", "python", metadata
        return "python", "python", metadata
    if (path / "index.html").exists():
        return "static-site", "static", metadata
    if (path / "Dockerfile").exists() or (path / "docker-compose.yml").exists():
        return "containerized-app", "docker", metadata
    if (path / "server.properties").exists():
        return "minecraft", "java", metadata
    return "unknown", "unknown", metadata


def _normalize_candidate(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    try:
        path = Path(path_value).resolve()
    except OSError:
        return None
    if not path.exists():
        return None
    if path.is_file():
        path = path.parent
    if not str(path).startswith(APP_ROOTS):
        return None
    return path


def _ports_by_pid() -> dict[int, list[int]]:
    mapping: dict[int, set[int]] = {}
    for connection in psutil.net_connections(kind="inet"):
        if connection.status != psutil.CONN_LISTEN or not connection.pid or not connection.laddr:
            continue
        mapping.setdefault(connection.pid, set()).add(int(connection.laddr.port))
    return {pid: sorted(list(ports)) for pid, ports in mapping.items()}


def detect_apps() -> list[dict]:
    port_map = _ports_by_pid()
    detected: dict[str, dict] = {}
    for proc in psutil.process_iter(["pid", "name", "cmdline", "cwd", "username", "status"]):
        try:
            info = proc.info
            path = _normalize_candidate(info.get("cwd"))
            if path is None:
                cmdline = " ".join(info.get("cmdline") or [])
                for token in cmdline.split():
                    candidate = _normalize_candidate(token)
                    if candidate is not None:
                        path = candidate
                        break
            if path is None:
                continue
            app_type, runtime, metadata = _classify_path(path)
            existing = detected.get(str(path))
            if existing is None:
                detected[str(path)] = {
                    "name": path.name,
                    "app_type": app_type,
                    "runtime": runtime,
                    "path": str(path),
                    "status": info.get("status") or "running",
                    "ports": port_map.get(proc.pid, []),
                    "service_name": "",
                    "process_name": info.get("name") or "",
                    "public_domain": "",
                    "exposure_status": "private",
                    "repo_url": "",
                    "branch": "main",
                    "metadata": {
                        **metadata,
                        "username": info.get("username") or "",
                        "pid": proc.pid,
                    },
                }
            else:
                existing["ports"] = sorted(set(existing["ports"]) | set(port_map.get(proc.pid, [])))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
            continue

    services = run_command(["systemctl", "list-units", "--type=service", "--all", "--no-legend", "--plain"], timeout=20)
    for raw_line in services.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        service_name = line.split()[0]
        details = run_command(["systemctl", "show", service_name, "--property=WorkingDirectory,ExecStart,ActiveState"], timeout=10)
        payload = {}
        for item in details.stdout.splitlines():
            if "=" in item:
                key, value = item.split("=", 1)
                payload[key] = value
        path = _normalize_candidate(payload.get("WorkingDirectory"))
        if path is None:
            continue
        item = detected.get(str(path))
        if item is None:
            app_type, runtime, metadata = _classify_path(path)
            item = {
                "name": path.name,
                "app_type": app_type,
                "runtime": runtime,
                "path": str(path),
                "status": payload.get("ActiveState") or "inactive",
                "ports": [],
                "service_name": service_name,
                "process_name": "",
                "public_domain": "",
                "exposure_status": "private",
                "repo_url": "",
                "branch": "main",
                "metadata": metadata,
            }
            detected[str(path)] = item
        item["service_name"] = service_name
        item["status"] = payload.get("ActiveState") or item["status"]
        item["metadata"]["exec_start"] = payload.get("ExecStart", "")
    return sorted(detected.values(), key=lambda entry: (entry["app_type"], entry["name"]))


def _record_to_dict(record: ManagedApp) -> dict:
    return {
        "id": record.id,
        "name": record.name,
        "app_type": record.app_type,
        "runtime": record.runtime,
        "path": record.path,
        "status": record.status,
        "ports": _load_json(record.ports_json, []),
        "service_name": record.service_name,
        "process_name": record.process_name,
        "public_domain": record.public_domain,
        "exposure_status": record.exposure_status,
        "repo_url": record.repo_url,
        "branch": record.branch,
        "metadata": _load_json(record.metadata_json, {}),
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


def refresh_inventory(db: Session) -> list[dict]:
    detected = detect_apps()
    existing = {item.path: item for item in db.scalars(select(ManagedApp)).all()}
    seen_paths = set()
    for app in detected:
        seen_paths.add(app["path"])
        record = existing.get(app["path"])
        if record is None:
            record = ManagedApp(path=app["path"], name=app["name"])
            db.add(record)
        record.name = app["name"]
        record.app_type = app["app_type"]
        record.runtime = app["runtime"]
        record.status = app["status"]
        record.ports_json = json.dumps(app["ports"])
        record.service_name = app["service_name"]
        record.process_name = app["process_name"]
        if not record.branch:
            record.branch = "main"
        merged_metadata = dict(_load_json(record.metadata_json, {}))
        merged_metadata.update(app["metadata"])
        record.metadata_json = json.dumps(merged_metadata, sort_keys=True)
    for path, record in existing.items():
        if path not in seen_paths:
            record.status = "missing"
    db.commit()
    return list_apps(db)


def list_apps(db: Session) -> list[dict]:
    items = db.scalars(select(ManagedApp).order_by(ManagedApp.updated_at.desc(), ManagedApp.name.asc())).all()
    if not items:
        return refresh_inventory(db)
    return [_record_to_dict(item) for item in items]


def get_app(db: Session, app_id: int) -> ManagedApp:
    app = db.scalar(select(ManagedApp).where(ManagedApp.id == app_id))
    if app is None:
        raise FileNotFoundError(f"Application {app_id} was not found")
    return app


def update_app_config(db: Session, app_id: int, updates: dict) -> dict:
    app = get_app(db, app_id)
    metadata = dict(_load_json(app.metadata_json, {}))
    metadata.update(updates.pop("metadata", {}))
    for key, value in updates.items():
        if hasattr(app, key):
            setattr(app, key, value)
    app.metadata_json = json.dumps(metadata, sort_keys=True)
    db.commit()
    db.refresh(app)
    return _record_to_dict(app)
