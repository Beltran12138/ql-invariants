# Benchmark results (2026-10-28)

Pre-registration: [BENCH.md](BENCH.md) (commit c48d516, written before any generation). Scripts:
`gen.py` (generation), `grade.py` (points, references, checks), `analyze.py` (primary metric, H1–H4).
Raw replies are in `gen/`, extracted code in `code/`, per-generation results in `results/`, the full
output of `analyze.py` in `analysis.txt`.

## Outcome

| hypothesis | prediction | result |
|---|---|---|
| H1 (T1, American fast) | ≥ 20% of generations have a serious model-free failure | **met**: 12/25 = 48% |
| H2 (T3, barrier) | ≥ 20% | **not met**: 3/25 = 12% |
| H3 (T1 + T2) | odds ratio of a serious failure inside \|r − q\|·√T > 2σ vs outside > 2 | **not met**: 1.09 (95% CI 0.94–1.27) |
| H4 (T2 vs T1) | no direction | T1 12/25, T2 12/25 |

So, at this scale: LLM-written American pricers often fail a check that needs no reference price;
barrier pricers mostly do not. The failures are **not** concentrated where QuantLib's own
approximations fail (carry large relative to volatility). The essay draft does not claim that they are.

## Primary metric (generations with ≥ 1 serious model-free failure, x/5)

| model | T1 American, < 1 ms | T2 American, unconstrained | T3 barrier |
|---|---:|---:|---:|
| Claude Opus 5.5 | 1/5 | 1/5 | 0/5 |
| Claude Sonnet 5.5 | 1/5 | 2/5 | 1/5 |
| DeepSeek `deepseek-v4-pro` | 5/5 | 2/5 | 0/5 |
| DeepSeek `deepseek-flash` | 3/5 | 2/5 | 1/5 |
| Gemini `gemini-3.1-pro-preview` | 2/5 | 5/5 | 1/5 |
| pooled | 12/25 | 12/25 | 3/25 |

No generation returned "no code". Three Sonnet replies (T1 2, T2 4, T2 5) had no code block on the first
attempt and were retried once as pre-registered; the first replies are kept as `gen/*.try1`. Per-point
counts and median call times are in `analysis.txt`.

n = 5 per cell: differences between models of one or two generations are not evidence of anything.

## Who was not tested

OpenAI (`codex exec`): not run. BENCH.md made it conditional on the login being restored; the CLI was
uninstalled on 2026-10-26. Denominator: 5 of the 6 planned models.

## Deviations from the plan

All are infrastructure; none changes a prompt, a model, k, the points or a check.

1. **Timeout.** The Claude subprocess timeout was raised from 3600 s to 5400 s after Opus T1 calls took
   1827–2569 s and one timed out.
2. **Process.** On Windows, `gen.py` now calls `claude.exe` directly instead of the npm `.CMD` wrapper: on a
   timeout Python killed only the wrapper and the surviving `claude.exe` kept the pipes open (one call hung
   for 6 hours).
3. **Where 12 Opus samples were generated.** After the local run was killed three times (session limits,
   a hang, then the machine itself), the 12 missing Opus samples (T1 1 and 5, all of T2 and T3) were
   generated in a cloud Linux sandbox on 2026-10-27: Claude Code 2.1.311 instead of 2.1.303, Opus
   concurrency 4 instead of 1, same prompts, same flags, empty working directory. Everything about that run
   is in `cloud_run_1027/` (environment, the two-line patch to `gen.py`, logs). The other 63 generations
   are local.
4. **Infrastructure failures not counted.** 17 replies were moved to `gen_infra_failed/` and regenerated:
   12 are CLI quota messages ("You've hit your session limit"), 2 are Windows "The system cannot execute the
   specified program" (a broken CLI binary), and 3 Sonnet T1 replies are empty stdout on both attempts
   (after 3–548 s). The 12 + 2 are not model answers. The 3 empty ones are a judgement call: BENCH.md says an
   empty reply counts as "no code", while `gen.py` (since then) treats empty stdout as a CLI failure. Either
   way the primary metric does not change, because "no code" rows are excluded from x/5; Sonnet T1 would be
   reported as 1/2 with 3 "no code" instead of 1/5.

