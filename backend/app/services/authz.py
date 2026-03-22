from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import get_config
from backend.app.models import AdminUser
from backend.app.security.passwords import verify_password


def verify_reauth(db: Session, username: str, confirm_password: str | None) -> None:
    if not get_config().security.require_reauth_for_dangerous_actions:
        return
    if not confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password confirmation is required")
    user = db.scalar(select(AdminUser).where(AdminUser.username == username))
    if not user or not verify_password(confirm_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Password confirmation failed")

