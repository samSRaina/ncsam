from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit, services
from app import enums as E
from app.db import get_db, utcnow
from app.models import Company, CompanyCriteria, Offer, OfferEvent, PolicyReview, Student, User
from app.policy import Verdict, acceptance_deadline
from app.schemas import (
    CompanyCriteriaIn,
    CompanyIn,
    CompanyUpdate,
    OfferCorrect,
    OfferCreate,
    OfferUpdate,
    ReasonRequired,
)
from app.security import STAFF_WRITE, client_ip, current_user, require_roles

router = APIRouter(tags=["offers"])


@router.get("/companies")
def list_companies(
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if user.role is E.Role.STUDENT:
        raise HTTPException(403, "Forbidden")
    q = select(Company)
    if user.role is E.Role.RECRUITER:
        q = q.where(Company.id == user.company_id)
    companies = list(db.scalars(q))
    response.headers["X-Total-Count"] = str(len(companies))
    return [{"id": c.id, "name": c.name, "category": c.category.value, "is_active": c.is_active} for c in companies]


@router.post("/companies", status_code=201)
def create_company(
    body: CompanyIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_WRITE)),
):
    c = Company(**body.model_dump())
    db.add(c)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Company exists")
    audit.log(
        db,
        user,
        "company_create",
        "company",
        c.id,
        after={"name": c.name, "category": c.category.value},
        ip=client_ip(request),
    )
    db.commit()
    return {"id": c.id, "name": c.name, "category": c.category.value, "is_active": c.is_active}


@router.patch("/companies/{company_id}")
def update_company(
    company_id: int,
    body: CompanyUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_WRITE)),
):
    c = db.get(Company, company_id)
    if not c:
        raise HTTPException(404, "Company not found")
    before = {"name": c.name, "category": c.category.value}
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        c.name = data["name"]
    if "category" in data and data["category"] is not None:
        c.category = data["category"]
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Company name already exists")
    audit.log(
        db,
        user,
        "company_update",
        "company",
        c.id,
        before=before,
        after={"name": c.name, "category": c.category.value},
        ip=client_ip(request),
    )
    db.commit()
    return {"id": c.id, "name": c.name, "category": c.category.value, "is_active": c.is_active}


@router.post("/companies/{company_id}/deactivate")
def deactivate_company(
    company_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_WRITE)),
):
    c = db.get(Company, company_id)
    if not c:
        raise HTTPException(404, "Company not found")
    before = {"is_active": c.is_active}
    c.is_active = False
    audit.log(
        db,
        user,
        "company_deactivate",
        "company",
        c.id,
        before=before,
        after={"is_active": False},
        ip=client_ip(request),
    )
    db.commit()
    return {"id": c.id, "name": c.name, "is_active": False}


