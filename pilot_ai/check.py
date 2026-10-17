"""Pilot checker (see PILOT.md). Runs in the main venv (QuantLib 1.44).

usage: check.py extract            # gen/*.raw -> code/*.py, static check
       check.py run [name ...]     # evaluate pricers, write results/*.json, print table
"""
import glob, json, math, os, random, re, subprocess, sys
import QuantLib as ql

HERE = os.path.dirname(os.path.abspath(__file__))
RUNPY = os.path.join(HERE, ".venv_run", "Scripts", "python.exe")
ALLOWED = {"math", "cmath", "numpy", "scipy", "functools"}
BANNED = re.compile(r"\b(os|sys|subprocess|socket|shutil|pathlib|ctypes|importlib|pickle)\b|"
                    r"\bopen\s*\(|\beval\s*\(|\bexec\s*\(|__import__|compile\s*\(")


def extract():
    os.makedirs(os.path.join(HERE, "code"), exist_ok=True)
    for raw in sorted(glob.glob(os.path.join(HERE, "gen", "*.raw"))):
        name = os.path.basename(raw)[:-4]
        txt = open(raw, encoding="utf-8").read()
        blocks = re.findall(r"```(?:python)?\n(.*?)```", txt, re.S)
        if not blocks:
            print(f"{name:12s} NO CODE ({len(txt)} chars)"); continue
        code = max(blocks, key=len)
        mods = {m.split(".")[0] for m in re.findall(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", code, re.M) for m in m if m}
        bad = sorted(mods - ALLOWED); ban = BANNED.findall(code)
        status = "OK" if not bad and not ban and "def american_price" in code else f"REJECT imports={bad} banned={ban}"
        if status == "OK":
            open(os.path.join(HERE, "code", name + ".py"), "w", encoding="utf-8").write(code)
        print(f"{name:12s} {status}  ({len(code.splitlines())} lines)")


# ---------- points (prompt B domain, integer days so T is exact for QuantLib too)
def points(n=600, seed=17):
    rng = random.Random(seed); pts = []
    for _ in range(n):
        days = int(round(math.exp(rng.uniform(math.log(1), math.log(3650)))))
        days = max(1, days)
        K = 100.0
        S = K * math.exp(rng.uniform(math.log(0.2), math.log(5)))
        pts.append(dict(S=S, K=K, days=days, r=rng.uniform(-0.02, 0.40), q=rng.uniform(-0.02, 0.40),
                        sigma=math.exp(rng.uniform(math.log(0.01), math.log(3.0))), is_call=rng.random() < 0.5))
    return pts


TODAY = ql.Date(15, 10, 2026); DC = ql.Actual365Fixed()
ql.Settings.instance().evaluationDate = TODAY


def ql_price(x, days, K, engine):
    p = ql.BlackScholesMertonProcess(ql.QuoteHandle(ql.SimpleQuote(x["S"])),
        ql.YieldTermStructureHandle(ql.FlatForward(TODAY, x["q"], DC)),
        ql.YieldTermStructureHandle(ql.FlatForward(TODAY, x["r"], DC)),
        ql.BlackVolTermStructureHandle(ql.BlackConstantVol(TODAY, ql.NullCalendar(), x["sigma"], DC)))
    pay = ql.PlainVanillaPayoff(ql.Option.Call if x["is_call"] else ql.Option.Put, K)
    if engine == "eu":
        o = ql.VanillaOption(pay, ql.EuropeanExercise(TODAY + days)); o.setPricingEngine(ql.AnalyticEuropeanEngine(p))
    else:
        o = ql.VanillaOption(pay, ql.AmericanExercise(TODAY, TODAY + days))
        o.setPricingEngine(ql.QdFpAmericanEngine(p, ql.QdFpAmericanEngine.highPrecisionScheme()))
        try:
            return o.NPV()
        except RuntimeError:
            # QdFp refuses the double-boundary case (q < r < 0 put, r < q < 0 call); use FD instead
            o.setPricingEngine(ql.FdBlackScholesVanillaEngine(p, 1000, 800))
    return o.NPV()


def variants(x):
    """The three evaluations each point needs: base, later maturity, strike +1%."""
    d2 = x["days"] + max(1, x["days"] // 10)
    return [(x["days"], x["K"]), (d2, x["K"]), (x["days"], x["K"] * 1.01)]


def reference(pts):
    path = os.path.join(HERE, "results", "reference.json")
    if os.path.exists(path):
        return json.load(open(path))
    ref = []
    for x in pts:
        ref.append(dict(eu=ql_price(x, x["days"], x["K"], "eu"),
                        qdfp=[ql_price(x, d, k, "qdfp") for d, k in variants(x)]))
    json.dump(ref, open(path, "w")); return ref


def evaluate(name, pts):
    inputs = [dict(S=x["S"], K=k, T=d / 365.0, r=x["r"], q=x["q"], sigma=x["sigma"], is_call=x["is_call"])
              for x in pts for d, k in variants(x)]
    wd = os.path.join(HERE, "results", "wd_" + name); os.makedirs(wd, exist_ok=True)
    inp = os.path.join(wd, "in.json"); outp = os.path.join(wd, "out.json")
    json.dump(inputs, open(inp, "w"))
    try:
        subprocess.run([RUNPY, "-I", os.path.join(HERE, "runner.py"), os.path.join(HERE, "code", name + ".py"), inp, outp],
                       cwd=wd, timeout=1800, check=True, capture_output=True)
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except subprocess.CalledProcessError as e:
        return None, "crash: " + e.stderr.decode(errors="ignore")[-200:]
    o = json.load(open(outp))
    return [o[3 * i:3 * i + 3] for i in range(len(pts))], None


def check(pts, ref, res):
    c = dict(n=len(pts), exc=0, nonfinite=0, mf_any=0, intrinsic=0, european=0, maturity=0, upper=0, strike=0,
             ref7=0, ms_med=None)
    times = []
    for x, rf, r3 in zip(pts, ref, res):
        times += [e["ms"] for e in r3]
        if any("err" in e for e in r3): c["exc"] += 1; continue
        if any(isinstance(e["v"], str) for e in r3): c["nonfinite"] += 1; c["mf_any"] += 1; continue
        a, a2, ak = (e["v"] for e in r3)
        S, K = x["S"], x["K"]; floor = 1e-8 * max(S, K); T = x["days"] / 365.0
        intr = max(S - K, 0) if x["is_call"] else max(K - S, 0)
        upper = S if x["is_call"] else K * max(1.0, math.exp(-x["r"] * T))
        bad = dict(intrinsic=a < intr - floor, european=a < rf["eu"] - floor,
                   maturity=a2 < a * 0.99 - floor, upper=a > upper + floor,
                   strike=(ak > a * 1.01 + floor) if x["is_call"] else (ak < a * 0.99 - floor))
        for k, v in bad.items(): c[k] += v
        c["mf_any"] += any(bad.values())
        q = rf["qdfp"][0]
        c["ref7"] += abs(a - q) > 0.02 * q + 1e-4 * max(S, K)
    times.sort(); c["ms_med"] = round(times[len(times) // 2], 3) if times else None
    return c


def run(names):
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    pts = points(); ref = reference(pts)
    rows = {}
    # controls, evaluated directly on the reference values
    rows["ctrl_qdfp"] = check(pts, ref, [[{"v": v, "ms": 0} for v in rf["qdfp"]] for rf in ref])
    eu_res = []
    for x in pts:
        eu_res.append([{"v": ql_price(x, d, k, "eu"), "ms": 0} for d, k in variants(x)])
    rows["ctrl_european"] = check(pts, ref, eu_res)
    for name in names:
        res, err = evaluate(name, pts)
        rows[name] = check(pts, ref, res) if res else {"error": err}
    json.dump(rows, open(os.path.join(HERE, "results", "table.json"), "w"), indent=1)
    cols = ["n", "exc", "nonfinite", "mf_any", "intrinsic", "european", "maturity", "upper", "strike", "ref7", "ms_med"]
    print(f"{'pricer':16s} " + " ".join(f"{c:>9s}" for c in cols))
    for k, v in rows.items():
        print(f"{k:16s} " + (" ".join(f"{str(v.get(c)):>9s}" for c in cols) if "error" not in v else v["error"]))


if __name__ == "__main__":
    if sys.argv[1] == "extract": extract()
    else: run(sys.argv[2:] or sorted(os.path.basename(p)[:-3] for p in glob.glob(os.path.join(HERE, "code", "*.py"))))
