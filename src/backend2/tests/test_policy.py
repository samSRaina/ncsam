from datetime import datetime

import pytest

from app.enums import Category as C
from app.enums import EligibilityStatus as El
from app.enums import OfferType as T
from app.enums import RegistrationStatus as Reg
from app.policy import (
    LiveOffer,
    Opportunity,
    StudentState,
    Verdict,
    acceptance_deadline,
    category_from_ctc,
    evaluate,
)


def st(*offers, reg=Reg.REGISTERED, el=El.ELIGIBLE, excl=0, flags=0):
    return StudentState(reg, el, excl, flags, tuple(offers))


V = Verdict


@pytest.mark.parametrize(
    "ctc,cat", [(16, C.A_PLUS), (15.99, C.A), (10, C.A), (9.99, C.B), (6, C.B), (5.99, C.C)]
)
def test_category_bands(ctc, cat):
    assert category_from_ctc(ctc) is cat


def test_clean_student_allowed():
    assert evaluate(st(), Opportunity(T.F, C.B, 8)).verdict is V.ALLOW


def test_a_plus_is_out_of_process():
    d = evaluate(st(LiveOffer(T.F, C.A_PLUS, 20)), Opportunity(T.F, C.A_PLUS, 25))
    assert d.verdict is V.BLOCK and d.reasons[0].code == "SWITCH_A_PLUS"


def test_a_only_to_a_plus():
    held = LiveOffer(T.F, C.A, 12)
    assert evaluate(st(held), Opportunity(T.F, C.A_PLUS, 18)).verdict is V.ALLOW
    assert evaluate(st(held), Opportunity(T.F, C.A, 14)).verdict is V.BLOCK
    assert evaluate(st(held), Opportunity(T.F, C.B, 8)).verdict is V.BLOCK


def test_b_needs_1_5x():
    held = LiveOffer(T.F, C.B, 8)
    assert evaluate(st(held), Opportunity(T.F, C.A, 11.9)).verdict is V.BLOCK
    assert evaluate(st(held), Opportunity(T.F, C.A, 12.0)).verdict is V.ALLOW


def test_b_unknown_ctc_uses_category_band():
    held = LiveOffer(T.F, C.B, 8)  # needs 12
    assert evaluate(st(held), Opportunity(T.F, C.A_PLUS)).verdict is V.ALLOW  # floor 16
    assert evaluate(st(held), Opportunity(T.F, C.C)).verdict is V.BLOCK  # ceiling 6
    assert evaluate(st(held), Opportunity(T.F, C.A)).verdict is V.REVIEW  # 10..16 straddles 12


def test_c_only_higher_category():
    held = LiveOffer(T.F, C.C, 4)
    assert evaluate(st(held), Opportunity(T.F, C.B, 7)).verdict is V.ALLOW
    assert evaluate(st(held), Opportunity(T.F, C.C, 5)).verdict is V.BLOCK


def test_internship_only_rules():
    held = LiveOffer(T.I, C.C)
    assert evaluate(st(held), Opportunity(T.I, C.C)).verdict is V.BLOCK
    assert evaluate(st(held), Opportunity(T.F, C.B, 8)).verdict is V.ALLOW
    assert evaluate(st(held), Opportunity(T.IF, C.B, 8)).verdict is V.ALLOW


def test_fte_only_then_internship_allowed():
    assert evaluate(st(LiveOffer(T.F, C.B, 8)), Opportunity(T.I, C.C)).verdict is V.ALLOW


def test_if_blocks_everything():
    held = LiveOffer(T.IF, C.B, 8)
    for t in T:
        assert evaluate(st(held), Opportunity(t, C.A_PLUS, 30)).verdict is V.BLOCK


def test_registration_and_eligibility():
    opp = Opportunity(T.F, C.B, 8)
    assert evaluate(st(reg=Reg.DEREGISTERED), opp).verdict is V.BLOCK
    assert evaluate(st(el=El.INELIGIBLE), opp).verdict is V.BLOCK
    assert evaluate(st(el=El.PENDING), opp).verdict is V.REVIEW


def test_absenteeism():
    opp = Opportunity(T.F, C.B, 8)
    assert evaluate(st(excl=2), opp).verdict is V.BLOCK
    assert evaluate(st(flags=1), opp).verdict is V.REVIEW


def test_reasons_accumulate_and_explain():
    d = evaluate(st(LiveOffer(T.IF, C.B, 8), reg=Reg.NOT_REGISTERED), Opportunity(T.F, C.B, 9))
    assert {r.code for r in d.reasons} >= {"NOT_REGISTERED", "TYPE_IF"}


def test_acceptance_deadline_is_earlier_of_24h_or_company():
    t = datetime(2026, 11, 1, 10)
    assert acceptance_deadline(t, None) == datetime(2026, 11, 2, 10)
    assert acceptance_deadline(t, 6) == datetime(2026, 11, 1, 16)
    assert acceptance_deadline(t, 72) == datetime(2026, 11, 2, 10)
