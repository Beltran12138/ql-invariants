"""Fine grid for the adaptive put (unverified pricer 0x3614...): strikes 90.00%..95.00% of spot in 5 bp steps
(the purchasable range) x periods 30..60 days every 3 days, at the scan block. Checks K1-K3 and M1 on the grid."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scan import batch, enc_quote

HERE = os.path.dirname(os.path.abspath(__file__))
Q = json.load(open(os.path.join(HERE, "quotes.json")))
A = "0xb91868948b3521f2923fd1d4f6456f6b3bc52e25"
S = Q["feeds"]["0x639fe6ab55c921f74e7fac1ee960c0b6293ba612"]["answer"]
block = hex(Q["block"])
bps = list(range(9000, 9501, 5))   # 5 bp steps: the public node rate-limits a 1 bp x daily grid
days = list(range(30, 61, 3))
grid = [(bp, d) for d in days for bp in bps]
res = batch([(A, enc_quote(10 ** 18, d * 86400, S * bp // 10000)) for bp, d in grid], block)
P = {}
for (bp, d), r in zip(grid, res):
    P[(bp, d)] = int(r[66:130], 16) if r else None
rev = sum(v is None for v in P.values())
viol = {"K1": [], "K2": [], "K3": [], "M1": []}
for d in days:
    for b0, b1 in zip(bps, bps[1:]):
        p0, p1 = P[(b0, d)], P[(b1, d)]
        dK = (S * b1 // 10000 - S * b0 // 10000) / 1e8
        if p1 < p0: viol["K1"].append((d, b0))
        if (p1 - p0) / 1e6 > dK + 1e-6: viol["K2"].append((d, b0, (p1 - p0) / 1e6, dK))
    for b0, b1, b2 in zip(bps, bps[1:], bps[2:]):
        if (P[(b2, d)] - P[(b1, d)]) - (P[(b1, d)] - P[(b0, d)]) < -2: viol["K3"].append((d, b1))
for bp in bps:
    for d0, d1 in zip(days, days[1:]):
        if P[(bp, d1)] < P[(bp, d0)]: viol["M1"].append((bp, d0))
print(f"{len(grid)} quotes, reverts {rev}")
print({k: len(v) for k, v in viol.items()})
for k, v in viol.items():
    if v: print(k, v[:10])
json.dump({"block": Q["block"], "S": S, "quotes": {f"{bp}_{d}": p for (bp, d), p in P.items()}, "violations": viol},
          open(os.path.join(HERE, "adaptive_fine.json"), "w"))
