# Pilot results (2026-10-17)

Pre-registration: `PILOT.md` (commit 166ed5f, written before any model output). Scripts: `gen.sh`
(generation), `check.py` (points, references, first scoring), `recheck.py` (final scoring from saved
outputs). Generated code is in `code/`, raw replies in `gen/`.

## Who was tested

| model | prompt A | prompt B | note |
|---|---|---|---|
| Claude Opus 5.5 (`claude -p`, empty cwd, tools disabled) | ✓ | ✓ | Same model family as the person who designed the checks. No project context leaked: user-level CLAUDE.md contains none of QuantLib / Bjerksund / invariant / option / pricing; no project memory for that cwd. |
| DeepSeek `deepseek-v4-pro` (raw API) | ✓ | ✓ | B: first call spent its 65,536 completion tokens on reasoning and returned no content (not counted as a generation); second call with `max_tokens` 250,000 returned code. |
| Gemini `gemini-3.1-pro-preview` (raw API) | ✓ | ✓ | |
| OpenAI (`codex exec`) | – | – | **Dropped**: 401, login expired. |
| Grok (`grok -p`) | – | – | **Dropped**: contaminated. The CLI ran as an agent with persistent memory shared by the two concurrent runs; on prompt A, which mentions nothing about stress or invariants, it wrote that it would avoid "BJS/BAW approximations breaking invariants under stress parameters", and neither run returned code. |

Denominator: 3 of the 5 planned models, 1 generation per (model, prompt).

## Harness corrections made after the run

Both were found by the negative control (QdFp failed a check at the same point as every pricer), and
both are the same mistake already listed in the README, a bound that assumes non-negative rates:

1. Put upper bound is K·max(1, e^{−rT}), not K (fixed in `fuzz_oracle/triage.py` before the pilot).
2. Call upper bound is S·max(1, e^{−qT}), not S: with q < 0 the European call itself exceeds S
   (fixed in `recheck.py`; `check.py`'s first table still has it).

Also: QdFp refuses the double-boundary case (q < r < 0 put); the reference falls back to FD 1000×800
there. After the fixes the negative control has 0 violations and the positive control (return the
European value) is flagged on 217 of 600 points.

## Results (600 points, prompt B domain, seed 17)

Model-free checks are counted when the gap exceeds 1e-8·max(S, K). "ref" is check 7,
|A − QdFp| > 2%·QdFp + 1e-4·max(S, K).

| pricer | method | any model-free | < intrinsic | < European | maturity | > upper | strike | ref | ms/call (median) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| QdFp (negative control) | | 0 | 0 | 0 | 0 | 0 | 0 | 0 | |
| Claude A | drift-adjusted tree N=2000 + Richardson | 9 (1.5%) | 0 | 9 | 0 | 0 | 0 | 0 | 120 |
| DeepSeek A | CRR N=2000 | 43 (7.2%) | 0 | 43 | 0 | 0 | 0 | 0 | 39 |
| Gemini A | CRR N=1000 | 55 (9.2%) | 0 | 53 | 0 | 2 | 1 | 2 | 57 |
| Claude B | Andersen–Lake–Offengelt fixed point (QdFp family), tree fallback | **0** | 0 | 0 | 0 | 0 | 0 | 0 | 0.43 |
| DeepSeek B | CRR N=150, pure Python, p clamped to [0, 1] | **77 (12.8%)** | 0 | 76 | 1 | 0 | 0 | 9 | 2.84 |
| Gemini B | tree N=100 + European control variate | **24 (4.0%)** | 19 | 0 | 4 | 1 | 0 | 10 | 0.99 |

Size of the "< European" gaps, relative to max(QdFp, 1e-4·max(S, K)): Claude A all ≤ 8.9e-6
(discretisation level); DeepSeek A 33 above 1e-4, 1 above 1% (max 1.7%); Gemini A 43 above 1e-4,
3 above 1% (max 3.3%); DeepSeek B 69 above 1e-4, 30 above 1%. Gemini B's 19 below-intrinsic gaps are
at most 2.4e-4 of intrinsic (no floor at the exercise value).

Worst cases (QdFp in brackets):

- Gemini A, put, S = 101.74, K = 100, 428 days, r = 1.7%, q = 39.8%, σ = 1.1%: **1.56e31** (34.20).
- DeepSeek B, call, S = 52.57, 1225 days, r = 34.5%, q = 9.1%, σ = 2.1%: **0** (7.339).
  Put, S = 258.74, 2363 days, r = 10.1%, q = 28.7%, σ = 1.6%: **0** (11.60).
- Gemini B, call, S = 39.18, 2765 days, r = 13.9%, q = −0.8%, σ = 283%: **63.25** (41.56), above
  the no-arbitrage upper bound; maturity violations of −20% to −35% at low prices.

The large failures share one condition: carry dominates volatility over a time step, |r − q|·√Δt > σ,
which pushes the CRR up-probability outside [0, 1] (Gemini A explodes, DeepSeek B clamps it and returns
nonsense). Checked by hand for the first two cases above: 0.013 > 0.011 and 0.038 > 0.021. QuantLib's
F1/F3 fail on the same kind of condition, |b|·√T > 2σ.

## Against the pre-registered outcomes

- **Expected for A** (< 1% for most models): **wrong**. 2 of 3 models are above 1%, with errors up to
  3.3% and one 1e31. The reasoning in PILOT.md ("a tree converges") holds only while the up-probability
  stays in [0, 1], which the stressed domain breaks. What mattered was the evaluation domain, not the
  prompt.
- **Hypothesis H** (≥ 2 models with a model-free rate ≥ 1% or ref errors on ≥ 5% under prompt B):
  **met**, 2 of 3 (DeepSeek 12.8%, Gemini 4.0%). Claude B passed every check.
- **Decision** per PILOT.md: continue, the benchmark is worth scoping.

## Limits

- n = 1 per (model, prompt); 3 models. One clean row (Claude B) and two failing rows could flip with
  another draw.
- The two bound corrections were made after seeing the data. They were applied to every row alike and
  were forced by the negative control, but they are post-hoc.
- The fixed floor (1e-8·scale) counts discretisation error of trees as violations (Claude A's 9 are of
  that kind). Rates in the "any model-free" column are therefore an upper bound on serious errors; the
  size breakdown above is the better read.
- Only American vanillas under Black–Scholes. No barrier options yet.
