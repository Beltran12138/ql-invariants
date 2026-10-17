"""Model-free invariant audit of vollib / py_vollib (scalar API).

Pricers are adapters  price(flag, S, K, T, r, q, sigma) -> float  (BSM convention; for the
Black model S is the forward F and q is ignored / set so that F = S e^{(r-q)T} with q = r).

Checks per market (S, r, q, T) and a strike strip:
  bounds   max(S e^-qT - K e^-rT, 0) <= C <= S e^-qT ;  max(K e^-rT - S e^-qT, 0) <= P <= K e^-rT
  parity   C - P = S e^-qT - K e^-rT
  slope_K  -e^-rT <= dC/dK <= 0 ; 0 <= dP/dK <= e^-rT   (divided differences)
  convex_K slopes non-decreasing in K
  vol_mono price non-decreasing on a sigma grid
  oracle   |price - mpmath(80 digits) price|  (differential; QuantLib analytic also measured)
  iv_rt    price -> iv -> price
  iv_band  prices outside the no-arbitrage band must raise (not return a number)
  greeks   analytical greeks vs Richardson central differences of the library's own price

Tolerances: closed form, no refinement knob -> absolute floor a = TOL_REL * scale
(scale = max(S e^-qT, K e^-rT)); difference checks scale it by 1/h.
"""
import math, random, json, sys, warnings
import mpmath as mp
import QuantLib as ql

warnings.filterwarnings("ignore", category=DeprecationWarning)
try:  # vollib is absent/incompatible in the legacy venv used for py_vollib_vectorized
    from vollib.black_scholes_merton import black_scholes_merton as _bsm
    from vollib.black_scholes_merton.implied_volatility import implied_volatility as _bsm_iv
    from vollib.black_scholes_merton.greeks import analytical as _bsm_ga
    from vollib.black_scholes_merton.greeks import numerical as _bsm_gn
    from vollib.black_scholes import black_scholes as _bs
    from vollib.black_scholes.implied_volatility import implied_volatility as _bs_iv
    from vollib.black import black as _black
    from vollib.black.implied_volatility import implied_volatility as _black_iv
    from vollib.black.greeks import analytical as _black_ga
except Exception as _e:  # noqa
    print("audit.py: vollib not importable:", repr(_e)[:80])

mp.mp.dps = 80
TOL_REL = 1e-12

# ---------------------------------------------------------------- pricers
def vollib_bsm(flag, S, K, T, r, q, sig):
    return float(_bsm(flag, S, K, T, r, sig, q))

def vollib_bs(flag, S, K, T, r, q, sig):          # q must be 0
    return float(_bs(flag, S, K, T, r, sig))

def vollib_black(flag, S, K, T, r, q, sig):       # S is the forward; q ignored
    return float(_black(flag, S, K, T, r, sig))

TODAY = ql.Date(15, 10, 2026)
DC = ql.Actual365Fixed()

def ql_bsm(flag, S, K, T, r, q, sig):
    """QuantLib analytic via blackFormula on the forward (exact same continuous T, no day rounding)."""
    F = S * math.exp((r - q) * T)
    df = math.exp(-r * T)
    typ = ql.Option.Call if flag == "c" else ql.Option.Put
    return ql.blackFormula(typ, K, F, sig * math.sqrt(T), df)

def ql_engine_bsm(flag, S, K, T, r, q, sig):
    """QuantLib AnalyticEuropeanEngine with a BSM process; T must be integer days / 365."""
    ql.Settings.instance().evaluationDate = TODAY
    p = ql.BlackScholesMertonProcess(
        ql.QuoteHandle(ql.SimpleQuote(S)),
        ql.YieldTermStructureHandle(ql.FlatForward(TODAY, q, DC)),
        ql.YieldTermStructureHandle(ql.FlatForward(TODAY, r, DC)),
        ql.BlackVolTermStructureHandle(ql.BlackConstantVol(TODAY, ql.NullCalendar(), sig, DC)))
    o = ql.VanillaOption(ql.PlainVanillaPayoff(ql.Option.Call if flag == "c" else ql.Option.Put, K),
                         ql.EuropeanExercise(TODAY + int(round(T * 365))))
    o.setPricingEngine(ql.AnalyticEuropeanEngine(p))
    return o.NPV()

