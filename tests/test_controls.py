"""Positive / negative controls: every check must be able to fail.

Case = aichao's #930 example (5% semiannual, flat 2%, call at 100 clean,
deep in the money so the call is certain), sigma ~ 0.
"""
import random
import QuantLib as ql
import pytest
from qlinv import callable_scan as CS

CASE = dict(today=ql.Date(18, 5, 2021).serialNumber(),
            issue=(ql.Date(20, 5, 2021) - 732).serialNumber(),
            maturity=ql.Date(14, 2, 2026).serialNumber(),
            freq="S", cal="US", conv="Following", dc="30/360", coupon=0.05, rate=0.02,
            settle=2, call_price=100.0, a=0.03, sigma=1e-6, kind="call",
            style="single", on_coupon=False)
COUPON_DATE = ql.Date(14, 2, 2022)


def run(cd, ctx_cls=None, **over):
    c = dict(CASE, **over)
    return CS.check(c, random.Random(0), cds=[cd], ctx_cls=ctx_cls)


class Buggy930(CS.Ctx):
    """Re-inject the pre-2021 behaviour: a call within 7 days before a coupon
    is snapped onto the coupon date AND the holder still gets that coupon."""
    def ql_price(self, call_dates, sigma=None, grid=None, kind=None):
        v = super().ql_price(call_dates, sigma, grid, kind)
        for cd in call_dates:
            for d, amt, cp in self.coupons():
                if cp is not None and 0 < d - cd <= 7:
                    v += amt * self.curve.discount(d) / self.curve.discount(self.settle)
        return v


@pytest.mark.parametrize("delta", [-10, -5, -3, -1, 0, 1, 5])
def test_negative_control_real_quantlib_passes(delta):
    r = run(COUPON_DATE + delta)
    assert r["viol"] == [], r


@pytest.mark.parametrize("delta", [-5, -3, -1])
def test_positive_control_buggy_pricer_is_caught(delta):
    r = run(COUPON_DATE + delta, ctx_cls=Buggy930)
    kinds = {v[0] for v in r["viol"]}
    assert "call_upper" in kinds, r


def test_positive_control_continuity_catches_jump():
    # one day before the 7-day window -> next day enters it -> jump of ~a coupon
    r = run(COUPON_DATE - 8, ctx_cls=Buggy930)
    assert "calldate_continuity" in {v[0] for v in r["viol"]}, r


class BuggyPut(CS.Ctx):
    def ql_price(self, call_dates, sigma=None, grid=None, kind=None):
        return super().ql_price(call_dates, sigma, grid, kind) - 0.5


def test_positive_control_put_lower():
    r = run(COUPON_DATE + 3, ctx_cls=BuggyPut, kind="put", rate=0.08)
    assert "put_lower" in {v[0] for v in r["viol"]}, r


class VolWrong(CS.Ctx):
    """Callable price that *increases* with vol (sign error)."""
    def ql_price(self, call_dates, sigma=None, grid=None, kind=None):
        s = self.c["sigma"] if sigma is None else sigma
        # +5 per 1% vol: must dominate the true (negative) vega of an ATM callable;
        # a first attempt with +0.5 per 1% was weaker than the real vega -> no violation
        return super().ql_price(call_dates, sigma, grid, kind) + 500 * s


def test_positive_control_vol_monotone():
    r = run(COUPON_DATE + 3, ctx_cls=VolWrong, sigma=0.01, rate=0.05)
    assert "call_vol_monotone" in {v[0] for v in r["viol"]}, r
