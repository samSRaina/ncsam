from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
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
    request: Request,
    response: Response,
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
    total_count = len(list(db.scalars(stmt)))
    response.headers["X-Total-Count"] = str(total_count)
    rows = list(db.scalars(stmt.order_by(Student.placement_id).limit(limit).offset(offset)))
    # Confidential read audit for listing students with contact data (once per request)
    audit.log(db, user, "read", "student_list", None, after={"count": len(rows)}, ip=client_ip(request))
    db.commit()
    return [services.student_out(db, user, s) for s in rows]


@router.get("/duplicates")
def list_duplicates(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN, E.Role.OFFICER)),
):
    """Lists likely duplicates by email, mobile, and name with batch."""
    students = list(db.scalars(select(Student)))
    by_email = {}
    by_mobile = {}
    by_name_batch = {}
    duplicates = []

    for s in students:
        # Check email
        if s.email in by_email:
            duplicates.append({"field": "email", "value": s.email, "student_ids": [by_email[s.email].id, s.id], "placement_ids": [by_email[s.email].placement_id, s.placement_id]})
        else:
            by_email[s.email] = s

        # Check mobile
        if s.mobile:
            if s.mobile in by_mobile:
                duplicates.append({"field": "mobile", "value": s.mobile, "student_ids": [by_mobile[s.mobile].id, s.id], "placement_ids": [by_mobile[s.mobile].placement_id, s.placement_id]})
            else:
                by_mobile[s.mobile] = s

        # Check name + batch
        key = (s.name.lower().strip(), s.batch.strip())
        if key in by_name_batch:
            duplicates.append({"field": "name_batch", "value": f"{s.name} ({s.batch})", "student_ids": [by_name_batch[key].id, s.id], "placement_ids": [by_name_batch[key].placement_id, s.placement_id]})
        else:
            by_name_batch[key] = s

    return {"duplicates": duplicates, "count": len(duplicates)}



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


@router.get("/{student_id}/attendance")
def student_attendance_history(
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    s = services.get_student_or_404(db, user, student_id)
    from app.models import Attendance, Company, Drive
    stmt = select(Attendance).where(Attendance.student_id == s.id).order_by(Attendance.created_at.desc())
    records = list(db.scalars(stmt))
    out = []
    for a in records:
        comp = db.get(Company, a.company_id)
        drive = db.get(Drive, a.drive_id) if a.drive_id else None
        out.append({
            "id": a.id,
            "student_id": a.student_id,
            "company_id": a.company_id,
            "company_name": comp.name if comp else None,
            "drive_id": a.drive_id,
            "drive_name": drive.name if drive else None,
            "event": a.event,
            "attended": a.attended,
            "emergency_exception": a.emergency_exception,
            "review_status": a.review_status,
            "created_at": a.created_at,
        })
    return out


@router.get("/{student_id}/restrictions")
def student_restrictions(
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    s = services.get_student_or_404(db, user, student_id)
    # Exclusions covered
    from app.models import Attendance, Drive
    active_exclusions = []
    if s.exclusion_drives_remaining > 0:
        # Find the drive that was missed (confirmed absence)
        missed_att = db.scalar(
            select(Attendance)
            .where(Attendance.student_id == s.id, Attendance.review_status == "confirmed")
            .order_by(Attendance.created_at.desc())
            .limit(1)
        )
        since_time = missed_att.created_at if missed_att else s.created_at
        future_drives = list(
            db.scalars(
                select(Drive)
                .where(Drive.drive_date >= since_time)
                .order_by(Drive.drive_date.asc())
                .limit(s.exclusion_drives_remaining)
            )
        )
        active_exclusions.append({
            "reason": f"Excluded from {s.exclusion_drives_remaining} drive(s) due to confirmed unexcused absence",
            "drives_remaining": s.exclusion_drives_remaining,
            "covered_drives": [{"id": d.id, "name": d.name, "date": d.drive_date} for d in future_drives],
        })

    return {
        "student_id": s.id,
        "exclusion_drives_remaining": s.exclusion_drives_remaining,
        "restrictions": active_exclusions,
    }


@router.get("/{student_id}/eligibility")
def check_eligibility(
    student_id: int,
    company_id: int,
    offer_type: E.OfferType,
    ctc_lpa: float | None = None,
    drive_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN, E.Role.OFFICER, E.Role.COORDINATOR)),
):
    """Dry-run of the rule engine: explains allow / block / review for a prospective drive."""
    s = services.get_student_or_404(db, user, student_id)
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    return services.check(db, s, company, offer_type, ctc_lpa, drive_id=drive_id).as_dict()


