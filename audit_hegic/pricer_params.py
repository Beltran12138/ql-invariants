"""Current parameters of the live pricers, read with eth_call at the scan block (quotes.json)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rpc import rpc, RpcError
from keccak import selector

HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, "quotes.json")))
block = hex(d["block"])


def call(to, sig, *args):
    data = selector(sig) + "".join("%064x" % a for a in args)
    try:
        r = rpc("eth_call", [{"to": to, "data": data}, block])
    except RpcError:
        return None
    return r if r and r != "0x" else None


def i256(h):
    v = int(h[2:66], 16)
    return v - (1 << 256) if v >> 255 else v


seen, todo, out = set(), sorted({c["pricer"] for c in d["classified"].values()}), {}
while todo:
    p = todo.pop()
    if p in seen:
        continue
    seen.add(p)
    row = {}
    if call(p, "basePricers(uint256)", 0):
        row["kind"] = "Combine"
        row["base"] = ["0x" + call(p, "basePricers(uint256)", i)[-40:] for i in range(2)]
        row["coef_1e5"] = [i256(call(p, "coeficients(uint256)", i)) for i in range(2)]
        todo += row["base"]
    elif call(p, "basePricer()"):
        row["kind"] = "ScaledPolynomial"
        row["base"] = ["0x" + call(p, "basePricer()")[-40:]]
        row["discount"] = [i256(call(p, "discount(uint256)", i)) for i in range(5)]
        todo += row["base"]
    elif call(p, "coefficients(uint256)", 0):
        row["kind"] = "Polynomial"
        row["coefficients"] = [i256(call(p, "coefficients(uint256)", i)) for i in range(5)]
    elif call(p, "impliedVolRate()"):
        row["kind"] = "IVL"
        row["impliedVolRate"] = int(call(p, "impliedVolRate()"), 16)
    else:
        row["kind"] = "unknown"
    for g in ["minPeriod()", "maxPeriod()", "priceCorrectionRate()", "utilizationRate()"]:
        r = call(p, g)
        if r:
            row[g] = int(r, 16)
    out[p] = row
    print(p, row)
json.dump(out, open(os.path.join(HERE, "pricer_params.json"), "w"), indent=1)
