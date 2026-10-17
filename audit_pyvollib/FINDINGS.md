# py_vollib / vollib invariant audit (2026-10-17)

Raw material, not reported upstream. Scripts and run outputs are in this folder.
V1 was re-run by hand after the scan; the other numbers come from the scan run (`runs/`) and were not
re-run separately.

## Versions

- vollib 1.0.11 (py-vollib 1.0.12 is now a deprecated transition package re-exporting vollib),
  py_lets_be_rational 1.1.2 (md5 of `lets_be_rational.py`: c96b30efa5cef21e723d5727dc8adad1),
  numpy 2.4.6, numba 0.68.0, QuantLib 1.44, mpmath 1.4.1, Python 3.11.9.
- Legacy venv for the vectorized package: py-vollib-vectorized 0.1.1, py_vollib 1.0.1,
  py_lets_be_rational 1.0.1, numba 0.60.0, numpy 1.26.4.

## Denominator

Seed 7, 400 markets per region, S = 100, 10 random strikes per market.

| region | σ | T | r, q | K/S |
|---|---|---|---|---|
| core | 5–80% | 0.05–3 y | −2% to 8% | 0.5–2 |
| stress | 0.1–300% (log) | 1 day–30 y (log) | −5% to 40% | 0.2–5 (log) |

Per subject (BSM; Black similar): bounds 8000, parity 4000, slope in K 7200, convexity in K 6400,
vol monotonicity 14400, 80-digit mpmath oracle 8000, IV round trip 8000, IV out-of-band 28000,
greeks vs exact derivatives 4020. About 449k check evaluations in total. Positive controls (one
mutation per check) and negative controls (QuantLib blackFormula + IV): 19/19 pass.

## Clean

- 0 invariant violations for vollib BSM, BS and Black, both regions, every check above.
- Price error vs the 80-digit oracle: BSM p99 9.2e-15 (core), 2.8e-13 (stress), max 5.7e-12.
  QuantLib is *less* accurate on deep OTM prices (p99 5.0e-8 in stress, max 1.9e-5 in core,
  cancellation), so a relative differential against QuantLib would have produced false positives.
- Every price outside the no-arbitrage band makes IV raise (0/28000 BSM, 0/28400 Black failures);
  the OptionStratLib #652 pattern does not occur.
- Black with a negative forward is rejected (math domain error).

## Findings

**V1 (looks unreported). NaN or negative volatility is silently priced as the zero-vol value.**
Repro `repro_nan_sigma.py` (re-run 2026-10-17):

```
discounted forward intrinsic (sigma=0 value): 10.89551496257486
bsm sigma=nan   : 10.89551496257486
bsm sigma=-0.2  : 10.89551496257486
bsm t=nan       : nan
black F=100 K=100 sigma=nan: 0.0
```

Cause: `py_lets_be_rational/lets_be_rational.py:785`,
`return intrinsic + max(0.0, ... normalised_black(...))`. `normalised_black` returns nan and
`max(0.0, nan)` is 0.0 in Python (`max(nan, 0.0)` is nan). Negative σ goes through the
denormalisation-cutoff branch and returns intrinsic. A missing vol becomes a plausible finite price.
Searched issue titles plus "nan" / "negative volatility": only #28 and #5, both unrelated; PRs not
searched. Medium confidence that it is unreported.

**V2. py_vollib_vectorized 0.1.1 fails on every pricing call on the current stack**
(numba `TypingError: cannot type infer runaway recursion`). Bisected (fresh `NUMBA_CACHE_DIR` per
config): works with py_lets_be_rational 1.0.1, fails with 1.1.2 under numba 0.60 and 0.68. Related but
not identical: vollib/py_vollib #35, py_vollib_vectorized #29.

**V3 (known: vectorized #13, #27).** `vectorized_black` returns the undiscounted price
(7.965567455405798 vs 7.577082146427273 at F = K = 100, T = 1, r = 5%, σ = 20%).

**V4 (known: py_vollib #28, closed).** Vectorized finite-difference greeks bump S by an absolute 0.01:
at S = K = 0.1 delta is −1.33% and gamma −3.2% off. Scalar vollib now bumps relatively.

**V5 (opt-in behaviour).** Vectorized IV with `on_error="ignore"` returns 0.0 for prices below
intrinsic or negative, but nan above the maximum.

## Not tested

Vectorized package on the current stack (V2); scalar BS IV and greeks; vollib's own numba path; fine
strike grids. The mpmath oracle shares the textbook formula, so a convention error common to both would
not show; parity and bounds guard against that.
