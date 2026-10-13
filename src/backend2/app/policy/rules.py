"""Pure policy engine. No DB, no FastAPI: input dataclasses in, Decision out.

Every verdict carries machine-readable reasons so the UI can explain
"allowed / blocked / referred for manual review". Thresholds live in PolicyConfig.
See README "Policy assumptions" for the places where the guidelines are ambiguous.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum
from math import inf

from app.enums import Category, EligibilityStatus, OfferType, RegistrationStatus


class Verdict(IntEnum):
    ALLOW = 0
    REVIEW = 1
    BLOCK = 2


@dataclass(frozen=True)
class PolicyConfig:
    a_plus_min: float = 16.0
    a_min: float = 10.0
    b_min: float = 6.0
    b_switch_multiplier: float = 1.5
    acceptance_window_hours: int = 24
    absence_exclusion_window: int = 3


DEFAULT_CONFIG = PolicyConfig()

_RANK = {Category.C: 0, Category.B: 1, Category.A: 2, Category.A_PLUS: 3}


def _bounds(cat: Category, cfg: PolicyConfig) -> tuple[float, float]:
    return {
        Category.A_PLUS: (cfg.a_plus_min, inf),
        Category.A: (cfg.a_min, cfg.a_plus_min),
        Category.B: (cfg.b_min, cfg.a_min),
        Category.C: (0.0, cfg.b_min),
    }[cat]


def category_from_ctc(ctc_lpa: float, cfg: PolicyConfig = DEFAULT_CONFIG) -> Category:
    if ctc_lpa >= cfg.a_plus_min:
        return Category.A_PLUS
    if ctc_lpa >= cfg.a_min:
        return Category.A
    if ctc_lpa >= cfg.b_min:
        return Category.B
    return Category.C


def has_fte(t: OfferType) -> bool:
    return t in (OfferType.F, OfferType.IF)


@dataclass(frozen=True)
class LiveOffer:
    """An offer that still counts: acceptance is pending or accepted."""

    offer_type: OfferType
    category: Category
    ctc_lpa: float | None = None


@dataclass(frozen=True)
class StudentState:
    registration: RegistrationStatus
    eligibility: EligibilityStatus
    exclusion_drives_remaining: int = 0
    open_absence_flags: int = 0
    live_offers: tuple[LiveOffer, ...] = ()
    course: str | None = None
    batch: str | None = None
    academic_score: float | None = None


@dataclass(frozen=True)
class CompanyCriteriaRule:
    allowed_courses: list[str] | None = None
    allowed_batches: list[str] | None = None
    min_academic_score: float | None = None
    requires_registration: bool = True


@dataclass(frozen=True)
class Opportunity:
    offer_type: OfferType
    category: Category
    ctc_lpa: float | None = None
    criteria: CompanyCriteriaRule | None = None


@dataclass(frozen=True)
class Reason:
    code: str
    verdict: Verdict
    message: str


@dataclass
class Decision:
    verdict: Verdict
    reasons: list[Reason] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict.name,
            "reasons": [
                {"code": r.code, "verdict": r.verdict.name, "message": r.message}
                for r in self.reasons
            ],
        }


def acceptance_deadline(
    offer_date: datetime, company_hours: int | None, cfg: PolicyConfig = DEFAULT_CONFIG
) -> datetime:
    """24 hours or the company's stated timeline, whichever is earlier."""
    hours = cfg.acceptance_window_hours
    if company_hours is not None:
        hours = min(hours, company_hours)
    return offer_date + timedelta(hours=hours)


def _switch_rule(existing: LiveOffer, opp: Opportunity, cfg: PolicyConfig) -> Reason | None:
    """FTE-to-FTE switching. Returns a Reason for BLOCK/REVIEW, None when allowed."""
    cat = existing.category
    if cat is Category.A_PLUS:
        return Reason(
            "SWITCH_A_PLUS",
            Verdict.BLOCK,
            "Selected in an A+ company: out of the placement process.",
        )
    if cat is Category.A:
        if opp.category is Category.A_PLUS:
            return None
        return Reason(
            "SWITCH_A",
            Verdict.BLOCK,
            f"Category A offer: switching allowed only to A+ (this is {opp.category.value}).",
        )
    if cat is Category.B:
        if existing.ctc_lpa is None:
            return Reason(
                "SWITCH_B_NO_CTC",
                Verdict.REVIEW,
                "Existing B offer has no recorded CTC; cannot test the 1.5x rule.",
            )
        need = existing.ctc_lpa * cfg.b_switch_multiplier
        if opp.ctc_lpa is not None:
            if opp.ctc_lpa >= need:
                return None
            return Reason(
                "SWITCH_B",
                Verdict.BLOCK,
                f"New CTC {opp.ctc_lpa} LPA is below 1.5x existing ({need:.2f} LPA).",
            )
        lo, hi = _bounds(
            opp.category, cfg
        )  # CTC unknown: decide from the category band if possible
        if lo >= need:
            return None
        if hi < need:
            return Reason(
                "SWITCH_B",
                Verdict.BLOCK,
                f"Category {opp.category.value} cannot reach 1.5x existing ({need:.2f} LPA).",
            )
        return Reason(
            "SWITCH_B_UNKNOWN_CTC",
            Verdict.REVIEW,
            f"CTC unknown; need at least {need:.2f} LPA (1.5x existing).",
        )
    # Category C: only higher-category opportunities (assumption, see README)
    if _RANK[opp.category] > _RANK[Category.C]:
        return None
    return Reason(
        "SWITCH_C", Verdict.BLOCK, "Category C offer: only higher-category drives allowed."
    )