@router.get("/companies/{company_id}/eligibility-rules")
def get_company_eligibility_rules(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if user.role is E.Role.STUDENT:
        raise HTTPException(403, "Forbidden")
    if user.role is E.Role.RECRUITER and user.company_id != company_id:
        raise HTTPException(403, "Forbidden")
    c = db.get(Company, company_id)
    if not c:
        raise HTTPException(404, "Company not found")
    rule = db.scalar(
        select(CompanyCriteria).where(
            CompanyCriteria.company_id == company_id, CompanyCriteria.drive_id.is_(None)
        )
    )
    if not rule:
        return {
            "company_id": company_id,
            "allowed_courses": None,
            "allowed_batches": None,
            "min_academic_score": None,
            "requires_registration": True,
            "notes": None,
        }
    return {
        "company_id": company_id,
        "allowed_courses": rule.allowed_courses,
        "allowed_batches": rule.allowed_batches,
        "min_academic_score": rule.min_academic_score,
        "requires_registration": rule.requires_registration,
        "notes": rule.notes,
    }


@router.put("/companies/{company_id}/eligibility-rules")
def update_company_eligibility_rules(
    company_id: int,
    body: CompanyCriteriaIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_WRITE)),
):
    c = db.get(Company, company_id)
    if not c:
        raise HTTPException(404, "Company not found")
    rule = db.scalar(
        select(CompanyCriteria).where(
            CompanyCriteria.company_id == company_id, CompanyCriteria.drive_id.is_(None)
        )
    )
    before = None
    if rule:
        before = {
            "allowed_courses": rule.allowed_courses,
            "allowed_batches": rule.allowed_batches,
            "min_academic_score": rule.min_academic_score,
            "requires_registration": rule.requires_registration,
            "notes": rule.notes,
        }
        rule.allowed_courses = body.allowed_courses
        rule.allowed_batches = body.allowed_batches
        rule.min_academic_score = body.min_academic_score
        rule.requires_registration = body.requires_registration
        rule.notes = body.notes
    else:
        rule = CompanyCriteria(
            company_id=company_id,
            drive_id=None,
            allowed_courses=body.allowed_courses,
            allowed_batches=body.allowed_batches,
            min_academic_score=body.min_academic_score,
            requires_registration=body.requires_registration,
            notes=body.notes,
        )
        db.add(rule)
    db.flush()
    audit.log(
        db,
        user,
        "company_criteria_update",
        "company_criteria",
        rule.id,
        before=before,
        after=body.model_dump(),
        ip=client_ip(request),
    )
    db.commit()
    return {
        "company_id": company_id,
        "allowed_courses": rule.allowed_courses,
        "allowed_batches": rule.allowed_batches,
        "min_academic_score": rule.min_academic_score,
        "requires_registration": rule.requires_registration,
        "notes": rule.notes,
    }



