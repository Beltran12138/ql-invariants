import math
import numpy as np
from scipy.stats import norm


def _bs_european(S, K, T, r, q, sigma, is_call):
    sq = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / sq
    d2 = d1 - sq
    dq, dr = math.exp(-q * T), math.exp(-r * T)
    if is_call:
        return S * dq * norm.cdf(d1) - K * dr * norm.cdf(d2)
    return K * dr * norm.cdf(-d2) - S * dq * norm.cdf(-d1)


def _pp_inversion(z, n):
    # Peizer-Pratt method 2 inversion (Leisen-Reimer)
    a = z / (n + 1.0 / 3.0 + 0.1 / (n + 1.0))
    val = 0.5 + math.copysign(0.5, z) * math.sqrt(max(0.0, 1.0 - math.exp(-a * a * (n + 1.0 / 6.0))))
    return min(max(val, 1e-12), 1.0 - 1e-12)


def _deterministic(S, K, T, r, q, is_call):
    # sigma == 0: choose the best exercise time on the deterministic path
    def val(t):
        f = S * math.exp((r - q) * t)
        pay = (f - K) if is_call else (K - f)
        return math.exp(-r * t) * max(pay, 0.0)

    cands = list(np.linspace(0.0, T, 4001))
    if r != q and q != 0 and r != 0:
        x = (r * K) / (q * S)
        if x > 0:
            t_star = math.log(x) / (r - q)
            if 0.0 <= t_star <= T:
                cands.append(t_star)
    return max(val(t) for t in cands)


def american_price(S, K, T, r, q, sigma, is_call):
    S, K, T, r, q, sigma = float(S), float(K), float(T), float(r), float(q), float(sigma)
    intrinsic = max(S - K, 0.0) if is_call else max(K - S, 0.0)

    if T <= 0.0:
        return intrinsic
    if S <= 0.0 or K <= 0.0:
        if is_call:
            return max(intrinsic, S * math.exp(-q * T) - K * math.exp(-r * T), 0.0)
        return max(intrinsic, K * math.exp(-r * T) - S * math.exp(-q * T), 0.0)
    if sigma <= 0.0:
        return _deterministic(S, K, T, r, q, is_call)

    euro = _bs_european(S, K, T, r, q, sigma, is_call)

    # Cases where early exercise is never optimal
    if is_call and q <= 0.0 and r >= q:
        return max(euro, intrinsic)
    if (not is_call) and r <= 0.0 and q >= r:
        return max(euro, intrinsic)

    # Leisen-Reimer binomial tree with European control variate
    n = 2001  # odd number of steps
    dt = T / n
    sq = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / sq
    d2 = d1 - sq
    p = _pp_inversion(d2, n)
    pp = _pp_inversion(d1, n)
    growth = math.exp((r - q) * dt)
    u = growth * pp / p
    d = (growth - p * u) / (1.0 - p)
    disc = math.exp(-r * dt)
    lu, ld = math.log(u), math.log(d)
    lS = math.log(S)
    sign = 1.0 if is_call else -1.0

    j = np.arange(n + 1)
    ST = np.exp(lS + j * lu + (n - j) * ld)
    payoff = np.maximum(sign * (ST - K), 0.0)
    am = payoff.copy()
    eu = payoff.copy()
    pu, pd = disc * p, disc * (1.0 - p)

    for i in range(n - 1, -1, -1):
        ji = j[: i + 1]
        Si = np.exp(lS + ji * lu + (i - ji) * ld)
        am = np.maximum(pu * am[1:] + pd * am[:-1], sign * (Si - K))
        eu = pu * eu[1:] + pd * eu[:-1]

    price = am[0] - eu[0] + euro
    return float(max(price, intrinsic, euro))
