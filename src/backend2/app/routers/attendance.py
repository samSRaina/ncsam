from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit, services
from app import enums as E
from app.db import get_db
from app.models import Attendance, Drive, PolicyReview, Student, User
from app.schemas import AbsenceReview, AttendanceIn
from app.security import STAFF_WRITE, client_ip, current_user, require_roles

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.get("")
def list_attendance(
    response: Response,
    student_id: int | None = None,
    company_id: int | None = None,
    drive_id: int | None = None,
    event: str | None = None,
    attended: bool | None = None,
    review_status: str | None = None,
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if user.role is E.Role.STUDENT:
        raise HTTPException(403, "Use /students/{id}/attendance")
    if user.role is E.Role.RECRUITER:
        raise HTTPException(403, "Forbidden")
    stmt = select(Attendance)
    if user.role is E.Role.COORDINATOR:
        stmt = stmt.join(Attendance.student_id == Student.id).where(Student.course == user.course)
    if student_id:
        stmt = stmt.where(Attendance.student_id == student_id)
    if company_id:
        stmt = stmt.where(Attendance.company_id == company_id)
    if drive_id:
        stmt = stmt.where(Attendance.drive_id == drive_id)
    if event:
        stmt = stmt.where(Attendance.event == event)
    if attended is not None:
        stmt = stmt.where(Attendance.attended == attended)
    if review_status:
        stmt = stmt.where(Attendance.review_status == review_status)
    if from_:
        stmt = stmt.where(Attendance.created_at >= from_)
    if to:
        stmt = stmt.where(Attendance.created_at <= to)

    total_count = len(list(db.scalars(stmt)))
    response.headers["X-Total-Count"] = str(total_count)
    rows = list(db.scalars(stmt.order_by(Attendance.created_at.desc()).limit(limit).offset(offset)))
    return [
        {
            "id": a.id,
            "student_id": a.student_id,
            "company_id": a.company_id,
            "drive_id": a.drive_id,
            "event": a.event,
            "attended": a.attended,
            "emergency_exception": a.emergency_exception,
            "review_status": a.review_status,
            "recorded_by": a.recorded_by,
            "created_at": a.created_at,
        }
        for a in rows
    ]


@router.get("/flags")
def list_absence_flags(
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if user.role in (E.Role.STUDENT, E.Role.RECRUITER):
        raise HTTPException(403, "Forbidden")
    stmt = select(Attendance).where(Attendance.review_status == "open")
    if user.role is E.Role.COORDINATOR:
        stmt = stmt.join(Student, Attendance.student_id == Student.id).where(Student.course == user.course)
    flags = list(db.scalars(stmt.order_by(Attendance.created_at.desc())))
    response.headers["X-Total-Count"] = str(len(flags))
    return [
        {
            "id": a.id,
            "student_id": a.student_id,
            "company_id": a.company_id,
            "drive_id": a.drive_id,
            "event": a.event,
            "attended": a.attended,
            "emergency_exception": a.emergency_exception,
            "review_status": a.review_status,
            "created_at": a.created_at,
        }
        for a in flags
    ]


@router.post("", status_code=201)
def record(
    body: AttendanceIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_WRITE)),
):
    s = services.get_student_or_404(db, user, body.student_id)
    if body.drive_id is not None:
        drive = db.get(Drive, body.drive_id)
        if not drive:
            raise HTTPException(404, "Drive not found")
        if drive.company_id != body.company_id:
            raise HTTPException(400, "Drive does not belong to the given company")

    flagged = not body.attended
    a = Attendance(
        student_id=s.id,
        company_id=body.company_id,
        drive_id=body.drive_id,
        event=body.event,
        attended=body.attended,
        emergency_exception=body.emergency_exception,
        review_status="open" if flagged else "none",
        recorded_by=user.id,
    )
    db.add(a)
    db.flush()

    # Automatic PolicyReview creation when absence is flagged
    if flagged:
        rev = PolicyReview(
            student_id=s.id,
            offer_id=None,
            drive_id=body.drive_id,
            kind=E.ReviewKind.ABSENTEEISM,
            reason=f"Unexcused absence flagged for event {body.event} (company {body.company_id})",
            status=E.ReviewStatus.OPEN,
            raised_by=user.id,
        )
        db.add(rev)

    audit.log(
        db,
        user,
        "attendance_record",
        "attendance",
        a.id,
        after={"student_id": s.id, "attended": a.attended, "review": a.review_status, "drive_id": a.drive_id},
        ip=client_ip(request),
    )
    db.commit()
    return {"id": a.id, "review_status": a.review_status}


@router.post("/{attendance_id}/review")
def review(
    attendance_id: int,
    body: AbsenceReview,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_WRITE)),
):
    a = db.get(Attendance, attendance_id)
    if not a or a.review_status != "open":
        raise HTTPException(404, "No open absence flag")
    s = db.get(Student, a.student_id)
    before = {"review": a.review_status, "exclusion": s.exclusion_drives_remaining}
    a.review_status = body.outcome
    cfg = services.get_current_policy_config(db)
    if body.outcome == "confirmed":
        # Confirmed absence without emergency exception excludes the student from next N drives
        if not a.emergency_exception:
            s.exclusion_drives_remaining = cfg.absence_exclusion_window
    audit.log(
        db,
        user,
        "absence_review",
        "attendance",
        a.id,
        before=before,
        after={"review": a.review_status, "exclusion": s.exclusion_drives_remaining},
        ip=client_ip(request),
    )
    db.commit()
    return {
        "review_status": a.review_status,
        "exclusion_drives_remaining": s.exclusion_drives_remaining,
    }