@router.post("/offers", status_code=201)
def create_offer(
    body: OfferCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_WRITE)),
):
    student = services.get_student_or_404(db, user, body.student_id)
    company = db.get(Company, body.company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    # type-level validation
    if body.offer_type is E.OfferType.I and body.ctc_lpa is not None:
        raise HTTPException(422, "Internship-only offers carry a stipend, not CTC")
    if body.offer_type is E.OfferType.F and body.stipend_amount is not None:
        raise HTTPException(422, "FTE-only offers carry CTC, not a stipend")
    if body.offer_type is not E.OfferType.I and body.ctc_lpa is None:
        raise HTTPException(422, "ctc_lpa required for F and I+F offers")

    decision = services.check(db, student, company, body.offer_type, body.ctc_lpa)
    d = decision.as_dict()
    if decision.verdict is Verdict.BLOCK:
        audit.log(
            db,
            user,
            "offer_blocked",
            "student",
            student.id,
            after={"attempt": body.model_dump(mode="json", exclude={"remarks"}), "decision": d},
            ip=client_ip(request),
        )
        db.commit()
        raise HTTPException(409, {"message": "Blocked by placement policy", "decision": d})
    if decision.verdict is Verdict.REVIEW and not body.override_reason:
        raise HTTPException(
            409, {"message": "Manual review required: resubmit with override_reason", "decision": d}
        )

    offer = Offer(
        student_id=student.id,
        company_id=company.id,
        offer_type=body.offer_type,
        ctc_lpa=body.ctc_lpa,
        stipend_amount=body.stipend_amount,
        stipend_period=body.stipend_period,
        ppo_status=E.PPOStatus.PENDING if body.offer_type is E.OfferType.IF else E.PPOStatus.NA,
        offer_date=body.offer_date,
        company_deadline_hours=body.company_deadline_hours,
        acceptance_deadline=acceptance_deadline(body.offer_date, body.company_deadline_hours),
        off_campus=body.off_campus,
        noc_status=body.noc_status,
        remarks=body.remarks,
        policy_verdict=decision.verdict.name,
        policy_reasons=d["reasons"],
        override_reason=body.override_reason,
        created_by=user.id,
    )
    db.add(offer)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Duplicate offer")
    audit.log(
        db,
        user,
        "offer_create",
        "offer",
        offer.id,
        after={
            "student_id": student.id,
            "company": company.name,
            "type": offer.offer_type.value,
            "verdict": offer.policy_verdict,
            "override_reason": offer.override_reason,
        },
        ip=client_ip(request),
    )
    # Log initial OfferEvent
    db.add(
        OfferEvent(
            offer_id=offer.id,
            event_type="created",
            actor_id=user.id,
            reason=body.remarks or "Initial offer creation",
            before=None,
            after={
                "student_id": student.id,
                "company_id": company.id,
                "type": offer.offer_type.value,
                "ctc_lpa": offer.ctc_lpa,
                "stipend_amount": offer.stipend_amount,
                "acceptance_status": offer.acceptance_status.value,
            },
        )
    )
    # 4.4 Automatic policy_reviews creation:
    # "automatically when the engine returns a manual-review outcome, when an absence is flagged, and when an off-campus offer or overridden block is recorded."
    if decision.verdict is Verdict.REVIEW or body.override_reason or body.off_campus:
        rev_kind = E.ReviewKind.OTHER
        if body.off_campus and not body.noc_status:
            rev_kind = E.ReviewKind.OFF_CAMPUS_UNREPORTED
        elif any("SWITCH" in r.get("code", "") for r in d["reasons"]):
            rev_kind = E.ReviewKind.SWITCHING_CONFLICT
        elif any("TYPE" in r.get("code", "") for r in d["reasons"]):
            rev_kind = E.ReviewKind.OFFER_TYPE_CONFLICT

        review_row = PolicyReview(
            student_id=student.id,
            offer_id=offer.id,
            drive_id=None,
            kind=rev_kind,
            reason=f"Offer creation review/override: {body.override_reason or 'Off-campus or policy review'}",
            status=E.ReviewStatus.OPEN,
            raised_by=user.id,
        )
        db.add(review_row)
    db.commit()
    return services.offer_out(user, offer, db=db)



@router.get("/offers")
def list_offers(
    pending_only: bool = False, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    if user.role is E.Role.STUDENT:
        raise HTTPException(403, "Use /students/{id}/offers")
    q = select(Offer)
    if user.role is E.Role.RECRUITER:
        q = q.where(Offer.company_id == user.company_id)
    elif user.role is E.Role.COORDINATOR:
        q = q.join(Offer.student).where(Offer.student.has(course=user.course))
    if pending_only:
        q = q.where(Offer.acceptance_status == E.Acceptance.PENDING)
    return [services.offer_out(user, o) for o in db.scalars(q.order_by(Offer.offer_date.desc()))]


@router.patch("/offers/{offer_id}")
def update_offer(
    offer_id: int,
    body: OfferUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_WRITE)),
):
    o = db.get(Offer, offer_id)
    if not o:
        raise HTTPException(404, "Not found")
    before = {
        "acceptance": o.acceptance_status.value,
        "joining": o.joining_status.value,
        "ppo": o.ppo_status.value,
        "noc": o.noc_status,
    }
    # Rule 4.6: Setting acceptance_status to accepted on an expired offer is refused with a clear error
    if body.acceptance_status == E.Acceptance.ACCEPTED and o.acceptance_status == E.Acceptance.EXPIRED:
        raise HTTPException(400, "Cannot accept an expired offer. Reinstatement by admin required.")

    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(
            o,
            {
                "acceptance_status": "acceptance_status",
                "joining_status": "joining_status",
                "ppo_status": "ppo_status",
            }.get(k, k),
            v,
        )
    after = {
        "acceptance": o.acceptance_status.value,
        "joining": o.joining_status.value,
        "ppo": o.ppo_status.value,
        "noc": o.noc_status,
    }
    event = OfferEvent(
        offer_id=o.id,
        event_type="status_changed",
        actor_id=user.id,
        reason=body.remarks,
        before=before,
        after=after,
    )
    db.add(event)
    audit.log(
        db,
        user,
        "offer_update",
        "offer",
        o.id,
        before=before,
        after=after,
        ip=client_ip(request),
    )
    db.commit()
    return services.offer_out(user, o, db=db)


