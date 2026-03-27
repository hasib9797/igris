from __future__ import annotations

import json
import urllib.error
import urllib.request
from html import escape
from pathlib import Path

from backend.app.config import AppConfig


MAILER_BASE_URL = "https://konoha-mailer.vercel.app"
MAILER_API_PATH = "/api/mail/send/write"
MAILER_KEY_PATH = Path(__file__).resolve().parents[3] / "public" / ".konoha-mailer-key"


def _load_mailer_api_key() -> str:
    if not MAILER_KEY_PATH.exists():
        return ""
    return MAILER_KEY_PATH.read_text(encoding="utf-8").strip()


def build_alert_html(*, title: str, summary: str, details: str) -> str:
    return f"""
<html>
  <body style="margin:0;padding:0;background:#0f172a;font-family:Arial,sans-serif;color:#e2e8f0;">
    <div style="max-width:680px;margin:0 auto;padding:32px 20px;">
      <div style="border:1px solid #1e293b;border-radius:24px;overflow:hidden;background:#111827;">
        <div style="padding:24px 28px;background:linear-gradient(135deg,#1d4ed8,#0f766e);">
          <div style="font-size:12px;letter-spacing:0.2em;text-transform:uppercase;opacity:0.85;">Igris Alert</div>
          <h1 style="margin:12px 0 0;font-size:28px;line-height:1.2;color:#ffffff;">{escape(title)}</h1>
        </div>
        <div style="padding:28px;">
          <p style="margin:0 0 16px;font-size:16px;line-height:1.7;color:#cbd5e1;">{escape(summary)}</p>
          <div style="padding:18px 20px;border-radius:18px;background:#0b1220;border:1px solid #1e293b;">
            <div style="font-size:12px;letter-spacing:0.18em;text-transform:uppercase;color:#60a5fa;margin-bottom:10px;">Details</div>
            <div style="font-size:14px;line-height:1.8;color:#e2e8f0;white-space:pre-wrap;">{escape(details)}</div>
          </div>
        </div>
      </div>
    </div>
  </body>
</html>
""".strip()


def send_email_notification(
    config: AppConfig,
    *,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    require_ready: bool = False,
) -> None:
    if not config.email.enabled:
        if require_ready:
            raise RuntimeError("Email alerts are disabled in Igris settings")
        return
    if not config.email.recipient:
        if require_ready:
            raise RuntimeError("No alert email address is configured")
        return

    api_key = _load_mailer_api_key()
    if not api_key:
        if require_ready:
            raise RuntimeError(f"Mailer API key file not found at {MAILER_KEY_PATH}")
        return

    payload = {
        "receiver": [config.email.recipient],
        "subject": subject,
        "html": html_body or build_alert_html(title=subject, summary=text_body, details=text_body),
        "text": text_body,
        "tags": ["igris", "alert"],
    }

    request = urllib.request.Request(
        f"{MAILER_BASE_URL}{MAILER_API_PATH}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-api-key": api_key},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status != 200:
                raise RuntimeError(f"Mailer request failed with status {response.status}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Mailer request failed with status {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Mailer request failed: {exc.reason}") from exc
