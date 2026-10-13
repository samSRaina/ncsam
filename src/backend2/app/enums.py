from enum import Enum


class Course(str, Enum):
    MTECH_CS = "M.Tech CS"
    MTECH_AIDS = "M.Tech AIDS"
    BTECH_MTECH_CS = "B.Tech-M.Tech CS"
    MSC_CS = "M.Sc CS"
    MSC_DFIS = "M.Sc DFIS"


class RegistrationStatus(str, Enum):
    REGISTERED = "registered"
    DEREGISTERED = "deregistered"
    NOT_REGISTERED = "not_registered"


class EligibilityStatus(str, Enum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    PENDING = "pending_verification"


class OfferType(str, Enum):
    I = "I"  # noqa: E741  internship only
    F = "F"  # FTE only
    IF = "I+F"  # internship + PPO/FTE


class Category(str, Enum):
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"


class PPOStatus(str, Enum):
    NA = "not_applicable"
    PENDING = "pending"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class Acceptance(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"


class Joining(str, Enum):
    PENDING = "pending"
    JOINED = "joined"
    NOT_JOINED = "not_joined"


class PlacementStatus(str, Enum):  # derived, never stored
    UNPLACED = "unplaced"
    INTERNSHIP_ONLY = "internship_only"
    FTE_ONLY = "fte_only"
    INTERNSHIP_PLUS = "internship_plus_ppo_fte"


class Role(str, Enum):
    ADMIN = "admin"
    OFFICER = "officer"
    COORDINATOR = "coordinator"
    RECRUITER = "recruiter"
    STUDENT = "student"


class DriveStatus(str, Enum):
    PLANNED = "planned"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ParticipantStatus(str, Enum):
    INVITED = "invited"
    REGISTERED = "registered"
    ATTENDED = "attended"
    ABSENT = "absent"
    SELECTED = "selected"
    REJECTED = "rejected"


class ReviewStatus(str, Enum):
    OPEN = "open"
    APPROVED = "approved"
    REJECTED = "rejected"
    DISMISSED = "dismissed"


class ReviewKind(str, Enum):
    SWITCHING_CONFLICT = "switching_conflict"
    OFFER_TYPE_CONFLICT = "offer_type_conflict"
    ABSENTEEISM = "absenteeism"
    OFF_CAMPUS_UNREPORTED = "off_campus_unreported"
    DEADLINE_BREACH = "deadline_breach"
    OTHER = "other"

