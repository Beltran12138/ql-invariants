import QuantLib as ql

today = ql.Date(15, 10, 2026)
ql.Settings.instance().evaluationDate = today
dc, cal = ql.Actual365Fixed(), ql.NullCalendar()


def proc(S, r, q, vol):
    return ql.BlackScholesMertonProcess(ql.QuoteHandle(ql.SimpleQuote(S)),
        ql.YieldTermStructureHandle(ql.FlatForward(today, q, dc)),
        ql.YieldTermStructureHandle(ql.FlatForward(today, r, dc)),
        ql.BlackVolTermStructureHandle(ql.BlackConstantVol(today, cal, vol, dc)))


def opt(kind, K, days, american=True):
    ex = ql.AmericanExercise(today, today + days) if american else ql.EuropeanExercise(today + days)
    return ql.VanillaOption(ql.PlainVanillaPayoff(kind, K), ex)


print("--- F2: Ju below European")
p = proc(100.0, 0.02, 0.0, 0.80)
for name, o, eng in [("Ju (American)", opt(ql.Option.Put, 110.0, 3), ql.JuQuadraticApproximationEngine(p)),
                     ("European analytic", opt(ql.Option.Put, 110.0, 3, False), ql.AnalyticEuropeanEngine(p)),
                     ("QdFp (American)", opt(ql.Option.Put, 110.0, 3), ql.QdFpAmericanEngine(p, ql.QdFpAmericanEngine.highPrecisionScheme()))]:
    o.setPricingEngine(eng); print(name, o.NPV())

print("--- F3: BAW / Ju raise on valid low-vol inputs")
for vol in [0.02, 0.0166]:
    p = proc(100.0, 0.0257, 0.0571, vol)
    for name, eng in [("BaroneAdesiWhaley", ql.BaroneAdesiWhaleyApproximationEngine(p)),
                      ("JuQuadratic", ql.JuQuadraticApproximationEngine(p)),
                      ("QdPlus", ql.QdPlusAmericanEngine(p))]:
        o = opt(ql.Option.Call, 100.0, 3 * 365); o.setPricingEngine(eng)
        try:
            print(f"vol={vol}", name, o.NPV())
        except RuntimeError as e:
            print(f"vol={vol}", name, "RuntimeError:", e)
