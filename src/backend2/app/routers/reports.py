import csv
import io
from collections import defaultdict
from datetime import datetime
from statistics import mean, median

import openpyxl
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit, services
from app import enums as E
from app.config import settings
from app.db import get_db, utcnow
from app.models import AuditLog, Company, Drive, Offer, PolicyReview, Student, User
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


def _csv_safe(v) -> str:
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


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
        c_placed = [s for s in cs if s.id in placed_ids]
        c_offers = [o for o in offers if o.student_id in {s.id for s in cs}]
        c_type_counts = defaultdict(int)
        for s in c_placed:
            st = services.placement_status(by_student[s.id]).value
            c_type_counts[st] += 1
        by_course[c.value] = {
            "students": len(cs),
            "registered": sum(s.registration_status is E.RegistrationStatus.REGISTERED for s in cs),
            "placed_unique": len(c_placed),
            "offers_total": len(c_offers),
            "internship_only": c_type_counts[E.PlacementStatus.INTERNSHIP_ONLY.value],
            "fte_only": c_type_counts[E.PlacementStatus.FTE_ONLY.value],
            "internship_ppo_fte": c_type_counts[E.PlacementStatus.INTERNSHIP_PLUS.value],
        }

    # Additive: by_batch grouping
    batches = sorted({s.batch for s in students})
    by_batch: dict[str, dict] = {}
    for b in batches:
        bs = [s for s in students if s.batch == b]
        b_placed = [s for s in bs if s.id in placed_ids]
        b_offers = [o for o in offers if o.student_id in {s.id for s in bs}]
        b_type_counts = defaultdict(int)
        for s in b_placed:
            st = services.placement_status(by_student[s.id]).value
            b_type_counts[st] += 1
        by_batch[b] = {
            "students": len(bs),
            "registered": sum(s.registration_status is E.RegistrationStatus.REGISTERED for s in bs),
            "eligible": sum(s.eligibility_status is E.EligibilityStatus.ELIGIBLE for s in bs),
            "placed_unique": len(b_placed),
            "unplaced": len(bs) - len(b_placed),
            "offers_total": len(b_offers),
            "internship_only": b_type_counts[E.PlacementStatus.INTERNSHIP_ONLY.value],
            "fte_only": b_type_counts[E.PlacementStatus.FTE_ONLY.value],
            "internship_ppo_fte": b_type_counts[E.PlacementStatus.INTERNSHIP_PLUS.value],
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
        "internship_only": status_counts[E.PlacementStatus.INTERNSHIP_ONLY.value],
        "fte_only": status_counts[E.PlacementStatus.FTE_ONLY.value],
        "internship_ppo_fte": status_counts[E.PlacementStatus.INTERNSHIP_PLUS.value],
        "by_course": by_course,
        "by_batch": by_batch,
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


@router.get("/reports/placements")
def report_placements(
    course: E.Course | None = None,
    batch: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*REPORT_ROLES)),
):
    """Course by batch outcome table with registered, eligible, ineligible, placed, unplaced and the three placement types."""
    sq = select(Student).where(Student.archived.is_(False))
    if user.role is E.Role.COORDINATOR:
        sq = sq.where(Student.course == user.course)
    elif course:
        sq = sq.where(Student.course == course)
    if batch:
        sq = sq.where(Student.batch == batch)
    students = list(db.scalars(sq))
    ids = {s.id for s in students}
    accepted = [o for o in db.scalars(select(Offer)) if o.student_id in ids and o.acceptance_status is E.Acceptance.ACCEPTED]

    by_student: dict[int, list[Offer]] = defaultdict(list)
    for o in accepted:
        by_student[o.student_id].append(o)
    placed_ids = set(by_student)

    # Group by (course, batch)
    table = []
    groups: dict[tuple[str, str], list[Student]] = defaultdict(list)
    for s in students:
        groups[(s.course.value, s.batch)].append(s)

    for (c_val, b_val), s_list in sorted(groups.items()):
        p_list = [s for s in s_list if s.id in placed_ids]
        type_counts = defaultdict(int)
        for s in p_list:
            type_counts[services.placement_status(by_student[s.id]).value] += 1
        table.append({
            "course": c_val,
            "batch": b_val,
            "total_students": len(s_list),
            "registered": sum(s.registration_status is E.RegistrationStatus.REGISTERED for s in s_list),
            "eligible": sum(s.eligibility_status is E.EligibilityStatus.ELIGIBLE for s in s_list),
            "ineligible": sum(s.eligibility_status is E.EligibilityStatus.INELIGIBLE for s in s_list),
            "placed": len(p_list),
            "unplaced": len(s_list) - len(p_list),
            "internship_only": type_counts[E.PlacementStatus.INTERNSHIP_ONLY.value],
            "fte_only": type_counts[E.PlacementStatus.FTE_ONLY.value],
            "internship_ppo_fte": type_counts[E.PlacementStatus.INTERNSHIP_PLUS.value],
        })
    return table


