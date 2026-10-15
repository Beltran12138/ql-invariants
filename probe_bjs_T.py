"""American put value vs maturity: approximations vs FD reference.
An American option with a longer maturity can never be worth less (the holder can
always exercise on the shorter schedule)."""
import QuantLib as ql
from qlinv.vanilla_scan import process, option, days

S, r, q, vol = 100.0, 0.0768, 0.0075, 0.0231
K = 100.0
print(f"QuantLib {ql.__version__}  S={S} K={K} r={r} q={q} vol={vol}  (ATM American put)")
print(f"{'T(days)':>8} {'BJS':>10} {'BAW':>10} {'Ju':>10} {'QD+':>10} {'FD 800x800':>11} {'European':>10}")
for d in [30, 60, 91, 120, 150, 182, 220, 274, 365, 500, 730]:
    T = d / 365
    row = []
    for eng in [ql.BjerksundStenslandApproximationEngine, ql.BaroneAdesiWhaleyApproximationEngine,
                ql.JuQuadraticApproximationEngine, ql.QdPlusAmericanEngine]:
        o = option("P", K, T, "A"); o.setPricingEngine(eng(process(S, r, q, vol))); row.append(o.NPV())
    o = option("P", K, T, "A"); o.setPricingEngine(ql.FdBlackScholesVanillaEngine(process(S, r, q, vol), 800, 800)); row.append(o.NPV())
    o = option("P", K, T, "E"); o.setPricingEngine(ql.AnalyticEuropeanEngine(process(S, r, q, vol))); row.append(o.NPV())
    print(f"{d:8d} " + " ".join(f"{v:10.5f}" for v in row))
