# Pilot: do LLM-written American option pricers violate model-free invariants?

Pre-registration. Written 2026-10-17 before any model output was requested; criteria are not revised
afterwards. Results go in `RESULTS.md`, next to this file.

## Why this design

The naive version ("ask 5 models for an American pricer, stop if violation rate ≈ 0") tests the prompt,
not the hypothesis: an unconstrained model will usually write a binomial tree, which converges, and
the violation rate will be ≈ 0. Everything found so far (QuantLib F1–F3, RIDGE arXiv 2607.25199 §6.1)
fails in stressed parameter regimes or where a fast approximation is used outside its domain. So the pilot
uses two prompts and treats prompt A as a control.

## Prompts (one generation per model per prompt, default sampling)

- **A, unconstrained**: write `american_price(S, K, T, r, q, sigma, is_call)` returning the price of an
  American option under Black–Scholes with continuous dividend yield. Python, standard library + numpy +
  scipy only. Code only.
- **B, constrained**: same, plus: under 1 ms per call (it will be called millions of times in a risk
  system), valid for r and q in [−2%, 40%], sigma in [1%, 300%], T from 1 day to 10 years, S/K in [0.2, 5].

Models: Claude (Opus 5.5, `claude -p`), OpenAI (`codex exec`), DeepSeek (API), Gemini (API), Grok
(`grok` CLI). If one is unreachable it is dropped and the denominator says so.

## Checks (independent of the model being tested; no LLM grades anything)

Same 600 random points for every implementation, drawn from prompt B's domain (seed 17).

Model-free (no reference value):
1. A ≥ intrinsic − floor
2. A ≥ European(T) − floor (European from QuantLib `AnalyticEuropeanEngine`)
3. A(T + max(1 day, T/10)) ≥ A(T)·(1 − 1%) − floor
4. A ≤ S (call), A ≤ K·max(1, e^{−rT}) (put), + floor
5. Call non-increasing in K, put non-decreasing in K: A(K·1.01) vs A(K), 1% relative + floor
6. Result is a finite float; exceptions counted separately

floor = 1e-8·max(S, K). Tolerances are the ones calibrated on QuantLib in `fuzz_oracle/` (QdFp passes
all of 1–4 there).

Reference-based (reported separately, never merged into the model-free rate):
7. |A − QdFp| > 2%·QdFp + 1e-4·max(S, K)

Controls: QuantLib QdFp wrapped in the same interface must pass 1–6 (negative control); a pricer that
returns the European value must fail 3 or 7 on the F1 region (positive control).

## Pre-registered outcomes

- **Expected for A**: model-free violation rate < 1% for most models. If A already shows ≥ 1% for ≥ 2
  models, that is stronger than expected, and gets reported as such.
- **Hypothesis H (prompt B)**: at least 2 of the models reachable have a model-free violation rate ≥ 1% of
  points, or a reference error (check 7) on ≥ 5% of points.
- **Stop**: if ≤ 1 model meets H, "LLM-written pricers need dedicated invariant checks" is not supported
  at this scale; do not build the benchmark.
- **Continue**: if H holds, the benchmark is worth scoping (American + barrier, stressed domain, several
  samples per model), per the 10-17 plan.

## Limits known in advance

n = 1 generation per (model, prompt): sampling variance is not measured, so a single bad or good draw can
decide a model's row. The 1% thresholds are judgement, fixed now. The checks have a detection floor:
on QuantLib's BJS, errors below about 2% passed every model-free check (`probe` sweep 2026-10-17), so a
clean model-free row means "no error large enough to break an invariant", not "accurate".

## Safety

Generated code is never executed in the repo directory. Each file is statically checked (imports
limited to math, cmath, numpy, scipy, functools; no os/sys/subprocess/socket/open/eval/exec/__import__)
and run in a subprocess with `python -I`, a timeout, and its own empty working directory.
