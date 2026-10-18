"""How often does maximising the BJS 1993 trigger change the price in ordinary parameter ranges,
and does the change move towards QdFp? (Companion to probe_bjs_maxI.py.)"""
import math, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe_bjs_maxI as m

rng = random.Random(5)
n = changed = closer = farther = above_qd = 0; worst = (0, None)
for _ in range(1000):
    S = 100 * rng.uniform(0.8, 1.2); K = 100.0; days = rng.randint(30, 3 * 365)
    r = rng.uniform(0.0, 0.10); q = rng.uniform(0.0, 0.10); v = rng.uniform(0.10, 0.50); c = rng.random() < 0.5
    T = days / 365.0
    base, _, ht = m.american(S, K, T, r, q, v, c, False)
    mx, _, _ = m.american(S, K, T, r, q, v, c, True)
    bjs, qd = m.ql_prices(S, K, days, r, q, v, c)
    if abs(base - bjs) > 1e-9 * K:   # skip points where QuantLib takes another branch
        continue
    n += 1
    d = (mx - base) / max(base, 1e-12)
    if d > 1e-6:
        changed += 1
        if abs(mx - qd) < abs(base - qd): closer += 1
        else: farther += 1
        if d > worst[0]: worst = (d, (round(S, 2), days, round(r, 4), round(q, 4), round(v, 3), "C" if c else "P", round(base, 6), round(mx, 6), round(qd, 6)))
    if mx > qd * (1 + 1e-4): above_qd += 1
print(f"points {n}; price changed by >1e-6 relative: {changed} (closer to QdFp {closer}, farther {farther}); "
      f"maximised above QdFp by >1e-4: {above_qd}; largest change {worst[0]:.3%} at {worst[1]}")
