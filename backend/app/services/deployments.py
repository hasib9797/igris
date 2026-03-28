from __future__ import annotations

import json
import shutil
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import get_config
from backend.app.models import DeploymentRecord, ManagedApp
from backend.app.services.command import run_command


def _metadata(app: ManagedApp) -> dict:
    try:
        return json.loads(app.metadata_json or "{}")
    except json.JSONDecodeError:
        return {}


def _save_metadata(app: ManagedApp, metadata: dict) -> None:
    app.metadata_json = json.dumps(metadata, sort_keys=True)


def save_deployment_config(db: Session, payload: dict) -> dict:
    app = db.scalar(select(ManagedApp).where(ManagedApp.path == payload["path"]))
    if app is None:
        app = ManagedApp(
            name=payload["app_name"],
            path=payload["path"],
            app_type="managed-app",
            runtime=payload.get("runtime") or "auto",
        )
        db.add(app)
        db.flush()
    app.name = payload["app_name"]
    app.runtime = payload.get("runtime") or app.runtime
    app.repo_url = payload.get("repo_url") or app.repo_url
    app.branch = payload.get("branch") or app.branch or "main"
    app.service_name = payload.get("service_name") or app.service_name
    metadata = _metadata(app)
    metadata["deploy"] = {
        "install_command": payload.get("install_command", ""),
        "build_command": payload.get("build_command", ""),
        "restart_command": payload.get("restart_command", ""),
        "port": payload.get("port"),
    }
    _save_metadata(app, metadata)
    db.commit()
    db.refresh(app)
    return {"id": app.id, "name": app.name, "path": app.path, "repo_url": app.repo_url, "branch": app.branch, "service_name": app.service_name, "metadata": metadata}


