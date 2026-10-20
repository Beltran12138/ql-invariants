"""Find the strategies in use: recent option mints on the PositionsManager -> other contracts logging in the same tx."""
import json, os, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpc import rpc

PM = "0x5Fe380D68fEe022d8acd42dc4D36FbfB249a76d5"
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

head = int(rpc("eth_blockNumber", []), 16)
print("head", head)
logs, hi, step = [], head, 5_000_000
while len(logs) < 60 and hi > 0:
    lo = max(0, hi - step)
    try:
        r = rpc("eth_getLogs", [{"address": PM, "topics": [TRANSFER, "0x" + "0" * 64], "fromBlock": hex(lo), "toBlock": hex(hi)}])
        logs += r
        print(lo, hi, len(r))
        hi = lo - 1
    except Exception as e:
        print("err", str(e)[:120])
        step //= 4
txs = sorted({(int(l["blockNumber"], 16), l["transactionHash"]) for l in logs}, reverse=True)
print("mints found", len(txs), "latest block", txs[0][0] if txs else None, "oldest", txs[-1][0] if txs else None)
emit = Counter()
for b, h in txs[:60]:
    for l in rpc("eth_getTransactionReceipt", [h])["logs"]:
        emit[l["address"].lower()] += 1
for a, c in emit.most_common():
    print(a, c)
json.dump({"head": head, "txs": txs, "emitters": emit}, open(os.path.join(os.path.dirname(__file__), "discover.json"), "w"), indent=1)
