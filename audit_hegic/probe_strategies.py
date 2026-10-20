"""For each contract seen in recent buy txs, try the HegicStrategy getters; print the ones that answer."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpc import call
from keccak import selector

HERE = os.path.dirname(os.path.abspath(__file__))
TOKENS = {"0xff970a61a04b1ca14834a43f5de4533ebddb5cc8", "0xaf88d065e77c8cc2239327c5edb3a432268e5831",
          "0x82af49447d8a07e3bd95bd0d56f35241523fbab1", "0x5fe380d68fee022d8acd42dc4d36fbfb249a76d5"}
GETTERS = ["pricer()", "priceProvider()", "minPeriod()", "maxPeriod()", "exerciseWindowDuration()", "k()", "lockedLimit()"]


def word(h, i=0):
    return int(h[2 + 64 * i: 2 + 64 * (i + 1)], 16)


emitters = json.load(open(os.path.join(HERE, "discover.json")))["emitters"]
out = {}
for a in emitters:
    if a in TOKENS:
        continue
    row = {}
    for g in GETTERS:
        try:
            r = call(a, selector(g))
            row[g] = word(r) if len(r) >= 66 else None
        except Exception as e:
            row[g] = None
    if row["pricer()"] is not None:
        row["pricer()"] = "0x%040x" % row["pricer()"]
        row["priceProvider()"] = "0x%040x" % row["priceProvider()"] if row["priceProvider()"] else None
        out[a] = row
        print(a, row)
    else:
        print(a, "not a strategy")
json.dump(out, open(os.path.join(HERE, "strategies.json"), "w"), indent=1)
