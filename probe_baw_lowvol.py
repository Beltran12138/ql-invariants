"""BAW / Ju throw 'forward + displacement (0 + 0) must be positive' for valid low-vol inputs?"""
import QuantLib as ql
from qlinv.vanilla_scan import process, option

print(f"QuantLib {ql.__version__}")
S, r, q, T = 100.0, 0.0257, 0.0571, 3.0
for vol in [0.05, 0.03, 0.025, 0.02, 0.0166, 0.01]:
    for kind in "CP":
        for m in [0.5, 0.8, 0.9, 1.0, 1.1, 1.25, 2.0]:
            row = []
            for name, eng in [("BAW", ql.BaroneAdesiWhaleyApproximationEngine), ("Ju", ql.JuQuadraticApproximationEngine),
                              ("BJS", ql.BjerksundStenslandApproximationEngine), ("QD+", ql.QdPlusAmericanEngine)]:
                o = option(kind, S * m, T, "A"); o.setPricingEngine(eng(process(S, r, q, vol)))
                try:
                    row.append(f"{o.NPV():10.4f}")
                except Exception as e:
                    row.append("     THROW")
            if any("THROW" in x for x in row):
                print(f"vol={vol:<7} {kind} K/S={m:<5} BAW,Ju,BJS,QD+ = {' '.join(row)}")