def oracle(flag, S, K, T, r, q, sig):
    S, K, T, r, q, sig = map(mp.mpf, (S, K, T, r, q, sig))
    v = sig * mp.sqrt(T)
    F = S * mp.e ** ((r - q) * T)
    d1 = (mp.log(F / K) + v * v / 2) / v
    d2 = d1 - v
    df = mp.e ** (-r * T)
    if flag == "c":
        return df * (F * mp.ncdf(d1) - K * mp.ncdf(d2))
    return df * (K * mp.ncdf(-d2) - F * mp.ncdf(-d1))

# ---------------------------------------------------------------- IV adapters
def vollib_bsm_iv(p, flag, S, K, T, r, q):
    return float(_bsm_iv(p, S, K, T, r, q, flag))

def vollib_black_iv(p, flag, S, K, T, r, q):
    return float(_black_iv(p, S, K, r, T, flag))

def ql_iv(p, flag, S, K, T, r, q):
    F = S * math.exp((r - q) * T)
    df = math.exp(-r * T)
    typ = ql.Option.Call if flag == "c" else ql.Option.Put
    sd = ql.blackFormulaImpliedStdDev(typ, K, F, p, df, 0.0, ql.nullDouble(), 1e-14, 1000)
    return sd / math.sqrt(T)

# ---------------------------------------------------------------- greeks adapters (convention-normalised)
def vollib_bsm_greeks(flag, S, K, T, r, q, sig, mod=None):
    mod = mod or _bsm_ga
    # vollib conventions: vega per 1 vol point (x0.01), theta per calendar day (/365), rho per 1% (x0.01)
    return dict(delta=mod.delta(flag, S, K, T, r, sig, q), gamma=mod.gamma(flag, S, K, T, r, sig, q),
                vega=mod.vega(flag, S, K, T, r, sig, q) * 100, theta=mod.theta(flag, S, K, T, r, sig, q) * 365,
                rho=mod.rho(flag, S, K, T, r, sig, q) * 100)

def vollib_black_greeks(flag, S, K, T, r, q, sig, mod=None):
    mod = mod or _black_ga
    return dict(delta=mod.delta(flag, S, K, T, r, sig), gamma=mod.gamma(flag, S, K, T, r, sig),
                vega=mod.vega(flag, S, K, T, r, sig) * 100, theta=mod.theta(flag, S, K, T, r, sig) * 365,
                rho=mod.rho(flag, S, K, T, r, sig) * 100)

def oracle_greeks(flag, S, K, T, r, q, sig, black=False):
    """Exact derivatives by mpmath numerical differentiation of the 80-digit oracle price.
    theta = -dP/dT ; rho = dP/dr with q fixed (BSM) or F fixed (Black)."""
    if black:  # S is the forward; price = e^-rT Black(F)
        f = lambda S_, T_, r_, sig_: oracle(flag, S_, K, T_, r_, r_, sig_)
    else:
        f = lambda S_, T_, r_, sig_: oracle(flag, S_, K, T_, r_, q, sig_)
    S, T, r, sig = map(mp.mpf, (S, T, r, sig))
    out = dict(delta=mp.diff(lambda x: f(x, T, r, sig), S),
               gamma=mp.diff(lambda x: f(x, T, r, sig), S, 2),
               vega=mp.diff(lambda x: f(S, T, r, x), sig),
               theta=-mp.diff(lambda x: f(S, x, r, sig), T))
    if black:  # F fixed: d/dr of e^-rT * undiscounted
        out["rho"] = mp.diff(lambda x: oracle(flag, S, K, T, x, x, sig), r)
    else:
        out["rho"] = mp.diff(lambda x: f(S, T, x, sig), r)
    return {k: float(v) for k, v in out.items()}

