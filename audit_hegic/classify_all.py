"""Name and constructor arguments (Sourcify) of every strategy that ever held a position (positions.json)."""
import json, os, sys, time, urllib.request
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpc import rpc

HERE = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(os.path.join(HERE, "positions.json")))["positions"]
cnt = Counter(p["strategy"] for p in P.values())
out = {}
for a, k in cnt.most_common():
    row = {"positions": k}
    req = urllib.request.Request(f"https://sourcify.dev/server/v2/contract/42161/{a}?fields=compilation,creationBytecode,abi",
                                 headers={"User-Agent": "ql-invariants-audit/0.1"})
    try:
        d = json.load(urllib.request.urlopen(req, timeout=60))
        row["name"] = d["compilation"]["name"]
        args = d["creationBytecode"]["transformationValues"].get("constructorArguments") or "0x"
        ctor = [x for x in d["abi"] if x["type"] == "constructor"]
        row["ctor_inputs"] = [i["name"] for i in ctor[0]["inputs"]] if ctor else []
        row["ctor_words"] = [int(args[2 + 64 * i: 66 + 64 * i], 16) for i in range((len(args) - 2) // 64)]
    except Exception as e:
        row["name"] = None
        row["code_len"] = len(rpc("eth_getCode", [a, "latest"]))
    out[a] = row
    print(a, k, row.get("name"), row.get("ctor_words", row.get("code_len")), flush=True)
    time.sleep(0.3)
json.dump(out, open(os.path.join(HERE, "strategies_all.json"), "w"), indent=1)
