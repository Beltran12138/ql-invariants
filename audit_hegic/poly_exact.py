"""Exact re-implementation of the Polynomial/Combine pricers (Solidity integer semantics), checked over each
pricer's full allowed period range [minPeriod, maxPeriod] = [7d, 90d], not only the ranges the strategies sell.

Cross-checked against the live quotes in quotes.json (must agree to the unit).
"""
import json, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(os.path.join(HERE, "pricer_params.json")))
Q = json.load(open(os.path.join(HERE, "quotes.json")))
INT_MAX = (1 << 255) - 1


def sdiv(a, b):   # Solidity signed division truncates toward zero
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def premium(p, period, amount, token_dec):
    """Returns premium (int) or None where the contract would revert (overflow / underflow)."""
    row = P[p]
    if row["kind"] == "Polynomial":
        c = row["coefficients"]
        terms = [c[0], c[1] * period, c[2] * period ** 2, c[3] * period ** 3, c[4] * period ** 4]
        if any(abs(t) > INT_MAX for t in terms):
            return None
        s = 0
        for t in terms:   # checked int256 arithmetic, left to right
            s += t
            if abs(s) > INT_MAX:
                return None
        if s < 0:
            return ("NEG", s)   # uint256(negative) wraps to a huge number
        return (s // 10 ** 24) * amount // 10 ** token_dec
    if row["kind"] == "Combine":
        a = premium(row["base"][0], period, amount, token_dec)
        b = premium(row["base"][1], period, amount, token_dec)
        if a is None or b is None or isinstance(a, tuple) or isinstance(b, tuple):
            return None
        s = a * row["coef_1e5"][0] + b * row["coef_1e5"][1]
        if s < 0:
            return ("NEG", s)
        return s // 10 ** 5
    raise ValueError(row["kind"])


# 1) agreement with the live quotes
cls = Q["classified"]
bad = n = 0
for a, q in Q["quotes"].items():
    pr = cls[a]["pricer"]
    if pr not in P or P[pr]["kind"] not in ("Polynomial", "Combine"):
        continue
    unit_dec = 18 if cls[a]["asset"] == "ETH" else 8
    for r in q["rows"]:
        mine = premium(pr, r["period"], 10 ** unit_dec, unit_dec)
        live = None if r.get("revert") else r["prem"]
        n += 1
        if (mine if not isinstance(mine, tuple) else "NEG") != live:
            bad += 1
            if bad < 5:
                print("MISMATCH", a[:10], r["period"], mine, live)
print(f"reimplementation vs live quotes: {n - bad}/{n} agree")

# 2) monotonicity in the period over the pricers' full range, hourly, and analytic critical points
lo, hi = 7 * 86400, 90 * 86400
for p, row in P.items():
    if row["kind"] not in ("Polynomial", "Combine"):
        continue
    vals = [(t, premium(p, t, 10 ** 18, 18)) for t in range(lo, hi + 1, 3600)]
    rev = [t for t, v in vals if v is None]
    neg = [t for t, v in vals if isinstance(v, tuple)]
    ok = [(t, v) for t, v in vals if isinstance(v, int)]
    drops = [(t0, v0, t1, v1) for (t0, v0), (t1, v1) in zip(ok, ok[1:]) if v1 < v0]
    msg = f"{p[:10]} {row['kind']:10s} hourly 7-90d: reverts {len(rev)}, negative {len(neg)}, decreases {len(drops)}"
    if drops:
        t0 = drops[0][0]; t1 = drops[-1][2]
        msg += f" (from {t0 / 86400:.2f}d to {t1 / 86400:.2f}d, worst step {min(v1 - v0 for _, v0, _, v1 in drops) / 1e6:.6f} USDC)"
    if row["kind"] == "Polynomial" and not rev:
        c = row["coefficients"]
        roots = np.roots([4 * c[4], 3 * c[3], 2 * c[2], c[1]])
        crit = sorted(r.real / 86400 for r in roots if abs(r.imag) < 1e-6 * abs(r) and 0 < r.real)
        msg += f"; dP/dT = 0 at days {[round(x, 1) for x in crit]}"
    print(msg)
