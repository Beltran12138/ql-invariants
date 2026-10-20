"""All logs ever emitted by the live pricers (parameter updates), plus the current on-chain parameters."""
import json, os, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpc import rpc
from keccak import keccak256, selector

HERE = os.path.dirname(os.path.abspath(__file__))
cls = json.load(open(os.path.join(HERE, "classified.json")))
pricers = sorted({c["pricer"] for c in cls.values()})
TOPICS = {"0x" + keccak256(s.encode()).hex(): s for s in [
    "SetCoefficients(int256[5])", "SetDiscount(int256[5])", "SetImpliedVolRate(uint256)", "SetSettlementFeeShare(uint256)",
    "SetPeriodLimits(uint256,uint256)", "RoleGranted(bytes32,address,address)", "RoleRevoked(bytes32,address,address)"]}

head = int(rpc("eth_blockNumber", []), 16)
logs = {p: [] for p in pricers}
for p in pricers:   # the public node allows wide ranges only for a single address
    lo = 30_000_000
    while lo <= head:
        hi = min(head, lo + 5_000_000 - 1)
        logs[p] += rpc("eth_getLogs", [{"address": p, "fromBlock": hex(lo), "toBlock": hex(hi)}])
        lo = hi + 1

out = {}
for p in pricers:
    ev = []
    for l in logs[p]:
        name = TOPICS.get(l["topics"][0], l["topics"][0][:10])
        data = l["data"][2:]
        words = [int(data[i:i + 64], 16) for i in range(0, len(data), 64)]
        words = [w - (1 << 256) if w >> 255 else w for w in words]
        ev.append({"block": int(l["blockNumber"], 16), "event": name, "words": words})
    blocks = sorted({e["block"] for e in ev})
    ts = {}
    for b in [blocks[0], blocks[-1]] if blocks else []:
        ts[b] = int(rpc("eth_getBlockByNumber", [hex(b), False])["timestamp"], 16)
    out[p] = ev
    used = [a[:8] for a, c in cls.items() if c["pricer"] == p]
    print(p, "used by", used, Counter(e["event"] for e in ev))
    if blocks:
        print("   first", blocks[0], ts[blocks[0]], " last", blocks[-1], ts[blocks[-1]])
        for e in [e for e in ev if e["event"] != "RoleGranted(bytes32,address,address)"][-3:]:
            print("   ", e["block"], e["event"], e["words"])
json.dump(out, open(os.path.join(HERE, "pricer_history.json"), "w"), indent=1)
