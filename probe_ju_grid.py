"""How often / how much does JuQuadraticApproximationEngine fall below the European value?
Grid over maturity, vol, moneyness, r, q (r, q >= 0); puts and calls."""
import itertools, math
import QuantLib as ql
from qlinv.vanilla_scan import process, option

S = 100.0
worst, n, bad = (0, None), 0, 0
for d, vol, m, r, q, kind in itertools.product([1, 2, 3, 5, 7, 14, 30], [0.1, 0.3, 0.5, 0.8, 1.2],
                                                [0.8, 0.9, 0.95, 1.0, 1.05, 1.1, 1.25], [0.0, 0.02, 0.06, 0.12],
                                                [0.0, 0.03, 0.08], "CP"):
    if r <= 0 and kind == "P" and False:
        continue
    T, K = d / 365, S * m
    o = option(kind, K, T, "A"); o.setPricingEngine(ql.JuQuadraticApproximationEngine(process(S, r, q, vol)))
    try:
        ju = o.NPV()
    except Exception:
        continue
    e = option(kind, K, T, "E"); e.setPricingEngine(ql.AnalyticEuropeanEngine(process(S, r, q, vol)))
    eu = e.NPV()
    n += 1
    if ju < eu - 1e-10:
        bad += 1
        rel = (eu - ju) / eu
        if rel > worst[0]:
            worst = (rel, dict(kind=kind, T_days=d, vol=vol, K_over_S=m, r=r, q=q, ju=ju, eu=eu))
print(f"QuantLib {ql.__version__}: {bad}/{n} grid points with Ju < European")
print("worst relative shortfall:", f"{worst[0]:.2%}", worst[1])
