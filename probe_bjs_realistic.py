"""How wrong is QuantLib's Bjerksund-Stensland engine in plausible high-carry markets?
Breakdown condition (derived from the code): carry b' of the call-equivalent < 0 and
|b'| * sqrt(T) > 2 * sigma  ->  trigger I < B0 (economically impossible).
Reference: FD 2000x2000 (converged check vs 1000x1000 printed)."""
import QuantLib as ql
from qlinv.vanilla_scan import process, option

cases = [
    # label, kind, S, K, r, q, vol, T
    ("EM FX put (r_dom 40%, r_for 5%, vol 15%) 1y ATM", "P", 100, 100, 0.40, 0.05, 0.15, 1.0),
    ("EM FX put 2y ATM", "P", 100, 100, 0.40, 0.05, 0.15, 2.0),
    ("EM FX call (r_dom 5%, r_for 40%) 1y ATM", "C", 100, 100, 0.05, 0.40, 0.15, 1.0),
    ("high-yield stock call (r 3%, q 12%, vol 10%) 3y", "C", 100, 100, 0.03, 0.12, 0.10, 3.0),
    ("rates-like put (r 7.68%, q 0.75%, vol 2.31%) 1y", "P", 100, 100, 0.0768, 0.0075, 0.0231, 1.0),
    ("control: typical equity put (r 5%, q 1%, vol 25%) 1y", "P", 100, 100, 0.05, 0.01, 0.25, 1.0),
    ("control: typical equity put 5y", "P", 100, 100, 0.05, 0.01, 0.25, 5.0),
]
print(f"QuantLib {ql.__version__}")
print(f"{'case':54s} {'2s/|b|)^2':>9} {'BJS':>9} {'Eur':>9} {'FD1000':>9} {'FD2000':>9} {'BJS err':>8} {'QD+':>9} {'BAW':>9}")
for label, kind, S, K, r, q, vol, T in cases:
    b = (q - r) if kind == "P" else (r - q)
    thr = (2 * vol / abs(b)) ** 2 if b < 0 else float("inf")
    vals = {}
    for name, mk in [("BJS", lambda p: ql.BjerksundStenslandApproximationEngine(p)),
                     ("QD+", lambda p: ql.QdPlusAmericanEngine(p)),
                     ("BAW", lambda p: ql.BaroneAdesiWhaleyApproximationEngine(p)),
                     ("FD1000", lambda p: ql.FdBlackScholesVanillaEngine(p, 1000, 1000)),
                     ("FD2000", lambda p: ql.FdBlackScholesVanillaEngine(p, 2000, 2000))]:
        o = option(kind, K, T, "A"); o.setPricingEngine(mk(process(S, r, q, vol)))
        try:
            vals[name] = o.NPV()
        except Exception as e:
            vals[name] = float("nan")
    o = option(kind, K, T, "E"); o.setPricingEngine(ql.AnalyticEuropeanEngine(process(S, r, q, vol)))
    vals["Eur"] = o.NPV()
    err = vals["BJS"] / vals["FD2000"] - 1
    print(f"{label:54s} {thr:9.3f} {vals['BJS']:9.4f} {vals['Eur']:9.4f} {vals['FD1000']:9.4f} {vals['FD2000']:9.4f} {err:8.1%} {vals['QD+']:9.4f} {vals['BAW']:9.4f}")
