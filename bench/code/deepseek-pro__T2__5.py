import numpy as np
from scipy.stats import norm
from scipy.optimize import minimize_scalar


def _european_bs(S, K, T, r, q, sigma, is_call):
    if T <= 0.0:
        return max(S - K, 0.0) if is_call else max(K - S, 0.0)
    if S <= 0.0:
        if is_call:
            return 0.0
        return K * np.exp(-r * T)
    if K <= 0.0:
        if is_call:
            return S * np.exp(-q * T) - K * np.exp(-r * T)
        return 0.0

    sqrtT = sigma * np.sqrt(T)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / sqrtT
    d2 = d1 - sqrtT

    if is_call:
        return S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    return K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1)


def _deterministic_price(S, K, T, r, q, is_call):
    if T <= 0.0:
        return max(S - K, 0.0) if is_call else max(K - S, 0.0)

    if S <= 0.0:
        if is_call:
            return 0.0
        return K if r >= 0.0 else K * np.exp(-r * T)

    def objective(t):
        S_t = S * np.exp((r - q) * t)
        if is_call:
            payoff = max(S_t - K, 0.0)
        else:
            payoff = max(K - S_t, 0.0)
        return -np.exp(-r * t) * payoff

    result = minimize_scalar(objective, bounds=(0.0, T), method='bounded')
    return float(-result.fun)


def american_price(S, K, T, r, q, sigma, is_call):
    S = float(S)
    K = float(K)
    T = float(T)
    r = float(r)
    q = float(q)
    sigma = float(sigma)
    is_call = bool(is_call)

    if T <= 0.0:
        return max(S - K, 0.0) if is_call else max(K - S, 0.0)

    if S <= 0.0:
        if is_call:
            return 0.0
        return K if r >= 0.0 else K * np.exp(-r * T)

    if sigma <= 0.0:
        return _deterministic_price(S, K, T, r, q, is_call)

    # American call without dividends never has early exercise for K >= 0.
    if is_call and q <= 0.0 and K >= 0.0:
        return _european_bs(S, K, T, r, q, sigma, is_call)

    # Jarrow-Rudd binomial tree.
    N = 2000
    s = sigma * np.sqrt(T / N)
    if s >= 2.0:
        N = max(N, int(np.ceil(sigma ** 2 * T / 2.0)) + 1)

    dt = T / N
    s = sigma * np.sqrt(dt)
    nu = (r - q - 0.5 * sigma * sigma) * dt

    u = np.exp(nu + s)
    d = np.exp(nu - s)

    p = (np.exp(0.5 * s * s) - np.exp(-s)) / (np.exp(s) - np.exp(-s))
    p = np.clip(p, 0.0, 1.0)

    disc = np.exp(-r * dt)

    log_u = np.log(u)
    log_ratio = np.log(d) - log_u
    j = np.arange(N + 1)

    log_S_cur = np.log(S) + N * log_u + j * log_ratio
    S_cur = np.exp(log_S_cur)

    if is_call:
        V = np.maximum(S_cur - K, 0.0)
    else:
        V = np.maximum(K - S_cur, 0.0)

    for _ in range(N - 1, -1, -1):
        S_cur = S_cur[:-1] / u

        if is_call:
            intrinsic = np.maximum(S_cur - K, 0.0)
        else:
            intrinsic = np.maximum(K - S_cur, 0.0)

        continuation = disc * (p * V[:-1] + (1.0 - p) * V[1:])
        V = np.maximum(intrinsic, continuation)

    return float(V[0])
