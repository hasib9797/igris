from backend.app.config import AppConfig
from backend.app.services.updates import load_runtime_state, save_runtime_state


def test_runtime_state_roundtrip(tmp_path):
    config = AppConfig()
    config.data_dir = tmp_path

    state = {"last_seen_remote_revision": "abc123", "last_update_check_at": "2026-03-27T00:00:00+00:00"}
    save_runtime_state(config, state)

    assert load_runtime_state(config) == state