# ---------------------------------------------------------------- sampling
REGIONS = {
    "core":   dict(sig=(0.05, 0.8, "u"), T=(0.05, 3.0, "u"), r=(-0.02, 0.08), q=(-0.02, 0.08), kx=(0.5, 2.0)),
    "stress": dict(sig=(0.001, 3.0, "log"), T=(1 / 365, 30.0, "log"), r=(-0.05, 0.40), q=(-0.05, 0.40), kx=(0.2, 5.0)),
}

def draw(rng, lo, hi, kind="u"):
    if kind == "log":
        return math.exp(rng.uniform(math.log(lo), math.log(hi)))
    return rng.uniform(lo, hi)

def sample_market(rng, region, model):
    R = REGIONS[region]
    m = dict(S=100.0, sig=draw(rng, *R["sig"]), T=draw(rng, *R["T"]),
             r=draw(rng, *R["r"]), q=draw(rng, *R["q"]))
    if model == "bs":
        m["q"] = 0.0
    if model == "black":
        m["q"] = m["r"]  # forward-measure: F = S
    lo, hi = R["kx"]
    m["Ks"] = sorted(100.0 * math.exp(rng.uniform(math.log(lo), math.log(hi))) for _ in range(9)) + [100.0]
    m["Ks"] = sorted(set(round(k, 10) for k in m["Ks"]))
    return m

# ---------------------------------------------------------------- checks
def check_prices(pr, m, viol, counts, tag):
    S, T, r, q, sig, Ks = m["S"], m["T"], m["r"], m["q"], m["sig"], m["Ks"]
    dq, dr = math.exp(-q * T), math.exp(-r * T)
    def add(inv, **kw):
        viol.append(dict(tag=tag, inv=inv, S=S, T=T, r=r, q=q, sig=sig, **kw))
    P = {}
    for k in "cp":
        for K in Ks:
            try:
                P[k, K] = pr(k, S, K, T, r, q, sig)
            except Exception as e:
                add("price_error", flag=k, K=K, err=repr(e)[:120])
                return
            if not math.isfinite(P[k, K]):
                add("nonfinite", flag=k, K=K, v=P[k, K]); return
    for K in Ks:
        a = TOL_REL * max(S * dq, K * dr)
        c, p = P["c", K], P["p", K]
        counts["bounds"] += 2; counts["parity"] += 1
        lo_c, hi_c = max(S * dq - K * dr, 0.0), S * dq
        lo_p, hi_p = max(K * dr - S * dq, 0.0), K * dr
        if c < lo_c - a or c > hi_c + a:
            add("bounds", flag="c", K=K, v=c, lo=lo_c, hi=hi_c, tol=a)
        if p < lo_p - a or p > hi_p + a:
            add("bounds", flag="p", K=K, v=p, lo=lo_p, hi=hi_p, tol=a)
        gap = (c - p) - (S * dq - K * dr)
        if abs(gap) > 4 * a:
            add("parity", K=K, gap=gap, tol=4 * a)
    for k in "cp":
        sl = []
        for K1, K2 in zip(Ks, Ks[1:]):
            h = K2 - K1
            a = TOL_REL * max(S * dq, K2 * dr)
            s = (P[k, K2] - P[k, K1]) / h
            sl.append((s, 2 * a / h, K1, K2))
            counts["slope_K"] += 1
            lo, hi = (-dr, 0.0) if k == "c" else (0.0, dr)
            if s < lo - 2 * a / h or s > hi + 2 * a / h:
                add("slope_K", flag=k, K1=K1, K2=K2, slope=s, lo=lo, hi=hi, tol=2 * a / h)
        for (s1, t1, K1, _), (s2, t2, _, K3) in zip(sl, sl[1:]):
            counts["convex_K"] += 1
            if s2 < s1 - (t1 + t2):
                add("convex_K", flag=k, K1=K1, K3=K3, ds=s2 - s1, tol=t1 + t2)
    # vol monotonicity on a fixed grid around sig
    grid = sorted(set([sig * f for f in (0.5, 0.9, 0.99, 1.0, 1.01, 1.1, 2.0)]))
    for k in "cp":
        for K in (Ks[0], 100.0, Ks[-1]):
            a = TOL_REL * max(S * dq, K * dr)
            vs = [pr(k, S, K, T, r, q, s) for s in grid]
            for s1, s2, v1, v2 in zip(grid, grid[1:], vs, vs[1:]):
                counts["vol_mono"] += 1
                if v2 < v1 - 2 * a:
                    add("vol_mono", flag=k, K=K, s1=s1, s2=s2, v1=v1, v2=v2, tol=2 * a)


