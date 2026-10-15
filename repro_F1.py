import QuantLib as ql
today = ql.Date(15, 10, 2026); ql.Settings.instance().evaluationDate = today
dc, cal = ql.Actual365Fixed(), ql.NullCalendar()
def proc(S, r, q, vol):
    return ql.BlackScholesMertonProcess(ql.QuoteHandle(ql.SimpleQuote(S)),
        ql.YieldTermStructureHandle(ql.FlatForward(today, q, dc)),
        ql.YieldTermStructureHandle(ql.FlatForward(today, r, dc)),
        ql.BlackVolTermStructureHandle(ql.BlackConstantVol(today, cal, vol, dc)))
p = proc(100.0, 0.40, 0.05, 0.15)          # e.g. American put on a high-carry currency pair
opt = ql.VanillaOption(ql.PlainVanillaPayoff(ql.Option.Put, 100.0),
                       ql.AmericanExercise(today, today + 365))
for name, eng in [("BjerksundStensland", ql.BjerksundStenslandApproximationEngine(p)),
                  ("QdFp highPrecision", ql.QdFpAmericanEngine(p, ql.QdFpAmericanEngine.highPrecisionScheme())),
                  ("Binomial CRR 4001", ql.BinomialVanillaEngine(p, "crr", 4001))]:
    opt.setPricingEngine(eng); print(name, opt.NPV())
