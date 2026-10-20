"""H-D1 detail: for each joint (ATM, 110%) ETH-call parameter state where the 110% call is quoted above the ATM call,
the shortest period at which it happens, and how long (blocks, seconds) the state lasted."""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpc import rpc

HERE = os.path.dirname(os.path.abspath(__file__))
H = json.load(open(os.path.join(HERE, "pricer_history.json")))
ATM, OTM = "0xc62a0b7e480a23bdcfe13ea08bdacedc278a14c1", "0x6316bc5f5df141ae88c436fe6047d334f1b7e485"
GRID = np.arange(7 * 86400, 90 * 86400 + 1, 3600, dtype=float)
POW = np.vstack([GRID ** k for k in range(5)])
INT_MAX = (1 << 255) - 1


def ex(c, t):
    """Solidity semantics: checked int256 terms and partial sums (overflow = revert = no quote), negative = no quote."""
    s = 0
    for k in range(5):
        term = c[k] * t ** k
        s += term
        if abs(term) > INT_MAX or abs(s) > INT_MAX:
            return None
    return None if s < 0 else s // 10 ** 24

ups = lambda p, k: [(e["block"], i, k, e["words"]) for i, e in enumerate(H[p]) if e["event"].startswith("SetCoefficients")]
ev = sorted(ups(ATM, "A") + ups(OTM, "O"))
head = int(rpc("eth_blockNumber", []), 16)
cur, rows = {"A": None, "O": None}, []
for j, (b, i, k, c) in enumerate(ev):
    cur[k] = c
    if cur["A"] is None or cur["O"] is None:
        continue
    nxt = ev[j + 1][0] if j + 1 < len(ev) else head
    va, vo = np.array(cur["A"], float) @ POW, np.array(cur["O"], float) @ POW
    m = vo > va * (1 + 1e-12)
    if not m.any():
        continue
    tmin = None
    hits = []
    for t in GRID[m]:
        eo, ea = ex(cur["O"], int(t)), ex(cur["A"], int(t))
        if eo is not None and ea is not None and eo > ea:
            hits.append((int(t), (eo - ea) / ea))
    if not hits:
        continue
    tmin = hits[0][0]
    worst = max(hits, key=lambda h: h[1])[0]
    rows.append({"block": b, "next_block": nxt, "blocks": nxt - b, "min_days": tmin / 86400,
                 "worst_days": worst / 86400, "atm": ex(cur["A"], worst) / 1e6, "otm": ex(cur["O"], worst) / 1e6})
print("violating states", len(rows))
for lim in (14, 30, 60, 90):
    sub = [r for r in rows if r["min_days"] <= lim]
    print(f"  violation reaches down to <= {lim:2d}d: {len(sub):5d} states, total {sum(r['blocks'] for r in sub):>12,} blocks")
# timestamps for the longest-lived ones within <= 30d
sub = sorted([r for r in rows if r["min_days"] <= 30], key=lambda r: -r["blocks"])[:8]
for r in sub:
    t0 = int(rpc("eth_getBlockByNumber", [hex(r["block"]), False])["timestamp"], 16)
    t1 = int(rpc("eth_getBlockByNumber", [hex(r["next_block"]), False])["timestamp"], 16)
    r["t0"], r["seconds"] = t0, t1 - t0
    print(f"  block {r['block']} lasted {r['seconds'] / 3600:.2f} h; 110% > ATM from {r['min_days']:.2f}d; at {r['worst_days']:.1f}d ATM {r['atm']:.2f} vs 110% {r['otm']:.2f}")
json.dump(rows, open(os.path.join(HERE, "history_d1.json"), "w"), indent=1)
