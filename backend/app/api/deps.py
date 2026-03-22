from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth.session import COOKIE_NAME, decode_session
from backend.app.db.session import get_db
from backend.app.models import AdminUser


def get_current_user(session_token: str | None = Cookie(default=None, alias=COOKIE_NAME), db: Session = Depends(get_db)) -> AdminUser:
    username = decode_session(session_token)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user = db.scalar(select(AdminUser).where(AdminUser.username == username))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