@router.get("/offers/pending-deadlines")
def pending_deadlines(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if user.role is E.Role.STUDENT:
        raise HTTPException(403, "Forbidden")
    q = select(Offer).where(Offer.acceptance_status == E.Acceptance.PENDING)
    if user.role is E.Role.RECRUITER:
        q = q.where(Offer.company_id == user.company_id)
    elif user.role is E.Role.COORDINATOR:
        q = q.join(Offer.student).where(Offer.student.has(course=user.course))
    now = utcnow()
    rows = list(db.scalars(q.order_by(Offer.acceptance_deadline.asc())))
    out = []
    for o in rows:
        d = services.offer_out(user, o, db=db)
        diff = (o.acceptance_deadline - now).total_seconds() / 3600.0
        d["hours_remaining"] = round(diff, 2)
        out.append(d)
    return out


@router.post("/offers/expire-overdue")
def expire_overdue(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN)),
):
    """Sets overdue pending offers to expired, writes audit per offer, and logs events."""
    now = utcnow()
    overdue_offers = list(
        db.scalars(
            select(Offer).where(
                Offer.acceptance_status == E.Acceptance.PENDING,
                Offer.acceptance_deadline < now,
            )
        )
    )
    expired_count = 0
    for o in overdue_offers:
        before = {"acceptance": o.acceptance_status.value}
        o.acceptance_status = E.Acceptance.EXPIRED
        after = {"acceptance": o.acceptance_status.value}
        db.add(
            OfferEvent(
                offer_id=o.id,
                event_type="expired",
                actor_id=user.id,
                reason="Automatic expiration after acceptance deadline",
                before=before,
                after=after,
            )
        )
        audit.log(
            db,
            user,
            "offer_expired",
            "offer",
            o.id,
            before=before,
            after=after,
            ip=client_ip(request),
        )
        # Check if policy review flag should be raised for deadline breach
        rev = PolicyReview(
            student_id=o.student_id,
            offer_id=o.id,
            drive_id=None,
            kind=E.ReviewKind.DEADLINE_BREACH,
            reason=f"Offer {o.id} expired past acceptance deadline {o.acceptance_deadline.isoformat()}",
            status=E.ReviewStatus.OPEN,
            raised_by=user.id,
        )
        db.add(rev)
        expired_count += 1
    db.commit()
    return {"expired_count": expired_count}


