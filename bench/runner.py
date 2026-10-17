"""Evaluate one generated pricer on a list of argument tuples. Runs in the isolated venv.

usage: runner.py <pricer.py> <function name> <inputs.json> <outputs.json>
"""
import importlib.util, json, math, sys, time

spec = importlib.util.spec_from_file_location("pricer", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
f = getattr(mod, sys.argv[2])

out = []
for args in json.load(open(sys.argv[3])):
    t0 = time.perf_counter()
    try:
        v = float(f(*args))
        out.append({"v": v if math.isfinite(v) else repr(v), "ms": 1e3 * (time.perf_counter() - t0)})
    except Exception as e:
        out.append({"err": type(e).__name__ + ": " + str(e)[:80], "ms": 1e3 * (time.perf_counter() - t0)})
json.dump(out, open(sys.argv[4], "w"))