def _record_deployment(db: Session, app: ManagedApp, *, status: str, revision: str, log_excerpt: str) -> DeploymentRecord:
    record = DeploymentRecord(
        app_name=app.name,
        repo_url=app.repo_url,
        branch=app.branch or "main",
        revision=revision,
        status=status,
        deployed_path=app.path,
        service_name=app.service_name,
        log_excerpt=log_excerpt[-6000:],
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_deployments(db: Session) -> list[dict]:
    items = db.scalars(select(DeploymentRecord).order_by(DeploymentRecord.created_at.desc())).all()
    return [
        {
            "id": item.id,
            "app_name": item.app_name,
            "repo_url": item.repo_url,
            "branch": item.branch,
            "revision": item.revision,
            "status": item.status,
            "deployed_path": item.deployed_path,
            "service_name": item.service_name,
            "log_excerpt": item.log_excerpt,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in items
    ]


def run_deployment(db: Session, app_id: int) -> dict:
    app = db.scalar(select(ManagedApp).where(ManagedApp.id == app_id))
    if app is None:
        raise FileNotFoundError(f"Application {app_id} was not found")
    app_path = Path(app.path)
    if not app_path.exists():
        raise FileNotFoundError(f"Application path does not exist: {app.path}")
    metadata = _metadata(app).get("deploy", {})
    if not app.repo_url:
        raise ValueError(f"{app.name} does not have a repo configured")

    before_revision = run_command(["git", "-C", str(app_path), "rev-parse", "HEAD"], timeout=20)
    current_revision = before_revision.stdout.strip() if before_revision.returncode == 0 else ""
    logs: list[str] = []

    def _step(command: str) -> None:
        result = run_command(["/bin/bash", "-lc", f"cd '{app.path}' && {command}"], timeout=900)
        logs.append(f"$ {command}\n{result.stdout}{result.stderr}")
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"Command failed: {command}")

    try:
        _step(f"git pull origin {app.branch or 'main'}")
        if metadata.get("install_command"):
            _step(str(metadata["install_command"]))
        if metadata.get("build_command"):
            _step(str(metadata["build_command"]))
        if metadata.get("restart_command"):
            _step(str(metadata["restart_command"]))
        elif app.service_name:
            _step(f"systemctl restart {app.service_name}")
        revision = run_command(["git", "-C", str(app_path), "rev-parse", "HEAD"], timeout=20).stdout.strip()
        record = _record_deployment(db, app, status="success", revision=revision, log_excerpt="\n".join(logs))
        return {"status": "success", "deployment": list_deployments(db)[0], "record_id": record.id}
    except Exception as exc:
        if current_revision:
            rollback = run_command(["git", "-C", str(app_path), "reset", "--hard", current_revision], timeout=60)
            logs.append(f"$ rollback to {current_revision}\n{rollback.stdout}{rollback.stderr}")
            if app.service_name:
                restart = run_command(["systemctl", "restart", app.service_name], timeout=60)
                logs.append(f"$ systemctl restart {app.service_name}\n{restart.stdout}{restart.stderr}")
        record = _record_deployment(db, app, status="failed", revision=current_revision, log_excerpt="\n".join(logs + [str(exc)]))
        return {"status": "failed", "error": str(exc), "record_id": record.id, "logs": "\n".join(logs)}


def _config_paths(domain: str) -> tuple[Path, Path]:
    config = get_config()
    available = Path(config.deploy.nginx_sites_available) / f"{domain}.conf"
    enabled = Path(config.deploy.nginx_sites_enabled) / f"{domain}.conf"
    return available, enabled


def build_exposure_preview(db: Session, app_id: int, domain: str, port: int | None, ssl_mode: str, open_firewall: bool) -> dict:
    app = db.scalar(select(ManagedApp).where(ManagedApp.id == app_id))
    if app is None:
        raise FileNotFoundError(f"Application {app_id} was not found")
    ports = []
    try:
        ports = json.loads(app.ports_json or "[]")
    except json.JSONDecodeError:
        ports = []
    target_port = int(port or (ports[0] if ports else 3000))
    upstream = f"http://127.0.0.1:{target_port}"
    server_block = [
        "server {",
        f"    server_name {domain};",
        "    location / {",
        f"        proxy_pass {upstream};",
        "        proxy_set_header Host $host;",
        "        proxy_set_header X-Real-IP $remote_addr;",
        "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
        "        proxy_set_header X-Forwarded-Proto $scheme;",
        "    }",
        "}",
    ]
    commands = [
        "nginx -t",
        f"ln -sf {_config_paths(domain)[0]} {_config_paths(domain)[1]}",
        "systemctl reload nginx",
    ]
    if open_firewall:
        commands.insert(0, "ufw allow 'Nginx Full'")
    if ssl_mode == "letsencrypt":
        commands.append(f"certbot --nginx -d {domain}")
    elif ssl_mode == "cloudflare":
        commands.append("Cloudflare mode selected: DNS token will be used if configured.")
    return {
        "app_id": app.id,
        "app_name": app.name,
        "domain": domain,
        "port": target_port,
        "ssl_mode": ssl_mode,
        "open_firewall": open_firewall,
        "nginx_config": "\n".join(server_block),
        "commands": commands,
    }


def apply_exposure(db: Session, app_id: int, domain: str, port: int | None, ssl_mode: str, open_firewall: bool) -> dict:
    preview = build_exposure_preview(db, app_id, domain, port, ssl_mode, open_firewall)
    available, enabled = _config_paths(domain)
    backup_dir = Path(get_config().deploy.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    if available.exists():
        shutil.copy2(available, backup_dir / f"{available.name}.bak")
    available.parent.mkdir(parents=True, exist_ok=True)
    enabled.parent.mkdir(parents=True, exist_ok=True)
    available.write_text(preview["nginx_config"] + "\n", encoding="utf-8")
    if open_firewall:
        run_command(["ufw", "allow", "Nginx Full"], timeout=30)
    test = run_command(["nginx", "-t"], timeout=30)
    if test.returncode != 0:
        raise RuntimeError(test.stderr.strip() or test.stdout.strip() or "nginx validation failed")
    if enabled.exists() or enabled.is_symlink():
        enabled.unlink()
    enabled.symlink_to(available)
    reload_result = run_command(["systemctl", "reload", "nginx"], timeout=30)
    if reload_result.returncode != 0:
        raise RuntimeError(reload_result.stderr.strip() or reload_result.stdout.strip() or "nginx reload failed")
    app = db.scalar(select(ManagedApp).where(ManagedApp.id == app_id))
    assert app is not None
    app.public_domain = domain
    app.exposure_status = "public"
    db.commit()
    return preview | {"status": "applied"}


def remove_exposure(db: Session, app_id: int) -> dict:
    app = db.scalar(select(ManagedApp).where(ManagedApp.id == app_id))
    if app is None:
        raise FileNotFoundError(f"Application {app_id} was not found")
    if not app.public_domain:
        return {"status": "noop", "message": "Application is already private"}
    available, enabled = _config_paths(app.public_domain)
    for path in (enabled, available):
        if path.exists() or path.is_symlink():
            path.unlink()
    run_command(["nginx", "-t"], timeout=30).ensure_success("nginx validation failed")
    run_command(["systemctl", "reload", "nginx"], timeout=30).ensure_success("nginx reload failed")
    domain = app.public_domain
    app.public_domain = ""
    app.exposure_status = "private"
    db.commit()
    return {"status": "removed", "domain": domain}
