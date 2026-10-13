"""Glue between ORM rows and the pure policy engine, plus visibility/serialisation rules."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import enums as E
from app.models import AuditLog, Company, CompanyCriteria, Offer, PolicySetting, Student, User
from app.policy import CompanyCriteriaRule, LiveOffer, Opportunity, PolicyConfig, StudentState, evaluate
from app.security import COMP_ROLES, CONTACT_ROLES

LIVE = (E.Acceptance.PENDING, E.Acceptance.ACCEPTED)


def mask_mobile(mobile: str | None) -> str | None:
    """Masks mobile number for Course Coordinator: e.g., 98******21.
    Keeps first 2 digits and last 2 digits, masking the middle.
    """
    if not mobile:
        return mobile
    s = str(mobile).strip()
    if len(s) <= 4:
        return "*" * len(s)
    return s[:2] + ("*" * (len(s) - 4)) + s[-2:]


def get_current_policy_config(db: Session) -> PolicyConfig:
    ps = db.scalar(select(PolicySetting).order_by(PolicySetting.version.desc()).limit(1))
    if not ps:
        return PolicyConfig()
    return PolicyConfig(
        a_plus_min=ps.a_plus_min,
        a_min=ps.a_min,
        b_min=ps.b_min,
        b_switch_multiplier=ps.b_switch_multiplier,
        acceptance_window_hours=ps.default_acceptance_window_hours,
        absence_exclusion_window=ps.absence_exclusion_window,
    )


def latest_audit_ref(db: Session, entity: str, entity_id: int | str) -> int | None:
    row = db.scalar(
        select(AuditLog.id)
        .where(AuditLog.entity == entity, AuditLog.entity_id == str(entity_id))
        .order_by(AuditLog.id.desc())
        .limit(1)
    )
    return row


def live_offers(db: Session, student_id: int) -> list[Offer]:
    return list(
        db.scalars(
            select(Offer).where(Offer.student_id == student_id, Offer.acceptance_status.in_(LIVE))
        )
    )


def student_state(db: Session, s: Student, open_flags: int = 0) -> StudentState:
    return StudentState(
        registration=s.registration_status,
        eligibility=s.eligibility_status,
        exclusion_drives_remaining=s.exclusion_drives_remaining,
        open_absence_flags=open_flags,
        live_offers=tuple(
            LiveOffer(o.offer_type, o.company.category, o.ctc_lpa) for o in live_offers(db, s.id)
        ),
        course=s.course.value if s.course else None,
        batch=s.batch,
        academic_score=s.academic_score,
    )


def open_flags(db: Session, student_id: int) -> int:
    from app.models import Attendance

    return len(
        list(
            db.scalars(
                select(Attendance.id).where(
                    Attendance.student_id == student_id, Attendance.review_status == "open"
                )
            )
        )
    )


def check(
    db: Session,
    s: Student,
    company: Company,
    offer_type: E.OfferType,
    ctc: float | None,
    drive_id: int | None = None,
):
    cfg = get_current_policy_config(db)
    crit_rule = None
    # Lookup drive-level criteria first, then company-level
    crit = None
    if drive_id:
        crit = db.scalar(
            select(CompanyCriteria).where(
                CompanyCriteria.company_id == company.id, CompanyCriteria.drive_id == drive_id
            )
        )
    if not crit:
        crit = db.scalar(
            select(CompanyCriteria).where(
                CompanyCriteria.company_id == company.id, CompanyCriteria.drive_id.is_(None)
            )
        )
    if crit:
        crit_rule = CompanyCriteriaRule(
            allowed_courses=crit.allowed_courses,
            allowed_batches=crit.allowed_batches,
            min_academic_score=crit.min_academic_score,
            requires_registration=crit.requires_registration,
        )

    opp = Opportunity(offer_type, company.category, ctc, criteria=crit_rule)
    return evaluate(student_state(db, s, open_flags(db, s.id)), opp, cfg=cfg)


def placement_status(offers: list[Offer]) -> E.PlacementStatus:
    """Derived from live offers, never stored, so it cannot be tampered with directly."""
    types = {o.offer_type for o in offers}
    if not types:
        return E.PlacementStatus.UNPLACED
    if E.OfferType.IF in types or {E.OfferType.I, E.OfferType.F} <= types:
        return E.PlacementStatus.INTERNSHIP_PLUS
    return (
        E.PlacementStatus.INTERNSHIP_ONLY if E.OfferType.I in types else E.PlacementStatus.FTE_ONLY
    )


# ---- visibility ---------------------------------------------------------------------------


def can_see_student(user: User, s: Student) -> bool:
    if user.role in (E.Role.ADMIN, E.Role.OFFICER):
        return True
    if user.role is E.Role.COORDINATOR:
        return user.course == s.course
    if user.role is E.Role.STUDENT:
        return user.student_id == s.id
    return False  # recruiters never browse the student table


def get_student_or_404(db: Session, user: User, student_id: int) -> Student:
    s = db.get(Student, student_id)
    if not s or not can_see_student(user, s):
        raise HTTPException(404, "Not found")  # 404 not 403: no record enumeration
    return s


def student_out(db: Session, user: User, s: Student) -> dict:
    d = {
        "id": s.id,
        "placement_id": s.placement_id,
        "name": s.name,
        "email": s.email,
        "course": s.course.value,
        "batch": s.batch,
        "registration_status": s.registration_status.value,
        "eligibility_status": s.eligibility_status.value,
        "placement_status": placement_status(live_offers(db, s.id)).value,
        "exclusion_drives_remaining": s.exclusion_drives_remaining,
        "academic_score": s.academic_score if user.role in (E.Role.ADMIN, E.Role.OFFICER) else None,
        "archived": s.archived,
        "audit_ref": latest_audit_ref(db, "student", s.id),
    }
    own = user.role is E.Role.STUDENT and user.student_id == s.id
    if user.role in (E.Role.ADMIN, E.Role.OFFICER) or own:
        d["mobile"] = s.mobile
    elif user.role is E.Role.COORDINATOR:
        d["mobile"] = mask_mobile(s.mobile)
    if user.role in (E.Role.ADMIN, E.Role.OFFICER):
        d["remarks"] = s.remarks
    return d


def offer_out(user: User, o: Offer, db: Session | None = None) -> dict:
    d = {
        "id": o.id,
        "student_id": o.student_id,
        "company_id": o.company_id,
        "company": o.company.name,
        "category": o.company.category.value,
        "offer_type": o.offer_type.value,
        "ppo_status": o.ppo_status.value,
        "acceptance_status": o.acceptance_status.value,
        "joining_status": o.joining_status.value,
        "offer_date": o.offer_date,
        "acceptance_deadline": o.acceptance_deadline,
        "off_campus": o.off_campus,
        "noc_status": o.noc_status,
        "policy_verdict": o.policy_verdict,
        "policy_reasons": o.policy_reasons,
    }
    if db is not None:
        d["audit_ref"] = latest_audit_ref(db, "offer", o.id)
    own = user.role is E.Role.STUDENT and user.student_id == o.student_id
    rec = user.role is E.Role.RECRUITER and user.company_id == o.company_id
    if user.role in COMP_ROLES or own or rec:
        d.update(
            ctc_lpa=o.ctc_lpa, stipend_amount=o.stipend_amount, stipend_period=o.stipend_period
        )
    return d


def audit_view(s: Student) -> dict:
    """What goes in audit before/after: no raw PII duplicated into the log."""
    return {
        "placement_id": s.placement_id,
        "name": s.name,
        "email": s.email,
        "mobile_last4": (s.mobile or "")[-4:],
        "course": s.course.value,
        "batch": s.batch,
        "registration_status": s.registration_status.value,
        "eligibility_status": s.eligibility_status.value,
        "archived": s.archived,
    }

