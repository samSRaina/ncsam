"""uv run python -m app.seed   (dev data only; prints generated passwords once)"""

import secrets

from sqlalchemy import select

from app import enums as E
from app.db import Base, SessionLocal, engine
from app.models import Company, Student, User
from app.security import hash_password


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(User).limit(1)):
            print("already seeded")
            return
        cos = [
            Company(name="Acme Cyber", category=E.Category.A_PLUS),
            Company(name="Globex Security", category=E.Category.A),
            Company(name="Initech", category=E.Category.B),
            Company(name="Hooli Labs", category=E.Category.C),
        ]
        db.add_all(cos)
        studs = [
            Student(
                placement_id=f"NFSU{i:04d}",
                name=f"Student {i}",
                mobile=f"98765{i:05d}",
                email=f"student{i}@nfsu.ac.in",
                course=c,
                batch="2026-27",
                registration_status=E.RegistrationStatus.REGISTERED,
                eligibility_status=E.EligibilityStatus.ELIGIBLE,
            )
            for i, c in enumerate(list(E.Course) * 2, start=1)
        ]
        db.add_all(studs)
        db.flush()
        accounts = [
            ("admin", E.Role.ADMIN, {}),
            ("officer", E.Role.OFFICER, {}),
            ("coord_dfis", E.Role.COORDINATOR, {"course": E.Course.MSC_DFIS}),
            ("recruiter_acme", E.Role.RECRUITER, {"company_id": cos[0].id}),
            ("student1", E.Role.STUDENT, {"student_id": studs[0].id}),
        ]
        for name, role, extra in accounts:
            pw = secrets.token_urlsafe(12)
            db.add(User(username=name, password_hash=hash_password(pw), role=role, **extra))
            print(f"{name:16} {role.value:12} {pw}")
        db.commit()


if __name__ == "__main__":
    main()
