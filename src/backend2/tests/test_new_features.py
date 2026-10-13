import io
from datetime import datetime, timedelta

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app import enums as E
from app.db import Base, SessionLocal, engine, utcnow
from app.main import app
from app.models import (
    Attendance,
    Company,
    CompanyCriteria,
    Drive,
    DriveParticipant,
    Offer,
    PolicyReview,
    PolicySetting,
    Student,
    User,
)
from app.security import hash_password

PW = "Test-password-123"
HDR = {"X-Requested-With": "placement-ui"}
PW_HASH = hash_password(PW)


@pytest.fixture()
def setup_env():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        # Default policy setting
        ps = PolicySetting(
            version=1,
            a_plus_min=16.0,
            a_min=10.0,
            b_min=6.0,
            b_switch_multiplier=1.5,
            absence_exclusion_window=3,
            default_acceptance_window_hours=24,
            retention_period_days=1825,
            mfa_required_roles=[],
        )
        db.add(ps)

        cos = [
            Company(name="PlusCo", category=E.Category.A_PLUS),
            Company(name="ACo", category=E.Category.A),
            Company(name="BCo", category=E.Category.B),
            Company(name="CCo", category=E.Category.C),
        ]
        studs = [
            Student(
                placement_id=f"NFSU000{i}",
                name=f"Student {i}",
                mobile=f"987654321{i}",
                email=f"s{i}@nfsu.ac.in",
                course=c,
                batch="2026-27",
                registration_status=E.RegistrationStatus.REGISTERED,
                eligibility_status=E.EligibilityStatus.ELIGIBLE,
                academic_score=85.0 + i,
            )
            for i, c in ((1, E.Course.MSC_DFIS), (2, E.Course.MSC_CS))
        ]
        db.add_all(cos + studs)
        db.flush()

        for name, role, extra in [
            ("admin", E.Role.ADMIN, {}),
            ("officer", E.Role.OFFICER, {}),
            ("coord", E.Role.COORDINATOR, {"course": E.Course.MSC_DFIS}),
            ("stu1", E.Role.STUDENT, {"student_id": studs[0].id}),
            ("stu2", E.Role.STUDENT, {"student_id": studs[1].id}),
            ("rec", E.Role.RECRUITER, {"company_id": cos[0].id}),
        ]:
            db.add(User(username=name, password_hash=PW_HASH, role=role, is_active=True, **extra))
        db.commit()
        return {
            "s1": studs[0].id,
            "s2": studs[1].id,
            "PlusCo": cos[0].id,
            "ACo": cos[1].id,
            "BCo": cos[2].id,
            "CCo": cos[3].id,
        }


def client_as(username: str) -> TestClient:
    c = TestClient(app, headers=HDR)
    r = c.post("/api/auth/login", json={"username": username, "password": PW})
    assert r.status_code == 200, r.text
    return c


# ---- 1. Section 3: Contact-data masking -----------------------------------


def test_contact_masking(setup_env):
    # Admin sees full mobile
    c_admin = client_as("admin")
    r = c_admin.get(f"/api/students/{setup_env['s1']}")
    assert r.status_code == 200
    assert r.json()["mobile"] == "9876543211"

    # Coordinator sees masked mobile (98******11)
    c_coord = client_as("coord")
    r = c_coord.get(f"/api/students/{setup_env['s1']}")
    assert r.status_code == 200
    masked = r.json()["mobile"]
    assert masked.startswith("98") and masked.endswith("11")
    assert "*" in masked

    # Student sees their own full mobile
    c_stu = client_as("stu1")
    r = c_stu.get(f"/api/students/{setup_env['s1']}")
    assert r.status_code == 200
    assert r.json()["mobile"] == "9876543211"


# ---- 2. Section 4.1 & 4.2: Drives and Criteria ---------------------------


def test_drives_and_company_criteria(setup_env):
    c_admin = client_as("admin")
    # Configure company criteria for PlusCo
    crit_payload = {
        "allowed_courses": ["M.Sc DFIS"],
        "allowed_batches": ["2026-27"],
        "min_academic_score": 80.0,
        "requires_registration": True,
        "notes": "Strict DFIS only",
    }
    r = c_admin.put(f"/api/companies/{setup_env['PlusCo']}/eligibility-rules", json=crit_payload)
    assert r.status_code == 200

    # Create a drive
    drive_payload = {
        "company_id": setup_env["PlusCo"],
        "name": "PlusCo Campus Drive 2026",
        "drive_date": (utcnow() + timedelta(days=2)).isoformat(),
        "status": "planned",
        "stages": ["ppt", "test", "interview"],
    }
    r = c_admin.post("/api/drives", json=drive_payload)
    assert r.status_code == 201
    drive_id = r.json()["id"]

    # Student 1 (DFIS) should be added successfully
    r = c_admin.post(f"/api/drives/{drive_id}/participants", json={"student_id": setup_env["s1"]})
    assert r.status_code == 200
    res = r.json()["results"][0]
    assert res["status"] == "added"

    # Student 2 (M.Sc CS) should be blocked by course criteria without override
    r = c_admin.post(f"/api/drives/{drive_id}/participants", json={"student_id": setup_env["s2"]})
    assert r.status_code == 200
    res = r.json()["results"][0]
    assert res["status"] == "blocked"
    assert "COURSE_INELIGIBLE" in str(res["decision"])

    # Student 2 with override should succeed
    r = c_admin.post(
        f"/api/drives/{drive_id}/participants",
        json={"student_id": setup_env["s2"], "override_reason": "Special departmental approval for exceptional candidate"},
    )
    assert r.status_code == 200
    res = r.json()["results"][0]
    assert res["status"] == "added"


