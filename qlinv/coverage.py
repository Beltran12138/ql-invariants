"""Coverage report for a scan jsonl: denominators by dimension + edge regions."""
import json, sys, collections
import QuantLib as ql
from qlinv.callable_scan import Ctx

path = sys.argv[1]
dims = ["kind", "style", "cal", "conv", "dc", "freq", "sigma", "on_coupon", "settle"]
cnt = {d: collections.Counter() for d in dims}
edge = collections.Counter()
viol = collections.Counter()
n = 0
for line in open(path, encoding="utf8"):
    r = json.loads(line)
    if "error" in r:
        continue
    n += 1
    c = r["case"]
    for d in dims:
        cnt[d][str(c[d])] += 1
    for v in r["viol"]:
        viol[v[0]] += 1
    ctx = Ctx(c, 10)
    pays = [cf.date() for cf in ctx.straight.cashflows()]
    unadj = list(ctx.sched)
    cds = [ql.Date(s) for s in c["call_dates"]]
    w7 = any(0 < (p - cd) <= 7 for cd in cds for p in pays)
    adj = any(cd in unadj and cd not in pays for cd in cds)  # call on unadjusted coupon date whose payment moved
    nonbiz = any(not ctx.sched.calendar().isBusinessDay(cd) for cd in cds)
    edge["call_within_7d_before_payment"] += w7
    edge["call_on_unadjusted_coupon_date_payment_moved"] += adj
    edge["call_on_non_business_day"] += nonbiz
    edge["zero_vol"] += c["sigma"] <= 1e-6
print("cases", n)
for d in dims:
    print(f"  {d:10s}", dict(cnt[d]))
print("edge regions", dict(edge))
print("violations", dict(viol))
