"""Ju quadratic approximation at very short maturities: American vs European and the
American put-call inequality S e^-qT - K <= C - P <= S - K e^-rT (r, q >= 0)."""
import math
import QuantLib as ql
from qlinv.vanilla_scan import process, option

print(f"QuantLib {ql.__version__}")
for (S, r, q, vol) in [(194.365234, 0.0589, 0.0423, 0.6477), (101.018354, 0.0285, 0.0397, 0.4965),
                       (100.0, 0.05, 0.02, 0.30)]:
    for d in [1, 2, 5, 10, 30]:
        T = d / 365
        for K in [S * 0.95, S, S * 1.05]:
            v = {}
            for kind in "CP":
                for name, mk in [("ju", ql.JuQuadraticApproximationEngine), ("baw", ql.BaroneAdesiWhaleyApproximationEngine),
                                 ("fd", lambda p: ql.FdBlackScholesVanillaEngine(p, 400, 800))]:
                    o = option(kind, K, T, "A"); o.setPricingEngine(mk(process(S, r, q, vol))); v[(name, kind)] = o.NPV()
                o = option(kind, K, T, "E"); o.setPricingEngine(ql.AnalyticEuropeanEngine(process(S, r, q, vol))); v[("eu", kind)] = o.NPV()
            hi = S - K * math.exp(-r * T)
            flags = []
            for kind in "CP":
                if v[("ju", kind)] < v[("eu", kind)] - 1e-9: flags.append(f"ju<eu({kind}) by {v[('eu', kind)] - v[('ju', kind)]:.4g}")
            if v[("ju", "C")] - v[("ju", "P")] > hi + 1e-9: flags.append(f"C-P>{'S-Ke^-rT'} by {v[('ju','C')]-v[('ju','P')]-hi:.4g}")
            if flags:
                print(f"S={S:.2f} r={r} q={q} vol={vol} T={d}d K/S={K/S:.2f}  ju C={v[('ju','C')]:.4f} P={v[('ju','P')]:.4f} | fd C={v[('fd','C')]:.4f} P={v[('fd','P')]:.4f} | eu C={v[('eu','C')]:.4f} | " + "; ".join(flags))
