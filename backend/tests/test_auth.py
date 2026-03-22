import importlib
import sys
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from backend.app.config import clear_config_cache
from backend.app.security.passwords import hash_password


def build_app(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    data_dir = tmp_path / "data"
    frontend_dist = tmp_path / "frontend-dist"
    data_dir.mkdir(parents=True, exist_ok=True)
    frontend_dist.mkdir(parents=True, exist_ok=True)
    (frontend_dist / "index.html").write_text("<!doctype html><html><body>Igris</body></html>", encoding="utf-8")
    assets_dir = frontend_dist / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "app.js").write_text("console.log('igris');", encoding="utf-8")
    config = {
        "server": {"host": "127.0.0.1", "port": 2511, "https_enabled": False},
        "auth": {
            "admin_username": "admin",
            "password_hash": hash_password("secret-pass"),
            "session_secret": "test-secret",
            "session_timeout_minutes": 30,
        },
        "system": {
            "managed_user": "ubuntu",
            "allow_terminal": False,
            "allow_package_install": True,
            "allow_user_management": True,
            "allow_network_management": True,
            "allow_service_management": True,
        },
        "modules": {"docker": False, "alerts": True, "tasks": True, "files": True},
        "security": {
            "trusted_subnets": [],
            "require_reauth_for_dangerous_actions": True,
            "audit_log_enabled": True,
        },
        "data_dir": str(data_dir),
        "audit_log_path": str(data_dir / "audit.log"),
        "database_url": f"sqlite:///{data_dir / 'database.db'}",
    }
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    monkeypatch.setenv("IGRIS_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("IGRIS_DATA_DIR", str(data_dir))
    monkeypatch.setenv("IGRIS_FRONTEND_DIST", str(frontend_dist))
    clear_config_cache()
    if "backend.app.main" in sys.modules:
        main_module = importlib.reload(sys.modules["backend.app.main"])
    else:
        main_module = importlib.import_module("backend.app.main")
    return main_module.create_app()


def test_auth_requires_login(tmp_path, monkeypatch):
    app = build_app(tmp_path, monkeypatch)
    client = TestClient(app)
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_login_and_overview_work(tmp_path, monkeypatch):
    app = build_app(tmp_path, monkeypatch)
    client = TestClient(app)

    login = client.post("/api/auth/login", json={"username": "admin", "password": "secret-pass"})
    assert login.status_code == 200

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "admin"

    overview = client.get("/api/system/overview")
    assert overview.status_code == 200
    assert "hostname" in overview.json()


def test_frontend_fallback_serves_index_and_assets(tmp_path, monkeypatch):
    app = build_app(tmp_path, monkeypatch)
    client = TestClient(app)

    root = client.get("/")
    assert root.status_code == 200
    assert "text/html" in root.headers["content-type"]
    assert "Igris" in root.text

    asset = client.get("/assets/app.js")
    assert asset.status_code == 200
    assert "console.log('igris');" in asset.text

    deep_route = client.get("/services/view")
    assert deep_route.status_code == 200
    assert "text/html" in deep_route.headers["content-type"]

    unknown_api = client.get("/api/does-not-exist")
    assert unknown_api.status_code == 404

    traversal = client.get("/..%2F..%2Fsecrets.txt")
    assert traversal.status_code == 404
