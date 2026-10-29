import numpy as np
from scipy.optimize import minimize_scalar

def american_price(S, K, T, r, q, sigma, is_call):
    if T <= 0.0:
        return max(S - K, 0.0) if is_call else max(K - S, 0.0)
    if S <= 0.0:
        return 0.0 if is_call else K
    if K <= 0.0:
        if is_call:
            return S if q >= 0.0 else S * np.exp(-q * T)
        return 0.0

    def det_price():
        def val(t):
            St = S * np.exp((r - q) * t)
            payoff = max(St - K, 0.0) if is_call else max(K - St, 0.0)
            return np.exp(-r * t) * payoff

        times = np.linspace(0.0, T, 1001)
        vals = np.array([val(t) for t in times])
        idx = int(np.argmax(vals))
        lo = times[max(0, idx - 1)]
        hi = times[min(len(times) - 1, idx + 1)]
        res = minimize_scalar(
            lambda t: -val(t),
            bounds=(lo, hi),
            method="bounded",
            options={"xatol": 1e-12},
        )
        return float(max(vals[idx], -res.fun, val(0.0), val(T)))

    if sigma <= 1e-12:
        return det_price()

    sqrtT = np.sqrt(T)
    sig_sqrtT = sigma * sqrtT
    if sig_sqrtT < 1e-12:
        return det_price()

    N = 2001
    dt = T / N

    d1 = (np.log(S) - np.log(K) + (r - q + 0.5 * sigma * sigma) * T) / sig_sqrtT
    d2 = d1 - sig_sqrtT

    n = N
    denom = n + 1.0 / 3.0 + 0.1 / (n + 1.0)
    arg = (d2 / denom) ** 2 * (n + 1.0 / 6.0)
    one_minus_exp = -np.expm1(-arg)
    p = 0.5 + np.sign(d2) * 0.5 * np.sqrt(max(0.0, one_minus_exp))

    def crr_price(Ncrr):
        dt_c = T / Ncrr
        sqrt_dt = np.sqrt(dt_c)
        u = np.exp(sigma * sqrt_dt)
        d = 1.0 / u
        disc = np.exp(-r * dt_c)
        p_c = (np.exp((r - q) * dt_c) - d) / (u - d)
        if p_c <= 0.0 or p_c >= 1.0:
            p_c = min(max(p_c, 1e-15), 1.0 - 1e-15)

        j = np.arange(Ncrr + 1, dtype=float)
        log_asset = np.log(S) + sigma * sqrt_dt * (2.0 * j - Ncrr)
        asset = np.exp(log_asset)

        if is_call:
            values = np.maximum(asset - K, 0.0)
        else:
            values = np.maximum(K - asset, 0.0)

        log_u = sigma * sqrt_dt
        for nn in range(Ncrr - 1, -1, -1):
            cont = disc * (
                p_c * values[1:nn + 2] + (1.0 - p_c) * values[0:nn + 1]
            )
            log_asset = log_asset[:-1] + log_u
            asset = np.exp(log_asset)
            if is_call:
                pay = np.maximum(asset - K, 0.0)
            else:
                pay = np.maximum(K - asset, 0.0)
            values = np.maximum(cont, pay)

        return float(values[0])

    if p <= 1e-14 or p >= 1.0 - 1e-14:
        return crr_price(4000)

    a = np.sqrt(np.expm1(sigma * sigma * dt))
    m = np.exp((r - q) * dt)
    sqrt_p = np.sqrt((1.0 - p) / p)
    sqrt_q = np.sqrt(p / (1.0 - p))

    u = m * (1.0 + a * sqrt_p)
    d = m * (1.0 - a * sqrt_q)

    if (
        not np.isfinite(u)
        or not np.isfinite(d)
        or u <= 0.0
        or d <= 0.0
        or d >= u
        or N * np.log(u) > 700.0
    ):
        return crr_price(4000)

    disc = np.exp(-r * dt)
    log_u = np.log(u)
    log_d = np.log(d)

    j = np.arange(N + 1, dtype=float)
    log_asset = np.log(S) + j * log_u + (N - j) * log_d
    asset = np.exp(log_asset)

    if is_call:
        values = np.maximum(asset - K, 0.0)
    else:
        values = np.maximum(K - asset, 0.0)

    for nn in range(N - 1, -1, -1):
        cont = disc * (
            p * values[1:nn + 2] + (1.0 - p) * values[0:nn + 1]
        )
        log_asset = log_asset[:-1] - log_d
        asset = np.exp(log_asset)
        if is_call:
            pay = np.maximum(asset - K, 0.0)
        else:
            pay = np.maximum(K - asset, 0.0)
        values = np.maximum(cont, pay)

    return float(values[0])
