"""Degenerate / invalid input probes and secondary differentials (scalar vollib).
Prints one line per probe: what was called, what came back (value or exception type).
"""
import math, random, warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
import audit as A
from vollib.black import black
from vollib.black.implied_volatility import implied_volatility as black_iv
from vollib.black_scholes_merton import black_scholes_merton as bsm
from vollib.black_scholes_merton.implied_volatility import implied_volatility as bsm_iv
from vollib.black_scholes_merton.greeks import analytical as ga, numerical as gn

def show(label, f):
    try:
        v = f()
        print(f"{label:70s} -> {v!r}")
    except Exception as e:
        print(f"{label:70s} -> RAISES {type(e).__name__}: {str(e)[:70]}")

print("== invalid / degenerate inputs")
show("black('c', F=-100, K=100, t=1, r=.01, sig=.2)", lambda: black('c', -100, 100, 1, .01, .2))
show("black('p', F=-100, K=100, t=1, r=.01, sig=.2)", lambda: black('p', -100, 100, 1, .01, .2))
show("black('c', F=100, K=-100, t=1, r=.01, sig=.2)", lambda: black('c', 100, -100, 1, .01, .2))
show("black('c', F=-100, K=-90, t=1, r=.01, sig=.2) [both neg]", lambda: black('c', -100, -90, 1, .01, .2))
show("black('c', F=0, K=100, ...)", lambda: black('c', 0, 100, 1, .01, .2))
show("black('p', F=100, K=0, ...)", lambda: black('p', 100, 0, 1, .01, .2))
show("black_iv(5, F=-100, K=100, r=.01, t=1, 'c')", lambda: black_iv(5, -100, 100, .01, 1, 'c'))
show("bsm('c', S=100, K=100, t=1, r=.01, sig=-0.2, q=0)  [neg vol]", lambda: bsm('c', 100, 100, 1, .01, -0.2, 0))
show("bsm('c', S=100, K=90, t=1, r=.01, sig=-0.2, q=0)  [neg vol, ITM]", lambda: bsm('c', 100, 90, 1, .01, -0.2, 0))
show("bsm('c', S=100, K=100, t=-1, r=.01, sig=.2, q=0)  [neg T]", lambda: bsm('c', 100, 100, -1, .01, .2, 0))
show("bsm('c', S=100, K=90, t=0, r=.01, sig=.2, q=0)  [T=0]", lambda: bsm('c', 100, 90, 0, .01, .2, 0))
show("bsm('c', S=100, K=90, t=1, r=.01, sig=0, q=0)  [sig=0]", lambda: bsm('c', 100, 90, 1, .01, 0, 0))
show("bsm('x', S=100, K=90, t=1, r=.01, sig=.2, q=0)  [bad flag]", lambda: bsm('x', 100, 90, 1, .01, .2, 0))
show("bsm('c', nan, 90, 1, .01, .2, 0)", lambda: bsm('c', float('nan'), 90, 1, .01, .2, 0))
show("bsm('c', 100, 90, 1, .01, nan, 0)", lambda: bsm('c', 100, 90, 1, .01, float('nan'), 0))
show("bsm_iv(nan, 100, 90, 1, .01, 0, 'c')", lambda: bsm_iv(float('nan'), 100, 90, 1, .01, 0, 'c'))
show("bsm_iv(5, 100, 100, t=0, .01, 0, 'c')  [T=0]", lambda: bsm_iv(5, 100, 100, 0, .01, 0, 'c'))
show("bsm_iv(5, 100, 100, t=-1, .01, 0, 'c')  [neg T]", lambda: bsm_iv(5, 100, 100, -1, .01, 0, 'c'))
show("bsm_iv(0, 100, 120, 1, .01, 0, 'c')  [zero price OTM]", lambda: bsm_iv(0.0, 100, 120, 1, .01, 0, 'c'))
show("bsm_iv(1e-320, 100, 120, 1, .01, 0, 'c')  [subnormal price]", lambda: bsm_iv(1e-320, 100, 120, 1, .01, 0, 'c'))
show("ga.delta('c', 100, 100, t=0, .01, .2, 0)  [T=0 analytic delta]", lambda: ga.delta('c', 100, 100, 0, .01, .2, 0))
show("ga.vega('c', 100, 100, 1, .01, sig=0, 0)", lambda: ga.vega('c', 100, 100, 1, .01, 0, 0))

print("\n== exact-boundary IV (price == lower bound, i.e. zero time value)")
for (S, K, T, r, q, k) in [(100, 80, 1, .05, 0, 'c'), (100, 120, 1, .05, 0, 'p'), (100, 80, 1, .3, .0, 'c')]:
    lo = max(S*math.exp(-q*T) - K*math.exp(-r*T), 0) if k == 'c' else max(K*math.exp(-r*T) - S*math.exp(-q*T), 0)
    show(f"bsm_iv(lower_bound={lo:.12g}, S={S},K={K},T={T},r={r},q={q},{k})", lambda: bsm_iv(lo, S, K, T, r, q, k))

print("\n== numerical greeks vs analytical, sigma < bump (0.01)")
for sig in (0.005, 0.009, 0.02, 0.2):
    for (k, K) in (('c', 100), ('c', 99.5)):
        a = ga.vega(k, 100, K, 0.25, 0.0, sig, 0.0)
        n = gn.vega(k, 100, K, 0.25, 0.0, sig, 0.0)
        print(f"vega sig={sig:<6} K={K:<6} analytic={a:.6g} numerical={n:.6g} ratio={n/a if a else float('nan'):.4g}")

print("\n== numerical theta for t <= 1/365 (uses price(t=1e-5) - price(t), not a 1-day step)")
for t in (0.5/365, 1/365, 2/365):
    a = ga.theta('c', 100, 100, t, 0.0, 0.2, 0.0)
    n = gn.theta('c', 100, 100, t, 0.0, 0.2, 0.0)
    print(f"theta t={t*365:.2f}d analytic(per day)={a:.6g} numerical={n:.6g} ratio={n/a:.4g}")

print("\n== differential vs QuantLib AnalyticEuropeanEngine (integer-day T, BSM process)")
rng = random.Random(11)
worst_abs, worst_rel, n = 0.0, 0.0, 0
worst = None
for i in range(300):
    S = 100.0
    T = rng.randint(1, 30 * 365) / 365.0
    r, q = rng.uniform(-.05, .4), rng.uniform(-.05, .4)
    sig = math.exp(rng.uniform(math.log(.001), math.log(3)))
    K = S * math.exp(rng.uniform(math.log(.2), math.log(5)))
    for k in 'cp':
        v = A.vollib_bsm(k, S, K, T, r, q, sig)
        w = A.ql_engine_bsm(k, S, K, T, r, q, sig)
        o = float(A.oracle(k, S, K, T, r, q, sig))
        scale = max(S*math.exp(-q*T), K*math.exp(-r*T))
        n += 1
        d = abs(v - w) / scale
        if d > worst_abs:
            worst_abs, worst = d, (k, S, K, T, r, q, sig, v, w, o)
print(f"n={n} pairs; max |vollib-QL|/scale = {worst_abs:.3g}")
k, S, K, T, r, q, sig, v, w, o = worst
print(f"  at {k} S={S} K={K:.6g} T={T:.6g} r={r:.4g} q={q:.4g} sig={sig:.4g}: vollib={v!r} QL={w!r} mpmath={o!r}")
print(f"  |vollib-oracle|/scale={abs(v-o)/scale:.3g}  |QL-oracle|/scale={abs(w-o)/scale:.3g}")
