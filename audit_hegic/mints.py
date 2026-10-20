"""Mint block of every position (PositionsManager Transfer from 0x0). Writes mints.json {id: block}."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpc import rpc

HERE = os.path.dirname(os.path.abspath(__file__))
PM = "0x5Fe380D68fEe022d8acd42dc4D36FbfB249a76d5"
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
head = int(rpc("eth_blockNumber", []), 16)
out, lo = {}, 30_000_000
while lo <= head:
    hi = min(head, lo + 5_000_000 - 1)
    for l in rpc("eth_getLogs", [{"address": PM, "topics": [TRANSFER, "0x" + "0" * 64], "fromBlock": hex(lo), "toBlock": hex(hi)}]):
        out[int(l["topics"][3], 16)] = int(l["blockNumber"], 16)
    lo = hi + 1
print("mints", len(out), "ids", min(out), max(out))
json.dump(out, open(os.path.join(HERE, "mints.json"), "w"))
