import math
import numpy as np

def _safe_exp(x):
    if x > 709.0:
        return float('inf')
    elif x < -745.0:
        return 0.0
    return math.exp(x)

def _norm_cdf(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))

def _euro_call_unit(x, T, r, q, sigma):
    sqrtT = math.sqrt(T)
    d1 = (math.log(x) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * sqrtT)
    d2 = d1 - sigma * sqrtT
    return x * math.exp(-q * T) * _norm_cdf(d1) - math.exp(-r * T) * _norm_cdf(d2)

def _phi(x, T, gamma, H, I, r, b, sigma):
    sigma2 = sigma * sigma
    sqrtT = math.sqrt(T)
    lam = (-r + gamma * b + 0.5 * gamma * (gamma - 1.0) * sigma2) * T
    kappa = 2.0 * b / sigma2 + (2.0 * gamma - 1.0)

    d1 = (math.log(x / H) + (b + (gamma - 0.5) * sigma2) * T) / (sigma * sqrtT)
    d2 = (math.log(I * I / (x * H)) + (b + (gamma - 0.5) * sigma2) * T) / (sigma * sqrtT)

    n1 = _norm_cdf(d1)
    n2 = _norm_cdf(d2)

    logA = lam + gamma * math.log(x)
    logB = logA + kappa * math.log(I / x)

    A = 0.0 if n1 == 0.0 else _safe_exp(logA) * n1
    B = 0.0 if n2 == 0.0 else _safe_exp(logB) * n2

    return A - B

def _bjerksund_call_unit(x, T, r, q, sigma):
    b = r - q
    sigma2 = sigma * sigma
    sqrtT = math.sqrt(T)

    tmp = b / sigma2 - 0.5
    beta = (0.5 - b / sigma2) + math.sqrt(tmp * tmp + 2.0 * r / sigma2)

    if beta <= 1.0 or beta > 200.0:
        return None

    BInf = 1.0 / (1.0 - 1.0 / beta)

    if q > 0.0:
        B0 = max(1.0, r / q)
    elif q == 0.0 and r < 0.0:
        B0 = 1.0
    else:
        return None

    denom = BInf - B0
    if denom <= 0.0:
        return None

    h = -(b * T + 2.0 * sigma * sqrtT) * (1.0 / denom)
    if h > 0.0:
        return None

    I = B0 + denom * (1.0 - _safe_exp(h))
    if I <= 1.0:
        return None

    alpha = (I - 1.0) * _safe_exp(-beta * math.log(I))

    phi1 = _phi(x, T, beta, I, I, r, b, sigma)
    phi2 = _phi(x, T, 1.0, I, I, r, b, sigma)
    phi3 = _phi(x, T, 1.0, I, 1.0, r, b, sigma)
    phi4 = _phi(x, T, 0.0, I, I, r, b, sigma)
    phi5 = _phi(x, T, 0.0, I, 1.0, r, b, sigma)

    alpha_Sbeta = (I - 1.0) * _safe_exp(beta * math.log(x / I))

    call = alpha_Sbeta - alpha * phi1 + phi2 - phi3 - phi4 + phi5

    if math.isnan(call) or math.isinf(call):
        return None
    if call > x:
        return None

    intrinsic = max(x - 1.0, 0.0)
    if call < intrinsic:
        call = intrinsic

    return call

def _binomial_call_unit(x, T, r, q, sigma):
    N = 300
    dt = T / N
    b = r - q

    nu = sigma * math.sqrt(dt)
    u = math.exp(nu)
    d = 1.0 / u

    e_bdt = math.exp(b * dt)
    denom = u - d

    if denom > 0.0:
        p = (e_bdt - d) / denom
        if p < 0.0 or p > 1.0:
            M = e_bdt
            V = math.exp(2.0 * b * dt) * math.expm1(sigma * sigma * dt)
            sqrtV = math.sqrt(max(V, 0.0))
            u = M + sqrtV
            d = M - sqrtV
            if d <= 0.0:
                u = math.exp(nu)
                d = math.exp(-nu)
            p = 0.5
    else:
        M = e_bdt
        V = math.exp(2.0 * b * dt) * math.expm1(sigma * sigma * dt)
        sqrtV = math.sqrt(max(V, 0.0))
        u = M + sqrtV
        d = M - sqrtV
        if d <= 0.0:
            u = math.exp(nu)
            d = math.exp(-nu)
        p = 0.5

    disc = math.exp(-r * dt)

    log_u = math.log(u)
    log_d = math.log(d)

    j = np.arange(N + 1, dtype=np.float64)
    log_S_arr = math.log(x) + log_d * N + (log_u - log_d) * j
    S_arr = np.exp(log_S_arr)

    values = np.maximum(S_arr - 1.0, 0.0)

    for _ in range(N - 1, -1, -1):
        S_arr = S_arr[:-1] / d
        values = (p * values[1:] + (1.0 - p) * values[:-1]) * disc
        np.maximum(values, S_arr - 1.0, out=values)

    return float(values[0])

def _american_call_unit(x, T, r, q, sigma):
    if T <= 0.0:
        return max(x - 1.0, 0.0)

    if q <= 0.0 and r >= 0.0:
        return _euro_call_unit(x, T, r, q, sigma)

    if q < 0.0 and r < 0.0:
        return _binomial_call_unit(x, T, r, q, sigma)

    call = _bjerksund_call_unit(x, T, r, q, sigma)
    if call is not None:
        return call

    return _binomial_call_unit(x, T, r, q, sigma)

def american_price(S, K, T, r, q, sigma, is_call):
    if T <= 0.0:
        if is_call:
            return max(S - K, 0.0)
        else:
            return max(K - S, 0.0)

    if is_call:
        return K * _american_call_unit(S / K, T, r, q, sigma)
    else:
        return S * _american_call_unit(K / S, T, q, r, sigma)
