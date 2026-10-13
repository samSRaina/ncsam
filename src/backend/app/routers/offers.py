from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit, services
from app import enums as E
from app.db import get_db
from app.models import Company, Offer, User
from app.policy import Verdict, acceptance_deadline
from app.schemas import CompanyIn, OfferCreate, OfferUpdate
from app.security import STAFF_WRITE, client_ip, current_user, require_roles

router = APIRouter(tags=["offers"])


@router.get("/companies")
def list_companies(db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role is E.Role.STUDENT:
        raise HTTPException(403, "Forbidden")
    q = select(Company)
    if user.role is E.Role.RECRUITER:
        q = q.where(Company.id == user.company_id)
    return [{"id": c.id, "name": c.name, "category": c.category.value} for c in db.scalars(q)]


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
    return {"id": c.id, "name": c.name, "category": c.category.value}


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
    db.commit()
    return services.offer_out(user, offer)


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
    audit.log(
        db,
        user,
        "offer_update",
        "offer",
        o.id,
        before=before,
        after={
            "acceptance": o.acceptance_status.value,
            "joining": o.joining_status.value,
            "ppo": o.ppo_status.value,
            "noc": o.noc_status,
        },
        ip=client_ip(request),
    )
    db.commit()
    return services.offer_out(user, o)
