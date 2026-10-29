import math
import numpy as np
from scipy.stats import norm


def _bs_european(S, K, T, r, q, sigma, is_call):
    S = np.asarray(S, dtype=float)
    sqT = sigma * math.sqrt(T)
    with np.errstate(divide="ignore", invalid="ignore"):
        d1 = (np.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / sqT
    d2 = d1 - sqT
    dfq = math.exp(-q * T)
    dfr = math.exp(-r * T)
    if is_call:
        return S * dfq * norm.cdf(d1) - K * dfr * norm.cdf(d2)
    return K * dfr * norm.cdf(-d2) - S * dfq * norm.cdf(-d1)


def _payoff(St, K, is_call):
    return np.maximum(St - K, 0.0) if is_call else np.maximum(K - St, 0.0)


def _bbs_tree(S, K, T, r, q, sigma, is_call, N):
    # Drift-centred binomial tree with Black-Scholes smoothing at the last step
    dt = T / N
    disc = math.exp(-r * dt)
    nu = r - q - 0.5 * sigma * sigma
    sq = sigma * math.sqrt(dt)
    u = math.exp(nu * dt + sq)
    d = math.exp(nu * dt - sq)
    p = (math.exp((r - q) * dt) - d) / (u - d)
    p = min(max(p, 0.0), 1.0)

    i = N - 1
    j = np.arange(N)
    St = S * np.exp(i * nu * dt + (2 * j - i) * sq)
    V = np.maximum(_bs_european(St, K, dt, r, q, sigma, is_call), _payoff(St, K, is_call))

    for i in range(N - 2, -1, -1):
        V = disc * (p * V[1:] + (1.0 - p) * V[:-1])
        j = np.arange(i + 1)
        St = S * np.exp(i * nu * dt + (2 * j - i) * sq)
        np.maximum(V, _payoff(St, K, is_call), out=V)
    return float(V[0])


def american_price(S, K, T, r, q, sigma, is_call):
    S, K, T, r, q, sigma = map(float, (S, K, T, r, q, sigma))
    is_call = bool(is_call)

    intrinsic = max(S - K, 0.0) if is_call else max(K - S, 0.0)
    if T <= 0.0:
        return intrinsic
    if S <= 0.0:
        return 0.0 if is_call else K
    if K <= 0.0:
        return S if is_call else 0.0  # call: exercise immediately is optimal

    # Deterministic case: optimise the exercise time along the forward path
    if sigma <= 0.0:
        t = np.linspace(0.0, T, 20001)
        St = S * np.exp((r - q) * t)
        vals = np.exp(-r * t) * _payoff(St, K, is_call)
        return float(max(vals.max(), intrinsic))

    # Early exercise is never optimal in these cases: European price is exact
    if is_call and q <= 0.0:
        return float(max(_bs_european(S, K, T, r, q, sigma, True), intrinsic))
    if (not is_call) and r <= 0.0:
        return float(max(_bs_european(S, K, T, r, q, sigma, False), intrinsic))

    # Binomial Black-Scholes with Richardson extrapolation
    N = 800
    v1 = _bbs_tree(S, K, T, r, q, sigma, is_call, N)
    v2 = _bbs_tree(S, K, T, r, q, sigma, is_call, 2 * N)
    price = 2.0 * v2 - v1

    euro = float(_bs_european(S, K, T, r, q, sigma, is_call))
    return float(max(price, euro, intrinsic))
