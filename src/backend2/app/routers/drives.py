from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit, services
from app import enums as E
from app.db import get_db, utcnow
from app.models import Company, CompanyCriteria, Drive, DriveParticipant, Student, User
from app.policy import Verdict
from app.schemas import CompanyCriteriaIn, DriveCreate, DriveParticipantAdd, DriveUpdate
from app.security import STAFF_WRITE, client_ip, current_user, require_roles

router = APIRouter(prefix="/drives", tags=["drives"])


@router.get("")
def list_drives(
    response: Response,
    company_id: int | None = None,
    status: E.DriveStatus | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if user.role is E.Role.STUDENT:
        raise HTTPException(403, "Forbidden")
    stmt = select(Drive)
    if user.role is E.Role.RECRUITER:
        stmt = stmt.where(Drive.company_id == user.company_id)
    elif company_id:
        stmt = stmt.where(Drive.company_id == company_id)
    if status:
        stmt = stmt.where(Drive.status == status)

    total_count = len(list(db.scalars(stmt)))
    response.headers["X-Total-Count"] = str(total_count)
    rows = list(db.scalars(stmt.order_by(Drive.drive_date.desc()).limit(limit).offset(offset)))
    return [
        {
            "id": d.id,
            "company_id": d.company_id,
            "company_name": d.company.name if d.company else None,
            "name": d.name,
            "drive_date": d.drive_date,
            "status": d.status.value,
            "stages": d.stages,
            "notes": d.notes if user.role not in (E.Role.RECRUITER,) else None,
            "created_at": d.created_at,
        }
        for d in rows
    ]


@router.post("", status_code=201)
def create_drive(
    body: DriveCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_WRITE)),
):
    c = db.get(Company, body.company_id)
    if not c:
        raise HTTPException(404, "Company not found")
    d = Drive(**body.model_dump())
    db.add(d)
    db.flush()
    audit.log(
        db,
        user,
        "drive_create",
        "drive",
        d.id,
        after={"name": d.name, "company_id": d.company_id, "drive_date": d.drive_date.isoformat(), "status": d.status.value},
        ip=client_ip(request),
    )
    db.commit()
    return {
        "id": d.id,
        "company_id": d.company_id,
        "name": d.name,
        "drive_date": d.drive_date,
        "status": d.status.value,
        "stages": d.stages,
        "notes": d.notes,
        "created_at": d.created_at,
    }


@router.get("/{id}")
def get_drive(
    id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    d = db.get(Drive, id)
    if not d:
        raise HTTPException(404, "Drive not found")
    if user.role is E.Role.STUDENT:
        raise HTTPException(403, "Forbidden")
    if user.role is E.Role.RECRUITER and user.company_id != d.company_id:
        raise HTTPException(403, "Forbidden")
    return {
        "id": d.id,
        "company_id": d.company_id,
        "company_name": d.company.name if d.company else None,
        "name": d.name,
        "drive_date": d.drive_date,
        "status": d.status.value,
        "stages": d.stages,
        "notes": d.notes if user.role not in (E.Role.RECRUITER,) else None,
        "created_at": d.created_at,
    }


@router.patch("/{id}")
def update_drive(
    id: int,
    body: DriveUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_WRITE)),
):
    d = db.get(Drive, id)
    if not d:
        raise HTTPException(404, "Drive not found")
    before = {
        "name": d.name,
        "drive_date": d.drive_date.isoformat(),
        "status": d.status.value,
        "stages": d.stages,
        "notes": d.notes,
    }
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(d, k, v)
    after = {
        "name": d.name,
        "drive_date": d.drive_date.isoformat(),
        "status": d.status.value,
        "stages": d.stages,
        "notes": d.notes,
    }
    audit.log(
        db,
        user,
        "drive_update",
        "drive",
        d.id,
        before=before,
        after=after,
        ip=client_ip(request),
    )
    db.commit()
    return {
        "id": d.id,
        "company_id": d.company_id,
        "name": d.name,
        "drive_date": d.drive_date,
        "status": d.status.value,
        "stages": d.stages,
        "notes": d.notes,
        "created_at": d.created_at,
    }


@router.post("/{id}/cancel")
def cancel_drive(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_WRITE)),
):
    d = db.get(Drive, id)
    if not d:
        raise HTTPException(404, "Drive not found")
    before = {"status": d.status.value}
    d.status = E.DriveStatus.CANCELLED
    audit.log(
        db,
        user,
        "drive_cancel",
        "drive",
        d.id,
        before=before,
        after={"status": d.status.value},
        ip=client_ip(request),
    )
    db.commit()
    return {"id": d.id, "status": d.status.value}


