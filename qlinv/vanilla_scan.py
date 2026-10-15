"""Model-free invariant scan for QuantLib vanilla option engines (Black-Scholes-Merton process).

For each random market (S, r, q, sigma, T) we price a strip of strikes with every
engine and check, per engine:
  bounds      European: max(0, S e^-qT - K e^-rT) <= C <= S e^-qT ; put analogous
              American: max(intrinsic, European lower bound) <= C <= S ; P <= K
  parity      European: C - P = S e^-qT - K e^-rT
              American: S e^-qT - K <= C - P <= S - K e^-rT
  slope_K     European call: -e^-rT <= dC/dK <= 0 ; put: 0 <= dP/dK <= e^-rT
              American call: -1 <= dC/dK <= 0 ; put: 0 <= dP/dK <= 1
  convex_K    second difference in K >= 0
  vol_mono    price non-decreasing in sigma
  am_ge_eu    American >= analytic European
  am_call_q0  American call with q = 0, r >= 0  ==  European call
  am_T_mono   American price non-decreasing in T
Tolerances: engine-specific error estimate (N vs 2N steps for lattices / FD; 4 standard
errors for MC) times 3, plus a floor of 1e-7 * S. Closed-form approximations
(BAW, Bjerksund-Stensland, Ju) have no refinement knob; their tolerance is the floor, and
their violations are reported as a separate class ("approximation"), not as bugs.
"""
import json, math, random, sys, time
import QuantLib as ql

TODAY = ql.Date(15, 10, 2026)
DC = ql.Actual365Fixed()
CAL = ql.NullCalendar()


def process(S, r, q, vol):
    ql.Settings.instance().evaluationDate = TODAY
    return ql.BlackScholesMertonProcess(
        ql.QuoteHandle(ql.SimpleQuote(S)),
        ql.YieldTermStructureHandle(ql.FlatForward(TODAY, q, DC)),
        ql.YieldTermStructureHandle(ql.FlatForward(TODAY, r, DC)),
        ql.BlackVolTermStructureHandle(ql.BlackConstantVol(TODAY, CAL, vol, DC)))


# engine name -> (exercise kind, factory(process, refine_level) , class)
def lattice(tree):
    return lambda p, lv: ql.BinomialVanillaEngine(p, tree, 400 * 2 ** lv + 1)


ENGINES = {
    "analytic": ("E", lambda p, lv: ql.AnalyticEuropeanEngine(p), "exact"),
    "integral": ("E", lambda p, lv: ql.IntegralEngine(p), "exact"),
    "fd_eu": ("E", lambda p, lv: ql.FdBlackScholesVanillaEngine(p, 100 * 2 ** lv, 200 * 2 ** lv), "refine"),
    "mc_eu": ("E", None, "mc"),
    **{f"bin_{t}_eu": ("E", lattice(t), "refine") for t in ["crr", "jr", "eqp", "trigeorgis", "tian", "lr", "joshi4"]},
    "fd_am": ("A", lambda p, lv: ql.FdBlackScholesVanillaEngine(p, 100 * 2 ** lv, 200 * 2 ** lv), "refine"),
    **{f"bin_{t}_am": ("A", lattice(t), "refine") for t in ["crr", "lr", "joshi4"]},
    "baw": ("A", lambda p, lv: ql.BaroneAdesiWhaleyApproximationEngine(p), "approx"),
    "bjs": ("A", lambda p, lv: ql.BjerksundStenslandApproximationEngine(p), "approx"),
    "ju": ("A", lambda p, lv: ql.JuQuadraticApproximationEngine(p), "approx"),
    "qdplus": ("A", lambda p, lv: ql.QdPlusAmericanEngine(p), "approx"),
    "qdfp": ("A", lambda p, lv: ql.QdFpAmericanEngine(p, ql.QdFpAmericanEngine.accurateScheme()), "refine0"),
}


def days(T):
    return max(1, int(round(T * 365)))


