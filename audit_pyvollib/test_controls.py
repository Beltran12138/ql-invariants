"""Positive / negative controls for audit.py.

Each mutation wraps a pricer (or IV / greek function) and breaks exactly one property;
the matching check must fire. Unmutated QuantLib blackFormula and vollib core must pass.
Run:  .venv/Scripts/python -m pytest -q test_controls.py
"""
import math, random
import pytest
import audit as A

MKT = dict(S=100.0, sig=0.25, T=0.5, r=0.03, q=0.01,
           Ks=[50.0, 80.0, 90.0, 95.0, 100.0, 105.0, 110.0, 125.0, 200.0])

def invs(pr, ivf=None, gfun=None, black=False, m=MKT):
    from collections import Counter
    v, c = [], Counter()
    A.check_prices(pr, m, v, c, "ctl")
    A.check_oracle(pr, m, v, c, "ctl", [])
    if ivf:
        A.check_iv(pr, ivf, m, v, c, "ctl")
    if gfun:
        A.check_greeks(pr, gfun, m, v, c, "ctl", black=black)
    return {x["inv"] for x in v if not x["inv"].startswith("info_")}

base = A.vollib_bsm
PRICE_MUT = {
    "parity":   lambda k, S, K, T, r, q, s: base(k, S, K, T, r, q, s) + (0.02 * S if k == "c" else 0),
    "slope_K":  lambda k, S, K, T, r, q, s: base(k, S, K, T, r, q, s) + (0.5 * K if k == "c" else 0),
    "convex_K": lambda k, S, K, T, r, q, s: base(k, S, K, T, r, q, s) + (5.0 if K == 100.0 else 0),
    "vol_mono": lambda k, S, K, T, r, q, s: base(k, S, K, T, r, q, s) - 40.0 * s,
    "bounds":   lambda k, S, K, T, r, q, s: base(k, S, K, T, r, q, s) + (2.0 * S if k == "c" else 0),
    "oracle_abs": lambda k, S, K, T, r, q, s: base(k, S, K, T, r, q, s) * (1 + 1e-9),
}

@pytest.mark.parametrize("pr", [A.ql_bsm, A.vollib_bsm])
def test_negative_prices(pr):
    assert invs(pr) == set()

def test_negative_iv_ql():
    assert invs(A.ql_bsm, ivf=A.ql_iv) == set()

def test_negative_iv_vollib():
    assert invs(A.vollib_bsm, ivf=A.vollib_bsm_iv, gfun=A.vollib_bsm_greeks) == set()

@pytest.mark.parametrize("inv", sorted(PRICE_MUT))
def test_positive_prices(inv):
    assert inv in invs(PRICE_MUT[inv]), invs(PRICE_MUT[inv])

def _iv_returns_number(p, k, S, K, T, r, q):
    try:
        return A.vollib_bsm_iv(p, k, S, K, T, r, q)
    except Exception:
        return 0.0  # broken: swallow error, return a number (OptionStratLib #652 pattern)

def _iv_biased(p, k, S, K, T, r, q):
    return A.vollib_bsm_iv(p, k, S, K, T, r, q) * 1.001

def test_positive_iv_band():
    assert "iv_band" in invs(A.vollib_bsm, ivf=_iv_returns_number)

def test_positive_iv_rt():
    assert "iv_rt" in invs(A.vollib_bsm, ivf=_iv_biased)

@pytest.mark.parametrize("g", ["delta", "gamma", "vega", "theta", "rho"])
def test_positive_greeks(g):
    def bad(*a):
        d = A.vollib_bsm_greeks(*a)
        d[g] *= 1.0001
        return d
    assert "greek_" + g in invs(A.vollib_bsm, gfun=bad)

def test_positive_greek_convention():
    # theta per-day not rescaled (the most likely convention mistake) must be flagged
    def bad(*a):
        d = A.vollib_bsm_greeks(*a)
        d["theta"] /= 365
        return d
    assert "greek_theta" in invs(A.vollib_bsm, gfun=bad)

def test_negative_black_greeks():
    m = dict(MKT, q=MKT["r"])
    assert invs(A.vollib_black, ivf=A.vollib_black_iv, gfun=A.vollib_black_greeks, black=True, m=m) == set()
