import csv
import io
from collections import defaultdict
from statistics import mean, median

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit, services
from app import enums as E
from app.db import get_db
from app.models import AuditLog, Offer, Student, User
from app.security import COMP_ROLES, STAFF_WRITE, client_ip, require_roles

router = APIRouter(tags=["reports"])
REPORT_ROLES = (E.Role.ADMIN, E.Role.OFFICER, E.Role.COORDINATOR)


def _stats(vals: list[float]) -> dict:
    return (
        {
            "count": len(vals),
            "highest": max(vals),
            "average": round(mean(vals), 2),
            "median": median(vals),
        }
        if vals
        else {"count": 0, "highest": None, "average": None, "median": None}
    )


@router.get("/reports/summary")
def summary(db: Session = Depends(get_db), user: User = Depends(require_roles(*REPORT_ROLES))):
    sq = select(Student).where(Student.archived.is_(False))
    if user.role is E.Role.COORDINATOR:
        sq = sq.where(Student.course == user.course)
    students = list(db.scalars(sq))
    ids = {s.id for s in students}
    offers = [o for o in db.scalars(select(Offer)) if o.student_id in ids]
    accepted = [o for o in offers if o.acceptance_status is E.Acceptance.ACCEPTED]

    # "placed" = at least one ACCEPTED offer. Unique students counted apart from offers.
    by_student: dict[int, list[Offer]] = defaultdict(list)
    for o in accepted:
        by_student[o.student_id].append(o)
    placed_ids = set(by_student)
    status_counts: dict[str, int] = defaultdict(int)
    for sid, os_ in by_student.items():
        status_counts[services.placement_status(os_).value] += 1

    by_course: dict[str, dict] = {}
    for c in E.Course:
        cs = [s for s in students if s.course == c]
        by_course[c.value] = {
            "students": len(cs),
            "registered": sum(s.registration_status is E.RegistrationStatus.REGISTERED for s in cs),
            "placed_unique": sum(s.id in placed_ids for s in cs),
            "offers_total": sum(o.student_id in {s.id for s in cs} for o in offers),
        }
    out = {
        "students": {
            "total": len(students),
            "registered": sum(
                s.registration_status is E.RegistrationStatus.REGISTERED for s in students
            ),
            "eligible": sum(s.eligibility_status is E.EligibilityStatus.ELIGIBLE for s in students),
            "ineligible": sum(
                s.eligibility_status is E.EligibilityStatus.INELIGIBLE for s in students
            ),
            "placed_unique": len(placed_ids),
            "unplaced": len(students) - len(placed_ids),
        },
        "offers_total": len(offers),
        "placement_status_counts": dict(status_counts),
        "by_course": by_course,
        "pending": {
            "offer_acceptance": sum(o.acceptance_status is E.Acceptance.PENDING for o in offers),
            "joining": sum(
                o.acceptance_status is E.Acceptance.ACCEPTED
                and o.joining_status is E.Joining.PENDING
                for o in offers
            ),
            "policy_review_cases": sum(o.policy_verdict == "REVIEW" for o in offers),
        },
    }
    if user.role in COMP_ROLES:  # compensation stays out of coordinator view
        best_ctc = [
            max(o.ctc_lpa for o in os_ if o.ctc_lpa)
            for os_ in by_student.values()
            if any(o.ctc_lpa for o in os_)
        ]
        stipends = [o.stipend_amount for o in accepted if o.stipend_amount]
        out["fte_ctc_lpa"] = _stats(best_ctc)  # per unique student (best accepted FTE CTC)
        out["internship_stipend"] = _stats(stipends)  # reported separately, never mixed with CTC
        comp: dict[str, dict] = {}
        for o in offers:
            c = comp.setdefault(
                o.company.name, {"category": o.company.category.value, "offers": 0, "ctcs": []}
            )
            c["offers"] += 1
            if o.ctc_lpa:
                c["ctcs"].append(o.ctc_lpa)
        out["company_wise"] = comp
    return out


@router.get("/reports/audit/verify")
def verify_audit(db: Session = Depends(get_db), user: User = Depends(require_roles(E.Role.ADMIN))):
    return audit.verify_chain(db)


@router.get("/audit")
def audit_log(
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN)),
):
    rows = db.scalars(
        select(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 500)).offset(offset)
    )
    return [
        {
            "id": r.id,
            "ts": r.ts,
            "actor_id": r.actor_id,
            "actor_role": r.actor_role,
            "action": r.action,
            "entity": r.entity,
            "entity_id": r.entity_id,
            "before": r.before,
            "after": r.after,
            "ip": r.ip,
        }
        for r in rows
    ]


def _csv_safe(v) -> str:
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s  # CSV/formula injection


@router.get("/export/students.csv")
def export_students(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_WRITE)),
):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "placement_id",
            "name",
            "mobile",
            "email",
            "course",
            "batch",
            "registration",
            "eligibility",
            "placement_status",
        ]
    )
    n = 0
    for s in db.scalars(select(Student).where(Student.archived.is_(False))):
        w.writerow(
            [
                _csv_safe(x)
                for x in (
                    s.placement_id,
                    s.name,
                    s.mobile,
                    s.email,
                    s.course.value,
                    s.batch,
                    s.registration_status.value,
                    s.eligibility_status.value,
                    services.placement_status(services.live_offers(db, s.id)).value,
                )
            ]
        )
        n += 1
    audit.log(
        db, user, "export_students", "student", None, after={"rows": n}, ip=client_ip(request)
    )
    db.commit()
    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=students.csv",
            "Cache-Control": "no-store",
        },
    )
