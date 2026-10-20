"""Measure each bull-call-spread contract's width from its own payoff function, then redo spread_overpay.

For a position with strike K well below the current price (S > 1.5 K, beyond any width sold), payOffAmount = w*K*amount,
so w = payoff / (K * amount). Contracts with no such position are reported as width unknown (not assumed)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpc import rpc, RpcError
from keccak import selector

HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.load(open(os.path.join(HERE, "spread_overpay.json")))
call = lambda to, sig, *a: rpc("eth_call", [{"to": to, "data": selector(sig) + "".join("%064x" % x for x in a)}, "latest"])
feeds = {"ETH": "0x639fe6ab55c921f74e7fac1ee960c0b6293ba612", "BTC": "0x6ce185860a4963106506c203335a2910413708e9"}
spot = {k: int(call(f, "latestRoundData()")[66:130], 16) for k, f in feeds.items()}
asset = lambda r: "ETH" if r["amount"] > 10 ** 14 else "BTC"
width = {}
for a in sorted({r["strategy"] for r in rows}):
    cand = sorted((r for r in rows if r["strategy"] == a), key=lambda r: r["strike"])
    for r in cand:
        if spot[asset(r)] > 1.5 * r["strike"]:
            try:
                po = int(call(a, "payOffAmount(uint256)", r["id"]), 16)
            except RpcError:
                continue
            dec = 18 if asset(r) == "ETH" else 8
            width[a] = po / 1e6 / (r["strike"] / 1e8 * r["amount"] / 10 ** dec)
            break
    print(a, asset(cand[0]), "width", round(width[a], 6) if a in width else "unknown", flush=True)
out = []
for r in rows:
    w = width.get(r["strategy"])
    if w:
        r["width"] = w
        r["ratio"] = r["ratio"] * 0.1 / w     # ratio was computed against a 10% width
        out.append(r)
out.sort(key=lambda r: -r["ratio"])
print(f"\n{len(out)} of {len(rows)} purchases with a measured width; premium / max payoff: max {out[0]['ratio']:.3f}, "
      f"median {out[len(out) // 2]['ratio']:.3f}; above 1: {sum(r['ratio'] > 1 for r in out)}")
for r in out[:3]:
    print("  ", r["id"], r["strategy"][:10], f"width {r['width']:.3f} paid {r['premium']:.2f} ratio {r['ratio']:.3f} period {r['period_days']:.0f}d")
json.dump({"width": width, "rows": out}, open(os.path.join(HERE, "spread_width.json"), "w"), indent=1)
