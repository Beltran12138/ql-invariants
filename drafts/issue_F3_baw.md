**Title:** Barone-Adesi-Whaley and Ju raise "forward + displacement must be positive" for valid low-volatility inputs

For an American call with q > r, low volatility and a maturity of a few years, both `BaroneAdesiWhaleyApproximationEngine` and `JuQuadraticApproximationEngine` throw instead of returning a value.

```python
import QuantLib as ql
today = ql.Date(15, 10, 2026); ql.Settings.instance().evaluationDate = today
dc, cal = ql.Actual365Fixed(), ql.NullCalendar()
def proc(S, r, q, vol):
    return ql.BlackScholesMertonProcess(ql.QuoteHandle(ql.SimpleQuote(S)),
        ql.YieldTermStructureHandle(ql.FlatForward(today, q, dc)),
        ql.YieldTermStructureHandle(ql.FlatForward(today, r, dc)),
        ql.BlackVolTermStructureHandle(ql.BlackConstantVol(today, cal, vol, dc)))
for vol in [0.02, 0.0166]:
    p = proc(100.0, 0.0257, 0.0571, vol)
    for name, eng in [("BaroneAdesiWhaley", ql.BaroneAdesiWhaleyApproximationEngine(p)),
                      ("JuQuadratic", ql.JuQuadraticApproximationEngine(p)),
                      ("QdPlus", ql.QdPlusAmericanEngine(p))]:
        o = ql.VanillaOption(ql.PlainVanillaPayoff(ql.Option.Call, 100.0),
                             ql.AmericanExercise(today, today + 3 * 365))
        o.setPricingEngine(eng)
        try:
            print(f"vol={vol}", name, o.NPV())
        except RuntimeError as e:
            print(f"vol={vol}", name, "RuntimeError:", e)
```

With 1.44:

```
vol=0.02 BaroneAdesiWhaley 0.22034947078018516
vol=0.02 JuQuadratic 0.23110729464344432
vol=0.02 QdPlus 0.23323815939473516
vol=0.0166 BaroneAdesiWhaley RuntimeError: forward + displacement (-1665.46 + 0) must be positive
vol=0.0166 JuQuadratic RuntimeError: forward + displacement (-1665.46 + 0) must be positive
vol=0.0166 QdPlus 0.16102887544621583
```

The same happens for every strike from 50 to 200 at vol 1.66% and 1%. In a random scan the exception appeared in 7 of 300 markets, all with vol between 1.66% and 2.34% and T of 1 year or more; the forward in the message was sometimes 0 and sometimes negative.

This is not #2749: that one needed σ√T below about 7e-4, failed on an overflowing seed (`inf forward`), and was fixed by #2755, which is in 1.44. Here σ√T ≈ 0.029 and the forward in the message is negative.

The message is consistent with the Newton step in `BaroneAdesiWhaleyApproximationEngine::criticalPrice`, `Si = (K + RHS - bi * Si) / (1 - bi)`, leaving the positive axis (Ju reuses `criticalPrice`): the seed has a guard (`if (!(Si > 0.0) || !std::isfinite(Si)) Si = Su;`), the iterates do not. I have not stepped through it, so take that as a guess. Damping the step or bracketing `Si` above the strike would be the obvious directions.
