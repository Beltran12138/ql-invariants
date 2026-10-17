# Fuzzed, fixed three times, and still 97% wrong

*Draft, 2026-10-17. Numbers are from QuantLib 1.44 unless stated; every one of them is reproducible
from the scripts in this repository.*

Price a one-year at-the-money American put with QuantLib's Bjerksund–Stensland engine, with
r = 40%, q = 5%, σ = 15%. It returns 0.0397. A binomial tree with 4001 steps returns 1.1563, and
QuantLib's own high-precision QdFp engine returns 1.1570. The engine is 97% low, and the number it
returns is the European price to every digit.

That is QuantLib issue #2903. Three things should have caught it before I did, and none of them did.
They each failed in an instructive way.

## What did not catch it

**Three recent fixes to the same engines.** Between August and October 2026 one contributor
fixed this family of approximations three times: #2728 (BAW and Ju below intrinsic at negative
rates), #2814 (BJS NaN where β = 1) and #2854 (BJS NaN at zero volatility). Each was a real bug, found
by a real check: *is the price NaN, is it below the exercise value?* The value in #2903 is finite and
above the exercise value. It passes both.

**Continuous fuzzing.** QuantLib is on Google's OSS-Fuzz. It builds every day (all seven builds from
10-11 to 10-17 succeeded), and `fuzz_vanilla_option.cpp` prices American options with exactly this
engine. In the 2026-10-15 coverage report, the line that computes the early-exercise trigger, the one
that goes wrong, was executed 65 times. The harness does this with the result:

```cpp
(void)option.NPV();
...
} catch (const std::exception&) {
}
```

A fuzzer without an oracle finds crashes. A wrong number is not a crash. The same harness also swallows
#2905, an exception raised on valid inputs, which turns up in 15 of 10,000 samples of the fuzzer's own
input domain.

**The engine's own guard.** The code has a fallback: when the approximation produces an exercise
trigger that is not usable, it returns the European value, which is a valid lower bound for an American
option. The fallback is what makes the bug quiet. It replaces a visibly broken number with a plausible
one.

## What did catch it

A property that holds under any arbitrage-free model, so it needs no reference price: *an American
option is worth at least as much when you extend its maturity.* You can always exercise the longer
option on the shorter one's expiry date. Sweep the maturity and Bjerksund–Stensland goes 1.107 at 150
days, 1.080 at 182, 0.952 at 220, 0.589 at 250, and 0.0925 at 268, where the fallback takes over.
The accurate engine rises the whole way, from 1.132 to 1.153.

The sweep also showed something I had not put in the original report. The fallback is the end of
the failure, not its start. At 220 days, before any fallback, the approximation is already 17% low,
and at 250 days 49% low. A fix that only rejects inputs past the threshold would leave that range
silently wrong.

There are other properties of the same kind: American ≥ European, call prices decreasing and convex in
the strike, put–call bounds. I ran them against 21 QuantLib engines over random markets. They turned
up three problems (#2903–#2905), and all three are the same type: an approximation formula used outside
the parameter range it was derived for. None of them is a floating-point problem. None is a model
problem in the 2008 sense either: the Black–Scholes assumptions were not the issue. The formula was
evaluated where it does not hold.

## The same shape in AI-written pricers

In July, Liu, Cheng, Cheng and Oosterlee published RIDGE (arXiv 2607.25199), which has LLMs write
option pricers and checks them with no-arbitrage tests, stress tests and benchmarks. Their summary
across five stochastic-volatility models: "the main failures are not programming mistakes and rarely
involve mathematical errors". Numerical choices that work at default parameters fail in stressed
regimes. That is the description of #2903, from code written by people, in a library with two decades
of review.

[PILOT RESULTS: TO FILL]

## What these checks cannot do

They are a coarse net. On the sweep above, the maturity check first fires between 150 and 182 days,
when the error is 2–5%. At 120 days the engine is 1.0% low and passes every model-free check. They
also say nothing about whether Black–Scholes was the right model. What they offer is a test with no
reference value to get wrong, which is the part a fuzzer is missing.

I wrote a draft fuzzer that adds four such checks to QuantLib's existing input domain
(`fuzz_oracle/`). Calibrated in Python on 13,000 samples, it flags the Bjerksund–Stensland cases
(errors from −4.6% to −99.8%) and the Ju-below-European case (#2904), and raises nothing on QdFp,
QD+ or Barone-Adesi–Whaley. It has not been compiled yet, and it will not be proposed until the
maintainers have looked at the open issues.

## Mistakes in my own harness

The harness was wrong more often than QuantLib. Rounded maturities made the analytic engine appear to
break parity. Two bounds I wrote down assumed non-negative rates, and every American engine
"violated" them at once. While writing this up, an upper bound for puts did the same thing for the
same reason. Rule of thumb: when every engine breaks the same property at the same time, the property
is wrong.
