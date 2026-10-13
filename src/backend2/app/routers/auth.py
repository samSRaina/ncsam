import json
import secrets
from datetime import timedelta

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.config import settings
from app.db import get_db, utcnow
from app.models import PolicySetting, SessionRow, User
from app.schemas import ChangePasswordIn, LoginIn, MFACodeIn, MFAVerifyIn
from app.security import (
    client_ip,
    create_session,
    current_user,
    destroy_session,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory temporary MFA pending logins: token -> {user_id, expires_at, attempts}
_MFA_PENDING = {}


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

    # 4.11 Optional multi-factor authentication (TOTP)
    # Check if user has MFA enabled or if role requires MFA
    ps = db.scalar(select(PolicySetting).order_by(PolicySetting.version.desc()).limit(1))
    role_requires_mfa = ps and ps.mfa_required_roles and user.role.value in ps.mfa_required_roles

    if user.mfa_enabled or role_requires_mfa:
        mfa_token = secrets.token_urlsafe(32)
        _MFA_PENDING[mfa_token] = {
            "user_id": user.id,
            "expires_at": now + timedelta(minutes=5),
            "attempts": 0,
        }
        audit.log(db, user, "login_mfa_pending", "user", user.id, ip=ip)
        db.commit()
        return {
            "mfa_required": True,
            "mfa_token": mfa_token,
            "message": "MFA verification code required",
        }

    # Session rotation / creation on login
    create_session(db, user, response)
    audit.log(db, user, "login", "user", user.id, ip=ip)
    db.commit()
    return {"id": user.id, "username": user.username, "role": user.role.value}


@router.post("/mfa/verify")
def mfa_verify(
    body: MFACodeIn,
    request: Request,
    response: Response,
    mfa_token: str | None = None,
    db: Session = Depends(get_db),
):
    token = mfa_token or request.headers.get("X-MFA-Token")
    if not token or token not in _MFA_PENDING:
        raise HTTPException(401, "Invalid or expired MFA session")

    pending = _MFA_PENDING[token]
    now = utcnow()
    if pending["expires_at"] < now:
        del _MFA_PENDING[token]
        raise HTTPException(401, "MFA session expired")

    if pending["attempts"] >= 5:
        del _MFA_PENDING[token]
        raise HTTPException(429, "Too many failed MFA attempts. Please log in again.")

    user = db.get(User, pending["user_id"])
    if not user or not user.is_active:
        del _MFA_PENDING[token]
        raise HTTPException(401, "User not found or inactive")

    # Verify TOTP code or recovery code
    valid = False
    if user.mfa_secret:
        totp = pyotp.TOTP(user.mfa_secret)
        valid = totp.verify(body.code, valid_window=1)

    # Check recovery code if not valid yet
    if not valid and user.mfa_recovery_codes:
        try:
            codes = json.loads(user.mfa_recovery_codes)
            if body.code in codes:
                codes.remove(body.code)
                user.mfa_recovery_codes = json.dumps(codes)
                valid = True
        except Exception:
            pass

    if not valid:
        pending["attempts"] += 1
        audit.log(db, user, "mfa_verify_failed", "user", user.id, ip=client_ip(request))
        db.commit()
        raise HTTPException(401, "Invalid MFA code")

    del _MFA_PENDING[token]
    create_session(db, user, response)
    audit.log(db, user, "mfa_login_success", "user", user.id, ip=client_ip(request))
    db.commit()
    return {"id": user.id, "username": user.username, "role": user.role.value}


@router.post("/mfa/enroll")
def mfa_enroll(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    secret = pyotp.random_base32()
    user.mfa_secret = secret
    db.commit()
    totp = pyotp.TOTP(secret)
    otpauth_url = totp.provisioning_uri(name=user.username, issuer_name="NFSU Placement Management")
    return {"secret": secret, "otpauth_url": otpauth_url}


@router.post("/mfa/activate")
def mfa_activate(
    body: MFAVerifyIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if not user.mfa_secret:
        raise HTTPException(400, "MFA enrollment must be called first")
    totp = pyotp.TOTP(user.mfa_secret)
    if not totp.verify(body.code, valid_window=1):
        raise HTTPException(400, "Invalid verification code")

    # Generate 8 recovery codes
    recovery_codes = [secrets.token_hex(4).upper() for _ in range(8)]
    user.mfa_enabled = True
    user.mfa_recovery_codes = json.dumps(recovery_codes)

    audit.log(db, user, "mfa_activate", "user", user.id, ip=client_ip(request))
    db.commit()
    return {
        "mfa_enabled": True,
        "recovery_codes": recovery_codes,
        "message": "MFA activated successfully. Store recovery codes safely.",
    }


@router.post("/mfa/disable")
def mfa_disable(
    body: MFAVerifyIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if not user.mfa_enabled or not user.mfa_secret:
        raise HTTPException(400, "MFA is not enabled")
    totp = pyotp.TOTP(user.mfa_secret)
    if not totp.verify(body.code, valid_window=1):
        raise HTTPException(400, "Invalid verification code")

    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_recovery_codes = None
    audit.log(db, user, "mfa_disable", "user", user.id, ip=client_ip(request))
    db.commit()
    return {"mfa_enabled": False, "message": "MFA disabled"}


@router.post("/change-password")
def change_password(
    body: ChangePasswordIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if not verify_password(body.current_password, user.password_hash):
        audit.log(db, user, "change_password_failed", "user", user.id, ip=client_ip(request))
        db.commit()
        raise HTTPException(400, "Current password incorrect")

    # Common passwords reject
    if body.new_password.lower() in ("password", "password123", "nfsu12345", "12345678"):
        raise HTTPException(400, "Password is too common")

    user.password_hash = hash_password(body.new_password)

    # Revoke all sessions for this user, then create a fresh session
    db.query(SessionRow).filter(SessionRow.user_id == user.id).delete()
    create_session(db, user, response)

    audit.log(db, user, "change_password", "user", user.id, ip=client_ip(request))
    db.commit()
    return {"ok": True, "message": "Password changed successfully"}


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
        "mfa_enabled": user.mfa_enabled,
    }