**Sensitivity of deviation 3.** Only Opus T1 mixes the two environments (3 local + 2 cloud). The cloud T1
calls were faster (239 and 453 s vs 1827–2569 s) and shorter (3.2 and 5.7 KB vs 7.1–12.1 KB), but used the
same family of methods (Andersen–Lake–Offengelt fixed point / QD+), and local Sonnet T1 times alone range
from 217 to 1786 s. Dropping the two cloud T1 samples: Opus T1 1/3, pooled T1 12/23 = 52% (H1 still met),
H3 odds ratio 1.09 (0.94–1.27). No conclusion changes.

## Controls (re-run 2026-10-28, unchanged since pre-registration)

| control | model-free failures (600 points) |
|---|---:|
| American negative: QdFp | 0 |
| American positive: return the European value | 230 (155 serious) |
| Barrier negative: QuantLib `AnalyticBarrierEngine` | 0 |
| Barrier positive: out = vanilla | 301 |
| Barrier positive: barrier moved away from spot | 208 |
| Barrier positive: r and q swapped | 431 |
| Barrier positive: zero cases priced as vanilla | 34 |

## A wrong reference, found by the pricers

The "ref" column (|A − QuantLib| > 2%) is not part of the primary metric. In T3, for 21 of the 25
generations the only disagreement with the reference is one point, #588: a down-and-out put with S = 40.81, K = 100,
H = 26.79, T = 747 days, r = 4.94%, q = 27.31%, σ = 1.30%.

At that point four independent generations (Opus, Sonnet, DeepSeek-pro, Gemini, T3 sample 1) agree with
each other and with a 60-digit computation to within 1e-13, and QuantLib returns 1.5138544 (+5.3%):

| method | down-and-out put |
|---|---:|
| absorbed-density integral, 60 digits (mpmath) | 1.43786773913201 |
| the four generations | 1.4378677391320 to 1.4378677391321 |
| QuantLib `FdBlackScholesBarrierEngine` 2000×4000 | 1.4555 |
| Monte Carlo, 20,000 paths × 4000 steps | 1.42 ± 0.07 |
| QuantLib `AnalyticBarrierEngine` | **1.5138544** |

Holding the other inputs and sweeping σ, QuantLib's analytic value is 4.6–5.6% high for σ ≤ 1.6% and
exact to 1e-15 from σ = 2% up. The switch sits where 2|μ|·|ln(H/S)| reaches about 709, the largest
exponent a double can hold (μ = (r − q)/σ² − 1/2): `pow(H/S, 2μ)` overflows while the normal CDF it
multiplies underflows to 0, and the guard added in 71892cf (2023, "Avoid NaNs in analytic barrier engine
for low volatility") sets that product to 0 ("The limit should be 0"). Here the product is not small: the
true value of the term is of the order of the option price. Mechanism: reading of the source plus the
location of the switch; I have not instrumented the C++.

The model-free checks cannot see this. QuantLib's knock-out and knock-in still add up to the vanilla
price (1.5138544 + 65.5303710 = 67.0442254), so in–out parity holds, and the barrier negative control
above passes with 0 failures. It was visible only
because several independent implementations disagreed with the reference in the same place, the same
rule of thumb as in the README, pointed the other way: when every pricer "fails" at one point, check
the reference.

This has not been reported to QuantLib yet.

## Limits

As listed in BENCH.md: one prompt wording per task, Black–Scholes only, continuous monitoring only, a
detection floor of about 2% for the model-free checks, and the checks were designed by someone who uses
one of the tested model families. Add: n = 5 per cell; 5 of 6 planned models; 12 Opus samples from a
second environment (deviation 3).
