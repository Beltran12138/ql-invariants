"""Evaluate one generated pricer on a list of inputs. Runs in the isolated venv.

usage: runner.py <pricer.py> <inputs.json> <outputs.json>
"""
import importlib.util, json, math, sys, time

spec = importlib.util.spec_from_file_location("pricer", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
f = mod.american_price

out = []
for x in json.load(open(sys.argv[2])):
    t0 = time.perf_counter()
    try:
        v = float(f(x["S"], x["K"], x["T"], x["r"], x["q"], x["sigma"], x["is_call"]))
        out.append({"v": v if math.isfinite(v) else repr(v), "ms": 1e3 * (time.perf_counter() - t0)})
    except Exception as e:
        out.append({"err": type(e).__name__ + ": " + str(e)[:80], "ms": 1e3 * (time.perf_counter() - t0)})
json.dump(out, open(sys.argv[3], "w"))
