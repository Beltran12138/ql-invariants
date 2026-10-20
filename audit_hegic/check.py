"""Model-free checks on quotes.json.

Every strategy here is a long position with a non-negative payoff f(S_exercise; strike fixed at purchase),
exercisable at any time before expiry (exerciseWindowDuration = 2^48-1). So for the same strike:
  M1  premium is non-decreasing in the period (the longer option can do everything the shorter can).
Adaptive put (user-chosen strike K, payoff (K-S)+):
  K1  premium non-decreasing in K;  K2  premium(K2) - premium(K1) <= K2 - K1;  K3  convex in K.
Bounds:  call premium <= S;  put premium <= K.
Not checked (and why): premium >= intrinsic is vacuous, the strike is at or out of the money at purchase.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, "quotes.json")))
feeds, cls = d["feeds"], d["classified"]
TOL = 1   # 1e-6 USDC: integer rounding in the contract

print(f"block {d['block']}  ts {d['timestamp']}")
viol = []
for a, q in d["quotes"].items():
    c = cls[a]
    S = feeds[c["feed"]]["answer"] / 10 ** feeds[c["feed"]]["decimals"]
    rows = [r for r in q["rows"] if not r.get("revert")]
    if not rows:
        print(f"{a} {c['asset']} {c['type']}: all quotes revert")
        continue
    prem = [r["prem"] for r in rows]
    for r0, r1 in zip(rows, rows[1:]):
        if r1["prem"] + TOL < r0["prem"]:
            viol.append(("M1", a, f"{r0['period'] / 86400:.2f}d {r0['prem'] / 1e6:.6f} > {r1['period'] / 86400:.2f}d {r1['prem'] / 1e6:.6f}"))
    mx = max(prem) / 1e6
    kind = (c["type"] or "?")
    if "Call" in kind and mx > S:
        viol.append(("B", a, f"call premium {mx} > S {S}"))
    if "Put" in kind and mx > S * (0.95 if "Adaptive" in kind else 1.0):
        viol.append(("B", a, f"put premium {mx} > K"))
    print(f"{a} {c['asset']} {kind:26s} {c['minDays']:.0f}-{c['maxDays']:.0f}d  prem/S {prem[0] / 1e6 / S:.4%} .. {prem[-1] / 1e6 / S:.4%}")
    if "strike_rows" in q:
        by_p = {}
        for r in q["strike_rows"]:
            by_p.setdefault(r["period"], []).append(r)
        for p, rs in by_p.items():
            rs = [r for r in rs if r["prem"] is not None]
            rs.sort(key=lambda r: r["strike"])
            inlim = lambda r: 9000 <= r["bp"] <= 9500
            for r0, r1 in zip(rs, rs[1:]):
                dK = (r1["strike"] - r0["strike"]) / 1e8
                dP = (r1["prem"] - r0["prem"]) / 1e6
                tag = "in-limits" if inlim(r0) and inlim(r1) else "outside limits"
                if dP < -1e-6:
                    viol.append(("K1", a, f"{p / 86400:.0f}d K {r0['bp'] / 100:.2f}%->{r1['bp'] / 100:.2f}%: premium falls {dP:.6f} ({tag})"))
                if dP > dK + 1e-6:
                    viol.append(("K2", a, f"{p / 86400:.0f}d K {r0['bp'] / 100:.2f}%->{r1['bp'] / 100:.2f}%: dP {dP:.6f} > dK {dK:.6f} ({tag})"))
            for r0, r1, r2 in zip(rs, rs[1:], rs[2:]):
                if (r2["prem"] - r1["prem"]) - (r1["prem"] - r0["prem"]) < -2 * TOL:
                    tag = "in-limits" if all(9000 <= r["bp"] <= 9500 for r in (r0, r1, r2)) else "outside limits"
                    viol.append(("K3", a, f"{p / 86400:.0f}d not convex at K {r1['bp'] / 100:.2f}% ({tag})"))
            pts = ", ".join(f"{r['bp'] / 100:.0f}%:{r['prem'] / 1e6:.2f}" for r in rs if r["bp"] % 500 == 0)
            print(f"    adaptive put {p / 86400:.0f}d  {pts}")

# cross-strategy: same pricer and same asset, the boundary period must agree
print()
by_pricer = {}
for a, c in cls.items():
    by_pricer.setdefault((c["pricer"], c["asset"]), []).append(a)
for (pr, asset), group in by_pricer.items():
    if len(group) > 1:
        print(f"pricer {pr[:10]} {asset}: shared by {len(group)} strategies " + ", ".join(f"{a[:8]}({cls[a]['minDays']:.0f}-{cls[a]['maxDays']:.0f}d)" for a in group))
print(f"\n{len(viol)} violations")
from collections import Counter
print(Counter((v[0], v[1][:10]) for v in viol))
for v in viol[:60]:
    print(" ", v[0], v[1][:10], v[2])
json.dump(viol, open(os.path.join(HERE, "violations.json"), "w"), indent=1)