@router.get("/offers/{offer_id}")
def get_offer(
    offer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    o = db.get(Offer, offer_id)
    if not o:
        raise HTTPException(404, "Not found")
    # Same role scoping as the list
    if user.role is E.Role.STUDENT and user.student_id != o.student_id:
        raise HTTPException(404, "Not found")
    if user.role is E.Role.RECRUITER and user.company_id != o.company_id:
        raise HTTPException(404, "Not found")
    if user.role is E.Role.COORDINATOR and o.student.course != user.course:
        raise HTTPException(404, "Not found")
    return services.offer_out(user, o, db=db)


@router.get("/offers/{offer_id}/history")
def get_offer_history(
    offer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    o = db.get(Offer, offer_id)
    if not o:
        raise HTTPException(404, "Not found")
    if user.role is E.Role.STUDENT and user.student_id != o.student_id:
        raise HTTPException(404, "Not found")
    if user.role is E.Role.RECRUITER and user.company_id != o.company_id:
        raise HTTPException(404, "Not found")
    if user.role is E.Role.COORDINATOR and o.student.course != user.course:
        raise HTTPException(404, "Not found")
    events = list(
        db.scalars(
            select(OfferEvent).where(OfferEvent.offer_id == offer_id).order_by(OfferEvent.created_at.asc())
        )
    )
    return [
        {
            "id": e.id,
            "offer_id": e.offer_id,
            "event_type": e.event_type,
            "actor_id": e.actor_id,
            "reason": e.reason,
            "before": e.before,
            "after": e.after,
            "created_at": e.created_at,
        }
        for e in events
    ]


@router.post("/offers/{offer_id}/correct")
def correct_offer(
    offer_id: int,
    body: OfferCorrect,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN)),
):
    o = db.get(Offer, offer_id)
    if not o:
        raise HTTPException(404, "Not found")
    before = {
        "ctc_lpa": o.ctc_lpa,
        "stipend_amount": o.stipend_amount,
        "stipend_period": o.stipend_period,
        "offer_type": o.offer_type.value,
        "acceptance_deadline": o.acceptance_deadline.isoformat() if o.acceptance_deadline else None,
    }
    if body.ctc_lpa is not None:
        o.ctc_lpa = body.ctc_lpa
    if body.stipend_amount is not None:
        o.stipend_amount = body.stipend_amount
    if body.stipend_period is not None:
        o.stipend_period = body.stipend_period
    if body.offer_type is not None:
        o.offer_type = body.offer_type
    if body.acceptance_deadline is not None:
        o.acceptance_deadline = body.acceptance_deadline

    # Re-run the policy engine
    decision = services.check(db, o.student, o.company, o.offer_type, o.ctc_lpa)
    d = decision.as_dict()
    o.policy_verdict = decision.verdict.name
    o.policy_reasons = d["reasons"]

    after = {
        "ctc_lpa": o.ctc_lpa,
        "stipend_amount": o.stipend_amount,
        "stipend_period": o.stipend_period,
        "offer_type": o.offer_type.value,
        "acceptance_deadline": o.acceptance_deadline.isoformat() if o.acceptance_deadline else None,
        "policy_verdict": o.policy_verdict,
    }
    db.add(
        OfferEvent(
            offer_id=o.id,
            event_type="corrected",
            actor_id=user.id,
            reason=body.reason,
            before=before,
            after=after,
        )
    )
    audit.log(
        db,
        user,
        "offer_corrected",
        "offer",
        o.id,
        before=before,
        after=after,
        ip=client_ip(request),
    )
    db.commit()
    return services.offer_out(user, o, db=db)


@router.post("/offers/{offer_id}/withdraw")
def withdraw_offer(
    offer_id: int,
    body: ReasonRequired,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_WRITE)),
):
    o = db.get(Offer, offer_id)
    if not o:
        raise HTTPException(404, "Not found")
    before = {"acceptance": o.acceptance_status.value}
    o.acceptance_status = E.Acceptance.DECLINED
    after = {"acceptance": o.acceptance_status.value}
    db.add(
        OfferEvent(
            offer_id=o.id,
            event_type="withdrawn",
            actor_id=user.id,
            reason=body.reason,
            before=before,
            after=after,
        )
    )
    audit.log(
        db,
        user,
        "offer_withdrawn",
        "offer",
        o.id,
        before=before,
        after=after,
        ip=client_ip(request),
    )
    db.commit()
    return services.offer_out(user, o, db=db)


@router.post("/offers/{offer_id}/reinstate")
def reinstate_offer(
    offer_id: int,
    body: ReasonRequired,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN)),
):
    o = db.get(Offer, offer_id)
    if not o:
        raise HTTPException(404, "Not found")
    if o.acceptance_status != E.Acceptance.EXPIRED:
        raise HTTPException(400, "Only expired offers can be reinstated")
    before = {"acceptance": o.acceptance_status.value}
    o.acceptance_status = E.Acceptance.PENDING
    after = {"acceptance": o.acceptance_status.value}
    db.add(
        OfferEvent(
            offer_id=o.id,
            event_type="reinstated",
            actor_id=user.id,
            reason=body.reason,
            before=before,
            after=after,
        )
    )
    audit.log(
        db,
        user,
        "offer_reinstated",
        "offer",
        o.id,
        before=before,
        after=after,
        ip=client_ip(request),
    )
    db.commit()
    return services.offer_out(user, o, db=db)

