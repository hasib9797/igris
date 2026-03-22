from pathlib import Path

import yaml

from backend.app.config import clear_config_cache
from scripts import setup_wizard


def test_setup_wizard_writes_config_and_initializes_db(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    data_dir = tmp_path / "data"
    service_template = tmp_path / "igris.service"
    ufw_profile = tmp_path / "igris.profile"
    service_template.write_text("[Unit]\nDescription=Igris\n", encoding="utf-8")
    ufw_profile.write_text("[Igris]\nports=2511/tcp\n", encoding="utf-8")

    answers = iter(["admin", "2511", "0.0.0.0", "ubuntu", "y", "n", "y"])
    passwords = iter(["secret-pass", "secret-pass"])
    calls: list[str] = []

    monkeypatch.setenv("IGRIS_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("IGRIS_DATA_DIR", str(data_dir))
    monkeypatch.setattr(setup_wizard, "CONFIG_PATH", config_path)
    monkeypatch.setattr(setup_wizard, "DATA_DIR", data_dir)
    monkeypatch.setattr(setup_wizard, "SERVICE_SOURCE", service_template)
    monkeypatch.setattr(setup_wizard, "UFW_PROFILE_SOURCE", ufw_profile)
    monkeypatch.setattr(setup_wizard, "UFW_PROFILE_DEST", tmp_path / "applications.d" / "igris")
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.setattr("getpass.getpass", lambda _: next(passwords))
    monkeypatch.setattr(setup_wizard, "install_service", lambda path: calls.append(f"install:{Path(path).name}"))
    monkeypatch.setattr(setup_wizard, "start_service", lambda: calls.append("start"))
    monkeypatch.setattr(setup_wizard, "install_ufw_profile", lambda: calls.append("ufw-profile"))
    monkeypatch.setattr(setup_wizard, "allow_port", lambda port: calls.append(f"allow:{port}"))
    monkeypatch.setattr(setup_wizard, "local_ip", lambda: "10.0.0.10")
    if hasattr(setup_wizard.os, "geteuid"):
        monkeypatch.setattr(setup_wizard.os, "geteuid", lambda: 0)

    clear_config_cache()
    setup_wizard.run_setup()

    assert config_path.exists()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert config["auth"]["admin_username"] == "admin"
    assert config["auth"]["password_hash"] != "secret-pass"
    assert Path(data_dir / "database.db").exists()
    assert calls == ["install:igris.service", "start", "ufw-profile", "allow:2511"]