@router.get("/{id}/participants")
def list_drive_participants(
    id: int,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    d = db.get(Drive, id)
    if not d:
        raise HTTPException(404, "Drive not found")
    if user.role is E.Role.STUDENT:
        raise HTTPException(403, "Forbidden")
    if user.role is E.Role.RECRUITER and user.company_id != d.company_id:
        raise HTTPException(403, "Forbidden")

    stmt = select(DriveParticipant).where(DriveParticipant.drive_id == id)
    participants = list(db.scalars(stmt))
    if user.role is E.Role.COORDINATOR:
        # Coordinator reads participants for their own course only
        participants = [p for p in participants if p.student.course == user.course]

    response.headers["X-Total-Count"] = str(len(participants))
    out = []
    for p in participants:
        s = p.student
        item = {
            "id": p.id,
            "drive_id": p.drive_id,
            "student_id": p.student_id,
            "student_name": s.name,
            "student_course": s.course.value,
            "student_batch": s.batch,
            "status": p.status.value,
            "override_reason": p.override_reason,
            "created_at": p.created_at,
        }
        # Recruiter reads only their own company's drives and sees participant names and course, not contact or comp data
        if user.role not in (E.Role.RECRUITER,):
            item["placement_id"] = s.placement_id
            if user.role in (E.Role.ADMIN, E.Role.OFFICER):
                item["mobile"] = s.mobile
                item["academic_score"] = s.academic_score
            elif user.role is E.Role.COORDINATOR:
                item["mobile"] = services.mask_mobile(s.mobile)
        out.append(item)
    return out


@router.post("/{id}/participants")
def add_drive_participants(
    id: int,
    body: DriveParticipantAdd,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_WRITE)),
):
    d = db.get(Drive, id)
    if not d:
        raise HTTPException(404, "Drive not found")
    s_ids = []
    if body.student_id is not None:
        s_ids.append(body.student_id)
    if body.student_ids:
        s_ids.extend(body.student_ids)
    if not s_ids:
        raise HTTPException(400, "student_id or student_ids must be provided")

    results = []
    company = d.company
    for sid in s_ids:
        s = db.get(Student, sid)
        if not s or s.archived:
            results.append({"student_id": sid, "status": "error", "message": "Student not found or archived"})
            continue
        # Check if already added
        existing = db.scalar(
            select(DriveParticipant).where(DriveParticipant.drive_id == id, DriveParticipant.student_id == sid)
        )
        if existing:
            results.append({"student_id": sid, "status": "skipped", "message": "Already a participant"})
            continue

        # Check eligibility (including 4.2 company criteria and 4.5 exclusions)
        # Default drive prospective offer_type is IF or FTE
        decision = services.check(db, s, company, E.OfferType.IF, ctc=None, drive_id=d.id)
        d_dict = decision.as_dict()

        if decision.verdict == Verdict.BLOCK and not body.override_reason:
            results.append({
                "student_id": sid,
                "status": "blocked",
                "message": "Student is blocked by eligibility/company criteria",
                "decision": d_dict,
            })
            continue

        if decision.verdict == Verdict.REVIEW and not body.override_reason:
            results.append({
                "student_id": sid,
                "status": "review_required",
                "message": "Manual review required. Provide override_reason.",
                "decision": d_dict,
            })
            continue

        part = DriveParticipant(
            drive_id=id,
            student_id=sid,
            status=E.ParticipantStatus.INVITED,
            override_reason=body.override_reason,
        )
        db.add(part)
        db.flush()
        audit.log(
            db,
            user,
            "drive_participant_add",
            "drive_participant",
            part.id,
            after={"drive_id": id, "student_id": sid, "override_reason": body.override_reason},
            ip=client_ip(request),
        )
        results.append({
            "student_id": sid,
            "status": "added",
            "participant_id": part.id,
            "decision": d_dict,
        })
    db.commit()
    return {"results": results}


@router.delete("/{id}/participants/{student_id}")
def remove_drive_participant(
    id: int,
    student_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_WRITE)),
):
    part = db.scalar(
        select(DriveParticipant).where(
            DriveParticipant.drive_id == id, DriveParticipant.student_id == student_id
        )
    )
    if not part:
        raise HTTPException(404, "Participant not found")
    before = {"drive_id": id, "student_id": student_id, "status": part.status.value}
    db.delete(part)
    audit.log(
        db,
        user,
        "drive_participant_remove",
        "drive_participant",
        part.id,
        before=before,
        after=None,
        ip=client_ip(request),
    )
    db.commit()
    return {"ok": True}


@router.get("/{id}/eligibility-rules")
def get_drive_eligibility_rules(
    id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    d = db.get(Drive, id)
    if not d:
        raise HTTPException(404, "Drive not found")
    if user.role is E.Role.STUDENT:
        raise HTTPException(403, "Forbidden")
    if user.role is E.Role.RECRUITER and user.company_id != d.company_id:
        raise HTTPException(403, "Forbidden")
    rule = db.scalar(
        select(CompanyCriteria).where(
            CompanyCriteria.company_id == d.company_id, CompanyCriteria.drive_id == id
        )
    )
    if not rule:
        return {
            "drive_id": id,
            "company_id": d.company_id,
            "allowed_courses": None,
            "allowed_batches": None,
            "min_academic_score": None,
            "requires_registration": True,
            "notes": None,
        }
    return {
        "drive_id": id,
        "company_id": d.company_id,
        "allowed_courses": rule.allowed_courses,
        "allowed_batches": rule.allowed_batches,
        "min_academic_score": rule.min_academic_score,
        "requires_registration": rule.requires_registration,
        "notes": rule.notes,
    }


@router.put("/{id}/eligibility-rules")
def update_drive_eligibility_rules(
    id: int,
    body: CompanyCriteriaIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_WRITE)),
):
    d = db.get(Drive, id)
    if not d:
        raise HTTPException(404, "Drive not found")
    rule = db.scalar(
        select(CompanyCriteria).where(
            CompanyCriteria.company_id == d.company_id, CompanyCriteria.drive_id == id
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
            company_id=d.company_id,
            drive_id=id,
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
        "drive_criteria_update",
        "company_criteria",
        rule.id,
        before=before,
        after=body.model_dump(),
        ip=client_ip(request),
    )
    db.commit()
    return {
        "drive_id": id,
        "company_id": d.company_id,
        "allowed_courses": rule.allowed_courses,
        "allowed_batches": rule.allowed_batches,
        "min_academic_score": rule.min_academic_score,
        "requires_registration": rule.requires_registration,
        "notes": rule.notes,
    }
