from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit
from app import enums as E
from app.db import get_db, utcnow
from app.models import Company, PolicySetting, SessionRow, Student, User
from app.schemas import (
    ResetPasswordIn,
    RetentionApply,
    UserCreate,
    UserUpdate,
)
from app.security import (
    client_ip,
    hash_password,
    require_roles,
)

router = APIRouter(prefix="/admin", tags=["admin"])


# ---- 4.10 User and Session Administration ---------------------------------


@router.get("/users")
def list_users(
    response: Response,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN)),
):
    stmt = select(User).order_by(User.id)
    total_count = len(list(db.scalars(stmt)))
    response.headers["X-Total-Count"] = str(total_count)
    users = list(db.scalars(stmt.limit(limit).offset(offset)))
    return [
        {
            "id": u.id,
            "username": u.username,
            "role": u.role.value,
            "course": u.course.value if u.course else None,
            "company_id": u.company_id,
            "student_id": u.student_id,
            "is_active": u.is_active,
            "mfa_enabled": u.mfa_enabled,
            "failed_logins": u.failed_logins,
            "locked_until": u.locked_until,
        }
        for u in users
    ]


@router.post("/users", status_code=201)
def create_user(
    body: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN)),
):
    if body.role is E.Role.COORDINATOR and not body.course:
        raise HTTPException(400, "Coordinator must have a course assigned")
    if body.role is E.Role.RECRUITER and not body.company_id:
        raise HTTPException(400, "Recruiter must have a company_id assigned")
    if body.role is E.Role.STUDENT and not body.student_id:
        raise HTTPException(400, "Student user must have a student_id assigned")

    new_user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
        course=body.course,
        company_id=body.company_id,
        student_id=body.student_id,
        is_active=True,
    )
    db.add(new_user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Username already exists")

    audit.log(
        db,
        user,
        "admin_user_create",
        "user",
        new_user.id,
        after={"username": new_user.username, "role": new_user.role.value},
        ip=client_ip(request),
    )
    db.commit()
    return {
        "id": new_user.id,
        "username": new_user.username,
        "role": new_user.role.value,
        "course": new_user.course.value if new_user.course else None,
        "company_id": new_user.company_id,
        "student_id": new_user.student_id,
        "is_active": new_user.is_active,
    }


@router.get("/users/{user_id}")
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN)),
):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    return {
        "id": u.id,
        "username": u.username,
        "role": u.role.value,
        "course": u.course.value if u.course else None,
        "company_id": u.company_id,
        "student_id": u.student_id,
        "is_active": u.is_active,
        "mfa_enabled": u.mfa_enabled,
        "failed_logins": u.failed_logins,
        "locked_until": u.locked_until,
    }


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    body: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN)),
):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")

    # Safety: admin cannot demote themselves
    if u.id == user.id and body.role is not None and body.role != E.Role.ADMIN:
        raise HTTPException(400, "An admin cannot demote themselves")

    # Safety: do not allow removal or deactivation of the last active admin
    if u.role == E.Role.ADMIN and (body.is_active is False or (body.role and body.role != E.Role.ADMIN)):
        active_admins = db.scalar(
            select(func.count(User.id)).where(User.role == E.Role.ADMIN, User.is_active.is_(True))
        )
        if active_admins <= 1:
            raise HTTPException(400, "Cannot deactivate or demote the last active admin")

    before = {
        "role": u.role.value,
        "is_active": u.is_active,
        "course": u.course.value if u.course else None,
        "company_id": u.company_id,
        "student_id": u.student_id,
    }

    if body.role is not None:
        u.role = body.role
    if body.is_active is not None:
        u.is_active = body.is_active
    if body.course is not None:
        u.course = body.course
    if body.company_id is not None:
        u.company_id = body.company_id
    if body.student_id is not None:
        u.student_id = body.student_id

    after = {
        "role": u.role.value,
        "is_active": u.is_active,
        "course": u.course.value if u.course else None,
        "company_id": u.company_id,
        "student_id": u.student_id,
    }
    audit.log(
        db,
        user,
        "admin_user_update",
        "user",
        u.id,
        before=before,
        after=after,
        ip=client_ip(request),
    )
    db.commit()
    return {
        "id": u.id,
        "username": u.username,
        "role": u.role.value,
        "course": u.course.value if u.course else None,
        "company_id": u.company_id,
        "student_id": u.student_id,
        "is_active": u.is_active,
    }


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    body: ResetPasswordIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN)),
):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    u.password_hash = hash_password(body.new_password)
    u.failed_logins = 0
    u.locked_until = None

    # Revoke user's other sessions
    db.query(SessionRow).filter(SessionRow.user_id == u.id).delete()

    audit.log(
        db,
        user,
        "admin_reset_password",
        "user",
        u.id,
        after={"username": u.username, "sessions_revoked": True},
        ip=client_ip(request),
    )
    db.commit()
    return {"ok": True, "message": "Password reset successfully"}