def evaluate(
    student: StudentState, opp: Opportunity, cfg: PolicyConfig = DEFAULT_CONFIG
) -> Decision:
    reasons: list[Reason] = []

    if student.registration is not RegistrationStatus.REGISTERED:
        reasons.append(
            Reason(
                "NOT_REGISTERED",
                Verdict.BLOCK,
                f"Placement registration is '{student.registration.value}'.",
            )
        )
    if student.eligibility is EligibilityStatus.INELIGIBLE:
        reasons.append(Reason("INELIGIBLE", Verdict.BLOCK, "Student is marked ineligible."))
    elif student.eligibility is EligibilityStatus.PENDING:
        reasons.append(
            Reason("ELIGIBILITY_PENDING", Verdict.REVIEW, "Eligibility not yet verified.")
        )

    if student.exclusion_drives_remaining > 0:
        reasons.append(
            Reason(
                "ABSENTEEISM_EXCLUSION",
                Verdict.BLOCK,
                f"Excluded from {student.exclusion_drives_remaining} more drive(s) for absenteeism.",
            )
        )
    elif student.open_absence_flags > 0:
        reasons.append(
            Reason(
                "ABSENTEEISM_FLAG",
                Verdict.REVIEW,
                "Open absenteeism flag awaiting authorised review.",
            )
        )

    for o in student.live_offers:
        if o.offer_type is OfferType.IF:
            reasons.append(
                Reason(
                    "TYPE_IF",
                    Verdict.BLOCK,
                    "Already holds an I+F offer: cannot join other I, F or I+F roles.",
                )
            )
        elif o.offer_type is OfferType.I and opp.offer_type is OfferType.I:
            reasons.append(
                Reason(
                    "TYPE_I",
                    Verdict.BLOCK,
                    "Already holds an internship-only offer: no other internship-only roles.",
                )
            )
        elif o.offer_type is OfferType.F and opp.offer_type is OfferType.IF:
            reasons.append(
                Reason(
                    "TYPE_F_THEN_IF",
                    Verdict.REVIEW,
                    "Holds an FTE-only offer; I+F includes an FTE component. Manual review.",
                )
            )

    # FTE-to-FTE switching (A+ rule applies to any FTE-bearing live offer)
    fte_live = [o for o in student.live_offers if has_fte(o.offer_type)]
    if fte_live and has_fte(opp.offer_type):
        best = max(fte_live, key=lambda o: (_RANK[o.category], o.ctc_lpa or 0))
        r = _switch_rule(best, opp, cfg)
        if r:
            reasons.append(r)

    # 4.2 Company-specific eligibility criteria evaluation
    if opp.criteria:
        crit = opp.criteria
        if crit.allowed_courses and student.course and student.course not in crit.allowed_courses:
            reasons.append(
                Reason(
                    "COURSE_INELIGIBLE",
                    Verdict.BLOCK,
                    f"Course '{student.course}' is not in allowed courses: {', '.join(crit.allowed_courses)}.",
                )
            )
        if crit.allowed_batches and student.batch and student.batch not in crit.allowed_batches:
            reasons.append(
                Reason(
                    "BATCH_INELIGIBLE",
                    Verdict.BLOCK,
                    f"Batch '{student.batch}' is not in allowed batches: {', '.join(crit.allowed_batches)}.",
                )
            )
        if crit.min_academic_score is not None:
            if student.academic_score is None:
                reasons.append(
                    Reason(
                        "ACADEMIC_SCORE_MISSING",
                        Verdict.REVIEW,
                        f"Company requires min score {crit.min_academic_score}, but student score is not recorded.",
                    )
                )
            elif student.academic_score < crit.min_academic_score:
                reasons.append(
                    Reason(
                        "ACADEMIC_SCORE_LOW",
                        Verdict.BLOCK,
                        f"Academic score {student.academic_score} is below required minimum {crit.min_academic_score}.",
                    )
                )
        if crit.requires_registration and student.registration is not RegistrationStatus.REGISTERED:
            # Registration already blocked above by NOT_REGISTERED, but ensure explicit criteria note if needed
            pass

    verdict = max((r.verdict for r in reasons), default=Verdict.ALLOW)
    if not reasons:
        reasons.append(Reason("OK", Verdict.ALLOW, "No policy rule blocks this opportunity."))
    return Decision(verdict, reasons)
