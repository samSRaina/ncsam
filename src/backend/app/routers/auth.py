from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.config import settings
from app.db import get_db, utcnow
from app.models import User
from app.schemas import LoginIn
from app.security import client_ip, create_session, current_user, destroy_session, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == body.username))
    now = utcnow()
    ip = client_ip(request)
    if user and user.locked_until and user.locked_until > now:
        audit.log(db, None, "login_locked", "user", user.id, ip=ip)
        db.commit()
        raise HTTPException(429, "Account temporarily locked")
    ok = verify_password(body.password, user.password_hash if user else None)
    if not (ok and user and user.is_active):
        if user:
            user.failed_logins += 1
            if user.failed_logins >= settings.max_failed_logins:
                user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
                user.failed_logins = 0
        audit.log(
            db,
            None,
            "login_failed",
            "user",
            user.id if user else None,
            after={"username": body.username[:64]},
            ip=ip,
        )
        db.commit()
        raise HTTPException(401, "Invalid credentials")  # same message for every failure
    user.failed_logins = 0
    create_session(db, user, response)
    audit.log(db, user, "login", "user", user.id, ip=ip)
    db.commit()
    return {"id": user.id, "username": user.username, "role": user.role.value}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    destroy_session(db, request, response)
    audit.log(db, user, "logout", "user", user.id, ip=client_ip(request))
    db.commit()
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role.value,
        "course": user.course.value if user.course else None,
    }