@router.get("/reports/packages")
def report_packages(
    course: E.Course | None = None,
    batch: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*REPORT_ROLES)),
):
    """Highest, average and median FTE CTC (overall, per course and per category) and, separately, stipend statistics by payment period."""
    if user.role not in COMP_ROLES:
        return {"error": "Compensation data restricted for Course Coordinator"}

    sq = select(Student).where(Student.archived.is_(False))
    if course:
        sq = sq.where(Student.course == course)
    if batch:
        sq = sq.where(Student.batch == batch)
    students = list(db.scalars(sq))
    ids = {s.id for s in students}
    accepted = [o for o in db.scalars(select(Offer)) if o.student_id in ids and o.acceptance_status is E.Acceptance.ACCEPTED]

    overall_ctc = [o.ctc_lpa for o in accepted if o.ctc_lpa is not None]
    by_course: dict[str, list[float]] = defaultdict(list)
    by_category: dict[str, list[float]] = defaultdict(list)
    for o in accepted:
        if o.ctc_lpa is not None:
            by_course[o.student.course.value].append(o.ctc_lpa)
            by_category[o.company.category.value].append(o.ctc_lpa)

    stipends_by_period: dict[str, list[float]] = defaultdict(list)
    for o in accepted:
        if o.stipend_amount is not None:
            period = o.stipend_period or "unspecified"
            stipends_by_period[period].append(o.stipend_amount)

    return {
        "overall_fte_ctc": _stats(overall_ctc),
        "by_course": {k: _stats(v) for k, v in by_course.items()},
        "by_category": {k: _stats(v) for k, v in by_category.items()},
        "stipend_by_period": {k: _stats(v) for k, v in stipends_by_period.items()},
    }


@router.get("/reports/companies")
def report_companies(
    company_id: int | None = None,
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*REPORT_ROLES)),
):
    """Per company: category, number of offers, unique students, offer types, and CTC and stipend summaries."""
    cq = select(Company)
    if company_id:
        cq = cq.where(Company.id == company_id)
    companies = list(db.scalars(cq))

    oq = select(Offer)
    if from_:
        oq = oq.where(Offer.offer_date >= from_)
    if to:
        oq = oq.where(Offer.offer_date <= to)
    all_offers = list(db.scalars(oq))

    results = []
    for c in companies:
        c_offers = [o for o in all_offers if o.company_id == c.id]
        if user.role is E.Role.COORDINATOR:
            c_offers = [o for o in c_offers if o.student.course == user.course]

        unique_students = len({o.student_id for o in c_offers})
        type_counts = defaultdict(int)
        for o in c_offers:
            type_counts[o.offer_type.value] += 1

        item = {
            "company_id": c.id,
            "company_name": c.name,
            "category": c.category.value,
            "is_active": c.is_active,
            "total_offers": len(c_offers),
            "unique_students": unique_students,
            "offer_types": dict(type_counts),
        }
        if user.role in COMP_ROLES:
            ctcs = [o.ctc_lpa for o in c_offers if o.ctc_lpa is not None]
            stipends = [o.stipend_amount for o in c_offers if o.stipend_amount is not None]
            item["ctc_summary"] = _stats(ctcs)
            item["stipend_summary"] = _stats(stipends)
        results.append(item)
    return results


