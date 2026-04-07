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
        "list_failed_services",
        lambda include_deleted=True: [
            type(
                "FailedService",
                (),
                {"name": "nginx.service", "status_line": "nginx.service loaded failed failed", "deleted": False},
            )()
        ],
    )

    summary, events = monitoring.build_monitor_summary(config)

    assert "AI monitor detected" in summary
    assert len(events) == 4
    assert any("CPU usage is 92%" in event.message for event in events)
    assert any(event.subject == "Igris alert: failed services detected" for event in events)


def test_build_monitor_summary_marks_deleted_services_as_one_time_events(monkeypatch):
    config = AppConfig()

    monkeypatch.setattr(monitoring.psutil, "cpu_percent", lambda interval=None: 10.0)
    monkeypatch.setattr(monitoring.psutil, "virtual_memory", lambda: _VirtualMemory(20.0))
    monkeypatch.setattr(monitoring.psutil, "disk_usage", lambda _: _DiskUsage(30.0))
    monkeypatch.setattr(
        monitoring,
        "list_failed_services",
        lambda include_deleted=True: [
            type(
                "FailedService",
                (),
                {
                    "name": "old-app.service",
                    "status_line": "old-app.service loaded failed failed",
                    "load_state": "not-found",
                    "active_state": "failed",
                    "sub_state": "failed",
                    "unit_file_state": "not-found",
                    "deleted": True,
                },
            )()
        ],
    )

    summary, events = monitoring.build_monitor_summary(config)

    assert "deleted service unit" in summary
    assert len(events) == 1
    assert events[0].once_key == "deleted-service:old-app.service"
    assert events[0].audit_action == "service.deleted_unit_detected"
