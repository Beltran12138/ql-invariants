"""Calibrate a cross-engine check: |A - QdPlus| > rel*QdPlus + absf*max(S,K)."""
import sys, json, collections
rel = float(sys.argv[2]); absf = float(sys.argv[3])
cnt = collections.Counter(); worst = {}; n = 0
for f in sys.argv[1].split(","):
    for l in open(f):
        r = json.loads(l); n += 1
        ref = r["res"]["QdPlus"]
        if not isinstance(ref, list): continue
        for e in ["BAW", "BJS", "Ju", "QdFp"]:
            v = r["res"][e]
            if not isinstance(v, list): continue
            d = abs(v[0] - ref[0])
            if d > rel * ref[0] + absf * max(r["S"], r["K"]):
                cnt[e] += 1
                w = (v[0] / ref[0] - 1) if ref[0] > 0 else None
                worst.setdefault(e, []).append(w)
print("N =", n, "rel", rel, "abs", absf)
for e in ["BAW", "BJS", "Ju", "QdFp"]:
    ws = sorted(x for x in worst.get(e, []) if x is not None)
    print(e, cnt[e], "err range:", (round(ws[0], 4), round(ws[-1], 4)) if ws else None)