@router.get("/reports/switching-eligible")
def report_switching_eligible(
    course: E.Course | None = None,
    batch: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*REPORT_ROLES)),
):
    """Students eligible for subsequent drives under the switching rules."""
    sq = select(Student).where(Student.archived.is_(False), Student.registration_status == E.RegistrationStatus.REGISTERED)
    if user.role is E.Role.COORDINATOR:
        sq = sq.where(Student.course == user.course)
    elif course:
        sq = sq.where(Student.course == course)
    if batch:
        sq = sq.where(Student.batch == batch)
    students = list(db.scalars(sq))

    eligible_list = []
    for s in students:
        l_offers = services.live_offers(db, s.id)
        if not l_offers:
            continue
        # Find best accepted/pending offer with FTE
        fte_offers = [o for o in l_offers if o.offer_type in (E.OfferType.F, E.OfferType.IF)]
        if not fte_offers:
            # Internship-only student: eligible for FTE and I+F drives
            eligible_list.append({
                "student_id": s.id,
                "placement_id": s.placement_id,
                "name": s.name,
                "course": s.course.value,
                "batch": s.batch,
                "current_category": None,
                "current_package_lpa": None,
                "applicable_rule": "Holds only internship: eligible for any FTE or I+F drives",
            })
            continue

        best = max(fte_offers, key=lambda o: ({"C": 0, "B": 1, "A": 2, "A+": 3}[o.company.category.value], o.ctc_lpa or 0))
        cat = best.company.category
        if cat == E.Category.A_PLUS:
            # Out of placement process
            continue
        elif cat == E.Category.A:
            rule_str = "Category A: eligible to switch only to A+ (>= 16 LPA)"
        elif cat == E.Category.B:
            need = (best.ctc_lpa * 1.5) if best.ctc_lpa else 9.0
            rule_str = f"Category B: eligible for >= 1.5x current ({need:.2f} LPA)"
        else:  # Category C
            rule_str = "Category C: eligible to move to higher categories (B, A, A+)"

        item = {
            "student_id": s.id,
            "placement_id": s.placement_id,
            "name": s.name,
            "course": s.course.value,
            "batch": s.batch,
            "current_category": cat.value,
            "applicable_rule": rule_str,
        }
        if user.role in COMP_ROLES:
            item["current_package_lpa"] = best.ctc_lpa
        eligible_list.append(item)
    return eligible_list


@router.get("/reports/pending")
def report_pending(
    course: E.Course | None = None,
    batch: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*REPORT_ROLES)),
):
    """Pending acceptance (with deadlines), pending joining, and pending NOC."""
    oq = select(Offer)
    if user.role is E.Role.COORDINATOR:
        oq = oq.join(Offer.student).where(Offer.student.has(course=user.course))
    elif course:
        oq = oq.join(Offer.student).where(Offer.student.has(course=course))
    if batch:
        oq = oq.join(Offer.student).where(Offer.student.has(batch=batch))

    offers = list(db.scalars(oq))
    now = utcnow()

    pending_acceptance = []
    for o in offers:
        if o.acceptance_status == E.Acceptance.PENDING:
            diff = (o.acceptance_deadline - now).total_seconds() / 3600.0
            pending_acceptance.append({
                "offer_id": o.id,
                "student_id": o.student_id,
                "student_name": o.student.name,
                "company_name": o.company.name,
                "deadline": o.acceptance_deadline,
                "hours_remaining": round(diff, 2),
                "is_expired": diff < 0,
            })

    pending_joining = [
        {
            "offer_id": o.id,
            "student_id": o.student_id,
            "student_name": o.student.name,
            "company_name": o.company.name,
            "offer_date": o.offer_date,
        }
        for o in offers
        if o.acceptance_status == E.Acceptance.ACCEPTED and o.joining_status == E.Joining.PENDING
    ]

    pending_noc = [
        {
            "offer_id": o.id,
            "student_id": o.student_id,
            "student_name": o.student.name,
            "company_name": o.company.name,
            "off_campus": o.off_campus,
            "noc_status": o.noc_status,
        }
        for o in offers
        if o.noc_status in (None, "pending", "requested") and o.off_campus
    ]

    return {
        "pending_acceptance": pending_acceptance,
        "pending_joining": pending_joining,
        "pending_noc": pending_noc,
    }


