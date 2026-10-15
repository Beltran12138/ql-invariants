"""Triage a vanilla scan: group findings by (engine, invariant), with the max gap/tol ratio
and the market that produced it. Ratios near 1 are tolerance noise; look at large ones."""
import json, sys, collections

rows = collections.defaultdict(list)
errs = collections.Counter()
markets = 0
for line in open(sys.argv[1], encoding="utf8"):
    r = json.loads(line)
    if "error" in r:
        errs["market_error"] += 1
        continue
    markets += 1
    for f in r["findings"]:
        if f["inv"] == "engine_error":
            errs[(f["engine"], f["error"][:90])] += 1
            continue
        ratio = abs(f["gap"]) / f["tol"] if f["tol"] > 0 else float("inf")
        rows[(f["cls"], f["engine"], f["inv"])].append((ratio, f, r["market"]))
print("markets", markets)
print(f"{'class':8s} {'engine':18s} {'invariant':14s} {'n':>5s} {'markets':>7s} {'max gap/tol':>12s}  worst market")
for k in sorted(rows, key=lambda k: -max(x[0] for x in rows[k])):
    xs = rows[k]
    nm = len({json.dumps(m, sort_keys=True) for _, _, m in xs})
    ratio, f, m = max(xs, key=lambda x: x[0])
    mk = {a: m[a] for a in ("S", "r", "q", "vol", "T")}
    print(f"{k[0]:8s} {k[1]:18s} {k[2]:14s} {len(xs):5d} {nm:7d} {ratio:12.1f}  {mk} kind={f['kind']} K/S={f['K']/m['S']:.3f} gap={f['gap']:.3g}")
print("engine errors:")
for k, v in errs.most_common(15):
    print("  ", v, k)
