# Findings

## F1. BjerksundStenslandApproximationEngine silently returns the European value when the trigger falls below B0 (negative carry, |b|·√T > 2σ)

Status: confirmed on QuantLib Python 1.44 (released 2026-10-13). The relevant code on master
(89057b22da, 2026-10-15) is unchanged; the only diff vs v1.44 is the zero-variance branch (#2854).
Reported upstream 2026-10-15: https://github.com/lballabio/QuantLib/issues/2903 (posted body verified identical to drafts/issue_F1_bjs.md). Before posting, searched QuantLib issues/PRs for "Bjerksund", "trigger price",
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

### Not claimed (F1)

- That the BJS (1993) formula itself is valid in this regime. Whether the paper restricts it is not
  checked (original paper not read). The point is that QuantLib returns a ~97%-wrong price silently,
  whereas Barone-Adesi-Whaley raises for inputs outside its domain (negative rates).
- A fix. Clamping I at B0 does not help (S ≥ B0 at the money → still European). Options for the
  maintainers: raise / flag outside the domain, or fall back to another engine. Their call.

## F2. JuQuadraticApproximationEngine can return less than the European value (minor)

Reported upstream 2026-10-15: https://github.com/lballabio/QuantLib/issues/2904 (posted body verified identical to drafts/issue_F2_ju.md).

Status: confirmed on QuantLib Python 1.44; master code path unchanged (latest commit on
juquadraticengine.cpp is f5b6d212, 2026-09-22, "Floor the Ju approximation at the exercise value").

That commit floors the approximation at the exercise value (intrinsic). An American option is also
bounded below by the European value, which can exceed intrinsic; the floor does not cover that.

Grid (probe_ju_grid.py): maturity {1,2,3,5,7,14,30} days × vol {0.1,0.3,0.5,0.8,1.2} × K/S {0.8…1.25}
× r {0,0.02,0.06,0.12} × q {0,0.03,0.08} × {call, put}: **43 / 5880** points below European.
Worst: put, T = 3 days, vol 80%, K/S = 1.1, r = 2%, q = 0 → Ju = 10.000000000000014 (exactly the
intrinsic floor), European = 10.3194, i.e. 3.1% below European. Second example from the random scan:
S=194.37, K/S=1.05, r=5.89%, q=4.23%, vol=64.77%, T=1 day: Ju put 9.8159, European 9.9355, FD 9.9379.

Suggested direction (maintainers' call): floor at max(European, exercise value), as
BjerksundStensland already does (`if (results.value < europeanResults.value) results = europeanResults;`).

## F3. Barone-Adesi-Whaley and Ju throw on valid low-volatility inputs (minor, robustness)

Status: observed on QuantLib Python 1.44. Suspected cause (not stepped through): the Newton step in BaroneAdesiWhaleyApproximationEngine::criticalPrice, Si = (K + RHS - bi*Si)/(1 - bi), leaves the positive axis; the seed is guarded, the iterates are not; Ju reuses criticalPrice. The forward in the message is sometimes 0, sometimes negative (-1665.46 in repro_F2_F3.py).

American call, S = 100, r = 2.57%, q = 5.71%, T = 3y: at vol = 1.66% (and 1%), both
`BaroneAdesiWhaleyApproximationEngine` and `JuQuadraticApproximationEngine` raise
`RuntimeError: forward + displacement (0 + 0) must be positive` for every strike in K/S ∈ [0.5, 2];
at vol ≥ 2% they return values (probe_baw_lowvol.py). Inputs are valid (r, q > 0, vol > 0); BJS and
QD+ price the same options. In the 300-market scan the same exception appeared in 7 markets, all with
vol between 1.66% and 2.34% and T ≥ 1y. The recent zero-volatility handling (2bea76d0) covers
variance < epsilon only.

Side observation in the same probe: BJS gives 0.0004 for the ATM call where QD+ gives 0.1610 —
this market (b = −3.1%, σ = 1.66%, T = 3y > T* = 1.13y) is inside the F1 region.

## Denominators (as of 2026-10-15)

- Callable/puttable bond tree engine: 2883 random bonds (seed 2), 0 violations; edge regions
  covered: call within 7 days before a coupon payment 602, call on an unadjusted coupon date whose
  payment moved 327, call on a non-business day 953, zero-vol equality 724.
- Vanilla engines: 450 random markets (seeds 7 and 8; 150 of them before the r<0 slope-bound fix),
  21 engines (analytic, integral, FD European/American, 7 binomial European, 3 binomial American,
  BAW, BJS, Ju, QD+, QdFp), 9 strikes × call/put per market. MC engine not scanned yet.
  Findings that survived triage: F1 (BJS, 30 markets with am_T_mono), F2 (Ju, ~10 markets),
  F3 (BAW/Ju exceptions, 7 markets). Everything else was tolerance noise (gap/tol < 4 for lattice/FD),
  QD+ approximation error at the 1e-5 relative level, or my own spec errors (three, see git log).