def check_oracle(pr, m, viol, counts, tag, relerr_log):
    S, T, r, q, sig, Ks = m["S"], m["T"], m["r"], m["q"], m["sig"], m["Ks"]
    for k in "cp":
        for K in Ks:
            v = pr(k, S, K, T, r, q, sig)
            o = oracle(k, S, K, T, r, q, sig)
            scale = max(S * math.exp(-q * T), K * math.exp(-r * T))
            ab = abs(v - float(o))
            rel = float(abs((mp.mpf(v) - o) / o)) if o > 1e-300 else (0.0 if v == 0 else float("inf"))
            relerr_log.append((rel, ab / scale, float(o) / scale))
            counts["oracle"] += 1
            if ab > 1e-11 * scale:
                viol.append(dict(tag=tag, inv="oracle_abs", flag=k, S=S, K=K, T=T, r=r, q=q, sig=sig,
                                 v=v, oracle=float(o), absdiff=ab, tol=1e-11 * scale))


def check_iv(pr, ivf, m, viol, counts, tag, black=False):
    S, T, r, q, sig, Ks = m["S"], m["T"], m["r"], m["q"], m["sig"], m["Ks"]
    dq, dr = math.exp(-q * T), math.exp(-r * T)
    for k in "cp":
        for K in Ks:
            p = pr(k, S, K, T, r, q, sig)
            lo = max(S * dq - K * dr, 0.0) if k == "c" else max(K * dr - S * dq, 0.0)
            hi = S * dq if k == "c" else K * dr
            scale = max(S * dq, K * dr)
            tv = p - lo  # time value
            # --- round trip
            counts["iv_rt"] += 1
            try:
                iv = ivf(p, k, S, K, T, r, q)
                p2 = pr(k, S, K, T, r, q, iv)
                if abs(p2 - p) > 1e-10 * scale:
                    viol.append(dict(tag=tag, inv="iv_rt" if tv > 1e-13 * scale else "info_iv_rt_zero_tv", flag=k, S=S, K=K, T=T, r=r, q=q, sig=sig, p=p,
                                     iv=iv, p2=p2, tv_rel=tv / scale))
            except Exception as e:
                # time value at or below double-precision noise: IV is ill-posed (zero vega)
                illp = tv <= 1e-13 * scale
                viol.append(dict(tag=tag, inv="info_iv_rt_error_zero_tv" if illp else "iv_rt_error", flag=k, S=S, K=K, T=T, r=r, q=q, sig=sig, p=p,
                                 tv_rel=tv / scale, err=repr(e)[:100]))
            # --- out of band must raise
            for name, bad in (("below_lo_rel", lo - 1e-6 * scale), ("below_lo_big", lo - 0.01 * scale),
                              ("above_hi_rel", hi + 1e-6 * scale), ("at_hi", hi), ("negative", -1e-3 * scale)):
                if name == "negative" and lo > 0:
                    continue
                counts["iv_band"] += 1
                try:
                    res = ivf(bad, k, S, K, T, r, q)
                    if res is not None and math.isfinite(res):
                        # price == sup of the band: attained only as sigma -> inf, a large finite iv is
                        # an ill-posed-but-defensible answer; logged as info, not counted as a violation
                        viol.append(dict(tag=tag, inv="iv_band" if name != "at_hi" else "info_iv_at_hi", case=name, flag=k, S=S, K=K, T=T, r=r, q=q,
                                         price_in=bad, lo=lo, hi=hi, returned=res))
                except Exception:
                    pass


