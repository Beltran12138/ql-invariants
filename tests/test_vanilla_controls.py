"""Positive / negative controls for the vanilla invariant checks.

Each mutation wraps a real engine and breaks exactly one property; the matching
check must fire. The unmutated analytic (European) and FD (American) engines must pass.
"""
import pytest
from qlinv import vanilla_scan as VS

MARKET = dict(S=100.0, r=0.03, q=0.01, vol=0.25, T=0.5,
              kx=[0.5, 0.8, 0.9, 0.95, 1.0, 1.05, 1.1, 1.25, 2.0])

_real_price = VS.price

MUTATIONS = {
    # name: (base engine, mutation f(kind, S, K, T, vol, v) -> v')
    "mut_parity": ("analytic", lambda k, S, K, T, vol, v: v + (0.02 * S if k == "C" else 0.0)),
    "mut_slope": ("analytic", lambda k, S, K, T, vol, v: v + (0.5 * K if k == "C" else 0.0)),
    "mut_convex": ("analytic", lambda k, S, K, T, vol, v: v + (5.0 if abs(K - S) < 1e-9 else 0.0)),
    "mut_vol": ("analytic", lambda k, S, K, T, vol, v: v - 40.0 * vol),
    "mut_bounds": ("analytic", lambda k, S, K, T, vol, v: v + (2.0 * S if k == "C" else 0.0)),
    "mut_am_eu": ("fd_am", lambda k, S, K, T, vol, v: v - 1.0),
    "mut_am_T": ("fd_am", lambda k, S, K, T, vol, v: v - 20.0 * T),
}


def mutated_price(name, kind, S, K, T, r, q, vol, lv=0, seed=42):
    if name in MUTATIONS:
        base, f = MUTATIONS[name]
        v, e = _real_price(base, kind, S, K, T, r, q, vol, lv, seed)
        return f(kind, S, K, T, vol, v), e
    return _real_price(name, kind, S, K, T, r, q, vol, lv, seed)


@pytest.fixture(autouse=True)
def patch(monkeypatch):
    monkeypatch.setattr(VS, "price", mutated_price)
    for name, (base, _) in MUTATIONS.items():
        monkeypatch.setitem(VS.ENGINES, name, VS.ENGINES[base])


def invs(engine):
    return {f["inv"] for f in VS.check_market(MARKET, [engine])}


@pytest.mark.parametrize("engine", ["analytic", "fd_am"])
def test_negative_control(engine):
    assert invs(engine) == set()


@pytest.mark.parametrize("engine,expected", [
    ("mut_parity", "parity"), ("mut_slope", "slope_K"), ("mut_convex", "convex_K"),
    ("mut_vol", "vol_mono"), ("mut_bounds", "bounds_hi"),
    ("mut_am_eu", "am_ge_eu"), ("mut_am_T", "am_T_mono"),
])
def test_positive_control(engine, expected):
    found = invs(engine)
    assert expected in found, found