@router.get("/reports/compliance")
def report_compliance(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*REPORT_ROLES)),
):
    """Open reviews, absence flags, overridden blocks, off-campus offers without NOC."""
    from app.models import Attendance
    rq = select(PolicyReview).where(PolicyReview.status == E.ReviewStatus.OPEN)
    if user.role is E.Role.COORDINATOR:
        rq = rq.join(Student, PolicyReview.student_id == Student.id).where(Student.course == user.course)
    open_reviews = [
        {"id": r.id, "student_id": r.student_id, "kind": r.kind.value, "reason": r.reason, "created_at": r.created_at}
        for r in db.scalars(rq)
    ]

    aq = select(Attendance).where(Attendance.review_status == "open")
    if user.role is E.Role.COORDINATOR:
        aq = aq.join(Student, Attendance.student_id == Student.id).where(Student.course == user.course)
    absence_flags = [
        {"id": a.id, "student_id": a.student_id, "company_id": a.company_id, "event": a.event, "created_at": a.created_at}
        for a in db.scalars(aq)
    ]

    oq = select(Offer).where(Offer.override_reason.isnot(None))
    if user.role is E.Role.COORDINATOR:
        oq = oq.join(Student, Offer.student_id == Student.id).where(Student.course == user.course)
    overridden_blocks = [
        {"id": o.id, "student_id": o.student_id, "company_id": o.company_id, "override_reason": o.override_reason}
        for o in db.scalars(oq)
    ]

    noc_q = select(Offer).where(Offer.off_campus.is_(True), Offer.noc_status.is_(None))
    if user.role is E.Role.COORDINATOR:
        noc_q = noc_q.join(Student, Offer.student_id == Student.id).where(Student.course == user.course)
    off_campus_no_noc = [
        {"id": o.id, "student_id": o.student_id, "company_id": o.company_id, "offer_date": o.offer_date}
        for o in db.scalars(noc_q)
    ]

    return {
        "open_reviews": open_reviews,
        "absence_flags": absence_flags,
        "overridden_blocks": overridden_blocks,
        "off_campus_without_noc": off_campus_no_noc,
    }


# ---- Audit and Verifier -------------------------------------------------------------------


@router.get("/reports/audit/verify")
def verify_audit(db: Session = Depends(get_db), user: User = Depends(require_roles(E.Role.ADMIN))):
    return audit.verify_chain(db)


@router.get("/audit")
def audit_log(
    response: Response,
    entity: str | None = None,
    entity_id: str | None = None,
    actor_id: int | None = None,
    action: str | None = None,
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(E.Role.ADMIN)),
):
    stmt = select(AuditLog)
    if entity:
        stmt = stmt.where(AuditLog.entity == entity)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if actor_id is not None:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if from_:
        stmt = stmt.where(AuditLog.ts >= from_)
    if to:
        stmt = stmt.where(AuditLog.ts <= to)

    total_count = len(list(db.scalars(stmt)))
    response.headers["X-Total-Count"] = str(total_count)
    rows = list(db.scalars(stmt.order_by(AuditLog.id.desc()).limit(min(limit, 500)).offset(offset)))
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
            "prev_hash": r.prev_hash,
            "row_hash": r.row_hash,
            "entry_hash": r.row_hash,
        }
        for r in rows
    ]


