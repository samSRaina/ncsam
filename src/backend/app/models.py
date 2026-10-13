from datetime import datetime

from cryptography.fernet import Fernet
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app import enums as E
from app.config import settings
from app.db import Base, utcnow

_fernet = Fernet(settings.fernet_key())


class EncryptedString(TypeDecorator):
    """Field-level encryption at rest (Fernet). Not searchable by design."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else _fernet.encrypt(value.encode()).decode()

    def process_result_value(self, value, dialect):
        return None if value is None else _fernet.decrypt(value.encode()).decode()


def enum_col(enum_cls, **kw):
    return mapped_column(
        SAEnum(
            enum_cls,
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
            validate_strings=True,
            length=32,
        ),
        **kw,
    )


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    category: Mapped[E.Category] = enum_col(E.Category)


class Student(Base):
    __tablename__ = "students"
    id: Mapped[int] = mapped_column(primary_key=True)
    placement_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    mobile: Mapped[str | None] = mapped_column(EncryptedString(300))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    course: Mapped[E.Course] = enum_col(E.Course, index=True)
    batch: Mapped[str] = mapped_column(String(9), index=True)  # e.g. "2026-27"
    registration_status: Mapped[E.RegistrationStatus] = enum_col(
        E.RegistrationStatus, default=E.RegistrationStatus.NOT_REGISTERED
    )
    eligibility_status: Mapped[E.EligibilityStatus] = enum_col(
        E.EligibilityStatus, default=E.EligibilityStatus.PENDING
    )
    exclusion_drives_remaining: Mapped[int] = mapped_column(Integer, default=0)
    remarks: Mapped[str | None] = mapped_column(Text)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    offers: Mapped[list["Offer"]] = relationship(back_populates="student")


class Offer(Base):
    """Append-only history. Never overwrite a previous offer event; add rows or update status."""

    __tablename__ = "offers"
    __table_args__ = (UniqueConstraint("student_id", "company_id", "offer_type", "offer_date"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    offer_type: Mapped[E.OfferType] = enum_col(E.OfferType)
    ctc_lpa: Mapped[float | None] = mapped_column(Float)  # annual FTE CTC, LPA
    stipend_amount: Mapped[float | None] = mapped_column(Float)  # internship, kept separate
    stipend_period: Mapped[str | None] = mapped_column(String(16))  # monthly | weekly | total
    ppo_status: Mapped[E.PPOStatus] = enum_col(E.PPOStatus, default=E.PPOStatus.NA)
    acceptance_status: Mapped[E.Acceptance] = enum_col(E.Acceptance, default=E.Acceptance.PENDING)
    joining_status: Mapped[E.Joining] = enum_col(E.Joining, default=E.Joining.PENDING)
    offer_date: Mapped[datetime] = mapped_column(DateTime)
    acceptance_deadline: Mapped[datetime] = mapped_column(DateTime)
    company_deadline_hours: Mapped[int | None] = mapped_column(Integer)
    off_campus: Mapped[bool] = mapped_column(Boolean, default=False)
    noc_status: Mapped[str | None] = mapped_column(String(32))
    policy_verdict: Mapped[str] = mapped_column(String(8))  # ALLOW | REVIEW (BLOCK never saved)
    policy_reasons: Mapped[list] = mapped_column(JSON)
    override_reason: Mapped[str | None] = mapped_column(Text)
    remarks: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    student: Mapped[Student] = relationship(back_populates="offers")
    company: Mapped[Company] = relationship()


class Attendance(Base):
    __tablename__ = "attendance"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    event: Mapped[str] = mapped_column(String(16))  # ppt | test | interview | other
    attended: Mapped[bool] = mapped_column(Boolean)
    emergency_exception: Mapped[bool] = mapped_column(Boolean, default=False)
    # none | open | confirmed | excused
    review_status: Mapped[str] = mapped_column(String(12), default="none")
    recorded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[E.Role] = enum_col(E.Role)
    course: Mapped[E.Course | None] = enum_col(E.Course, nullable=True)  # coordinator scope
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"))  # recruiter scope
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id"))  # student self
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)


class SessionRow(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class AuditLog(Base):
    """Hash-chained: row_hash = sha256(prev_hash + canonical payload)."""

    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    actor_id: Mapped[int | None] = mapped_column(Integer)
    actor_role: Mapped[str | None] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(48), index=True)
    entity: Mapped[str | None] = mapped_column(String(32))
    entity_id: Mapped[str | None] = mapped_column(String(32))
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    ip: Mapped[str | None] = mapped_column(String(45))
    prev_hash: Mapped[str] = mapped_column(String(64))
    row_hash: Mapped[str] = mapped_column(String(64))
