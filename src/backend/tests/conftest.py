import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["FIELD_ENCRYPTION_KEY"] = "q2l0gSgDq4dUQeJk5J6kS8mWm1m7bQp1X8o4zq9mQ0s="  # test only

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import enums as E  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Company, Student, User  # noqa: E402
from app.security import hash_password  # noqa: E402

PW = "Test-password-123"
HDR = {"X-Requested-With": "placement-ui"}
PW_HASH = hash_password(PW)  # hash once; argon2 is deliberately slow


@pytest.fixture()
def env():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        cos = [
            Company(name="PlusCo", category=E.Category.A_PLUS),
            Company(name="ACo", category=E.Category.A),
            Company(name="BCo", category=E.Category.B),
            Company(name="CCo", category=E.Category.C),
        ]
        studs = [
            Student(
                placement_id=f"NFSU000{i}",
                name=f"S{i}",
                mobile=f"900000000{i}",
                email=f"s{i}@x.in",
                course=c,
                batch="2026-27",
                registration_status=E.RegistrationStatus.REGISTERED,
                eligibility_status=E.EligibilityStatus.ELIGIBLE,
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
            ("rec", E.Role.RECRUITER, {"company_id": cos[0].id}),
        ]:
            db.add(User(username=name, password_hash=PW_HASH, role=role, **extra))
        db.commit()
        ids = {"s1": studs[0].id, "s2": studs[1].id, **{c.name: c.id for c in cos}}
    return ids


def client_as(username: str) -> TestClient:
    c = TestClient(app, headers=HDR)
    r = c.post("/api/auth/login", json={"username": username, "password": PW})
    assert r.status_code == 200, r.text
    return c
