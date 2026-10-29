import math
from scipy.stats import norm

def _safe_exp(log_val):
    if log_val < -745.0:
        return 0.0
    if log_val > 709.0:
        return 1.0e308
    return math.exp(log_val)

def _safe_term(sign, log_abs_coeff, z):
    if sign == 0.0:
        return 0.0
    log_val = log_abs_coeff + norm.logcdf(z)
    if log_val < -745.0:
        return 0.0
    if log_val > 709.0:
        return sign * 1.0e308
    return sign * math.exp(log_val)

def _calc_abcd(S, K, H, T, r, q, sigma, phi, eta):
    sqrtT = math.sqrt(T)
    d = sigma * sqrtT
    lam = (r - q + 0.5 * sigma * sigma) / (sigma * sigma)

    x1 = math.log(S / K) / d + lam * d
    x2 = math.log(S / H) / d + lam * d
    y1 = math.log((H * H) / (S * K)) / d + lam * d
    y2 = math.log(H / S) / d + lam * d

    A = (phi * S * math.exp(-q * T) * norm.cdf(phi * x1)
         - phi * K * math.exp(-r * T) * norm.cdf(phi * x1 - phi * d))
    B = (phi * S * math.exp(-q * T) * norm.cdf(phi * x2)
         - phi * K * math.exp(-r * T) * norm.cdf(phi * x2 - phi * d))

    log_HS = math.log(H / S)
    log_abs_S = math.log(S) - q * T + 2.0 * lam * log_HS
    log_abs_K = math.log(K) - r * T + 2.0 * (lam - 1.0) * log_HS

    z_y1 = eta * y1
    z_y1_d = eta * y1 - eta * d
    z_y2 = eta * y2
    z_y2_d = eta * y2 - eta * d

    C = (_safe_term(phi, log_abs_S, z_y1)
         + _safe_term(-phi, log_abs_K, z_y1_d))
    D = (_safe_term(phi, log_abs_S, z_y2)
         + _safe_term(-phi, log_abs_K, z_y2_d))

    return A, B, C, D

def _vanilla_price(S, K, T, r, q, sigma, is_call):
    sqrtT = math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * sqrtT)
    d2 = d1 - sigma * sqrtT
    if is_call:
        return S * math.exp(-q * T) * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    else:
        return K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1)

def barrier_price(S, K, H, T, r, q, sigma, is_call, barrier_type):
    phi = 1.0 if is_call else -1.0
    vanilla = _vanilla_price(S, K, T, r, q, sigma, is_call)

    if barrier_type in ("down-and-out", "down-and-in"):
        if S <= H:
            return 0.0 if barrier_type == "down-and-out" else vanilla
        eta = 1.0
    elif barrier_type in ("up-and-out", "up-and-in"):
        if S >= H:
            return 0.0 if barrier_type == "up-and-out" else vanilla
        eta = -1.0
    else:
        raise ValueError("unknown barrier_type")

    A, B, C, D = _calc_abcd(S, K, H, T, r, q, sigma, phi, eta)

    if eta == 1.0:  # down barrier
        if is_call:
            out = (A - C) if H <= K else (B - D)
        else:
            out = (A - B + C - D) if H <= K else 0.0
    else:  # up barrier
        if is_call:
            out = 0.0 if H <= K else (A - B + C - D)
        else:
            out = (B - D) if H <= K else (A - C)

    if barrier_type in ("down-and-out", "up-and-out"):
        return out
    else:
        return vanilla - out
