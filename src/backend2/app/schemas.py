import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app import enums as E


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)  # blocks mass assignment


_PID = re.compile(r"^[A-Z0-9][A-Z0-9\-]{3,19}$")
_MOBILE = re.compile(r"^\+?[0-9]{10,13}$")


def _check_mobile(v):
    if v is not None and not _MOBILE.match(v):
        raise ValueError("invalid mobile number")
    return v


class LoginIn(Strict):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class StudentCreate(Strict):
    placement_id: str
    name: str = Field(min_length=2, max_length=200)
    mobile: str | None = None
    email: EmailStr
    course: E.Course
    batch: str = Field(pattern=r"^\d{4}-\d{2}$")
    registration_status: E.RegistrationStatus = E.RegistrationStatus.NOT_REGISTERED
    eligibility_status: E.EligibilityStatus = E.EligibilityStatus.PENDING
    academic_score: float | None = Field(default=None, ge=0, le=100)
    remarks: str | None = Field(default=None, max_length=1000)

    @field_validator("placement_id")
    @classmethod
    def _pid(cls, v: str) -> str:
        v = v.upper()
        if not _PID.match(v):
            raise ValueError("invalid placement id")
        return v

    @field_validator("mobile")
    @classmethod
    def _chk_mobile(cls, v):
        return _check_mobile(v)


class StudentUpdate(Strict):
    """No placement status, no exclusion counters: those are derived or workflow-owned."""

    name: str | None = Field(default=None, min_length=2, max_length=200)
    mobile: str | None = None
    email: EmailStr | None = None
    course: E.Course | None = None
    batch: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    registration_status: E.RegistrationStatus | None = None
    eligibility_status: E.EligibilityStatus | None = None
    academic_score: float | None = Field(default=None, ge=0, le=100)
    remarks: str | None = Field(default=None, max_length=1000)

    @field_validator("mobile")
    @classmethod
    def _chk_mobile(cls, v):
        return _check_mobile(v)


class CompanyIn(Strict):
    name: str = Field(min_length=1, max_length=200)
    category: E.Category


class OfferCreate(Strict):
    student_id: int
    company_id: int
    offer_type: E.OfferType
    ctc_lpa: float | None = Field(default=None, gt=0, le=1000)
    stipend_amount: float | None = Field(default=None, ge=0)
    stipend_period: str | None = Field(default=None, pattern="^(monthly|weekly|total)$")
    offer_date: datetime
    company_deadline_hours: int | None = Field(default=None, gt=0)
    off_campus: bool = False
    noc_status: str | None = Field(default=None, max_length=32)
    remarks: str | None = Field(default=None, max_length=1000)
    override_reason: str | None = Field(default=None, min_length=10, max_length=1000)


class OfferUpdate(Strict):
    acceptance_status: E.Acceptance | None = None
    joining_status: E.Joining | None = None
    ppo_status: E.PPOStatus | None = None
    noc_status: str | None = Field(default=None, max_length=32)
    remarks: str | None = Field(default=None, max_length=1000)


class AttendanceIn(Strict):
    student_id: int
    company_id: int
    drive_id: int | None = None
    event: str = Field(pattern="^(ppt|test|interview|other)$")
    attended: bool
    emergency_exception: bool = False


class AbsenceReview(Strict):
    outcome: str = Field(pattern="^(confirmed|excused)$")


class DriveCreate(Strict):
    company_id: int
    name: str = Field(min_length=1, max_length=200)
    drive_date: datetime
    status: E.DriveStatus = E.DriveStatus.PLANNED
    stages: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=2000)


class DriveUpdate(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    drive_date: datetime | None = None
    status: E.DriveStatus | None = None
    stages: list[str] | None = None
    notes: str | None = Field(default=None, max_length=2000)


class DriveParticipantAdd(Strict):
    student_id: int | None = None
    student_ids: list[int] | None = None
    override_reason: str | None = Field(default=None, min_length=10, max_length=1000)


class CompanyCriteriaIn(Strict):
    allowed_courses: list[str] | None = None
    allowed_batches: list[str] | None = None
    min_academic_score: float | None = Field(default=None, ge=0, le=100)
    requires_registration: bool = True
    notes: str | None = Field(default=None, max_length=1000)


class PolicyRulesUpdate(Strict):
    a_plus_min: float = Field(gt=0)
    a_min: float = Field(gt=0)
    b_min: float = Field(gt=0)
    b_switch_multiplier: float = Field(ge=1.0)
    absence_exclusion_window: int = Field(ge=0)
    default_acceptance_window_hours: int = Field(gt=0)
    retention_period_days: int = Field(ge=1)
    mfa_required_roles: list[str] = Field(default_factory=list)


class PolicyReviewCreate(Strict):
    student_id: int
    offer_id: int | None = None
    drive_id: int | None = None
    kind: E.ReviewKind
    reason: str = Field(min_length=5, max_length=1000)


class PolicyReviewDecision(Strict):
    outcome: E.ReviewStatus
    decision_reason: str = Field(min_length=10, max_length=1000)


class OfferCorrect(Strict):
    ctc_lpa: float | None = Field(default=None, gt=0, le=1000)
    stipend_amount: float | None = Field(default=None, ge=0)
    stipend_period: str | None = Field(default=None, pattern="^(monthly|weekly|total)$")
    offer_type: E.OfferType | None = None
    acceptance_deadline: datetime | None = None
    reason: str = Field(min_length=10, max_length=1000)


class ReasonRequired(Strict):
    reason: str = Field(min_length=10, max_length=1000)


class CompanyUpdate(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: E.Category | None = None


class UserCreate(Strict):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=256)
    role: E.Role
    course: E.Course | None = None
    company_id: int | None = None
    student_id: int | None = None


class UserUpdate(Strict):
    role: E.Role | None = None
    is_active: bool | None = None
    course: E.Course | None = None
    company_id: int | None = None
    student_id: int | None = None


class ChangePasswordIn(Strict):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class ResetPasswordIn(Strict):
    new_password: str = Field(min_length=8, max_length=256)


class MFAEnrollOut(Strict):
    secret: str
    otpauth_url: str


class MFAVerifyIn(Strict):
    code: str = Field(min_length=6, max_length=6)


class MFACodeIn(Strict):
    code: str = Field(min_length=6, max_length=16)


class RetentionApply(Strict):
    confirm: bool = False