# ---- 3. Section 4.3: Configurable Policy Rules ---------------------------


def test_policy_settings_rules(setup_env):
    c_admin = client_as("admin")
    r = c_admin.get("/api/policy/rules")
    assert r.status_code == 200
    assert r.json()["a_plus_min"] == 16.0

    # Non-admin cannot update rules
    c_officer = client_as("officer")
    r = c_officer.put(
        "/api/policy/rules",
        json={
            "a_plus_min": 18.0,
            "a_min": 12.0,
            "b_min": 8.0,
            "b_switch_multiplier": 1.6,
            "absence_exclusion_window": 4,
            "default_acceptance_window_hours": 48,
            "retention_period_days": 1800,
        },
    )
    assert r.status_code == 403

    # Admin updates rules
    r = c_admin.put(
        "/api/policy/rules",
        json={
            "a_plus_min": 18.0,
            "a_min": 12.0,
            "b_min": 8.0,
            "b_switch_multiplier": 1.6,
            "absence_exclusion_window": 4,
            "default_acceptance_window_hours": 48,
            "retention_period_days": 1800,
        },
    )
    assert r.status_code == 200
    assert r.json()["version"] == 2
    assert r.json()["a_plus_min"] == 18.0


# ---- 4. Section 4.4 & 4.5: Attendance, Exclusions, and Reviews -----------


