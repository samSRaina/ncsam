import csv
import io
import re

import openpyxl
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit, services
from app import enums as E
from app.config import settings
from app.db import get_db
from app.models import Student, User
from app.schemas import StudentCreate
from app.security import STAFF_WRITE, client_ip, require_roles

router = APIRouter(prefix="/import", tags=["import"])

CSV_HEADER = [
    "placement_id",
    "name",
    "mobile",
    "email",
    "course",
    "batch",
    "registration_status",
    "eligibility_status",
    "academic_score",
    "remarks",
]

EXAMPLE_ROW = [
    "2026-MTECH-001",
    "Jane Doe",
    "+919876543210",
    "jane.doe@nfsu.ac.in",
    "M.Tech CS",
    "2026-27",
    "registered",
    "eligible",
    "85.5",
    "Direct admission",
]


@router.get("/students/template")
def get_students_template():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_HEADER)
    w.writerow(EXAMPLE_ROW)
    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=students_template.csv",
            "Cache-Control": "no-store",
        },
    )


def _neutralize(val: str | None) -> str | None:
    if not val:
        return val
    s = str(val).strip()
    if s and s[0] in ("=", "+", "-", "@"):
        return "'" + s
    return s


@router.post("/students")
async def import_students(
    request: Request,
    file: UploadFile = File(...),
    dry_run: bool = Query(True),
    partial: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_WRITE)),
):
    contents = await file.read()
    if len(contents) > settings.max_import_size_bytes:
        raise HTTPException(413, f"File size exceeds maximum {settings.max_import_size_bytes} bytes")

    filename = file.filename or ""
    rows = []
    if filename.endswith(".csv"):
        try:
            # Handle UTF-8 with BOM or plain UTF-8
            text_data = contents.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(400, "CSV file must be UTF-8 encoded")
        reader = csv.reader(io.StringIO(text_data))
        for r in reader:
            rows.append(r)
    elif filename.endswith(".xlsx"):
        try:
            wb = openpyxl.load_workbook(io.BytesIO(contents), data_only=True)
            ws = wb.active
            for r in ws.iter_rows(values_only=True):
                rows.append([str(c) if c is not None else "" for c in r])
        except Exception as e:
            raise HTTPException(400, f"Failed to parse XLSX file: {e}")
    else:
        raise HTTPException(400, "Only .csv and .xlsx files are supported")

    if not rows:
        raise HTTPException(400, "File is empty")

    header = [h.strip().lower() for h in rows[0]]
    data_rows = rows[1:]

    if len(data_rows) > settings.max_import_rows:
        raise HTTPException(400, f"Row count {len(data_rows)} exceeds maximum {settings.max_import_rows}")

    # Build field mapping from header
    col_map = {name: i for i, name in enumerate(header)}
    req_fields = ["placement_id", "name", "email", "course", "batch"]
    for rf in req_fields:
        if rf not in col_map:
            raise HTTPException(400, f"Missing required column in header: {rf}")

    # Existing records to check against duplicates
    existing_pids = {pid.upper() for pid in db.scalars(select(Student.placement_id)) if pid}
    existing_emails = {em.lower() for em in db.scalars(select(Student.email)) if em}

    seen_pids = set()
    seen_emails = set()

    results = []
    valid_students_to_create = []

    for idx, r in enumerate(data_rows, start=2):
        row_errors = []
        if not any(r):
            continue  # skip blank line

        def get_val(col_name):
            pos = col_map.get(col_name)
            if pos is not None and pos < len(r):
                v = r[pos].strip()
                return _neutralize(v)
            return None

        pid = get_val("placement_id")
        name = get_val("name")
        email = get_val("email")
        mobile = get_val("mobile")
        course_str = get_val("course")
        batch = get_val("batch")
        reg_status_str = get_val("registration_status") or "not_registered"
        elig_status_str = get_val("eligibility_status") or "pending_verification"
        score_str = get_val("academic_score")
        remarks = get_val("remarks")

        score = None
        if score_str:
            try:
                score = float(score_str)
            except ValueError:
                row_errors.append("academic_score must be a number")

        # Duplicate detection inside file
        if pid:
            norm_pid = pid.upper()
            if norm_pid in seen_pids:
                row_errors.append(f"Duplicate placement_id in file: {pid}")
            elif norm_pid in existing_pids:
                row_errors.append(f"Placement ID already exists in system: {pid}")
            seen_pids.add(norm_pid)

        if email:
            norm_email = email.lower()
            if norm_email in seen_emails:
                row_errors.append(f"Duplicate email in file: {email}")
            elif norm_email in existing_emails:
                row_errors.append(f"Email already exists in system: {email}")
            seen_emails.add(norm_email)

        # Validate through StudentCreate schema
        student_obj = None
        try:
            student_obj = StudentCreate(
                placement_id=pid or "",
                name=name or "",
                mobile=mobile if mobile else None,
                email=email or "",
                course=course_str,
                batch=batch or "",
                registration_status=reg_status_str,
                eligibility_status=elig_status_str,
                academic_score=score,
                remarks=remarks,
            )
        except ValidationError as ve:
            for err in ve.errors():
                row_errors.append(f"{err['loc'][0]}: {err['msg']}")

        if row_errors:
            results.append({"row": idx, "status": "error", "errors": row_errors})
        else:
            results.append({"row": idx, "status": "valid", "placement_id": pid})
            valid_students_to_create.append(student_obj)

    total_rows = len(results)
    valid_count = len(valid_students_to_create)
    error_count = total_rows - valid_count

    committed = False
    if not dry_run:
        # All-or-nothing by default, unless partial=True
        if error_count > 0 and not partial:
            raise HTTPException(400, {
                "message": "Import rejected due to validation errors (all-or-nothing mode)",
                "results": results,
                "summary": {"total": total_rows, "valid": valid_count, "errors": error_count, "committed": False},
            })

        for sc in valid_students_to_create:
            s = Student(**sc.model_dump())
            db.add(s)
            db.flush()
            audit.log(
                db,
                user,
                "student_create",
                "student",
                s.id,
                after=services.audit_view(s),
                ip=client_ip(request),
            )

        audit.log(
            db,
            user,
            "bulk_import_students",
            "student_import",
            None,
            after={
                "filename": filename,
                "total_rows": total_rows,
                "imported_rows": len(valid_students_to_create),
                "partial": partial,
            },
            ip=client_ip(request),
        )
        db.commit()
        committed = True

    return {
        "dry_run": dry_run,
        "committed": committed,
        "summary": {
            "total_rows": total_rows,
            "valid_rows": valid_count,
            "error_rows": error_count,
        },
        "results": results,
    }
