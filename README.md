# ql-invariants

Model-free invariant scans for [QuantLib](https://github.com/lballabio/QuantLib) pricing engines.

An arbitrage-free price has to satisfy some properties under *any* model: a call is decreasing and
convex in the strike, put–call parity holds for European options, an American option is worth at least
the European one and does not lose value when its maturity is extended, an issuer-callable bond is
worth no more than the bond called on any of its call dates. A computed price that violates one of
these is wrong whatever model was chosen, so the properties can be tested without knowing the right
answer.

This repository samples random markets and contracts, prices them with QuantLib (Python, 1.44), and
checks those properties. It is a one-weekend spike with a pre-registered success / stop criterion
([PLAN.md](PLAN.md), translated from [PLAN.zh.md](PLAN.zh.md), written before the first scan).

## Results

Details, reproductions and root causes: [FINDINGS.md](FINDINGS.md).

| | engine | what happens | status |
|---|---|---|---|
| **F1** | `BjerksundStenslandApproximationEngine` | With negative carry for the call-equivalent (put with r > q, or call with q > r) and \|b\|·√T > 2σ, the early-exercise trigger falls below the strike and the engine silently returns the **European** value. Example: 1y ATM American put, r = 40%, q = 5%, σ = 15%: BJS 0.0397, binomial CRR 4001 1.1563, QdFp 1.1570 (−97%). | reported, [QuantLib#2903](https://github.com/lballabio/QuantLib/issues/2903) |
| F2 | `JuQuadraticApproximationEngine` | Can return less than the European value (43 of 5880 grid points, worst −3.1%); the floor added in 2026-09 is the exercise value, not max(European, exercise). | reported, [QuantLib#2904](https://github.com/lballabio/QuantLib/issues/2904) |
| F3 | `BaroneAdesiWhaleyApproximationEngine`, `JuQuadraticApproximationEngine` | Raise `forward + displacement (0 + 0) must be positive` on valid low-volatility inputs (σ ≲ 1.7%, q > r, T ≥ 1y). | reported, [QuantLib#2905](https://github.com/lballabio/QuantLib/issues/2905) |

F1 is invisible to the checks used by recent fixes to the same engines (NaN, below intrinsic): the
returned European value is finite and above intrinsic. It was caught by "an American option is
non-decreasing in maturity".

### Since 2026-10-15

- **F1 starts before T\*.** The European fallback only takes over at T\* ≈ 268 days in the example;
  before that the approximation is already 17% low at 220 days and 49% low at 250
  ([FINDINGS.md](FINDINGS.md#additions-2026-10-17)). #2903 was reproduced independently in C++.
- **OSS-Fuzz runs this engine without an oracle.** QuantLib's fuzz harness prices American options with
  BAW and BJS and discards the result. [`fuzz_oracle/`](fuzz_oracle/) calibrates four model-free checks
  over the fuzzer's own input domain (13,000 samples: flags the BJS and Ju cases, 0 flags on QdFp, QD+,
  BAW) and has a draft fuzzer, not compiled yet.
- **LLM-written pricers** ([`pilot_ai/`](pilot_ai/), pre-registered): three models, two prompts, 600
  stressed points. With a 1 ms requirement, Claude's fixed-point solver passed every check; DeepSeek's
  and Gemini's trees failed model-free checks on 12.8% and 4.0% of points. Without it, one tree returned
  1.56e31 for a put worth 34.2. The large failures share F1's condition: carry large relative to
  volatility. n = 1 draw per model; see [RESULTS.md](pilot_ai/RESULTS.md) for the limits.
- **py_vollib** ([`audit_pyvollib/`](audit_pyvollib/FINDINGS.md)): 0 invariant violations in about 449k
  checks; NaN or negative volatility is silently priced as the zero-volatility value.

### What was checked and found clean

- **Callable / puttable fixed-rate bonds, `TreeCallableFixedRateBondEngine` (Hull–White):**
  2883 random bonds (seed 2), **0 violations**. The reference values (straight bond, bond truncated at
  each call date) are computed from the raw coupon list and curve discount factors, not with a QuantLib
  bond engine. Edge regions covered: call within 7 days before a coupon payment (602 bonds, the region of
  the 2020 bug #930, fixed in 2021), call on an unadjusted coupon date whose payment was moved (327),
  call on a non-business day (953), zero-volatility equality (724).
- **Vanilla engines:** 450 random markets × 21 engines (analytic, integral, FD European and American,
  7 binomial European, 3 binomial American, BAW, BJS, Ju, QD+, QdFp) × 9 strikes × call/put.
  Monte Carlo engines are not scanned yet. Apart from F1–F3, everything flagged was tolerance noise,
  QD+ approximation error around 1e-5 relative, or an error in my own specification (below).

Not counted as findings: the Leisen–Reimer and Joshi binomial trees raise `invalid up probability`
for some low-volatility, short-step inputs, and BAW/Ju refuse negative rates by design. I did not look
into whether the tree exceptions are avoidable.

"Clean" means: no violation of *these* invariants in *these* samples. Coverage outside them is unknown.

## Method

- `qlinv/callable_scan.py`, `qlinv/vanilla_scan.py`: random generators and checks.
- Tolerances come from the engine's own error estimate (N vs 2N steps for lattices and FD) times 3,
  plus a small floor; closed-form approximations get only the floor, and their violations are reported
  as a separate class.
- `tests/`: positive controls (a deliberately broken pricer for each check; the check must fire) and
  negative controls (analytic and FD engines must pass). 22 tests.
  The callable-bond controls existed before the bond scan; the vanilla controls were added after the
  vanilla scans, with the checks themselves unchanged except for the slope-bound fix below.
- `probe_*.py`: one-off scripts used to isolate and confirm each finding.

```
python -m venv .venv && .venv/Scripts/python -m pip install QuantLib==1.44 hypothesis pytest
PYTHONPATH=. .venv/Scripts/python -m pytest -q tests
PYTHONPATH=. .venv/Scripts/python qlinv/callable_scan.py 3000 2 runs/bonds.jsonl
PYTHONPATH=. .venv/Scripts/python qlinv/vanilla_scan.py 300 8 runs/vanilla.jsonl
PYTHONPATH=. .venv/Scripts/python qlinv/triage.py runs/vanilla.jsonl
```

## Mistakes in my own harness (kept on purpose)

The harness was wrong more often than QuantLib was. Each of these first showed up as a "violation":

1. Option maturities were rounded to whole days, but the bounds used the unrounded T, so the analytic
   engine itself appeared to break parity. Caught by the negative control.
2. The American put–call inequality S e^-qT − K ≤ C − P ≤ S − K e^-rT assumes r ≥ 0; with negative
   rates every American engine "violated" it.
3. With r < 0 an American put is never exercised early, equals the European put, and its slope in the
   strike is e^-rT > 1; I had bounded it by 1. Every American engine "violated" it at once.
4. A positive control was too weak: a vega sign error injected at +0.5 per vol point was smaller than
   the true vega, so the check did not fire. The check was fine; the control was strengthened.

Rule of thumb that came out of it: when several independent engines violate the same property at the
same time, suspect the specification first.

## License

BSD 3-Clause, see [LICENSE](LICENSE). Not affiliated with the QuantLib project.
