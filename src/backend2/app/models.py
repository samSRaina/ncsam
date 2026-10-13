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
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


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
    academic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
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
    drive_id: Mapped[int | None] = mapped_column(ForeignKey("drives.id"), nullable=True)
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
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret: Mapped[str | None] = mapped_column(EncryptedString(300), nullable=True)
    mfa_recovery_codes: Mapped[str | None] = mapped_column(Text, nullable=True)


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


class PolicySetting(Base):
    __tablename__ = "policy_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    a_plus_min: Mapped[float] = mapped_column(Float, default=16.0)
    a_min: Mapped[float] = mapped_column(Float, default=10.0)
    b_min: Mapped[float] = mapped_column(Float, default=6.0)
    b_switch_multiplier: Mapped[float] = mapped_column(Float, default=1.5)
    absence_exclusion_window: Mapped[int] = mapped_column(Integer, default=3)
    default_acceptance_window_hours: Mapped[int] = mapped_column(Integer, default=24)
    retention_period_days: Mapped[int] = mapped_column(Integer, default=1825)  # 5 years
    mfa_required_roles: Mapped[list | None] = mapped_column(JSON, default=list)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Drive(Base):
    __tablename__ = "drives"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    drive_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[E.DriveStatus] = enum_col(E.DriveStatus, default=E.DriveStatus.PLANNED)
    stages: Mapped[list] = mapped_column(JSON, default=list)  # list of ppt, test, interview, other
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    company: Mapped[Company] = relationship()
    participants: Mapped[list["DriveParticipant"]] = relationship(back_populates="drive", cascade="all, delete-orphan")


class DriveParticipant(Base):
    __tablename__ = "drive_participants"
    __table_args__ = (UniqueConstraint("drive_id", "student_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    drive_id: Mapped[int] = mapped_column(ForeignKey("drives.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    status: Mapped[E.ParticipantStatus] = enum_col(E.ParticipantStatus, default=E.ParticipantStatus.INVITED)
    override_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    drive: Mapped[Drive] = relationship(back_populates="participants")
    student: Mapped[Student] = relationship()


class CompanyCriteria(Base):
    __tablename__ = "company_criteria"
    __table_args__ = (UniqueConstraint("company_id", "drive_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    drive_id: Mapped[int | None] = mapped_column(ForeignKey("drives.id"), nullable=True, index=True)
    allowed_courses: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list of course names or empty for all
    allowed_batches: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list of batch strings
    min_academic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    requires_registration: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class PolicyReview(Base):
    __tablename__ = "policy_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    offer_id: Mapped[int | None] = mapped_column(ForeignKey("offers.id"), nullable=True)
    drive_id: Mapped[int | None] = mapped_column(ForeignKey("drives.id"), nullable=True)
    kind: Mapped[E.ReviewKind] = enum_col(E.ReviewKind)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[E.ReviewStatus] = enum_col(E.ReviewStatus, default=E.ReviewStatus.OPEN)
    raised_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    student: Mapped[Student] = relationship()


class OfferEvent(Base):
    """Append-only history of offer lifecycle events."""
    __tablename__ = "offer_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(32))  # created | status_changed | corrected | withdrawn | expired | reinstated
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str | None] = mapped_column(Text)
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

