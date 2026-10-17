# Benchmark: model-free invariant checks on LLM-written option pricers

Pre-registration. Written 2026-10-17, before any generation for this benchmark. The 2026-10-17 pilot
(`pilot_ai/`, n = 1 per model) is exploratory and is not part of these results; this run is
confirmatory. Hypotheses, metrics and thresholds below are not revised after generation starts.
Corrections to the checker itself are allowed only if forced by a control, are applied to every row
alike, and are listed in RESULTS.md.

## Tasks (prompts in `prompts/`, identical for every model)

- **T1 American, fast**: pilot prompt B (under 1 ms per call; r, q in [−2%, 40%], σ in [1%, 300%],
  T in [1 day, 10 years], S/K in [0.2, 5]).
- **T2 American, unconstrained**: pilot prompt A.
- **T3 Barrier**: European single-barrier option, continuous monitoring, no rebate, Black–Scholes with
  continuous yield. `barrier_price(S, K, H, T, r, q, sigma, is_call, barrier_type)` with barrier_type in
  {"down-and-out", "down-and-in", "up-and-out", "up-and-in"}. Same parameter domain as T1, H/S in
  [0.5, 2] on either side; the prompt says what to return when the spot is already beyond the barrier.

## Models and samples

k = 5 independent generations per (model, task), default sampling, fresh context each time.
Planned: Claude Opus 5.5 and Claude Sonnet 5.5 (`claude -p`, empty cwd, tools disabled), DeepSeek
`deepseek-v4-pro` and `deepseek-flash` (raw API), Gemini `gemini-3.1-pro-preview` (raw API), OpenAI via
`codex exec` if its login is restored. Grok is excluded (agent mode with persistent memory; contaminated
in the pilot). A generation that returns no code (empty, truncated, refusal) is retried once and counted
as "no code" if it fails again; "no code" rows are reported, not dropped.

## Grader (no LLM grades anything)

Points: 600 per task, seed 23 (T1/T2 share the same points; T3 its own 600), drawn from the stated
domain; maturities are integer days, T = days/365.

American (T1, T2), as in the pilot after its corrections: ≥ intrinsic; ≥ European; non-decreasing in
maturity (T + max(1 day, T/10)); ≤ S·max(1, e^{−qT}) for calls, ≤ K·max(1, e^{−rT}) for puts; call
non-increasing / put non-decreasing in K (K·1.01). Reference: QuantLib QdFp high precision, FD
1000×800 where QdFp refuses (double boundary).

Barrier (T3), model-free: in + out = vanilla European (in–out parity, holds in any model with zero
rebate and identical monitoring); 0 ≤ each ≤ vanilla; knocked-out at inception (spot at or beyond the
barrier) ⇒ out = 0 and in = vanilla; out value non-increasing as the barrier moves towards the spot
(H·1.01 for down, H/1.01 for up) and in value non-decreasing; up-and-out call with H ≤ K and
down-and-out put with H ≥ K are worth 0. Reference: QuantLib `AnalyticBarrierEngine`.

A model-free check fails when its gap exceeds 1e-8·max(S, K). A failure is **serious** when the gap
also exceeds 1% of max(reference value, 1e-4·max(S, K)). Exceptions, NaN and inf are counted separately
and count as serious.

## Primary metric

Per generation: does it have at least one serious model-free failure on the 600 points (yes/no)?
Reported per (model, task) as x/5, and pooled per task.

## Hypotheses

- **H1 (T1)**: pooled over all models, ≥ 20% of generations have a serious model-free failure.
- **H2 (T3)**: same, ≥ 20%.
- **H3 (mechanism, T1 + T2 pooled)**: points with |r − q|·√T > 2σ (the region where QuantLib's F1/F3
  fail) are over-represented among serious failures: the odds ratio of a serious failure inside vs
  outside that region, over all (generation, point) pairs, is > 2.
- **H4 (T2 vs T1)**: reported without a directional prediction (the pilot reversed my prior).

If H1 and H2 both fail, the claim "LLM-written pricers need dedicated checks" is not supported at
this scale and is reported as such.

## Limits known in advance

One prompt wording per task; Black–Scholes only; continuous monitoring only; the model-free checks have a
detection floor (errors below about 2% often pass, see FINDINGS.md); the person who designed the checks
uses one of the tested model families.

## Safety

As in the pilot: static check of imports and calls, execution in a separate venv with `python -I`, own
empty working directory, timeout.
