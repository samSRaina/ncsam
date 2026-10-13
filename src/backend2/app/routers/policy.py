from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit, services
from app import enums as E
from app.db import get_db, utcnow
from app.models import PolicyReview, PolicySetting, Student, User
from app.schemas import PolicyReviewCreate, PolicyReviewDecision, PolicyRulesUpdate
from app.security import client_ip, current_user, require_roles

policy_router = APIRouter(prefix="/policy", tags=["policy"])


@policy_router.get("/rules")
def get_policy_rules(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN, E.Role.OFFICER)),
):
    row = db.scalar(select(PolicySetting).order_by(PolicySetting.version.desc()).limit(1))
    if not row:
        raise HTTPException(404, "No policy rules found")
    return {
        "version": row.version,
        "a_plus_min": row.a_plus_min,
        "a_min": row.a_min,
        "b_min": row.b_min,
        "b_switch_multiplier": row.b_switch_multiplier,
        "absence_exclusion_window": row.absence_exclusion_window,
        "default_acceptance_window_hours": row.default_acceptance_window_hours,
        "retention_period_days": row.retention_period_days,
        "mfa_required_roles": row.mfa_required_roles,
        "created_at": row.created_at,
    }


@policy_router.put("/rules")
def update_policy_rules(
    body: PolicyRulesUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN)),
):
    # Validation: reject nonsensical values (overlapping or inverted bands, multiplier below 1, window below 0)
    if not (body.a_plus_min > body.a_min > body.b_min > 0):
        raise HTTPException(400, "Category bands must satisfy A+ > A > B > 0")
    if body.b_switch_multiplier < 1.0:
        raise HTTPException(400, "b_switch_multiplier must be >= 1.0")
    if body.absence_exclusion_window < 0:
        raise HTTPException(400, "absence_exclusion_window must be >= 0")
    if body.default_acceptance_window_hours <= 0:
        raise HTTPException(400, "default_acceptance_window_hours must be > 0")

    last = db.scalar(select(PolicySetting).order_by(PolicySetting.version.desc()).limit(1))
    new_version = (last.version + 1) if last else 1
    before = {
        "version": last.version if last else None,
        "a_plus_min": last.a_plus_min if last else None,
        "a_min": last.a_min if last else None,
        "b_min": last.b_min if last else None,
        "b_switch_multiplier": last.b_switch_multiplier if last else None,
        "absence_exclusion_window": last.absence_exclusion_window if last else None,
        "default_acceptance_window_hours": last.default_acceptance_window_hours if last else None,
        "retention_period_days": last.retention_period_days if last else None,
    }
    new_row = PolicySetting(
        version=new_version,
        a_plus_min=body.a_plus_min,
        a_min=body.a_min,
        b_min=body.b_min,
        b_switch_multiplier=body.b_switch_multiplier,
        absence_exclusion_window=body.absence_exclusion_window,
        default_acceptance_window_hours=body.default_acceptance_window_hours,
        retention_period_days=body.retention_period_days,
        mfa_required_roles=body.mfa_required_roles,
        created_by=user.id,
    )
    db.add(new_row)
    db.flush()
    audit.log(
        db,
        user,
        "policy_rules_update",
        "policy_settings",
        new_row.id,
        before=before,
        after=body.model_dump(),
        ip=client_ip(request),
    )
    db.commit()
    return {
        "version": new_row.version,
        "a_plus_min": new_row.a_plus_min,
        "a_min": new_row.a_min,
        "b_min": new_row.b_min,
        "b_switch_multiplier": new_row.b_switch_multiplier,
        "absence_exclusion_window": new_row.absence_exclusion_window,
        "default_acceptance_window_hours": new_row.default_acceptance_window_hours,
        "retention_period_days": new_row.retention_period_days,
        "mfa_required_roles": new_row.mfa_required_roles,
        "created_at": new_row.created_at,
    }


@policy_router.get("/rules/history")
def policy_rules_history(
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN, E.Role.OFFICER)),
):
    rows = list(db.scalars(select(PolicySetting).order_by(PolicySetting.version.desc())))
    response.headers["X-Total-Count"] = str(len(rows))
    return [
        {
            "version": r.version,
            "a_plus_min": r.a_plus_min,
            "a_min": r.a_min,
            "b_min": r.b_min,
            "b_switch_multiplier": r.b_switch_multiplier,
            "absence_exclusion_window": r.absence_exclusion_window,
            "default_acceptance_window_hours": r.default_acceptance_window_hours,
            "retention_period_days": r.retention_period_days,
            "mfa_required_roles": r.mfa_required_roles,
            "created_by": r.created_by,
            "created_at": r.created_at,
        }
        for r in rows
    ]