# ---- Exports ------------------------------------------------------------------------------


@router.get("/export/students.csv")
def export_students(
    request: Request,
    course: E.Course | None = None,
    batch: str | None = None,
    registration_status: E.RegistrationStatus | None = None,
    eligibility_status: E.EligibilityStatus | None = None,
    include_archived: bool = False,
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
    stmt = select(Student)
    if not include_archived:
        stmt = stmt.where(Student.archived.is_(False))
    if course:
        stmt = stmt.where(Student.course == course)
    if batch:
        stmt = stmt.where(Student.batch == batch)
    if registration_status:
        stmt = stmt.where(Student.registration_status == registration_status)
    if eligibility_status:
        stmt = stmt.where(Student.eligibility_status == eligibility_status)

    students = list(db.scalars(stmt.order_by(Student.placement_id).limit(settings.export_max_rows)))
    n = 0
    for s in students:
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
        db,
        user,
        "export_students",
        "student",
        None,
        after={"rows": n, "format": "csv", "filters": {"course": course, "batch": batch}},
        ip=client_ip(request),
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


@router.get("/export/students.xlsx")
def export_students_xlsx(
    request: Request,
    course: E.Course | None = None,
    batch: str | None = None,
    registration_status: E.RegistrationStatus | None = None,
    eligibility_status: E.EligibilityStatus | None = None,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_WRITE)),
):
    stmt = select(Student)
    if not include_archived:
        stmt = stmt.where(Student.archived.is_(False))
    if course:
        stmt = stmt.where(Student.course == course)
    if batch:
        stmt = stmt.where(Student.batch == batch)
    if registration_status:
        stmt = stmt.where(Student.registration_status == registration_status)
    if eligibility_status:
        stmt = stmt.where(Student.eligibility_status == eligibility_status)

    students = list(db.scalars(stmt.order_by(Student.placement_id).limit(settings.export_max_rows)))
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Students"
    headers = [
        "placement_id", "name", "mobile", "email", "course", "batch",
        "registration", "eligibility", "placement_status",
    ]
    ws.append(headers)
    n = 0
    for s in students:
        row = [
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
        ws.append(row)
        n += 1

    out = io.BytesIO()
    wb.save(out)
    audit.log(
        db,
        user,
        "export_students",
        "student",
        None,
        after={"rows": n, "format": "xlsx", "filters": {"course": course, "batch": batch}},
        ip=client_ip(request),
    )
    db.commit()
    return Response(
        out.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=students.xlsx",
            "Cache-Control": "no-store",
        },
    )


@router.get("/export/offers.csv")
def export_offers_csv(
    request: Request,
    pending_only: bool = False,
    company_id: int | None = None,
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_WRITE)),
):
    stmt = select(Offer)
    if pending_only:
        stmt = stmt.where(Offer.acceptance_status == E.Acceptance.PENDING)
    if company_id:
        stmt = stmt.where(Offer.company_id == company_id)
    if from_:
        stmt = stmt.where(Offer.offer_date >= from_)
    if to:
        stmt = stmt.where(Offer.offer_date <= to)

    offers = list(db.scalars(stmt.order_by(Offer.offer_date.desc()).limit(settings.export_max_rows)))
    buf = io.StringIO()
    w = csv.writer(buf)
    headers = [
        "offer_id", "placement_id", "student_name", "company", "category",
        "offer_type", "acceptance_status", "joining_status", "offer_date",
        "acceptance_deadline", "off_campus", "noc_status"
    ]
    if user.role in COMP_ROLES:
        headers.extend(["ctc_lpa", "stipend_amount", "stipend_period"])
    w.writerow(headers)

    n = 0
    for o in offers:
        row = [
            _csv_safe(x)
            for x in (
                o.id,
                o.student.placement_id,
                o.student.name,
                o.company.name,
                o.company.category.value,
                o.offer_type.value,
                o.acceptance_status.value,
                o.joining_status.value,
                o.offer_date.isoformat(),
                o.acceptance_deadline.isoformat(),
                o.off_campus,
                o.noc_status,
            )
        ]
        if user.role in COMP_ROLES:
            row.extend([_csv_safe(o.ctc_lpa), _csv_safe(o.stipend_amount), _csv_safe(o.stipend_period)])
        w.writerow(row)
        n += 1

    audit.log(
        db,
        user,
        "export_offers",
        "offer",
        None,
        after={"rows": n, "format": "csv", "filters": {"company_id": company_id}},
        ip=client_ip(request),
    )
    db.commit()
    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=offers.csv",
            "Cache-Control": "no-store",
        },
    )


