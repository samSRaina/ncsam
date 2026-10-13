from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import audit, services
from app.db import get_db
from app.models import Attendance, Student, User
from app.schemas import AbsenceReview, AttendanceIn
from app.security import STAFF_WRITE, client_ip, require_roles

router = APIRouter(prefix="/attendance", tags=["attendance"])
EXCLUSION_DRIVES = 3


@router.post("", status_code=201)
def record(
    body: AttendanceIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_WRITE)),
):
    s = services.get_student_or_404(db, user, body.student_id)
    flagged = not body.attended
    a = Attendance(
        student_id=s.id,
        company_id=body.company_id,
        event=body.event,
        attended=body.attended,
        emergency_exception=body.emergency_exception,
        review_status="open" if flagged else "none",
        recorded_by=user.id,
    )
    db.add(a)
    db.flush()
    audit.log(
        db,
        user,
        "attendance_record",
        "attendance",
        a.id,
        after={"student_id": s.id, "attended": a.attended, "review": a.review_status},
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
    if body.outcome == "confirmed":
        s.exclusion_drives_remaining = EXCLUSION_DRIVES
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
