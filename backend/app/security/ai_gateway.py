from __future__ import annotations

import hashlib
import hmac
import json
import time

from backend.app.config import AppConfig


def build_gateway_headers(config: AppConfig, payload: dict) -> dict[str, str]:
    timestamp = str(int(time.time()))
    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    secret = config.assistant.gateway_shared_secret.strip()
    digest = hmac.new(secret.encode("utf-8"), f"{timestamp}.{serialized}".encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-Igris-Timestamp": timestamp,
        "X-Igris-Signature": digest,
        "X-Igris-Client": "igris-server",
    }
