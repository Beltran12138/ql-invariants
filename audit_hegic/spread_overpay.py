"""Did any buyer of a long bull-call-spread (unverified family, runtime code length 17952; priced as
ATM call - 0.8 x 110% call, so the width is taken as 10% of the strike) pay more than the spread's maximum payoff?
Reads the strategies' Acquired events: (id, StrategyData(amount, strike), negativePNL, positivePNL, period, ...).
Prints the ratio premium / (0.1 x strike x amount) for every purchase; > 1 means paying more than the max payoff."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpc import rpc
from keccak import keccak256

HERE = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(os.path.join(HERE, "strategies_all.json")))
M = json.load(open(os.path.join(HERE, "mints.json")))
fam = [a for a, r in S.items() if r.get("code_len") == 17952]
TOPIC = "0x" + keccak256(b"Acquired(uint256,(uint128,uint128),uint256,uint256,uint256,bytes[])").hex()
head = int(rpc("eth_blockNumber", []), 16)
rows = []
P = json.load(open(os.path.join(HERE, "positions.json")))["positions"]
for a in fam:
    blocks = [M[i] for i, p in P.items() if p["strategy"] == a]
    lo, head = min(blocks), max(blocks)   # only the span in which this strategy minted positions
    while lo <= head:
        hi = min(head, lo + 5_000_000 - 1)
        for l in rpc("eth_getLogs", [{"address": a, "topics": [TOPIC], "fromBlock": hex(lo), "toBlock": hex(hi)}]):
            d = l["data"][2:]
            wd = [int(d[i:i + 64], 16) for i in range(0, len(d), 64)]
            pid = int(l["topics"][1], 16) if len(l["topics"]) > 1 else wd.pop(0)
            amount, strike, neg, pos, period = wd[0], wd[1], wd[2], wd[3], wd[4]
            unit = 1e18 if strike < 10 ** 13 else 1e8          # ETH strikes (8-dec feed) are < 1e13
            dec = 18 if amount > 10 ** 14 else 8
            cap = 0.1 * strike / 1e8 * amount / 10 ** dec
            rows.append({"strategy": a, "id": pid, "block": int(l["blockNumber"], 16), "amount": amount, "strike": strike,
                         "premium": pos / 1e6, "period_days": period / 86400, "cap": cap, "ratio": pos / 1e6 / cap if cap else None})
        lo = hi + 1
    print(a, "events so far", len(rows), flush=True)
rows.sort(key=lambda r: -(r["ratio"] or 0))
print(f"\n{len(rows)} purchases on {len(fam)} contracts; premium / max payoff: max {rows[0]['ratio']:.3f}, "
      f"median {rows[len(rows) // 2]['ratio']:.3f}; above 1: {sum(r['ratio'] > 1 for r in rows)}")
for r in rows[:5]:
    print("  ", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})
json.dump(rows, open(os.path.join(HERE, "spread_overpay.json"), "w"), indent=1)
