import QuantLib as ql
today = ql.Date(15, 10, 2026); ql.Settings.instance().evaluationDate = today
dc, cal = ql.Actual365Fixed(), ql.NullCalendar()
p = ql.BlackScholesMertonProcess(ql.QuoteHandle(ql.SimpleQuote(100.0)),
    ql.YieldTermStructureHandle(ql.FlatForward(today, 0.05, dc)),
    ql.YieldTermStructureHandle(ql.FlatForward(today, 0.40, dc)),
    ql.BlackVolTermStructureHandle(ql.BlackConstantVol(today, cal, 0.15, dc)))
pay = ql.PlainVanillaPayoff(ql.Option.Put, 100.0)
print("T*days", (2*0.15/0.35)**2*365)
for d in [30,60,91,120,150,182,220,250,268,280,300,365,730]:
    am = ql.VanillaOption(pay, ql.AmericanExercise(today, today+d))
    eu = ql.VanillaOption(pay, ql.EuropeanExercise(today+d))
    am.setPricingEngine(ql.BjerksundStenslandApproximationEngine(p)); b=am.NPV()
    am.setPricingEngine(ql.QdFpAmericanEngine(p, ql.QdFpAmericanEngine.highPrecisionScheme())); q=am.NPV()
    eu.setPricingEngine(ql.AnalyticEuropeanEngine(p)); e=eu.NPV()
    print(f"{d:4d} BJS {b:.6f} QdFp {q:.6f} Eu {e:.6f} err {100*(b/q-1):+.2f}%")
