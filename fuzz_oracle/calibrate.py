"""Calibrate the invariant oracle proposed for QuantLib's fuzz-test-suite.

Samples the same input domain as fuzz-test-suite/fuzz_vanilla_option.cpp
(type, K, S in [1,500], r in [-0.02,0.15], q in [0,0.10], vol in [0.01,3],
maturity 7..3650 days, Actual360, today 2025-01-15) uniformly, and applies
the checks the new fuzzer would make. Reports violation counts per engine.
"""
import sys, json, random, math
import QuantLib as ql

N = int(sys.argv[1]); seed = int(sys.argv[2]); out = sys.argv[3]
rng = random.Random(seed)
today = ql.Date(15, 1, 2025); ql.Settings.instance().evaluationDate = today
dc = ql.Actual360()

def proc(S, r, q, v):
    return ql.BlackScholesMertonProcess(ql.QuoteHandle(ql.SimpleQuote(S)),
        ql.YieldTermStructureHandle(ql.FlatForward(today, q, dc)),
        ql.YieldTermStructureHandle(ql.FlatForward(today, r, dc)),
        ql.BlackVolTermStructureHandle(ql.BlackConstantVol(today, ql.NullCalendar(), v, dc)))

ENGINES = {
    "BAW": lambda p: ql.BaroneAdesiWhaleyApproximationEngine(p),
    "BJS": lambda p: ql.BjerksundStenslandApproximationEngine(p),
    "Ju": lambda p: ql.JuQuadraticApproximationEngine(p),
    "QdPlus": lambda p: ql.QdPlusAmericanEngine(p),
    "QdFp": lambda p: ql.QdFpAmericanEngine(p, ql.QdFpAmericanEngine.highPrecisionScheme()),
}

def price(eng, p, typ, K, days, american=True):
    pay = ql.PlainVanillaPayoff(typ, K)
    ex = ql.AmericanExercise(today, today + days) if american else ql.EuropeanExercise(today + days)
    o = ql.VanillaOption(pay, ex)
    o.setPricingEngine(eng(p) if american else ql.AnalyticEuropeanEngine(p))
    return o.NPV()

with open(out, "w") as f:
    for i in range(N):
        typ = rng.choice([ql.Option.Put, ql.Option.Call])
        K = rng.uniform(1, 500); S = rng.uniform(1, 500)
        r = rng.uniform(-0.02, 0.15); q = rng.uniform(0.0, 0.10)
        v = rng.uniform(0.01, 3.0); days = rng.randint(7, 3650)
        d2 = days + max(1, days // 10)
        p = proc(S, r, q, v)
        eu = price(None, p, typ, K, days, american=False)
        intr = max(S - K, 0) if typ == ql.Option.Call else max(K - S, 0)
        rec = dict(i=i, typ="C" if typ == ql.Option.Call else "P", K=K, S=S, r=r, q=q, v=v, days=days, d2=d2, eu=eu, intr=intr, res={})
        for name, eng in ENGINES.items():
            try:
                a1 = price(eng, p, typ, K, days); a2 = price(eng, p, typ, K, d2)
                rec["res"][name] = [a1, a2]
            except RuntimeError as e:
                rec["res"][name] = str(e)[:80]
        f.write(json.dumps(rec) + "\n")
