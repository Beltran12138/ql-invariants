"""Every position ever opened: lockedLiquidity(id) on the treasury (strategy, collateral, premium paid, expiry)
and, for the classic strategies, strategyData(id) (amount, strike). Current state only - no archive node needed.

Resumable: each batch of results is appended to positions_cache.jsonl as it arrives, and a rerun skips what is
already there (the process has been killed twice mid-run). Writes positions.json at the end."""
import json, os, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpc import rpc
from keccak import selector
from scan import batch

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "positions_cache.jsonl")
TRE, PM = "0xec096ea6eB9aa5ea689b0CF00882366E92377371", "0x5Fe380D68fEe022d8acd42dc4D36FbfB249a76d5"
w = lambda r, i: int(r[2 + 64 * i: 66 + 64 * i], 16)

done = {"ll": {}, "sd": {}}
meta = None
if os.path.exists(CACHE):
    for line in open(CACHE):
        rec = json.loads(line)
        if rec["k"] == "meta":
            meta = rec
        else:
            done[rec["k"]][int(rec["id"])] = rec["r"]
if meta is None:
    block = rpc("eth_blockNumber", [])
    n = int(rpc("eth_call", [{"to": PM, "data": selector("nextTokenId()")}, block]), 16)
    meta = {"k": "meta", "block": block, "n": n}
    open(CACHE, "a").write(json.dumps(meta) + "\n")
block, n = meta["block"], meta["n"]
print("block", int(block, 16), "positions", n, "cached ll", len(done["ll"]), "sd", len(done["sd"]), flush=True)


def fetch(kind, items):
    """items: list of (id, to, data); results appended to the cache 500 at a time."""
    todo = [x for x in items if x[0] not in done[kind]]
    for i in range(0, len(todo), 500):
        chunk = todo[i:i + 500]
        res = batch([(t, d) for _, t, d in chunk], block)
        with open(CACHE, "a") as f:
            for (pid, _, _), r in zip(chunk, res):
                done[kind][pid] = r
                f.write(json.dumps({"k": kind, "id": pid, "r": r}) + "\n")
        print(kind, len(done[kind]), flush=True)


fetch("ll", [(i, TRE, selector("lockedLiquidity(uint256)") + "%064x" % i) for i in range(n)])
pos = {}
for i, r in done["ll"].items():
    if r and w(r, 1) != 0:
        pos[i] = {"state": w(r, 0), "strategy": "0x%040x" % w(r, 1), "neg": w(r, 2), "prem": w(r, 3), "exp": w(r, 4)}
print("positions with liquidity records", len(pos), "of", n, flush=True)
fetch("sd", [(i, pos[i]["strategy"], selector("strategyData(uint256)") + "%064x" % i) for i in sorted(pos)])
for i in pos:
    r = done["sd"].get(i)
    if r and len(r) == 2 + 128:      # classic StrategyData(uint128 amount, uint128 strike)
        pos[i]["amount"], pos[i]["strike"] = w(r, 0), w(r, 1)
    elif r:
        pos[i]["sd_raw"] = r[:400]
json.dump({"block": int(block, 16), "n": n, "positions": pos}, open(os.path.join(HERE, "positions.json"), "w"))
print(Counter(p["strategy"] for p in pos.values()).most_common(60))