@router.get("/export/offers.xlsx")
def export_offers_xlsx(
    request: Request,
    pending_only: bool = False,
    company_id: int | None = None,
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_WRITE)),
):
    stmt = select(Offer)
    if pending_only:
        stmt = stmt.where(Offer.acceptance_status == E.Acceptance.PENDING)
    if company_id:
        stmt = stmt.where(Offer.company_id == company_id)
    if from_:
        stmt = stmt.where(Offer.offer_date >= from_)
    if to:
        stmt = stmt.where(Offer.offer_date <= to)

    offers = list(db.scalars(stmt.order_by(Offer.offer_date.desc()).limit(settings.export_max_rows)))
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Offers"
    headers = [
        "offer_id", "placement_id", "student_name", "company", "category",
        "offer_type", "acceptance_status", "joining_status", "offer_date",
        "acceptance_deadline", "off_campus", "noc_status"
    ]
    if user.role in COMP_ROLES:
        headers.extend(["ctc_lpa", "stipend_amount", "stipend_period"])
    ws.append(headers)

    n = 0
    for o in offers:
        row = [
            _csv_safe(x)
            for x in (
                o.id,
                o.student.placement_id,
                o.student.name,
                o.company.name,
                o.company.category.value,
                o.offer_type.value,
                o.acceptance_status.value,
                o.joining_status.value,
                o.offer_date.isoformat(),
                o.acceptance_deadline.isoformat(),
                o.off_campus,
                o.noc_status,
            )
        ]
        if user.role in COMP_ROLES:
            row.extend([_csv_safe(o.ctc_lpa), _csv_safe(o.stipend_amount), _csv_safe(o.stipend_period)])
        ws.append(row)
        n += 1

    out = io.BytesIO()
    wb.save(out)
    audit.log(
        db,
        user,
        "export_offers",
        "offer",
        None,
        after={"rows": n, "format": "xlsx", "filters": {"company_id": company_id}},
        ip=client_ip(request),
    )
    db.commit()
    return Response(
        out.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=offers.xlsx",
            "Cache-Control": "no-store",
        },
    )


@router.get("/export/placements.csv")
def export_placements_csv(
    request: Request,
    course: E.Course | None = None,
    batch: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_WRITE)),
):
    table = report_placements(course=course, batch=batch, db=db, user=user)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "course", "batch", "total_students", "registered", "eligible",
        "ineligible", "placed", "unplaced", "internship_only", "fte_only", "internship_ppo_fte"
    ])
    n = 0
    for row in table:
        w.writerow([_csv_safe(row[k]) for k in (
            "course", "batch", "total_students", "registered", "eligible",
            "ineligible", "placed", "unplaced", "internship_only", "fte_only", "internship_ppo_fte"
        )])
        n += 1

    audit.log(
        db,
        user,
        "export_placements",
        "placement_report",
        None,
        after={"rows": n, "format": "csv", "filters": {"course": course, "batch": batch}},
        ip=client_ip(request),
    )
    db.commit()
    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=placements.csv",
            "Cache-Control": "no-store",
        },
    )
