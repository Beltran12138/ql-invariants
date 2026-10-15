# Findings

## F1. BjerksundStenslandApproximationEngine silently returns the European value when the trigger falls below B0 (negative carry, |b|·√T > 2σ)

Status: confirmed on QuantLib Python 1.44 (released 2026-10-13). The relevant code on master
(89057b22da, 2026-10-15) is unchanged; the only diff vs v1.44 is the zero-variance branch (#2854).
Not yet reported upstream (searched QuantLib issues/PRs for "Bjerksund", "trigger price",
"negative carry"; the three recent BJS PRs #2728/#2814/#2854 fix NaN, beta=1 and zero-vol cases,
whose checks — NaN, below-intrinsic — cannot see this one because the returned European value is
finite and above intrinsic).

### Minimal reproduction

```python
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
```

Observed (QuantLib 1.44):

| engine | value |
|---|---|
| BjerksundStensland | 0.0397 (= European analytic, every digit) |
| QdFp high precision | 1.15699 |
| Binomial CRR 4001 | 1.15631 |
| FD 2000×2000 | 1.1553 |
| QD+ | 1.1605 |
| Barone-Adesi-Whaley | 1.1010 |

BJS underprices by ~97%. The symmetric call (r=5%, q=40%) gives the same numbers.

### Root cause (bjerksundstenslandengine.cpp, americanCallApproximation)

The put is priced as a call via put-call symmetry (spot↔strike, r↔q), so the call-equivalent has
carry b' = q − r < 0. Then

    ht = -(bT + 2*sqrt(variance)) * B0 / (BInfinity - B0)
    I  = B0 + (BInfinity - B0) * (1 - exp(ht))

When bT + 2σ√T < 0, i.e. |b'|·√T > 2σ, ht > 0 and the trigger I drops below B0 = max(X, rT/(rT−bT)·X) ≥ X —
an exercise boundary below the strike, which is impossible for a call. For long enough maturities I
becomes negative. The engine then takes `S >= I` → `immediateExercise` (worth 0 at the money), and the
final `if (results.value < europeanResults.value) results = europeanResults;` returns the European price.

The breakdown threshold T* = (2σ/|b'|)² matches the observed onset: for r=7.68%, q=0.75%, σ=2.31%,
T* = 0.444y and the BJS value collapses to European between 150 and 182 days (probe_bjs_T.py);
for r=40%, q=5%, σ=15%, T* = 0.735y. With typical equity inputs (r=5%, q=1%, σ=25%) T* = 156y and BJS is fine
(−1.3% vs FD at 1y), which is why ordinary tests do not see it.

### How it was found

Invariant `am_T_mono` (an American option is non-decreasing in maturity) failed for BJS in a random
market; BJS's value fell from 0.134 at 91 days to 0.0098 at 182 days while FD stayed at ~0.140.

### Not claimed

- That the BJS (1993) formula itself is valid in this regime. Whether the paper restricts it is not
  checked (original paper not read). The point is that QuantLib returns a ~97%-wrong price silently,
  whereas Barone-Adesi-Whaley raises for inputs outside its domain (negative rates).
- A fix. Clamping I at B0 does not help (S ≥ B0 at the money → still European). Options for the
  maintainers: raise / flag outside the domain, or fall back to another engine. Their call.
