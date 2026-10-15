**Title:** JuQuadraticApproximationEngine can price an American option below the European value

f5b6d212 floors the Ju approximation at the exercise value. An American option is also bounded below by the European value, which can be above the exercise value, and that bound is not enforced.

```python
import QuantLib as ql
today = ql.Date(15, 10, 2026); ql.Settings.instance().evaluationDate = today
dc, cal = ql.Actual365Fixed(), ql.NullCalendar()
def proc(S, r, q, vol):
    return ql.BlackScholesMertonProcess(ql.QuoteHandle(ql.SimpleQuote(S)),
        ql.YieldTermStructureHandle(ql.FlatForward(today, q, dc)),
        ql.YieldTermStructureHandle(ql.FlatForward(today, r, dc)),
        ql.BlackVolTermStructureHandle(ql.BlackConstantVol(today, cal, vol, dc)))
p = proc(100.0, 0.02, 0.0, 0.80)
payoff = ql.PlainVanillaPayoff(ql.Option.Put, 110.0)
am = ql.VanillaOption(payoff, ql.AmericanExercise(today, today + 3))
eu = ql.VanillaOption(payoff, ql.EuropeanExercise(today + 3))
am.setPricingEngine(ql.JuQuadraticApproximationEngine(p)); print("Ju", am.NPV())
eu.setPricingEngine(ql.AnalyticEuropeanEngine(p)); print("European", eu.NPV())
am.setPricingEngine(ql.QdFpAmericanEngine(p, ql.QdFpAmericanEngine.highPrecisionScheme())); print("QdFp", am.NPV())
```

With 1.44:

```
Ju 10.0
European 10.319421294132978
QdFp 10.323291148853768
```

Here the correction term pushes the value below intrinsic, the new floor lifts it back to exactly 10, and the result is still 3.1% below the European price. On a grid of maturity {1, 2, 3, 5, 7, 14, 30} days × vol {0.1, 0.3, 0.5, 0.8, 1.2} × K/S {0.8, 0.9, 0.95, 1, 1.05, 1.1, 1.25} × r {0, 0.02, 0.06, 0.12} × q {0, 0.03, 0.08} × call/put, 43 of 5880 options come out below European, all at short maturities and high volatility.

Flooring at max(European, exercise value) would cover both, the way Bjerksund-Stensland already falls back to the European result (`if (results.value < europeanResults.value) results = europeanResults;`). Whether the greeks should follow the European ones in that case, as they do in BJS, is your call.
