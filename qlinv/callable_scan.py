"""Model-free invariant scan for QuantLib callable / puttable fixed-rate bonds.

Spec (model-free, holds under any arbitrage-free short-rate model that fits the curve):
  Let T_i = "bond truncated at call date c_i": all coupons paid on dates <= c_i,
  plus at c_i the call amount = call clean price + accrued(c_i)
  (coupons paid strictly after c_i are replaced by the call; accrued covers them).
  Let S = straight bond (no call).
  Callable  (issuer option):  V_call <= min(S, min_i T_i)
  Puttable  (holder option):  V_put  >= max(S, max_i T_i)
  As vol -> 0 (deterministic rates) both become equalities.
  Callable value is non-increasing in vol; puttable non-decreasing.
  Moving a single call date by one day moves V by at most a few days of carry.

The reference values S and T_i are computed here from the raw coupon list and
curve discount factors -- NOT with a QuantLib bond engine -- so the oracle does
not share the tree engine's event-handling code. Schedule/coupon generation and
accrual are taken from QuantLib cash flows (that is the contract spec, shared).
"""
import json, math, random, sys, time
import QuantLib as ql

CALS = {"Null": ql.NullCalendar(), "TARGET": ql.TARGET(),
        "US": ql.UnitedStates(ql.UnitedStates.GovernmentBond)}
CONVS = {"Unadjusted": ql.Unadjusted, "Following": ql.Following,
         "ModFollowing": ql.ModifiedFollowing}
DCS = {"30/360": ql.Thirty360(ql.Thirty360.BondBasis),
       "ActAct": ql.ActualActual(ql.ActualActual.Bond),
       "Act365": ql.Actual365Fixed()}
FREQS = {"A": ql.Annual, "S": ql.Semiannual, "Q": ql.Quarterly}


def make_case(rng):
    today = ql.Date(1, 1, 2020) + rng.randrange(0, 3 * 365)
    issue = today - rng.randrange(30, 3 * 365)
    years = rng.randrange(2, 16)
    maturity = issue + ql.Period(years, ql.Years) + rng.randrange(-40, 40)
    c = dict(
        today=today.serialNumber(), issue=issue.serialNumber(),
        maturity=maturity.serialNumber(),
        freq=rng.choice(list(FREQS)), cal=rng.choice(list(CALS)),
        conv=rng.choice(list(CONVS)), dc=rng.choice(list(DCS)),
        coupon=round(rng.uniform(0.0, 0.12), 4), rate=round(rng.uniform(0.0, 0.10), 4),
        settle=rng.choice([0, 2]), call_price=round(rng.uniform(95, 105), 2),
        a=rng.choice([0.01, 0.1]), sigma=rng.choice([1e-6, 0.005, 0.01, 0.02]),
        kind=rng.choice(["call", "put"]), style=rng.choice(["single", "bermudan"]),
        on_coupon=rng.random() < 0.5,  # snap call dates onto (unadjusted) coupon dates
    )
    return c


class Ctx:
    def __init__(self, c, grid):
        self.c = c
        self.today = ql.Date(c["today"])
        ql.Settings.instance().evaluationDate = self.today
        cal, conv = CALS[c["cal"]], CONVS[c["conv"]]
        self.sched = ql.Schedule(ql.Date(c["issue"]), ql.Date(c["maturity"]),
                                 ql.Period(FREQS[c["freq"]]), cal, ql.Unadjusted,
                                 ql.Unadjusted, ql.DateGeneration.Backward, False)
        self.dc = DCS[c["dc"]]
        self.conv = conv
        self.curve = ql.YieldTermStructureHandle(
            ql.FlatForward(self.today, c["rate"], ql.Actual365Fixed(), ql.Continuous))
        self.straight = ql.FixedRateBond(c["settle"], 100.0, self.sched, [c["coupon"]],
                                         self.dc, conv, 100.0, ql.Date(c["issue"]))
        self.settle = self.straight.settlementDate()
        self.grid = grid

    # ---- independent oracle -------------------------------------------------
    def coupons(self):
        out = []
        for cf in self.straight.cashflows():
            cp = ql.as_fixed_rate_coupon(cf)
            out.append((cf.date(), cf.amount(), cp))
        return out

    def pv(self, flows):
        d0 = self.curve.discount(self.settle)
        return sum(a * self.curve.discount(d) / d0 for d, a in flows if d > self.settle)

    def accrued(self, d):
        acc = 0.0
        for date, amt, cp in self.coupons():
            if cp is None:
                continue
            if cp.accrualStartDate() < d <= cp.accrualEndDate() and date > d:
                acc += cp.accruedAmount(d)
        return acc

    def S(self):
        return self.pv([(d, a) for d, a, _ in self.coupons()])

    def T(self, cd):
        flows = [(d, a) for d, a, cp in self.coupons() if d <= cd and cp is not None]
        flows.append((cd, self.c["call_price"] + self.accrued(cd)))
        return self.pv(flows)

    # ---- QuantLib under test --------------------------------------------------
    def ql_price(self, call_dates, sigma=None, grid=None, kind=None):
        c = self.c
        kind = kind or c["kind"]
        cs = ql.CallabilitySchedule()
        for d in call_dates:
            cs.append(ql.Callability(ql.BondPrice(c["call_price"], ql.BondPrice.Clean),
                                     ql.Callability.Call if kind == "call" else ql.Callability.Put, d))
        b = ql.CallableFixedRateBond(c["settle"], 100.0, self.sched, [c["coupon"]], self.dc,
                                     self.conv, 100.0, ql.Date(c["issue"]), cs)
        model = ql.HullWhite(self.curve, c["a"], sigma if sigma is not None else c["sigma"])
        b.setPricingEngine(ql.TreeCallableFixedRateBondEngine(model, grid or self.grid))
        return b.dirtyPrice()


