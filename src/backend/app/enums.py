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
