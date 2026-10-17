"""Apply the proposed fuzz oracle to calibrate.py output.

Oracle (any violation = finding):
  below_intrinsic : A(T)   < intrinsic - floor
  below_european  : A(T)   < E(T)      - floor
  decreasing_in_T : A(T2)  < A(T) * (1 - rel) - floor        (T2 = T + max(1, T/10) days)
  above_upper     : A(T)   > upper + floor,  upper = S (call), K * max(1, e^{-rT}) (put)
floor = 1e-8 * max(S, K).  rel = 1% by default: the approximations' own
non-monotonicity in T stays below 0.6% in calibration, F1 drops are 26-99%.
"""
import sys, json, math, collections
recs = [json.loads(l) for l in open(sys.argv[1])]
rel = float(sys.argv[2]) if len(sys.argv) > 2 else 0.01
cnt = collections.Counter(); exc = collections.Counter(); ex = {}
for r in recs:
    floor = 1e-8 * max(r["S"], r["K"])
    T = r["days"] / 360.0
    upper = r["S"] if r["typ"] == "C" else r["K"] * max(1.0, math.exp(-r["r"] * T))
    for name, v in r["res"].items():
        if isinstance(v, str):
            exc[(name, v.split("(")[0].strip())] += 1; continue
        a1, a2 = v
        checks = {
            "below_intrinsic": a1 < r["intr"] - floor,
            "below_european": a1 < r["eu"] - floor,
            "decreasing_in_T": a2 < a1 * (1 - rel) - floor,
            "above_upper": a1 > upper + floor,
        }
        for k, bad in checks.items():
            if bad:
                cnt[(name, k)] += 1
                qd = r["res"].get("QdFp")
                err = a1 / qd[0] - 1 if isinstance(qd, list) and qd[0] > 0 else None
                ex.setdefault((name, k), []).append((err, r["i"]))
print("N =", len(recs), " rel =", rel)
for k in sorted(cnt):
    errs = sorted(e for e, _ in ex[k] if e is not None)
    print(k, cnt[k], " err vs QdFp min/max:", (round(errs[0], 4), round(errs[-1], 4)) if errs else None, " sample i:", [i for _, i in ex[k][:3]])
if not cnt: print("no violations")
print("exceptions:", dict(exc))
