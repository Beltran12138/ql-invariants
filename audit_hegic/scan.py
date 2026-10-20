"""Quote every live strategy on a period grid (and a strike grid for the adaptive put) at one pinned block.

Quotes come from the strategy's own view function, calculateNegativepnlAndPositivepnl(amount, period, additional);
positivepnl is what ProxySeller charges the buyer (USDC, 6 decimals). Writes quotes.json.
"""
import json, os, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpc import RPC, rpc
from keccak import selector

HERE = os.path.dirname(os.path.abspath(__file__))
SEL_Q = selector("calculateNegativepnlAndPositivepnl(uint256,uint256,bytes[])")
SEL_LRD = selector("latestRoundData()")
SEL_DEC = selector("decimals()")
STEP = 6 * 3600


def w(x):
    return "%064x" % x


def enc_quote(amount, period, strike=None):
    if strike is None:
        return SEL_Q + w(amount) + w(period) + w(0x60) + w(0)
    # bytes[] with one element abi.encode(uint256 strike)
    return SEL_Q + w(amount) + w(period) + w(0x60) + w(1) + w(0x20) + w(32) + w(strike)


def batch(calls, block):
    """calls: list of (to, data). Returns list of hex results or None on revert."""
    out = []
    for i in range(0, len(calls), 50):
        chunk = calls[i:i + 50]
        body = [{"jsonrpc": "2.0", "id": j, "method": "eth_call", "params": [{"to": t, "data": d}, block]} for j, (t, d) in enumerate(chunk)]
        for attempt in range(10):
            try:
                req = urllib.request.Request(RPC, json.dumps(body).encode(), {"Content-Type": "application/json", "User-Agent": "ql-invariants-audit/0.1"})
                res = json.load(urllib.request.urlopen(req, timeout=120))
                break
            except Exception:
                if attempt == 9:
                    raise
                time.sleep(min(60, 2 ** attempt))   # 429s from the public node clear within a minute
        by = {r["id"]: r for r in res}
        out += [by[j].get("result") if "error" not in by[j] else None for j in range(len(chunk))]
        time.sleep(1.0)   # the public node answers 429 at ~3 batches/s
    return out


def main():
    cls = json.load(open(os.path.join(HERE, "classified.json")))
    block = rpc("eth_blockNumber", [])
    bts = int(rpc("eth_getBlockByNumber", [block, False])["timestamp"], 16)
    feeds = {}
    for a, c in cls.items():
        f = json.load(open(os.path.join(HERE, "strategies.json")))[a]["priceProvider()"]
        if f not in feeds:
            r = rpc("eth_call", [{"to": f, "data": SEL_LRD}, block])
            dec = int(rpc("eth_call", [{"to": f, "data": SEL_DEC}, block]), 16)
            feeds[f] = {"answer": int(r[66:130], 16), "decimals": dec, "updatedAt": int(r[194:258], 16)}
        c["feed"] = f
    print("block", int(block, 16), "ts", bts, {k[:8]: v for k, v in feeds.items()})
    quotes = {}
    for a, c in cls.items():
        unit = 10 ** (18 if c["asset"] == "ETH" else 8)
        lo, hi = int(c["minDays"] * 86400), int(c["maxDays"] * 86400)
        periods = sorted(set(list(range(lo, hi + 1, STEP)) + [hi]))
        calls = [(a, enc_quote(unit, p)) for p in periods]
        res = batch(calls, block)
        rows = [{"period": p, "neg": int(r[2:66], 16), "prem": int(r[66:130], 16)} if r else {"period": p, "revert": True} for p, r in zip(periods, res)]
        q = {"rows": rows}
        if c["type"] == "HegicStrategyAdaptivePut":
            S = feeds[c["feed"]]["answer"]
            grid = []
            for bp in range(8000, 12001, 25):          # 80%..120% of spot; purchasable only within the 90-95% limits
                for p in (lo, (lo + hi) // 2, hi):
                    grid.append((bp, p))
            res = batch([(a, enc_quote(unit, p, S * bp // 10000)) for bp, p in grid], block)
            q["strike_rows"] = [{"bp": bp, "strike": S * bp // 10000, "period": p, "prem": int(r[66:130], 16) if r else None} for (bp, p), r in zip(grid, res)]
        quotes[a] = q
        nrev = sum(1 for r in rows if r.get("revert"))
        print(a, c["asset"], c["type"], f'{c["minDays"]:.0f}-{c["maxDays"]:.0f}d', "n", len(rows), "reverts", nrev,
              "prem first/last", rows[0].get("prem"), rows[-1].get("prem"))
    json.dump({"block": int(block, 16), "timestamp": bts, "feeds": feeds, "classified": cls, "quotes": quotes},
              open(os.path.join(HERE, "quotes.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
