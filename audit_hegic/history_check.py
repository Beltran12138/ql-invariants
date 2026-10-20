"""Replay every SetCoefficients update of the live Polynomial pricers (from pricer_history.json) and check each
parameter state that was ever live:
  H-M1  premium non-decreasing in the period, 6-hour grid over the pricer's full range [7d, 90d]
        (and separately over the ranges the strategies actually sell)
  H-NEG polynomial negative somewhere in [7d, 90d] (uint256 cast would wrap -> revert or absurd quote)
  H-D1  110% ETH call (0x6316) quoted above the ATM ETH call (0xc62a) at the same moment and period
Float64 screening, then every flagged state is re-checked with the exact integer implementation.
"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))
H = json.load(open(os.path.join(HERE, "pricer_history.json")))
CLS = json.load(open(os.path.join(HERE, "classified.json")))
GRID = np.arange(7 * 86400, 90 * 86400 + 1, 6 * 3600, dtype=float)
POW = np.vstack([GRID ** k for k in range(5)])            # 5 x n


def exact(c, t):
    s = c[0] + c[1] * t + c[2] * t ** 2 + c[3] * t ** 3 + c[4] * t ** 4
    return None if s < 0 else s // 10 ** 24


sold = {}
for a, c in CLS.items():
    sold.setdefault(c["pricer"], []).append((c["minDays"] * 86400, c["maxDays"] * 86400))

states = {}
summary = {}
for p, ev in H.items():
    ups = [(e["block"], i, e["words"]) for i, e in enumerate(ev) if e["event"].startswith("SetCoefficients")]
    if not ups:
        continue
    states[p] = ups
    C = np.array([u[2] for u in ups], dtype=float)         # m x 5
    V = C @ POW                                            # m x n premiums * 1e24
    neg = (V < 0).any(axis=1)
    dec = (np.diff(V, axis=1) < -1e-9 * np.abs(V[:, 1:]).clip(min=1e24)).any(axis=1)
    # exact confirmation
    conf_dec, conf_neg, sold_dec = [], [], []
    for j in np.where(dec | neg)[0]:
        c = ups[j][2]
        vals = [exact(c, int(t)) for t in GRID]
        if any(v is None for v in vals):
            conf_neg.append(j)
        ok = [(t, v) for t, v in zip(GRID, vals) if v is not None]
        drops = [(t0, t1, v0, v1) for (t0, v0), (t1, v1) in zip(ok, ok[1:]) if v1 < v0]
        if drops:
            conf_dec.append((j, drops))
            if any(lo <= t0 and t1 <= hi for (t0, t1, _, _) in drops for lo, hi in sold.get(p, [])):
                sold_dec.append(j)
    summary[p] = {"updates": len(ups), "first_block": ups[0][0], "last_block": ups[-1][0],
                  "decreasing_states": len(conf_dec), "decreasing_in_sold_range": len(sold_dec), "negative_states": len(conf_neg)}
    print(p[:10], summary[p])
    for j, drops in conf_dec[:3]:
        t0, t1, v0, v1 = drops[0]
        print(f"    e.g. block {ups[j][0]}: {t0 / 86400:.2f}d {v0 / 1e6:.6f} -> {t1 / 86400:.2f}d {v1 / 1e6:.6f} USDC/unit"
              f" ({len(drops)} drops, {drops[0][0] / 86400:.1f}..{drops[-1][1] / 86400:.1f}d)")

# H-D1: merge the two ETH call pricers' timelines
ATM, OTM = "0xc62a0b7e480a23bdcfe13ea08bdacedc278a14c1", "0x6316bc5f5df141ae88c436fe6047d334f1b7e485"
ev = sorted([(b, i, "A", c) for b, i, c in states[ATM]] + [(b, i, "O", c) for b, i, c in states[OTM]])
cur = {"A": None, "O": None}
bad = []
n = 0
for b, i, k, c in ev:
    cur[k] = c
    if cur["A"] is None or cur["O"] is None:
        continue
    n += 1
    va = np.array(cur["A"], dtype=float) @ POW
    vo = np.array(cur["O"], dtype=float) @ POW
    if (vo > va * (1 + 1e-12)).any():
        t = GRID[np.argmax(vo - va)]
        ea, eo = exact(cur["A"], int(t)), exact(cur["O"], int(t))
        if ea is not None and eo is not None and eo > ea:
            bad.append((b, t / 86400, ea / 1e6, eo / 1e6))
print(f"\nH-D1: {n} joint states of ATM/110% ETH call; states with 110% call > ATM call somewhere in 7-90d: {len(bad)}")
for x in bad[:5]:
    print("   block %d  %.2fd  ATM %.6f  110%% %.6f" % x)
json.dump({"summary": summary, "D1": bad}, open(os.path.join(HERE, "history_check.json"), "w"), indent=1)
