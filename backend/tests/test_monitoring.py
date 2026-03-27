from backend.app.config import AppConfig
from backend.app.services import monitoring


class _VirtualMemory:
    def __init__(self, percent: float):
        self.percent = percent


class _DiskUsage:
    def __init__(self, percent: float):
        self.percent = percent


def test_build_monitor_summary_reports_threshold_breaches(monkeypatch):
    config = AppConfig()
    config.monitoring.cpu_threshold_percent = 80
    config.monitoring.memory_threshold_percent = 80
    config.monitoring.disk_threshold_percent = 80

    monkeypatch.setattr(monitoring.psutil, "cpu_percent", lambda interval=None: 92.0)
    monkeypatch.setattr(monitoring.psutil, "virtual_memory", lambda: _VirtualMemory(88.0))
    monkeypatch.setattr(monitoring.psutil, "disk_usage", lambda _: _DiskUsage(91.0))
    monkeypatch.setattr(
        monitoring.psutil,
        "process_iter",
        lambda attrs=None: [],
    )
    monkeypatch.setattr(
        monitoring,
        "run_command",
        lambda command, timeout=10: type("Result", (), {"stdout": "nginx.service loaded failed failed\n", "returncode": 0})(),
    )

    summary, events = monitoring.build_monitor_summary(config)

    assert "AI monitor detected" in summary
    assert len(events) == 4
    assert any("CPU usage is 92%" in event.message for event in events)
    assert any(event.subject == "Igris alert: failed services detected" for event in events)
