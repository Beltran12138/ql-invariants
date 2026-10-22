"""Benchmark grader (see BENCH.md). Runs in the main venv (QuantLib 1.44).

usage: grade.py controls                 # run positive/negative controls for both task families
       grade.py extract                  # gen/*.raw -> code/*.py with static check
       grade.py run [name ...]           # evaluate code/<name>.py, write results/<name>.json
       grade.py table                    # summary table from results/*.json
Names are <model>__<task>__<k>, e.g. deepseek-pro__T1__3.
"""
import glob, json, math, os, random, re, subprocess, sys
import QuantLib as ql

HERE = os.path.dirname(os.path.abspath(__file__))
RUNPY = os.path.join(HERE, "..", "pilot_ai", ".venv_run", "Scripts", "python.exe")
ALLOWED = {"math", "cmath", "numpy", "scipy", "functools", "typing", "__future__"}
BANNED = re.compile(r"\b(os|sys|subprocess|socket|shutil|pathlib|ctypes|importlib|pickle)\b\.|"
                    r"\bopen\s*\(|\beval\s*\(|\bexec\s*\(|__import__|\bcompile\s*\(")
TODAY = ql.Date(15, 10, 2026); DC = ql.Actual365Fixed()
ql.Settings.instance().evaluationDate = TODAY
SERIOUS = 0.01


# ------------------------------------------------------------------ QuantLib references
def process(S, r, q, sigma):
    return ql.BlackScholesMertonProcess(ql.QuoteHandle(ql.SimpleQuote(S)),
        ql.YieldTermStructureHandle(ql.FlatForward(TODAY, q, DC)),
        ql.YieldTermStructureHandle(ql.FlatForward(TODAY, r, DC)),
        ql.BlackVolTermStructureHandle(ql.BlackConstantVol(TODAY, ql.NullCalendar(), sigma, DC)))


def european(S, K, days, r, q, sigma, is_call):
    o = ql.VanillaOption(ql.PlainVanillaPayoff(ql.Option.Call if is_call else ql.Option.Put, K),
                         ql.EuropeanExercise(TODAY + days))
    o.setPricingEngine(ql.AnalyticEuropeanEngine(process(S, r, q, sigma)))
    return o.NPV()


def american_ref(S, K, days, r, q, sigma, is_call):
    p = process(S, r, q, sigma)
    o = ql.VanillaOption(ql.PlainVanillaPayoff(ql.Option.Call if is_call else ql.Option.Put, K),
                         ql.AmericanExercise(TODAY, TODAY + days))
    o.setPricingEngine(ql.QdFpAmericanEngine(p, ql.QdFpAmericanEngine.highPrecisionScheme()))
    try:
        return o.NPV()
    except RuntimeError:  # double-boundary case
        o.setPricingEngine(ql.FdBlackScholesVanillaEngine(p, 1000, 800))
        return o.NPV()


BT = {"down-and-out": ql.Barrier.DownOut, "down-and-in": ql.Barrier.DownIn,
      "up-and-out": ql.Barrier.UpOut, "up-and-in": ql.Barrier.UpIn}


def breached(S, H, bt):
    return S <= H if bt.startswith("down") else S >= H


def barrier_ref(S, K, H, days, r, q, sigma, is_call, bt):
    if breached(S, H, bt):
        return 0.0 if bt.endswith("out") else european(S, K, days, r, q, sigma, is_call)
    o = ql.BarrierOption(BT[bt], H, 0.0, ql.PlainVanillaPayoff(ql.Option.Call if is_call else ql.Option.Put, K),
                         ql.EuropeanExercise(TODAY + days))
    o.setPricingEngine(ql.AnalyticBarrierEngine(process(S, r, q, sigma)))
    return o.NPV()


# ------------------------------------------------------------------ points
def american_points(n=600, seed=23):
    rng = random.Random(seed); pts = []
    for _ in range(n):
        days = max(1, int(round(math.exp(rng.uniform(0, math.log(3650))))))
        pts.append(dict(S=100.0 * math.exp(rng.uniform(math.log(0.2), math.log(5))), K=100.0, days=days,
                        r=rng.uniform(-0.02, 0.40), q=rng.uniform(-0.02, 0.40),
                        sigma=math.exp(rng.uniform(math.log(0.01), math.log(3.0))), is_call=rng.random() < 0.5))
    return pts


