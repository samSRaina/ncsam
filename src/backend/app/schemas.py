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
    event: str = Field(pattern="^(ppt|test|interview|other)$")
    attended: bool
    emergency_exception: bool = False


class AbsenceReview(Strict):
    outcome: str = Field(pattern="^(confirmed|excused)$")
