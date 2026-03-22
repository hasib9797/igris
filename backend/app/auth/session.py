from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Response
from itsdangerous import BadSignature, URLSafeTimedSerializer

from backend.app.config import get_config


COOKIE_NAME = "igris_session"


def serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_config().auth.session_secret, salt="igris-session")


def create_session(username: str) -> str:
    return serializer().dumps({"username": username})


def decode_session(token: str | None) -> str | None:
    if not token:
        return None
    try:
        max_age = get_config().auth.session_timeout_minutes * 60
        payload = serializer().loads(token, max_age=max_age)
        return str(payload.get("username"))
    except BadSignature:
        return None


def set_session_cookie(response: Response, username: str) -> None:
    ttl = get_config().auth.session_timeout_minutes * 60
    expires = datetime.now(timezone.utc) + timedelta(seconds=ttl)
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_session(username),
        httponly=True,
        samesite="lax",
        secure=get_config().server.https_enabled,
        expires=expires,
        max_age=ttl,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME)

