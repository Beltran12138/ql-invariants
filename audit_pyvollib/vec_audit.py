"""Same invariant checks against py_vollib_vectorized 0.1.1 (scalar calls through its numpy API),
plus checks that matter for its design: IV error modes, finite-difference greeks with an ABSOLUTE
spot bump dS = 0.01, and degree-1 homogeneity in (S, K).
Separate process from audit.py's vollib run because importing py_vollib_vectorized monkey-patches py_vollib.
"""
import math, json, random, sys, warnings, collections
import numpy as np
import audit as A          # captures the unpatched vollib functions first
import py_vollib_vectorized as V

warnings.filterwarnings("ignore")

def vec_bsm(flag, S, K, T, r, q, sig):
    return float(V.vectorized_black_scholes_merton(flag, S, K, T, r, sig, q, return_as="numpy")[0])

def vec_black(flag, S, K, T, r, q, sig):
    return float(V.vectorized_black(flag, S, K, T, r, sig, return_as="numpy")[0])

def vec_bsm_iv_factory(on_error):
    def f(p, flag, S, K, T, r, q):
        v = float(V.vectorized_implied_volatility(p, S, K, T, r, flag, q=q, model="black_scholes_merton",
                                                  on_error=on_error, return_as="numpy")[0])
        return v
    return f

def vec_greeks(flag, S, K, T, r, q, sig, model="black_scholes_merton"):
    kw = dict(q=q, model=model, return_as="numpy")
    return dict(delta=float(V.vectorized_delta(flag, S, K, T, r, sig, **kw)[0]),
                gamma=float(V.vectorized_gamma(flag, S, K, T, r, sig, **kw)[0]),
                vega=float(V.vectorized_vega(flag, S, K, T, r, sig, **kw)[0]),
                theta=float(V.vectorized_theta(flag, S, K, T, r, sig, **kw)[0]),
                rho=float(V.vectorized_rho(flag, S, K, T, r, sig, **kw)[0]))

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    out = open("runs/vec_scan.jsonl", "w")
    for sname, pr, ivf, model in [("vec_bsm", vec_bsm, vec_bsm_iv_factory("warn"), "bsm"),
                                  ("vec_bsm_iv_ignore", vec_bsm, vec_bsm_iv_factory("ignore"), "bsm"),
                                  ("vec_black", vec_black, None, "black")]:
        for region in A.REGIONS:
            v, c, rel = A.run(pr, ivf, None, model, region, n, 7)
            byinv = collections.Counter(x["inv"] for x in v)
            rels = sorted(x[0] for x in rel if x[2] > 1e-200)
            summ = dict(subject=sname, region=region, n_markets=n, checks=dict(c), violations=dict(byinv),
                        oracle_relerr_p99=rels[int(len(rels) * .99)], oracle_relerr_max=rels[-1])
            print(json.dumps(summ))
            out.write(json.dumps(dict(summary=summ)) + "\n")
            for x in v:
                out.write(json.dumps(dict(subject=sname, **x), default=str) + "\n")

    print("\n== IV error modes, out-of-band prices (S=100 K=80 T=1 r=.05 q=0 call; intrinsic lo=23.9016)")
    S, K, T, r, q = 100.0, 80.0, 1.0, 0.05, 0.0
    lo = S - K * math.exp(-r * T)
    for p in (lo - 1.0, lo - 1e-6, -1.0, S + 1.0):
        for oe in ("raise", "warn", "ignore"):
            try:
                res = V.vectorized_implied_volatility(p, S, K, T, r, "c", q=q, model="black_scholes_merton",
                                                      on_error=oe, return_as="numpy")
                print(f"price={p:<12.8g} on_error={oe:<6} -> {res.tolist()}")
            except Exception as e:
                print(f"price={p:<12.8g} on_error={oe:<6} -> RAISES {type(e).__name__}")

    print("\n== greeks vs exact (mpmath) at S=100 and scaled copies (degree-1 homogeneity: delta invariant, gamma*lam)")
    base = dict(K=100.0, T=0.25, r=0.03, q=0.0, sig=0.3)
    for lam in (1.0, 0.01, 0.001, 100.0):
        S, K = 100.0 * lam, base["K"] * lam
        g = vec_greeks("c", S, K, base["T"], base["r"], base["q"], base["sig"])
        sg = dict(delta=float("nan"))
        o = A.oracle_greeks("c", S, K, base["T"], base["r"], base["q"], base["sig"])
        print(f"lam={lam:<6} S=K={S:<8g} delta vec={g['delta']:.6g} exact={o['delta']:.6g} | "
              f"gamma vec={g['gamma']:.6g} exact={o['gamma']:.6g}")
