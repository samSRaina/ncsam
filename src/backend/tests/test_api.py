from fastapi.testclient import TestClient

from app import audit
from app.db import SessionLocal
from app.main import app
from app.models import AuditLog
from tests.conftest import HDR, PW, client_as

OFFER = {"offer_date": "2026-11-01T10:00:00"}


def _offer(c, env, student, company, t, **kw):
    body = {"student_id": env[student], "company_id": env[company], "offer_type": t, **OFFER, **kw}
    return c.post("/api/offers", json=body)


def test_auth_required_and_csrf_header(env):
    c = TestClient(app)
    assert c.get("/api/students").status_code == 401
    assert c.post("/api/auth/login", json={"username": "a", "password": "b"}).status_code == 403
    assert (
        c.post("/api/auth/login", json={"username": "a", "password": "b"}, headers=HDR).status_code
        == 401
    )


def test_lockout_after_repeated_failures(env):
    c = TestClient(app, headers=HDR)
    for _ in range(5):
        assert (
            c.post("/api/auth/login", json={"username": "officer", "password": "bad"}).status_code
            == 401
        )
    assert (
        c.post("/api/auth/login", json={"username": "officer", "password": PW}).status_code == 429
    )


def test_student_cannot_write_or_see_others(env):
    c = client_as("stu1")
    assert c.get(f"/api/students/{env['s1']}").status_code == 200
    assert c.get(f"/api/students/{env['s2']}").status_code == 404  # IDOR attempt
    assert (
        c.patch(f"/api/students/{env['s1']}", json={"eligibility_status": "eligible"}).status_code
        == 403
    )
    assert c.get("/api/students").status_code == 403
    assert _offer(c, env, "s1", "BCo", "F", ctc_lpa=8).status_code == 403
    assert c.get("/api/reports/summary").status_code == 403


def test_mass_assignment_rejected(env):
    c = client_as("officer")
    r = c.patch(f"/api/students/{env['s1']}", json={"placement_status": "fte_only"})
    assert r.status_code == 422
    r = c.patch(f"/api/students/{env['s1']}", json={"exclusion_drives_remaining": 0})
    assert r.status_code == 422


def test_coordinator_scoped_and_no_compensation(env):
    c = client_as("coord")
    rows = c.get("/api/students").json()
    assert [r["placement_id"] for r in rows] == ["NFSU0001"]
    assert c.get(f"/api/students/{env['s2']}").status_code == 404
    assert "fte_ctc_lpa" not in c.get("/api/reports/summary").json()


def test_recruiter_cannot_browse_students(env):
    c = client_as("rec")
    assert c.get(f"/api/students/{env['s1']}").status_code == 404
    assert c.get("/api/students").status_code == 403


def test_sql_injection_probe_is_inert(env):
    c = client_as("officer")
    for q in ["' OR 1=1 --", "'; DROP TABLE students; --", "%", "_"]:
        r = c.get("/api/students", params={"q": q})
        assert r.status_code == 200 and r.json() == []
    assert len(c.get("/api/students").json()) == 2


def test_duplicate_placement_id_rejected(env):
    c = client_as("officer")
    body = {
        "placement_id": "NFSU0001",
        "name": "Dup Student",
        "email": "dup@x.in",
        "course": "M.Sc CS",
        "batch": "2026-27",
    }
    assert c.post("/api/students", json=body).status_code == 409


def test_policy_enforced_on_offers(env):
    c = client_as("officer")
    assert _offer(c, env, "s1", "ACo", "F", ctc_lpa=12).status_code == 201
    r = _offer(c, env, "s1", "BCo", "F", ctc_lpa=8)
    assert r.status_code == 409
    assert r.json()["detail"]["decision"]["reasons"][0]["code"] == "SWITCH_A"
    assert _offer(c, env, "s1", "PlusCo", "F", ctc_lpa=20).status_code == 201
    # A+ now held: out of process
    assert (
        _offer(
            c, env, "s1", "PlusCo", "F", ctc_lpa=30, offer_date="2026-11-05T10:00:00"
        ).status_code
        == 409
    )


def test_declined_offer_frees_student(env):
    c = client_as("officer")
    oid = _offer(c, env, "s1", "ACo", "F", ctc_lpa=12).json()["id"]
    assert _offer(c, env, "s1", "BCo", "F", ctc_lpa=8).status_code == 409
    assert c.patch(f"/api/offers/{oid}", json={"acceptance_status": "declined"}).status_code == 200
    assert _offer(c, env, "s1", "BCo", "F", ctc_lpa=8).status_code == 201


def test_report_counts_unique_students_not_offers(env):
    c = client_as("officer")
    o1 = _offer(c, env, "s1", "CCo", "I", stipend_amount=20000, stipend_period="monthly").json()[
        "id"
    ]
    o2 = _offer(c, env, "s1", "BCo", "F", ctc_lpa=8, offer_date="2026-11-02T10:00:00").json()["id"]
    for oid in (o1, o2):
        c.patch(f"/api/offers/{oid}", json={"acceptance_status": "accepted"})
    s = c.get("/api/reports/summary").json()
    assert s["students"]["placed_unique"] == 1 and s["offers_total"] == 2
    assert s["fte_ctc_lpa"]["highest"] == 8 and s["internship_stipend"]["highest"] == 20000


def test_mobile_encrypted_at_rest(env):
    from sqlalchemy import text

    from app.db import engine

    with engine.connect() as conn:
        raw = conn.execute(
            text("select mobile from students where id=:i"), {"i": env["s1"]}
        ).scalar()
    assert "9000000001" not in raw
    assert client_as("officer").get(f"/api/students/{env['s1']}").json()["mobile"] == "9000000001"
    assert "mobile" not in client_as("rec").get("/api/companies").json()


def test_audit_chain_detects_tampering(env):
    c = client_as("officer")
    c.patch(f"/api/students/{env['s1']}", json={"remarks": "checked"})
    with SessionLocal() as db:
        assert audit.verify_chain(db)["ok"]
        row = db.query(AuditLog).filter(AuditLog.action == "student_update").one()
        row.after = {**row.after, "eligibility_status": "ineligible"}
        db.commit()
        assert not audit.verify_chain(db)["ok"]


def test_export_is_audited_and_formula_safe(env):
    c = client_as("officer")
    c.patch(f"/api/students/{env['s1']}", json={"name": "=HYPERLINK(1)"})
    r = c.get("/api/export/students.csv")
    assert "'=HYPERLINK(1)" in r.text
    assert client_as("coord").get("/api/export/students.csv").status_code == 403
    admin = client_as("admin")
    assert any(a["action"] == "export_students" for a in admin.get("/api/audit").json())
