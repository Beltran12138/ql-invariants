For an American option whose call-equivalent has negative carry b (a put with r > q, or a call with q > r), `BjerksundStenslandApproximationEngine` returns the European price whenever |b|·√T > 2σ. The American value can be many times larger.

```python
import QuantLib as ql
today = ql.Date(15, 10, 2026); ql.Settings.instance().evaluationDate = today
dc, cal = ql.Actual365Fixed(), ql.NullCalendar()
def proc(S, r, q, vol):
    return ql.BlackScholesMertonProcess(ql.QuoteHandle(ql.SimpleQuote(S)),
        ql.YieldTermStructureHandle(ql.FlatForward(today, q, dc)),
        ql.YieldTermStructureHandle(ql.FlatForward(today, r, dc)),
        ql.BlackVolTermStructureHandle(ql.BlackConstantVol(today, cal, vol, dc)))
p = proc(100.0, 0.40, 0.05, 0.15)
opt = ql.VanillaOption(ql.PlainVanillaPayoff(ql.Option.Put, 100.0),
                       ql.AmericanExercise(today, today + 365))
for name, eng in [("BjerksundStensland", ql.BjerksundStenslandApproximationEngine(p)),
                  ("QdFp highPrecision", ql.QdFpAmericanEngine(p, ql.QdFpAmericanEngine.highPrecisionScheme())),
                  ("Binomial CRR 4001", ql.BinomialVanillaEngine(p, "crr", 4001))]:
    opt.setPricingEngine(eng); print(name, opt.NPV())
```

With 1.44:

```
BjerksundStensland 0.0396681860081434
QdFp highPrecision 1.1569888350901052
Binomial CRR 4001 1.1563056080539456
```

The BJS value equals the analytic European price to every digit. The call with r = 5%, q = 40% gives the same numbers.

**Where it happens.** In `americanCallApproximation`,

```cpp
const Real ht = -(bT + 2.0*std::sqrt(variance)) * B0 / (BInfinity - B0);
const Real I  = B0 + (BInfinity - B0) * (1 - std::exp(ht));
```

When `bT + 2*sqrt(variance) < 0`, `ht > 0` and the trigger `I` falls below `B0 >= X`; for long enough maturities it is negative. `S >= I` then selects `immediateExercise` (zero at the money), and the final `if (results.value < europeanResults.value)` replaces it with the European value.

The onset matches T* = (2σ/|b|)². With r = 7.68%, q = 0.75%, σ = 2.31% (T* ≈ 0.44y), an at-the-money American put prices at 0.134 for 91 days and 0.0098 for 182 days under BJS, while FD stays near 0.140. With usual equity inputs (r = 5%, q = 1%, σ = 25%), T* is about 156 years, which is probably why the existing tests do not see it.

The returned value is finite and above intrinsic, so NaN or below-intrinsic checks do not catch it. It shows up as an American price that decreases with maturity.

I have not checked whether the 1993 paper restricts the formula to this domain. Clamping `I` at `B0` would not help at the money, since `S >= B0` still selects immediate exercise. Raising outside the domain, as Barone-Adesi-Whaley does for negative rates, might be the least surprising behaviour, but that is your call.

Found with a model-free invariant scan (American value non-decreasing in maturity); FD 2000×2000, CRR 4001 and QdFp high precision agree to about 1e-3.