def barrier_points(n=600, seed=23):
    rng = random.Random(seed + 1); pts = []
    for _ in range(n):
        days = max(1, int(round(math.exp(rng.uniform(0, math.log(3650))))))
        S = 100.0 * math.exp(rng.uniform(math.log(0.2), math.log(5)))
        down = rng.random() < 0.5
        if rng.random() < 0.1:   # breached at inception
            h = rng.uniform(1.0, 1.2) if down else rng.uniform(1 / 1.2, 1.0)
        else:
            h = math.exp(rng.uniform(math.log(0.5), math.log(0.995))) if down else math.exp(rng.uniform(math.log(1.005), math.log(2.0)))
        pts.append(dict(S=S, K=100.0, H=S * h, days=days, r=rng.uniform(-0.02, 0.40), q=rng.uniform(-0.02, 0.40),
                        sigma=math.exp(rng.uniform(math.log(0.01), math.log(3.0))), is_call=rng.random() < 0.5,
                        dir="down" if down else "up"))
    return pts


def american_calls(x):
    """(days, K) for base, later maturity, strike +1%."""
    return [(x["days"], x["K"]), (x["days"] + max(1, x["days"] // 10), x["K"]), (x["days"], x["K"] * 1.01)]


def barrier_calls(x):
    """(H, type) for out, in, out with barrier moved towards spot, in with barrier moved towards spot."""
    H2 = x["H"] * 1.01 if x["dir"] == "down" else x["H"] / 1.01
    d = x["dir"]
    return [(x["H"], d + "-and-out"), (x["H"], d + "-and-in"), (H2, d + "-and-out"), (H2, d + "-and-in")]


def references(task):
    path = os.path.join(HERE, "results", f"reference_{task}.json")
    if os.path.exists(path):
        return json.load(open(path))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ref = []
    if task == "american":
        for x in american_points():
            ref.append(dict(eu=european(x["S"], x["K"], x["days"], x["r"], x["q"], x["sigma"], x["is_call"]),
                            am=[american_ref(x["S"], k, d, x["r"], x["q"], x["sigma"], x["is_call"]) for d, k in american_calls(x)]))
    else:
        for x in barrier_points():
            ref.append(dict(van=european(x["S"], x["K"], x["days"], x["r"], x["q"], x["sigma"], x["is_call"]),
                            bar=[barrier_ref(x["S"], x["K"], h, x["days"], x["r"], x["q"], x["sigma"], x["is_call"], bt)
                                 for h, bt in barrier_calls(x)]))
    json.dump(ref, open(path, "w"))
    return ref


# ------------------------------------------------------------------ checks
def _fail(gap, ref_val, scale):
    """None if ok, else 'minor' or 'serious'."""
    if not gap > 1e-8 * scale:
        return None
    return "serious" if gap > SERIOUS * max(abs(ref_val), 1e-4 * scale) else "minor"


def check_american(pts, ref, vals):
    """vals: per point a list of 3 floats or an error string. Returns per-point dicts of failures."""
    out = []
    for x, rf, v in zip(pts, ref, vals):
        if isinstance(v, str):
            out.append({"error": "serious"}); continue
        a, a2, ak = v
        S, K = x["S"], x["K"]; sc = max(S, K); T = x["days"] / 365.0; am = rf["am"][0]
        intr = max(S - K, 0) if x["is_call"] else max(K - S, 0)
        up = S * max(1.0, math.exp(-x["q"] * T)) if x["is_call"] else K * max(1.0, math.exp(-x["r"] * T))
        f = {"intrinsic": _fail(intr - a, am, sc), "european": _fail(rf["eu"] - a, am, sc),
             "maturity": _fail(a * 0.99 - a2, am, sc), "upper": _fail(a - up, am, sc),
             "strike": _fail((ak - a * 1.01) if x["is_call"] else (a * 0.99 - ak), am, sc)}
        f = {k: s for k, s in f.items() if s}
        if abs(a - am) > 0.02 * am + 1e-4 * sc:
            f["ref"] = "ref"
        out.append(f)
    return out


def check_barrier(pts, ref, vals):
    out = []
    for x, rf, v in zip(pts, ref, vals):
        if isinstance(v, str):
            out.append({"error": "serious"}); continue
        o, i, o2, i2 = v
        S, K, H = x["S"], x["K"], x["H"]; sc = max(S, K, H); van = rf["van"]
        bt_out = x["dir"] + "-and-out"
        f = {"parity": _fail(abs(o + i - van), van, sc),
             "out_bounds": _fail(max(-o, o - van), van, sc), "in_bounds": _fail(max(-i, i - van), van, sc),
             "out_barrier": _fail(o2 - o * 1.01, rf["bar"][0], sc), "in_barrier": _fail(i * 0.99 - i2, rf["bar"][1], sc)}
        if breached(S, H, bt_out):
            f["breached_out"] = _fail(abs(o), van, sc); f["breached_in"] = _fail(abs(i - van), van, sc)
        if (x["dir"] == "up" and x["is_call"] and H <= K) or (x["dir"] == "down" and not x["is_call"] and H >= K):
            f["zero_case"] = _fail(abs(o), van, sc)
        f = {k: s for k, s in f.items() if s}
        if abs(o - rf["bar"][0]) > 0.02 * rf["bar"][0] + 1e-4 * sc or abs(i - rf["bar"][1]) > 0.02 * rf["bar"][1] + 1e-4 * sc:
            f["ref"] = "ref"
        out.append(f)
    return out


def summarize(fails):
    n = len(fails)
    mf = [f for f in fails if any(k != "ref" for k in f)]
    ser = [f for f in fails if any(s == "serious" for k, s in f.items() if k != "ref")]
    kinds = {}
    for f in fails:
        for k, s in f.items():
            kinds[k + ("" if s in ("ref",) else "/" + s)] = kinds.get(k + ("" if s in ("ref",) else "/" + s), 0) + 1
    return dict(n=n, model_free=len(mf), serious=len(ser), ref=sum("ref" in f for f in fails), kinds=kinds)


# ------------------------------------------------------------------ controls
def controls():
    for task in ["american", "barrier"]:
        pts = american_points() if task == "american" else barrier_points(); ref = references(task)
        if task == "american":
            neg = [rf["am"] for rf in ref]
            pos = [[european(x["S"], k, d, x["r"], x["q"], x["sigma"], x["is_call"]) for d, k in american_calls(x)] for x in pts]
            rows = {"neg: QdFp": check_american(pts, ref, neg), "pos: European value": check_american(pts, ref, pos)}
        else:
            neg = [rf["bar"] for rf in ref]
            # pos 1: knock-out returns the vanilla value
            pos1 = [[rf["van"], rf["bar"][1], rf["van"], rf["bar"][3]] for rf in ref]
            # pos 2: r and q swapped in every price; in = vanilla(swapped) - out(swapped), so parity holds by construction
            pos2 = []
            for x in pts:
                vs = european(x["S"], x["K"], x["days"], x["q"], x["r"], x["sigma"], x["is_call"])
                outs = [barrier_ref(x["S"], x["K"], h, x["days"], x["q"], x["r"], x["sigma"], x["is_call"], bt) for h, bt in barrier_calls(x)]
                pos2.append([outs[0], vs - outs[0], outs[2], vs - outs[2]])
            # pos 3: up-and-out call / down-and-out put zero cases returned as vanilla
            pos3 = []
            for x, rf in zip(pts, ref):
                v = list(rf["bar"])
                zc = (x["dir"] == "up" and x["is_call"] and x["H"] <= x["K"]) or (x["dir"] == "down" and not x["is_call"] and x["H"] >= x["K"])
                if zc and not breached(x["S"], x["H"], x["dir"] + "-and-out"):
                    v = [rf["van"], 0.0, rf["van"], 0.0]
                pos3.append(v)
            # pos 4: the "moved" barrier is moved away from the spot instead of towards it
            pos4 = []
            for x, rf in zip(pts, ref):
                Haway = x["H"] / 1.01 if x["dir"] == "down" else x["H"] * 1.01
                d = x["dir"]
                pos4.append([rf["bar"][0], rf["bar"][1],
                             barrier_ref(x["S"], x["K"], Haway, x["days"], x["r"], x["q"], x["sigma"], x["is_call"], d + "-and-out"),
                             barrier_ref(x["S"], x["K"], Haway, x["days"], x["r"], x["q"], x["sigma"], x["is_call"], d + "-and-in")])
            rows = {"neg: QuantLib analytic": check_barrier(pts, ref, neg), "pos: out = vanilla": check_barrier(pts, ref, pos1),
                    "pos: barrier moved away": check_barrier(pts, ref, pos4),
                    "pos: r and q swapped": check_barrier(pts, ref, pos2), "pos: zero cases = vanilla": check_barrier(pts, ref, pos3)}
        for k, fails in rows.items():
            print(f"{task:9s} {k:28s} {summarize(fails)}")


# ------------------------------------------------------------------ generated code
def extract():
    for raw in sorted(glob.glob(os.path.join(HERE, "gen", "*.raw"))):
        name = os.path.basename(raw)[:-4]
        if os.path.exists(os.path.join(HERE, "code", name + ".py")):
            continue
        txt = open(raw, encoding="utf-8").read()
        blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", txt, re.S)
        if not blocks:
            print(f"{name:28s} NO CODE ({len(txt)} chars)"); continue
        code = max(blocks, key=len)
        mods = {m.split(".")[0] for pair in re.findall(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", code, re.M) for m in pair if m}
        bad = sorted(mods - ALLOWED); ban = BANNED.findall(code)
        fn = "barrier_price" if "__T3__" in name else "american_price"
        if bad or ban or f"def {fn}" not in code:
            print(f"{name:28s} REJECT imports={bad} banned={ban} has_fn={f'def {fn}' in code}"); continue
        open(os.path.join(HERE, "code", name + ".py"), "w", encoding="utf-8").write(code)
        print(f"{name:28s} OK ({len(code.splitlines())} lines)")


def run_one(name):
    task = "barrier" if "__T3__" in name else "american"
    pts = american_points() if task == "american" else barrier_points(); ref = references(task)
    if task == "american":
        args = [[x["S"], k, d / 365.0, x["r"], x["q"], x["sigma"], x["is_call"]] for x in pts for d, k in american_calls(x)]
        fn, per = "american_price", 3
    else:
        args = [[x["S"], x["K"], h, x["days"] / 365.0, x["r"], x["q"], x["sigma"], x["is_call"], bt] for x in pts for h, bt in barrier_calls(x)]
        fn, per = "barrier_price", 4
    wd = os.path.join(HERE, "results", "wd", name); os.makedirs(wd, exist_ok=True)
    inp, outp = os.path.join(wd, "in.json"), os.path.join(wd, "out.json")
    json.dump(args, open(inp, "w"))
    status = "ok"
    try:
        subprocess.run([RUNPY, "-I", os.path.join(HERE, "runner.py"), os.path.join(HERE, "code", name + ".py"), fn, inp, outp],
                       cwd=wd, timeout=3600, check=True, capture_output=True,
                       env=dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1"))
    except subprocess.TimeoutExpired:
        status = "timeout"
    except subprocess.CalledProcessError as e:
        status = "crash: " + e.stderr.decode(errors="ignore")[-300:]
    res = dict(name=name, task=task, status=status)
    if status == "ok":
        o = json.load(open(outp))
        vals = []
        for i in range(len(pts)):
            chunk = o[per * i:per * i + per]
            bad = [e for e in chunk if "err" in e or isinstance(e.get("v"), str)]
            vals.append((bad[0].get("err") or bad[0]["v"]) if bad else [e["v"] for e in chunk])
        fails = check_american(pts, ref, vals) if task == "american" else check_barrier(pts, ref, vals)
        ms = sorted(e["ms"] for e in o)
        res.update(summarize(fails), ms_median=ms[len(ms) // 2], fails=fails)
    json.dump(res, open(os.path.join(HERE, "results", name + ".json"), "w"))
    return res


def table():
    rows = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(HERE, "results", "*__*.json")))]
    for r in rows:
        if r["status"] != "ok":
            print(f"{r['name']:28s} {r['status'][:60]}"); continue
        print(f"{r['name']:28s} model-free {r['model_free']:4d}  serious {r['serious']:4d}  ref {r['ref']:4d}  ms {r['ms_median']:9.3f}  {r['kinds']}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "controls": controls()
    elif cmd == "extract": extract()
    elif cmd == "table": table()
    elif cmd == "run":
        names = sys.argv[2:] or sorted(os.path.basename(p)[:-3] for p in glob.glob(os.path.join(HERE, "code", "*.py"))
                                       if not os.path.exists(os.path.join(HERE, "results", os.path.basename(p)[:-3] + ".json")))
        for n in names:
            r = run_one(n); print(n, r["status"], {k: r.get(k) for k in ("model_free", "serious", "ref", "ms_median")})