# ---- 4.4 Manual-review queue and violation flags -----------------------

reviews_router = APIRouter(prefix="/policy/reviews", tags=["policy_reviews"])


@reviews_router.get("")
def list_reviews(
    response: Response,
    status: E.ReviewStatus | None = None,
    kind: E.ReviewKind | None = None,
    student_id: int | None = None,
    course: E.Course | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if user.role in (E.Role.STUDENT, E.Role.RECRUITER):
        raise HTTPException(403, "Forbidden")
    stmt = select(PolicyReview)
    if user.role is E.Role.COORDINATOR:
        stmt = stmt.join(Student, PolicyReview.student_id == Student.id).where(Student.course == user.course)
    elif course:
        stmt = stmt.join(Student, PolicyReview.student_id == Student.id).where(Student.course == course)
    if status:
        stmt = stmt.where(PolicyReview.status == status)
    if kind:
        stmt = stmt.where(PolicyReview.kind == kind)
    if student_id:
        stmt = stmt.where(PolicyReview.student_id == student_id)

    total_count = len(list(db.scalars(stmt)))
    response.headers["X-Total-Count"] = str(total_count)
    rows = list(db.scalars(stmt.order_by(PolicyReview.created_at.desc()).limit(limit).offset(offset)))
    return [
        {
            "id": r.id,
            "student_id": r.student_id,
            "offer_id": r.offer_id,
            "drive_id": r.drive_id,
            "kind": r.kind.value,
            "reason": r.reason,
            "status": r.status.value,
            "raised_by": r.raised_by,
            "decided_by": r.decided_by,
            "decision_reason": r.decision_reason,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        }
        for r in rows
    ]


@reviews_router.get("/{id}")
def get_review(
    id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if user.role in (E.Role.STUDENT, E.Role.RECRUITER):
        raise HTTPException(403, "Forbidden")
    r = db.get(PolicyReview, id)
    if not r:
        raise HTTPException(404, "Policy review not found")
    if user.role is E.Role.COORDINATOR and r.student.course != user.course:
        raise HTTPException(404, "Policy review not found")
    return {
        "id": r.id,
        "student_id": r.student_id,
        "offer_id": r.offer_id,
        "drive_id": r.drive_id,
        "kind": r.kind.value,
        "reason": r.reason,
        "status": r.status.value,
        "raised_by": r.raised_by,
        "decided_by": r.decided_by,
        "decision_reason": r.decision_reason,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


@reviews_router.post("", status_code=201)
def create_review(
    body: PolicyReviewCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN, E.Role.OFFICER)),
):
    s = db.get(Student, body.student_id)
    if not s:
        raise HTTPException(404, "Student not found")
    r = PolicyReview(
        student_id=body.student_id,
        offer_id=body.offer_id,
        drive_id=body.drive_id,
        kind=body.kind,
        reason=body.reason,
        status=E.ReviewStatus.OPEN,
        raised_by=user.id,
    )
    db.add(r)
    db.flush()
    audit.log(
        db,
        user,
        "policy_review_create",
        "policy_review",
        r.id,
        after={"student_id": r.student_id, "kind": r.kind.value, "reason": r.reason},
        ip=client_ip(request),
    )
    db.commit()
    return {
        "id": r.id,
        "student_id": r.student_id,
        "offer_id": r.offer_id,
        "drive_id": r.drive_id,
        "kind": r.kind.value,
        "reason": r.reason,
        "status": r.status.value,
        "raised_by": r.raised_by,
        "created_at": r.created_at,
    }


@reviews_router.post("/{id}/decision")
def decide_review(
    id: int,
    body: PolicyReviewDecision,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN)),
):
    r = db.get(PolicyReview, id)
    if not r:
        raise HTTPException(404, "Policy review not found")
    if r.status != E.ReviewStatus.OPEN:
        raise HTTPException(400, "Review is already decided")
    before = {"status": r.status.value, "decision_reason": r.decision_reason}
    r.status = body.outcome
    r.decided_by = user.id
    r.decision_reason = body.decision_reason
    after = {"status": r.status.value, "decision_reason": r.decision_reason, "decided_by": user.id}
    audit.log(
        db,
        user,
        "policy_review_decision",
        "policy_review",
        r.id,
        before=before,
        after=after,
        ip=client_ip(request),
    )
    db.commit()
    return {
        "id": r.id,
        "status": r.status.value,
        "decided_by": r.decided_by,
        "decision_reason": r.decision_reason,
        "updated_at": r.updated_at,
    }
