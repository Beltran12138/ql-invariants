import numpy as np
from math import exp, log, sqrt

def american_price(S, K, T, r, q, sigma, is_call):
    if T <= 0:
        return float(max(S - K, 0.0) if is_call else max(K - S, 0.0))

    if sigma <= 1e-14:
        candidates = [0.0, T]
        if is_call:
            if q > 0.0 and r > 0.0:
                ratio = r * K / (q * S)
                denom = r - q
                if ratio > 0.0 and abs(denom) > 1e-15:
                    tcrit = log(ratio) / denom
                    if 0.0 < tcrit < T:
                        candidates.append(tcrit)
        else:
            if r > 0.0 and q > 0.0:
                ratio = q * S / (r * K)
                denom = q - r
                if ratio > 0.0 and abs(denom) > 1e-15:
                    tcrit = log(ratio) / denom
                    if 0.0 < tcrit < T:
                        candidates.append(tcrit)
        vals = []
        for t in candidates:
            if is_call:
                vals.append(S * exp(-q * t) - K * exp(-r * t))
            else:
                vals.append(K * exp(-r * t) - S * exp(-q * t))
        return float(max(0.0, max(vals)))

    N = 4096
    dt = T / N
    sqrt_dt = sqrt(dt)
    u = exp(sigma * sqrt_dt)
    d = 1.0 / u
    disc = exp(-r * dt)
    p = (exp((r - q) * dt) - d) / (u - d)
    if p <= 0.0:
        p = 1e-15
    elif p >= 1.0:
        p = 1.0 - 1e-15

    j = np.arange(N + 1)
    stock = S * np.exp(sigma * sqrt_dt * (N - 2 * j))

    if is_call:
        values = np.maximum(stock - K, 0.0)
    else:
        values = np.maximum(K - stock, 0.0)

    for i in range(N - 1, -1, -1):
        values = disc * (p * values[:-1] + (1.0 - p) * values[1:])
        stock_i = S * np.exp(sigma * sqrt_dt * (i - 2 * np.arange(i + 1)))
        if is_call:
            values = np.maximum(values, stock_i - K)
        else:
            values = np.maximum(values, K - stock_i)

    return float(values[0])