def test_attendance_and_exclusions(setup_env):
    c_officer = client_as("officer")
    # Record absence for student 1 without emergency exception
    att_payload = {
        "student_id": setup_env["s1"],
        "company_id": setup_env["ACo"],
        "event": "interview",
        "attended": False,
        "emergency_exception": False,
    }
    r = c_officer.post("/api/attendance", json=att_payload)
    assert r.status_code == 201
    att_id = r.json()["id"]

    # Confirm absence
    r = c_officer.post(f"/api/attendance/{att_id}/review", json={"outcome": "confirmed"})
    assert r.status_code == 200
    assert r.json()["exclusion_drives_remaining"] == 3

    # Check restrictions endpoint
    r = c_officer.get(f"/api/students/{setup_env['s1']}/restrictions")
    assert r.status_code == 200
    assert r.json()["exclusion_drives_remaining"] == 3
    assert len(r.json()["restrictions"]) == 1

    # Check review queue for the automatically raised absence review
    c_admin = client_as("admin")
    r = c_admin.get("/api/policy/reviews", params={"student_id": setup_env["s1"], "kind": "absenteeism"})
    assert r.status_code == 200
    reviews = r.json()
    assert len(reviews) >= 1
    rev_id = reviews[0]["id"]

    # Decide review
    r = c_admin.post(
        f"/api/policy/reviews/{rev_id}/decision",
        json={"outcome": "approved", "decision_reason": "Medical certificate verified and approved by committee"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


# ---- 5. Section 4.6 & 4.12: Offer Expiry, History, and Correction --------


def test_offer_expiry_and_corrections(setup_env):
    c_officer = client_as("officer")
    offer_date = utcnow() - timedelta(hours=30)
    # Create an offer that expired past 24h
    r = c_officer.post(
        "/api/offers",
        json={
            "student_id": setup_env["s1"],
            "company_id": setup_env["ACo"],
            "offer_type": "F",
            "ctc_lpa": 12.0,
            "offer_date": offer_date.isoformat(),
            "company_deadline_hours": 12,
        },
    )
    assert r.status_code == 201
    offer_id = r.json()["id"]
    assert "acceptance_deadline" in r.json()

    c_admin = client_as("admin")
    # Expire overdue
    r = c_admin.post("/api/offers/expire-overdue")
    assert r.status_code == 200
    assert r.json()["expired_count"] >= 1

    # Check that accepting an expired offer is refused
    r = c_officer.patch(f"/api/offers/{offer_id}", json={"acceptance_status": "accepted"})
    assert r.status_code == 400
    assert "expired" in r.text.lower()

    # Admin reinstates
    r = c_admin.post(
        f"/api/offers/{offer_id}/reinstate",
        json={"reason": "Student requested deadline extension due to campus network issue"},
    )
    assert r.status_code == 200
    assert r.json()["acceptance_status"] == "pending"

    # Admin corrects offer CTC
    r = c_admin.post(
        f"/api/offers/{offer_id}/correct",
        json={"ctc_lpa": 14.5, "reason": "Corrected revised package offered by company"},
    )
    assert r.status_code == 200
    assert r.json()["ctc_lpa"] == 14.5

    # Check history
    r = c_admin.get(f"/api/offers/{offer_id}/history")
    assert r.status_code == 200
    event_types = [e["event_type"] for e in r.json()]
    assert "created" in event_types
    assert "expired" in event_types
    assert "reinstated" in event_types
    assert "corrected" in event_types


# ---- 6. Section 4.7: Bulk Import ------------------------------------------


def test_bulk_import_students(setup_env):
    c_officer = client_as("officer")
    # Test template endpoint
    r = c_officer.get("/api/import/students/template")
    assert r.status_code == 200
    assert "placement_id" in r.text

    csv_content = (
        "placement_id,name,mobile,email,course,batch,registration_status,eligibility_status,academic_score,remarks\n"
        "NFSU2026-901,Alice Smith,9123456789,alice@nfsu.ac.in,M.Tech CS,2026-27,registered,eligible,88.0,Direct\n"
        "NFSU2026-902,Bob Jones,9123456780,bob@nfsu.ac.in,M.Tech AIDS,2026-27,registered,eligible,82.5,Direct\n"
    )

    # Dry run
    files = {"file": ("students.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    r = c_officer.post("/api/import/students?dry_run=true", files=files)
    assert r.status_code == 200
    assert r.json()["summary"]["valid_rows"] == 2
    assert r.json()["committed"] is False

    # Actual commit
    files = {"file": ("students.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    r = c_officer.post("/api/import/students?dry_run=false", files=files)
    assert r.status_code == 200
    assert r.json()["summary"]["valid_rows"] == 2
    assert r.json()["committed"] is True

    # Verify student exists
    r = c_officer.get("/api/students", params={"q": "NFSU2026-901"})
    assert r.status_code == 200
    assert len(r.json()) == 1


# ---- 7. Section 4.8 & 4.9: Reports and Exports ----------------------------


def test_reports_and_exports(setup_env):
    c_admin = client_as("admin")
    # Reports placements
    r = c_admin.get("/api/reports/placements")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # Reports packages
    r = c_admin.get("/api/reports/packages")
    assert r.status_code == 200
    assert "overall_fte_ctc" in r.json()

    # Reports companies
    r = c_admin.get("/api/reports/companies")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # Reports switching-eligible
    r = c_admin.get("/api/reports/switching-eligible")
    assert r.status_code == 200

    # Exports
    r = c_admin.get("/api/export/students.xlsx")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    r = c_admin.get("/api/export/offers.csv")
    assert r.status_code == 200

    r = c_admin.get("/api/export/offers.xlsx")
    assert r.status_code == 200

    r = c_admin.get("/api/export/placements.csv")
    assert r.status_code == 200


# ---- 8. Section 4.10 & 4.11: User Admin & MFA ----------------------------


def test_user_admin_and_mfa(setup_env):
    c_admin = client_as("admin")
    # Create new user
    r = c_admin.post(
        "/api/admin/users",
        json={
            "username": "new_officer",
            "password": "Initial-password-123",
            "role": "officer",
        },
    )
    assert r.status_code == 201
    user_id = r.json()["id"]

    # Change password for self
    r = c_admin.post(
        "/api/auth/change-password",
        json={"current_password": PW, "new_password": "NewAdminPassword-2026!"},
    )
    assert r.status_code == 200

    # MFA Enrollment for admin
    r = c_admin.post("/api/auth/mfa/enroll")
    assert r.status_code == 200
    secret = r.json()["secret"]

    import pyotp
    code = pyotp.TOTP(secret).now()

    # Activate MFA
    r = c_admin.post("/api/auth/mfa/activate", json={"code": code})
    assert r.status_code == 200
    assert r.json()["mfa_enabled"] is True
    recovery_codes = r.json()["recovery_codes"]

    # Next login requires MFA
    c = TestClient(app, headers=HDR)
    r = c.post("/api/auth/login", json={"username": "admin", "password": "NewAdminPassword-2026!"})
    assert r.status_code == 200
    assert r.json().get("mfa_required") is True
    mfa_token = r.json()["mfa_token"]

    # Verify with recovery code
    r = c.post(
        "/api/auth/mfa/verify",
        json={"code": recovery_codes[0]},
        headers={"X-MFA-Token": mfa_token},
    )
    assert r.status_code == 200
    assert r.json()["username"] == "admin"


# ---- 9. Section 4.13 & 4.14: Retention and Audit Hardening ---------------


def test_retention_and_audit(setup_env):
    c_admin = client_as("admin")
    # Verify audit hash chain
    r = c_admin.get("/api/reports/audit/verify")
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # Check audit entries carry hash chain
    r = c_admin.get("/api/audit")
    assert r.status_code == 200
    entries = r.json()
    assert len(entries) > 0
    assert "entry_hash" in entries[0]
    assert "prev_hash" in entries[0]

    # Retention preview
    r = c_admin.post("/api/admin/retention/preview")
    assert r.status_code == 200
    assert "eligible_count" in r.json()

    # Retention apply without confirm should fail
    r = c_admin.post("/api/admin/retention/apply", json={"confirm": False})
    assert r.status_code == 400

    r = c_admin.post("/api/admin/retention/apply", json={"confirm": True})
    assert r.status_code == 200
