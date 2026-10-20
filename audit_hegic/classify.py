"""Classify live strategies: verified name, or the verified contract whose runtime code differs only in a few bytes
(immutables). Also decode the constructor-set strike scale / strike limits where Sourcify has them."""
import json, os, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpc import rpc

HERE = os.path.dirname(os.path.abspath(__file__))
strats = json.load(open(os.path.join(HERE, "strategies.json")))
names = json.load(open(os.path.join(HERE, "contract_names.json")))
code = {a: rpc("eth_getCode", [a, "latest"]) for a in strats}


def ndiff(x, y):
    if len(x) != len(y):
        return None
    return sum(1 for i in range(2, len(x), 2) if x[i:i + 2] != y[i:i + 2])


verified = {a: names[a]["name"] for a in strats if names.get(a, {}).get("name")}
out = {}
for a in strats:
    if a in verified:
        out[a] = {"type": verified[a], "how": "sourcify"}
        continue
    best = min(((ndiff(code[a], code[v]), v) for v in verified if ndiff(code[a], code[v]) is not None), default=(None, None))
    out[a] = {"type": verified[best[1]] + "?" if best[1] else None, "how": f"code diff {best[0]} bytes vs {best[1]}" if best[1] else f"len {len(code[a])}, no same-length verified"}
for a in strats:
    req = urllib.request.Request(f"https://sourcify.dev/server/v2/contract/42161/{a}?fields=creationBytecode", headers={"User-Agent": "ql-invariants-audit/0.1"})
    try:
        args = json.load(urllib.request.urlopen(req, timeout=60))["creationBytecode"]["transformationValues"]["constructorArguments"]
        w = [int(args[2 + 64 * i: 66 + 64 * i], 16) for i in range((len(args) - 2) // 64)]
        out[a]["ctor_words"] = w[2:8]
    except Exception:
        out[a]["ctor_words"] = None
for a, s in strats.items():
    feed = {"0x639fe6ab55c921f74e7fac1ee960c0b6293ba612": "ETH", "0x6ce185860a4963106506c203335a2910413708e9": "BTC"}.get(s["priceProvider()"], s["priceProvider()"])
    out[a].update(asset=feed, minDays=s["minPeriod()"] / 86400, maxDays=s["maxPeriod()"] / 86400, pricer=s["pricer()"])
    print(a, out[a])
json.dump(out, open(os.path.join(HERE, "classified.json"), "w"), indent=1)
