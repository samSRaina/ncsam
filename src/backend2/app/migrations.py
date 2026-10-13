"""Idempotent database migration utility matching project conventions.
Only adds missing tables, missing columns (nullable or defaulted), and seeds initial policy settings.
"""

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.models import PolicySetting


def run_migrations(bind=engine):
    # 1. Create any missing tables defined in metadata
    Base.metadata.create_all(bind)

    # 2. Add any columns that might be missing in existing tables
    inspector = inspect(bind)
    with bind.connect() as conn:
        # Check companies table
        company_cols = {c["name"] for c in inspector.get_columns("companies")}
        if "is_active" not in company_cols:
            conn.execute(text("ALTER TABLE companies ADD COLUMN is_active BOOLEAN DEFAULT 1 NOT NULL"))

        # Check students table
        student_cols = {c["name"] for c in inspector.get_columns("students")}
        if "academic_score" not in student_cols:
            conn.execute(text("ALTER TABLE students ADD COLUMN academic_score FLOAT"))

        # Check attendance table
        attendance_cols = {c["name"] for c in inspector.get_columns("attendance")}
        if "drive_id" not in attendance_cols:
            conn.execute(text("ALTER TABLE attendance ADD COLUMN drive_id INTEGER REFERENCES drives(id)"))

        # Check users table
        user_cols = {c["name"] for c in inspector.get_columns("users")}
        if "mfa_enabled" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN mfa_enabled BOOLEAN DEFAULT 0 NOT NULL"))
        if "mfa_secret" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN mfa_secret VARCHAR(300)"))
        if "mfa_recovery_codes" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN mfa_recovery_codes TEXT"))

        conn.commit()

    # 3. Seed default policy setting (version 1) if not present
    with Session(bind) as db:
        first = db.query(PolicySetting).filter_by(version=1).first()
        if not first:
            default_ps = PolicySetting(
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
            db.add(default_ps)
            db.commit()