def option(kind, K, T, ex):
    mat = TODAY + days(T)
    payoff = ql.PlainVanillaPayoff(ql.Option.Call if kind == "C" else ql.Option.Put, K)
    exercise = ql.EuropeanExercise(mat) if ex == "E" else ql.AmericanExercise(TODAY, mat)
    return ql.VanillaOption(payoff, exercise)


def price(name, kind, S, K, T, r, q, vol, lv=0, seed=42):
    ex, fac, cls = ENGINES[name]
    p = process(S, r, q, vol)
    o = option(kind, K, T, ex)
    if cls == "mc":
        eng = ql.MCEuropeanEngine(p, "pseudorandom", timeSteps=1, requiredSamples=200000,
                                  seed=seed, antitheticVariate=True)
        o.setPricingEngine(eng)
        return o.NPV(), 4 * o.errorEstimate()
    o.setPricingEngine(fac(p, lv))
    v = o.NPV()
    if cls == "refine":
        o2 = option(kind, K, T, ex)
        o2.setPricingEngine(fac(p, lv + 1))
        return v, 3 * abs(v - o2.NPV())
    return v, 0.0


def check_market(m, engines):
    S, r, q, vol = m["S"], m["r"], m["q"], m["vol"]
    T = days(m["T"]) / 365.0  # exact year fraction the engines see (Act/365, integer days)
    Ks = [S * x for x in m["kx"]]
    floor = 1e-7 * S
    dq, dr = math.exp(-q * T), math.exp(-r * T)
    out = []

    def add(eng, inv, kind, K, gap, tol):
        out.append(dict(engine=eng, inv=inv, kind=kind, K=K, gap=gap, tol=tol,
                        cls=ENGINES[eng][2]))

    for name in engines:
        try:
            out.extend(check_engine(name, S, r, q, vol, T, Ks, floor, dq, dr))
        except Exception as e:
            out.append(dict(engine=name, inv="engine_error", error=repr(e)[:200], cls=ENGINES[name][2]))
    return out


