"""Primary metric and H1-H4 from results/*.json (see BENCH.md). Runs in the main venv.

Generations whose raw reply had no code count as "no code" (reported, not dropped); for the primary
metric they are listed separately and excluded from the x/5 numerator and denominator only where noted.
"""
import glob, json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grade

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["opus", "sonnet", "deepseek-pro", "deepseek-flash", "gemini-pro"]
TASKS = ["T1", "T2", "T3"]

res = {os.path.basename(p)[:-5]: json.load(open(p)) for p in glob.glob(os.path.join(HERE, "results", "*__*.json"))}
raws = {os.path.basename(p)[:-4] for p in glob.glob(os.path.join(HERE, "gen", "*.raw"))}
codes = {os.path.basename(p)[:-3] for p in glob.glob(os.path.join(HERE, "code", "*.py"))}


def serious_any(r):
    return r["status"] != "ok" or r["serious"] > 0


print("Primary metric: generations with >= 1 serious model-free failure (x / graded), plus no-code and ref-only rows\n")
print(f"{'model':16s}" + "".join(f"{t:>26s}" for t in TASKS))
pooled = {t: [0, 0] for t in TASKS}
for m in MODELS:
    cells = []
    for t in TASKS:
        names = [f"{m}__{t}__{k}" for k in range(1, 6)]
        graded = [res[n] for n in names if n in res]
        nocode = [n for n in names if n in raws and n not in codes]
        missing = [n for n in names if n not in raws]
        x = sum(serious_any(r) for r in graded)
        refonly = sum(1 for r in graded if r["status"] == "ok" and r["serious"] == 0 and r["ref"] >= 30)
        pooled[t][0] += x; pooled[t][1] += len(graded)
        cells.append(f"{x}/{len(graded)} nc{len(nocode)} miss{len(missing)} refonly{refonly}")
    print(f"{m:16s}" + "".join(f"{c:>26s}" for c in cells))
print()
for t in TASKS:
    x, n = pooled[t]
    print(f"pooled {t}: {x}/{n} = {x / n:.0%}" if n else f"pooled {t}: no data")

x1, n1 = pooled["T1"]; x3, n3 = pooled["T3"]
print(f"\nH1 (T1 pooled >= 20%): {'MET' if n1 and x1 / n1 >= 0.2 else 'NOT MET'} ({x1}/{n1})")
print(f"H2 (T3 pooled >= 20%): {'MET' if n3 and x3 / n3 >= 0.2 else 'NOT MET'} ({x3}/{n3})")

# H3: odds ratio of a serious failure inside |r-q|*sqrt(T) > 2 sigma vs outside, over (generation, point) pairs, T1+T2
pts = grade.american_points()
inside = [abs(x["r"] - x["q"]) * math.sqrt(x["days"] / 365.0) > 2 * x["sigma"] for x in pts]
a = b = c = d = 0   # a: inside & serious, b: inside & ok, c: outside & serious, d: outside & ok
for n, r in res.items():
    if "__T3__" in n or r["status"] != "ok":
        continue
    for f, ins in zip(r["fails"], inside):
        s = any(v == "serious" for k, v in f.items() if k != "ref")
        if ins: a += s; b += not s
        else: c += s; d += not s
orr = (a * d) / (b * c) if b and c else float("inf")
print(f"\nH3: inside region {sum(inside)}/{len(pts)} points; serious inside {a}/{a + b}, outside {c}/{c + d}; "
      f"odds ratio {orr:.2f} -> {'MET' if orr > 2 else 'NOT MET'}")
if a and b and c and d:
    se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    print(f"    95% CI (Woolf) {math.exp(math.log(orr) - 1.96 * se):.2f} .. {math.exp(math.log(orr) + 1.96 * se):.2f}")

x2, n2 = pooled["T2"]
print(f"\nH4 (T2 vs T1, no direction): T1 {x1}/{n1}, T2 {x2}/{n2}")

print("\nPer generation (serious / model-free / ref, median ms):")
for n in sorted(res):
    r = res[n]
    print(f"  {n:24s} " + (f"{r['serious']:4d} {r['model_free']:4d} {r['ref']:4d} {r['ms_median']:9.3f}" if r["status"] == "ok" else r["status"][:60]))
