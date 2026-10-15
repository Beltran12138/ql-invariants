# Pre-registration (English translation)

Translation of `PLAN.zh.md`, which was written before any scan ran and is unchanged since
commit `b3dd40d` (2026-10-15). If the two differ, the Chinese original is authoritative.

Started 2026-10-15. QuantLib Python 1.44 (PyPI wheel), Python 3.11.9, Windows 11.

## Question

Nobody in the public domain runs systematic model-free invariant tests against QuantLib's pricing
engines; QuantLib's own tests are mostly reference values and cross-engine comparisons. These
invariants must hold under any arbitrage-free model, so a computed price that violates one is a bug in
the code, whether or not the model is right. Motivating case: QuantLib issue #930 (2020), a bond
called in 7 days priced about 5 points above its call price because of schedule/event logic.

## Pre-registered criteria (fixed, not revised afterwards)

- **Success**: at least one previously unreported invariant violation, minimally reproduced, with
  "tolerance set wrong / bug in my harness / known discretisation artefact" ruled out. Only then
  consider an upstream issue (shown to the user for review first).
- **Failure = stop**: if 10 invariants run on QuantLib Python with no violation, stop and record
  "engines covered, inputs sampled, 0 violations" as a negative result.
- **Time box**: one weekend's worth of work.

## Discipline (carried over from oai-math-recheck)

1. **Positive controls**: every invariant gets a deliberately wrong pricer; the harness must report a
   violation, otherwise the check has no teeth.
2. **Negative controls**: the analytic Black–Scholes engine must pass everything (it is the only
   thing that can serve as a reference).
3. **No hand-picked tolerances**: for discretising engines, tolerance = a multiple of the engine's own
   error estimate (deviation from the analytic value, or the N vs 2N difference), plus a floating-point
   floor. A fixed threshold would either report known artefacts (binomial oscillation in strike) as
   bugs or let real bugs through.
4. Any "nothing found" must come with its denominator: engines × invariants × samples.
5. Every violation is first suspected to be mine: harness bug first, then known artefact, and only
   then a finding.