def check_engine(name, S, r, q, vol, T, Ks, floor, dq, dr):
    out = []

    def add(eng, inv, kind, K, gap, tol):
        out.append(dict(engine=eng, inv=inv, kind=kind, K=K, gap=gap, tol=tol,
                        cls=ENGINES[eng][2]))

    if True:
        ex = ENGINES[name][0]
        P = {}
        for kind in "CP":
            for K in Ks:
                P[(kind, K)] = price(name, kind, S, K, T, r, q, vol)
        for K in Ks:
            (c, ec), (p, ep) = P[("C", K)], P[("P", K)]
            tc, tp = ec + floor, ep + floor
            if ex == "E":
                lo_c, hi_c = max(0.0, S * dq - K * dr), S * dq
                lo_p, hi_p = max(0.0, K * dr - S * dq), K * dr
            else:
                lo_c, hi_c = max(0.0, S - K, S * dq - K * dr), S
                # r < 0: American put >= European put which can exceed K, so the cap is max(K, K e^-rT)
                lo_p, hi_p = max(0.0, K - S, K * dr - S * dq), max(K, K * dr)
            if c < lo_c - tc: add(name, "bounds_lo", "C", K, lo_c - c, tc)
            if c > hi_c + tc: add(name, "bounds_hi", "C", K, c - hi_c, tc)
            if p < lo_p - tp: add(name, "bounds_lo", "P", K, lo_p - p, tp)
            if p > hi_p + tp: add(name, "bounds_hi", "P", K, p - hi_p, tp)
            d = c - p
            if ex == "E":
                f = S * dq - K * dr
                if abs(d - f) > tc + tp: add(name, "parity", "CP", K, d - f, tc + tp)
            elif r >= 0:  # textbook American put-call inequality assumes r >= 0, q >= 0
                if d < S * dq - K - tc - tp: add(name, "parity_am_lo", "CP", K, S * dq - K - d, tc + tp)
                if d > S - K * dr + tc + tp: add(name, "parity_am_hi", "CP", K, d - (S - K * dr), tc + tp)
        for kind in "CP":
            for i in range(len(Ks) - 1):
                K0, K1 = Ks[i], Ks[i + 1]
                (v0, e0), (v1, e1) = P[(kind, K0)], P[(kind, K1)]
                tol = (e0 + e1 + 2 * floor) / (K1 - K0)
                s = (v1 - v0) / (K1 - K0)
                bnd = dr if ex == "E" else 1.0
                if kind == "C" and (s > tol or s < -bnd - tol): add(name, "slope_K", kind, K0, s, tol)
                if kind == "P" and (s < -tol or s > bnd + tol): add(name, "slope_K", kind, K0, s, tol)
            for i in range(1, len(Ks) - 1):
                (a, ea), (b, eb), (cc, ec2) = P[(kind, Ks[i - 1])], P[(kind, Ks[i])], P[(kind, Ks[i + 1])]
                h0, h1 = Ks[i] - Ks[i - 1], Ks[i + 1] - Ks[i]
                conv = (cc - b) / h1 - (b - a) / h0
                tol = (ea + eb + ec2 + 3 * floor) * (1 / h0 + 1 / h1)
                if conv < -tol: add(name, "convex_K", kind, Ks[i], conv, tol)
        # vol monotonicity and American-specific checks at the ATM strike
        K = Ks[len(Ks) // 2]
        for kind in "CP":
            v, e = P[(kind, K)]
            vh, eh = price(name, kind, S, K, T, r, q, vol * 1.25)
            if vh < v - e - eh - 2 * floor: add(name, "vol_mono", kind, K, vh - v, e + eh + 2 * floor)
            if ex == "A":
                eu, _ = price("analytic", kind, S, K, T, r, q, vol)
                if v < eu - e - floor: add(name, "am_ge_eu", kind, K, eu - v, e + floor)
                vT, eT = price(name, kind, S, K, T * 1.5, r, q, vol)
                if vT < v - e - eT - 2 * floor: add(name, "am_T_mono", kind, K, v - vT, e + eT + 2 * floor)
        if ex == "A" and r >= 0:
            v, e = price(name, "C", S, K, T, r, 0.0, vol)
            eu, _ = price("analytic", "C", S, K, T, r, 0.0, vol)
            if abs(v - eu) > e + floor: add(name, "am_call_q0", "C", K, v - eu, e + floor)
    return out


def make_market(rng):
    return dict(S=round(rng.choice([1.0, 10.0, 100.0, 5000.0]) * rng.uniform(0.5, 2.0), 6),
                r=round(rng.uniform(-0.01, 0.10), 4), q=round(rng.uniform(0.0, 0.08), 4),
                vol=round(rng.choice([0.02, 0.1, 0.25, 0.6, 1.2]) * rng.uniform(0.8, 1.2), 4),
                T=round(rng.choice([1 / 365, 7 / 365, 0.1, 0.5, 1.0, 3.0, 10.0]), 6),
                kx=sorted({round(x, 4) for x in [0.5, 0.8, 0.9, 0.95, 1.0, 1.05, 1.1, 1.25, 2.0]}))


def main(n, seed, out, engines):
    rng = random.Random(seed)
    stats = dict(markets=0, errors=0, findings=0)
    t0 = time.time()
    with open(out, "w", encoding="utf8") as f:
        for i in range(n):
            m = make_market(rng)
            try:
                res = check_market(m, engines)
            except Exception as e:
                stats["errors"] += 1
                f.write(json.dumps(dict(i=i, market=m, error=repr(e))) + "\n")
                continue
            stats["markets"] += 1
            stats["findings"] += len(res)
            f.write(json.dumps(dict(i=i, market=m, findings=res)) + "\n")
    stats["secs"] = round(time.time() - t0, 1)
    print(json.dumps(stats))


if __name__ == "__main__":
    engines = sys.argv[4].split(",") if len(sys.argv) > 4 else [e for e in ENGINES if e != "mc_eu"]
    main(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3], engines)
