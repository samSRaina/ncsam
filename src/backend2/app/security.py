import hashlib
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db, utcnow
from app.enums import Role
from app.models import SessionRow, User

COOKIE = "session"
_ph = PasswordHasher()
_DUMMY = _ph.hash("dummy-password-for-timing")

# Field visibility by role. Everything else is denied by default.
CONTACT_ROLES = {Role.ADMIN, Role.OFFICER, Role.COORDINATOR}
COMP_ROLES = {Role.ADMIN, Role.OFFICER}
STAFF_WRITE = {Role.ADMIN, Role.OFFICER}


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(pw: str, hashed: str | None) -> bool:
    try:
        return _ph.verify(hashed or _DUMMY, pw) and hashed is not None
    except VerificationError:
        return False


def _h(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User, response: Response) -> None:
    token = secrets.token_urlsafe(32)
    now = utcnow()
    db.add(
        SessionRow(
            token_hash=_h(token),
            user_id=user.id,
            created_at=now,
            last_seen=now,
            expires_at=now + timedelta(hours=settings.session_absolute_hours),
        )
    )
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        samesite="strict",
        secure=settings.cookie_secure,
        max_age=settings.session_absolute_hours * 3600,
    )


def destroy_session(db: Session, request: Request, response: Response) -> None:
    token = request.cookies.get(COOKIE)
    if token:
        row = db.scalar(select(SessionRow).where(SessionRow.token_hash == _h(token)))
        if row:
            db.delete(row)
    response.delete_cookie(COOKIE)


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE)
    unauth = HTTPException(401, "Not authenticated")
    if not token:
        raise unauth
    row = db.scalar(select(SessionRow).where(SessionRow.token_hash == _h(token)))
    now = utcnow()
    if (
        not row
        or row.expires_at < now
        or row.last_seen + timedelta(minutes=settings.session_idle_minutes) < now
    ):
        if row:
            db.delete(row)
            db.commit()
        raise unauth
    user = db.get(User, row.user_id)
    if not user or not user.is_active:
        raise unauth
    row.last_seen = now
    db.commit()
    return user


def require_roles(*roles: Role):
    allowed = set(roles)

    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(403, "Forbidden")
        return user

    return dep


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
