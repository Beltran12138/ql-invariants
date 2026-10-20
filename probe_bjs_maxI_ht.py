"""Check of a claim on QuantLib#2903 (2026-10-19): every option whose price changes under the max-I fix has
ht in about [-1.81, -0.09]. Same draw as probe_bjs_maxI_normal.py (seed 5); also reports the error of the
published value against QdFp, binned by ht, over all points (changed or not)."""
import os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe_bjs_maxI as m

rng = random.Random(5)
hts_changed, rows = [], []
for _ in range(1000):
    S = 100 * rng.uniform(0.8, 1.2); K = 100.0; days = rng.randint(30, 3 * 365)
    r = rng.uniform(0.0, 0.10); q = rng.uniform(0.0, 0.10); v = rng.uniform(0.10, 0.50); c = rng.random() < 0.5
    T = days / 365.0
    base, _, ht = m.american(S, K, T, r, q, v, c, False)
    mx, _, _ = m.american(S, K, T, r, q, v, c, True)
    bjs, qd = m.ql_prices(S, K, days, r, q, v, c)
    if abs(base - bjs) > 1e-9 * K:
        continue
    rows.append((ht, base / qd - 1, mx / qd - 1))
    if (mx - base) / max(base, 1e-12) > 1e-6:
        hts_changed.append(ht)
print(f"points {len(rows)}, changed {len(hts_changed)}, ht of changed in [{min(hts_changed):.3f}, {max(hts_changed):.3f}]")
unchanged_in_band = sum(1 for ht, _, _ in rows if min(hts_changed) <= ht <= max(hts_changed)) - len(hts_changed)
print(f"points inside that ht band whose price does not change: {unchanged_in_band}")
for lo, hi in [(-99, -2), (-2, -1.5), (-1.5, -1), (-1, -0.5), (-0.5, 0), (0, 99)]:
    sub = [(a, b) for ht, a, b in rows if lo <= ht < hi]
    if sub:
        print(f"  ht in [{lo:5}, {hi:5}): n={len(sub):4d}  published worst {min(a for a, _ in sub):+.3%}  maximised worst {min(b for _, b in sub):+.3%}")