@router.post("/users/{user_id}/unlock")
def unlock_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN)),
):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    u.failed_logins = 0
    u.locked_until = None
    audit.log(
        db,
        user,
        "admin_unlock_user",
        "user",
        u.id,
        after={"username": u.username, "unlocked": True},
        ip=client_ip(request),
    )
    db.commit()
    return {"ok": True, "message": "User unlocked"}


@router.get("/sessions")
def list_sessions(
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN)),
):
    now = utcnow()
    rows = list(
        db.scalars(
            select(SessionRow).where(SessionRow.expires_at > now).order_by(SessionRow.last_seen.desc())
        )
    )
    response.headers["X-Total-Count"] = str(len(rows))
    return [
        {
            "id": s.id,
            "user_id": s.user_id,
            "created_at": s.created_at,
            "last_seen": s.last_seen,
            "expires_at": s.expires_at,
        }
        for s in rows
    ]


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN)),
):
    s = db.get(SessionRow, session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    before = {"user_id": s.user_id, "session_id": s.id}
    db.delete(s)
    audit.log(
        db,
        user,
        "admin_delete_session",
        "session",
        session_id,
        before=before,
        after=None,
        ip=client_ip(request),
    )
    db.commit()
    return {"ok": True}


# ---- 4.13 Retention (Preview and Apply) -----------------------------------


@router.post("/retention/preview")
def retention_preview(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN)),
):
    ps = db.scalar(select(PolicySetting).order_by(PolicySetting.version.desc()).limit(1))
    days = ps.retention_period_days if ps else 1825
    cutoff = utcnow() - timedelta(days=days)

    eligible = list(
        db.scalars(
            select(Student).where(Student.archived.is_(True), Student.updated_at < cutoff)
        )
    )
    return {
        "retention_period_days": days,
        "cutoff_date": cutoff,
        "eligible_count": len(eligible),
        "students": [
            {
                "id": s.id,
                "placement_id": s.placement_id,
                "name": s.name,
                "archived": s.archived,
                "updated_at": s.updated_at,
            }
            for s in eligible
        ],
    }


@router.post("/retention/apply")
def retention_apply(
    body: RetentionApply,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN)),
):
    if not body.confirm:
        raise HTTPException(400, "Explicit confirmation (confirm: true) required to apply retention anonymisation")

    ps = db.scalar(select(PolicySetting).order_by(PolicySetting.version.desc()).limit(1))
    days = ps.retention_period_days if ps else 1825
    cutoff = utcnow() - timedelta(days=days)

    eligible = list(
        db.scalars(
            select(Student).where(Student.archived.is_(True), Student.updated_at < cutoff)
        )
    )

    anonymised_count = 0
    for s in eligible:
        before = services.audit_view(s)
        s.name = f"Anonymised Student {s.id}"
        s.email = f"anonymised_{s.id}@retention.local"
        s.mobile = None
        s.remarks = "Personal data anonymised per data retention policy"
        after = services.audit_view(s)
        audit.log(
            db,
            user,
            "student_retention_anonymise",
            "student",
            s.id,
            before=before,
            after=after,
            ip=client_ip(request),
        )
        anonymised_count += 1

    db.commit()
    return {
        "anonymised_count": anonymised_count,
        "cutoff_date": cutoff,
        "message": f"Successfully anonymised {anonymised_count} archived student record(s).",
    }
