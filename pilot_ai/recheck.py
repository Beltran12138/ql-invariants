"""Re-score saved outputs (results/wd_*/out.json) without re-running the pricers.

Fix vs check.py (found by the negative control, 2026-10-17): the call upper bound is
S*max(1, e^{-qT}), not S; with q < 0 the European call itself exceeds S.
Also reports the size of each violation relative to the price scale.
"""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check
pts = check.points(); ref = json.load(open("results/reference.json"))

def score(name, res):
    c = dict(mf_any=0, intrinsic=0, european=0, maturity=0, upper=0, strike=0, ref7=0, exc=0)
    sizes = {k: [] for k in ["intrinsic", "european", "maturity", "upper", "strike"]}
    for x, rf, r3 in zip(pts, ref, res):
        if any("err" in e for e in r3): c["exc"] += 1; continue
        a, a2, ak = (e["v"] for e in r3)
        S, K = x["S"], x["K"]; floor = 1e-8 * max(S, K); T = x["days"] / 365.0
        intr = max(S - K, 0) if x["is_call"] else max(K - S, 0)
        upper = S * max(1.0, math.exp(-x["q"] * T)) if x["is_call"] else K * max(1.0, math.exp(-x["r"] * T))
        gap = dict(intrinsic=intr - a, european=rf["eu"] - a, maturity=a * 0.99 - a2, upper=a - upper,
                   strike=(ak - a * 1.01) if x["is_call"] else (a * 0.99 - ak))
        bad = {k: g > floor for k, g in gap.items()}
        for k, v in bad.items():
            if v: c[k] += 1; sizes[k].append(gap[k] / max(rf["qdfp"][0], 1e-4 * max(S, K)))
        c["mf_any"] += any(bad.values())
        q = rf["qdfp"][0]; c["ref7"] += abs(a - q) > 0.02 * q + 1e-4 * max(S, K)
    return c, sizes

rows = {"ctrl_qdfp": [[{"v": v} for v in rf["qdfp"]] for rf in ref]}
for d in sorted(os.listdir("results")):
    if d.startswith("wd_"):
        o = json.load(open(f"results/{d}/out.json")); rows[d[3:]] = [o[3*i:3*i+3] for i in range(len(pts))]
cols = ["exc", "mf_any", "intrinsic", "european", "maturity", "upper", "strike", "ref7"]
print(f"{'pricer':12s}" + "".join(f"{c:>10s}" for c in cols) + "   size of 'european' gaps (rel. to price): >1e-6  >1e-4  >1e-2  max")
for k, res in rows.items():
    c, s = score(k, res); e = s["european"]
    print(f"{k:12s}" + "".join(f"{c[x]:>10d}" for x in cols) +
          f"   {sum(v > 1e-6 for v in e):>5d} {sum(v > 1e-4 for v in e):>6d} {sum(v > 1e-2 for v in e):>6d}  {max(e) if e else 0:.2e}")