def check_greeks(pr, gfun, m, viol, counts, tag, black=False, Ks=None):
    S, T, r, q, sig = m["S"], m["T"], m["r"], m["q"], m["sig"]
    for k in "cp":
        for K in (Ks or (m["Ks"][0], 100.0, m["Ks"][-1])):
            g = gfun(k, S, K, T, r, q, sig)
            o = oracle_greeks(k, S, K, T, r, q, sig, black=black)
            for name in g:
                counts["greeks"] += 1
                scale_map = dict(delta=1.0, gamma=1.0 / S, vega=S, theta=S, rho=S * max(T, 1e-9))
                gv = float(g[name])
                err = abs(gv - o[name])
                tol = 1e-8 * scale_map[name] * max(1.0, abs(o[name]) / scale_map[name])
                if not math.isfinite(gv) or err > tol:
                    viol.append(dict(tag=tag, inv="greek_" + name, flag=k, S=S, K=K, T=T, r=r, q=q, sig=sig,
                                     lib=gv, oracle=o[name], err=err, tol=tol))


def run(pr, ivf, gfun, model, region, n, seed, do_oracle=True, do_greeks=True):
    rng = random.Random(seed)
    viol, counts, rel = [], {}, []
    from collections import Counter
    counts = Counter()
    for i in range(n):
        m = sample_market(rng, region, model)
        tag = f"{model}/{region}/{i}"
        check_prices(pr, m, viol, counts, tag)
        if do_oracle:
            check_oracle(pr, m, viol, counts, tag, rel)
        if ivf:
            check_iv(pr, ivf, m, viol, counts, tag)
        if gfun and do_greeks and i % 3 == 0:
            check_greeks(pr, gfun, m, viol, counts, tag, black=(model == "black"))
    return viol, counts, rel


if __name__ == "__main__":
    import argparse, collections
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="runs/scan.jsonl")
    a = ap.parse_args()
    SUBJECTS = {
        "vollib_bsm": (vollib_bsm, vollib_bsm_iv, vollib_bsm_greeks, "bsm"),
        "vollib_bs": (vollib_bs, None, None, "bs"),
        "vollib_black": (vollib_black, vollib_black_iv, vollib_black_greeks, "black"),
        "ql_blackFormula": (ql_bsm, ql_iv, None, "bsm"),
    }
    import os
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w") as fh:
        for sname, (pr, ivf, gf, model) in SUBJECTS.items():
            for region in REGIONS:
                v, c, rel = run(pr, ivf, gf, model, region, a.n, a.seed)
                byinv = collections.Counter(x["inv"] for x in v)
                rels = sorted(x[0] for x in rel if x[2] > 1e-200)
                summ = dict(subject=sname, region=region, n_markets=a.n, seed=a.seed, checks=dict(c),
                            violations=dict(byinv),
                            oracle_relerr_p50=rels[len(rels) // 2] if rels else None,
                            oracle_relerr_p99=rels[int(len(rels) * .99)] if rels else None,
                            oracle_relerr_max=rels[-1] if rels else None)
                print(json.dumps(summ))
                fh.write(json.dumps(dict(summary=summ)) + "\n")
                for x in v:
                    fh.write(json.dumps(dict(subject=sname, **x), default=str) + "\n")
