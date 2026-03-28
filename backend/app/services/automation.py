from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from backend.app.config import clear_config_cache, get_config
from backend.app.db.session import get_session_factory
from backend.app.services import applications as application_service
from backend.app.services import incidents as incident_service
from backend.app.services import integrations as integration_service
from backend.app.services.modules import alerts as alert_service
from backend.app.services.monitoring import MonitorEvent, build_monitor_summary
from backend.app.services.notifications import build_alert_html, send_email_notification
from backend.app.services.updates import fetch_remote_revision, load_runtime_state, save_runtime_state, trigger_auto_update


logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit_event(event: MonitorEvent, *, email_body: str | None = None) -> None:
    config = get_config()
    with get_session_factory()() as db:
        created = alert_service.create_alert_once(
            db,
            level=event.level,
            message=event.message,
            source=event.source,
            within_minutes=max(30, config.monitoring.interval_seconds // 60),
        )
    if created:
        try:
            summary = email_body or event.message
            send_email_notification(
                config,
                subject=event.subject,
                text_body=summary,
                html_body=build_alert_html(title=event.subject, summary=event.message, details=summary),
            )
        except Exception as exc:
            logger.warning("Failed to send Igris email notification: %s", exc)
        try:
            integration_service.dispatch_event(
                db,
                f"incident.{event.source}",
                {"title": event.subject, "message": event.message, "severity": event.level, "source": event.source},
            )
        except Exception as exc:
            logger.warning("Failed to send integration notification: %s", exc)


def run_monitor_cycle() -> None:
    clear_config_cache()
    config = get_config()
    if not config.monitoring.enabled:
        return
    summary, events = build_monitor_summary(config)
    for event in events:
        _emit_event(event, email_body=f"{event.message}\n\nSummary: {summary}")
    with get_session_factory()() as db:
        incident_service.scan_incidents(db)
        application_service.refresh_inventory(db)


def run_update_cycle() -> None:
    clear_config_cache()
    config = get_config()
    if not config.updates.enabled:
        return

    state = load_runtime_state(config)
    remote_revision = fetch_remote_revision(config)
    if not remote_revision:
        return

    if not state.get("last_seen_remote_revision"):
        state["last_seen_remote_revision"] = remote_revision
        state["last_update_check_at"] = _utc_now()
        save_runtime_state(config, state)
        return

    if remote_revision != state.get("last_seen_remote_revision"):
        short_rev = remote_revision[:7]
        alert_message = f"Igris update detected on {config.updates.branch}: commit {short_rev} is available from {config.updates.repo_url}."
        with get_session_factory()() as db:
            created = alert_service.create_alert_once(
                db,
                level="info",
                message=alert_message,
                source="repo-watch",
                within_minutes=max(30, config.updates.check_interval_seconds // 60),
            )
        if created:
            try:
                send_email_notification(
                    config,
                    subject="Igris alert: update available",
                    text_body=alert_message,
                    html_body=build_alert_html(title="Update available", summary=alert_message, details=alert_message),
                )
            except Exception as exc:
                logger.warning("Failed to send repo update notification: %s", exc)

        state["last_seen_remote_revision"] = remote_revision
        state["last_update_detected_at"] = _utc_now()

        if config.updates.auto_update and state.get("last_auto_update_revision") != remote_revision:
            auto_update_message = f"Igris auto-update is starting for commit {short_rev} from {config.updates.branch}."
            with get_session_factory()() as db:
                alert_service.create_alert_once(
                    db,
                    level="info",
                    message=auto_update_message,
                    source="repo-watch",
                    within_minutes=15,
                )
            try:
                send_email_notification(
                    config,
                    subject="Igris alert: auto-update starting",
                    text_body=auto_update_message,
                    html_body=build_alert_html(title="Auto-update starting", summary=auto_update_message, details=auto_update_message),
                )
            except Exception as exc:
                logger.warning("Failed to send auto-update notification: %s", exc)
            trigger_auto_update()
            state["last_auto_update_revision"] = remote_revision
            state["last_auto_update_started_at"] = _utc_now()

    state["last_update_check_at"] = _utc_now()
    save_runtime_state(config, state)


async def run_background_loops(stop_event: asyncio.Event) -> None:
    last_monitor_at = 0.0
    last_update_at = 0.0
    while not stop_event.is_set():
        try:
            clear_config_cache()
            config = get_config()
            now = time.time()
            if config.monitoring.enabled and now - last_monitor_at >= max(60, config.monitoring.interval_seconds):
                await asyncio.to_thread(run_monitor_cycle)
                last_monitor_at = now
            if config.updates.enabled and now - last_update_at >= max(120, config.updates.check_interval_seconds):
                await asyncio.to_thread(run_update_cycle)
                last_update_at = now
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Igris background automation loop failed: %s", exc)
        await asyncio.sleep(15)
