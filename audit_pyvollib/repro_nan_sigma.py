"""Minimal repro: NaN / negative volatility or NaN time silently priced as the zero-vol (forward-intrinsic) value."""
import warnings; warnings.filterwarnings("ignore")
import math
from vollib.black_scholes_merton import black_scholes_merton as bsm
from vollib.black import black
nan = float("nan")
S, K, t, r, q = 100.0, 90.0, 1.0, 0.01, 0.0
zero_vol = math.exp(-r*t) * max(S*math.exp((r-q)*t) - K, 0)
print("discounted forward intrinsic (sigma=0 value):", zero_vol)
print("bsm sigma=0     :", float(bsm('c', S, K, t, r, 0.0, q)))
print("bsm sigma=nan   :", float(bsm('c', S, K, t, r, nan, q)))
print("bsm sigma=-0.2  :", float(bsm('c', S, K, t, r, -0.2, q)))
print("bsm t=nan       :", float(bsm('c', S, K, nan, r, 0.2, q)))
print("bsm sigma=+0.2  :", float(bsm('c', S, K, t, r, 0.2, q)))
print("black F=100 K=100 sigma=nan:", float(black('c', 100.0, 100.0, 1.0, 0.01, nan)))
print("bsm K=nan       :", float(bsm('c', S, nan, t, r, 0.2, q)))