def call_dates_for(ctx, rng):
    c = ctx.c
    lo = ctx.settle + 10
    hi = ql.Date(c["maturity"]) - 10
    if hi <= lo:
        return None
    if c["on_coupon"]:
        cands = [d for d in ctx.sched if lo < d < hi]
        if not cands:
            return None
        if c["style"] == "single":
            return [rng.choice(cands)]
        k = rng.randrange(len(cands))
        return cands[k:]
    if c["style"] == "single":
        return [lo + rng.randrange(0, hi - lo)]
    start = lo + rng.randrange(0, max(1, (hi - lo) // 2))
    step = rng.choice([30, 91, 182])
    out, d = [], start
    while d < hi:
        out.append(d)
        d = d + step
    return out


def check(c, rng, grid=200, cds=None, ctx_cls=None):
    ctx = (ctx_cls or Ctx)(c, grid)
    cds = cds if cds is not None else call_dates_for(ctx, rng)
    if not cds:
        return None
    c["call_dates"] = [d.serialNumber() for d in cds]
    S = ctx.S()
    Ts = [ctx.T(d) for d in cds]
    v = ctx.ql_price(cds)
    v2 = ctx.ql_price(cds, grid=2 * grid)
    tol = 3 * abs(v - v2) + 1e-4  # discretization estimate + floor (price per 100)
    res = dict(S=S, Tmin=min(Ts), Tmax=max(Ts), V=v, V2=v2, tol=tol, viol=[])
    if c["kind"] == "call":
        bound = min(S, min(Ts))
        if v > bound + tol:
            res["viol"].append(("call_upper", v - bound))
        if c["sigma"] <= 1e-6 and v < bound - tol:
            res["viol"].append(("call_zero_vol_eq", bound - v))
        vhi = ctx.ql_price(cds, sigma=c["sigma"] + 0.01)
        if vhi > v + tol:
            res["viol"].append(("call_vol_monotone", vhi - v))
    else:
        bound = max(S, max(Ts))
        if v < bound - tol:
            res["viol"].append(("put_lower", bound - v))
        if c["sigma"] <= 1e-6 and v > bound + tol:
            res["viol"].append(("put_zero_vol_eq", v - bound))
        vhi = ctx.ql_price(cds, sigma=c["sigma"] + 0.01)
        if vhi < v - tol:
            res["viol"].append(("put_vol_monotone", v - vhi))
    if c["style"] == "single":
        vs = ctx.ql_price([cds[0] + 1])
        if abs(vs - v) > 0.15 + tol:
            res["viol"].append(("calldate_continuity", vs - v))
    return res


def main(n, seed, out):
    rng = random.Random(seed)
    stats = dict(cases=0, skipped=0, errors=0, viol_cases=0)
    t0 = time.time()
    with open(out, "w", encoding="utf8") as f:
        for i in range(n):
            c = make_case(rng)
            try:
                r = check(c, rng)
            except Exception as e:  # record, don't hide
                stats["errors"] += 1
                f.write(json.dumps(dict(i=i, case=c, error=repr(e))) + "\n")
                continue
            if r is None:
                stats["skipped"] += 1
                continue
            stats["cases"] += 1
            if r["viol"]:
                stats["viol_cases"] += 1
            f.write(json.dumps(dict(i=i, case=c, **r)) + "\n")
    stats["secs"] = round(time.time() - t0, 1)
    print(json.dumps(stats))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3])
