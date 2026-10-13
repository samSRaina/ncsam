from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit, services
from app import enums as E
from app.db import get_db
from app.models import Company, Offer, Student, User
from app.schemas import StudentCreate, StudentUpdate
from app.security import STAFF_WRITE, client_ip, current_user, require_roles

router = APIRouter(prefix="/students", tags=["students"])


def _escape_like(q: str) -> str:
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("")
def list_students(
    course: E.Course | None = None,
    batch: str | None = None,
    q: str | None = Query(None, max_length=100),
    registration_status: E.RegistrationStatus | None = None,
    eligibility_status: E.EligibilityStatus | None = None,
    include_archived: bool = False,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN, E.Role.OFFICER, E.Role.COORDINATOR)),
):
    stmt = select(Student)
    if user.role is E.Role.COORDINATOR:
        stmt = stmt.where(Student.course == user.course)  # scope enforced server-side
    elif course:
        stmt = stmt.where(Student.course == course)
    if batch:
        stmt = stmt.where(Student.batch == batch)
    if registration_status:
        stmt = stmt.where(Student.registration_status == registration_status)
    if eligibility_status:
        stmt = stmt.where(Student.eligibility_status == eligibility_status)
    if not include_archived:
        stmt = stmt.where(Student.archived.is_(False))
    if q:
        like = f"%{_escape_like(q)}%"
        stmt = stmt.where(
            Student.name.ilike(like, escape="\\") | Student.placement_id.ilike(like, escape="\\")
        )
    rows = db.scalars(stmt.order_by(Student.placement_id).limit(limit).offset(offset))
    return [services.student_out(db, user, s) for s in rows]


@router.post("", status_code=201)
def create_student(
    body: StudentCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_WRITE)),
):
    s = Student(**body.model_dump())
    db.add(s)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Duplicate placement_id or email")
    audit.log(
        db,
        user,
        "student_create",
        "student",
        s.id,
        after=services.audit_view(s),
        ip=client_ip(request),
    )
    db.commit()
    return services.student_out(db, user, s)


@router.get("/me")
def my_record(db: Session = Depends(get_db), user: User = Depends(require_roles(E.Role.STUDENT))):
    return services.student_out(db, user, services.get_student_or_404(db, user, user.student_id))


@router.get("/{student_id}")
def get_student(
    student_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    s = services.get_student_or_404(db, user, student_id)
    if user.role is not E.Role.STUDENT:
        audit.log(db, user, "student_view", "student", s.id, ip=client_ip(request))
        db.commit()
    return services.student_out(db, user, s)


@router.patch("/{student_id}")
def update_student(
    student_id: int,
    body: StudentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_WRITE)),
):
    s = services.get_student_or_404(db, user, student_id)
    before = services.audit_view(s)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Duplicate email")
    audit.log(
        db,
        user,
        "student_update",
        "student",
        s.id,
        before=before,
        after=services.audit_view(s),
        ip=client_ip(request),
    )
    db.commit()
    return services.student_out(db, user, s)


@router.delete("/{student_id}")
def archive_student(
    student_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN)),
):
    """Soft delete only; offer history is retained. Hard delete = retention procedure (see docs)."""
    s = services.get_student_or_404(db, user, student_id)
    before = services.audit_view(s)
    s.archived = True
    audit.log(
        db,
        user,
        "student_archive",
        "student",
        s.id,
        before=before,
        after=services.audit_view(s),
        ip=client_ip(request),
    )
    db.commit()
    return {"ok": True}


@router.get("/{student_id}/offers")
def student_offers(
    student_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    s = services.get_student_or_404(db, user, student_id)
    offers = db.scalars(select(Offer).where(Offer.student_id == s.id).order_by(Offer.offer_date))
    return [services.offer_out(user, o) for o in offers]


@router.get("/{student_id}/eligibility")
def check_eligibility(
    student_id: int,
    company_id: int,
    offer_type: E.OfferType,
    ctc_lpa: float | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN, E.Role.OFFICER, E.Role.COORDINATOR)),
):
    """Dry-run of the rule engine: explains allow / block / review for a prospective drive."""
    s = services.get_student_or_404(db, user, student_id)
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    return services.check(db, s, company, offer_type, ctc_lpa).as_dict()
