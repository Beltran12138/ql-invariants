"""Download Sourcify-verified sources of the live strategies and their pricers (chain 42161)."""
import json, os, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "onchain_src")


def get(addr):
    url = f"https://sourcify.dev/server/v2/contract/42161/{addr}?fields=compilation,sources,deployment"
    req = urllib.request.Request(url, headers={"User-Agent": "ql-invariants-audit/0.1"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=60))
    except Exception as e:
        return {"error": repr(e)[:200]}


strats = json.load(open(os.path.join(HERE, "strategies.json")))
addrs = sorted(set(strats) | {v["pricer()"] for v in strats.values()})
index = {}
for a in addrs:
    d = get(a)
    if "compilation" not in d:
        index[a] = {"name": None, "error": d.get("error") or d.get("message") or str(d)[:200]}
        print(a, "NOT VERIFIED", index[a]["error"][:80])
        continue
    c = d["compilation"]
    index[a] = {"name": c.get("name"), "fqn": c.get("fullyQualifiedName"),
                "deployed_block": (d.get("deployment") or {}).get("blockNumber")}
    os.makedirs(os.path.join(OUT, a), exist_ok=True)
    for path, s in (d.get("sources") or {}).items():
        if "node_modules" in path or "@openzeppelin" in path:
            continue
        fn = os.path.join(OUT, a, path.replace("/", "__").replace(":", "_"))
        open(fn, "w", encoding="utf-8").write(s["content"])
    print(a, index[a]["name"], index[a]["deployed_block"])
json.dump(index, open(os.path.join(HERE, "contract_names.json"), "w"), indent=1)
