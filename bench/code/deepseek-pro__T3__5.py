import math
from math import log, exp, sqrt
from scipy.stats import norm


def _exp_diff(log_a, log_b):
    """Return exp(log_a) - exp(log_b) robustly."""
    if log_a == -math.inf and log_b == -math.inf:
        return 0.0
    if log_a == -math.inf:
        return -_exp_diff(log_b, log_a)
    if log_b == -math.inf:
        if log_a > 709.0:
            return math.inf
        return math.exp(log_a)

    if log_a >= log_b:
        if log_a > 709.0:
            diff = log_b - log_a
            if diff == 0.0:
                return 0.0
            temp = math.exp(diff)
            if temp == 1.0:
                return 0.0
            log_factor = math.log1p(-temp)
            log_result = log_a + log_factor
            if log_result > 709.0:
                return math.inf
            return math.exp(log_result)
        else:
            return math.exp(log_a) - math.exp(log_b)
    else:
        return -_exp_diff(log_b, log_a)


def _vanilla_price(S, K, T, r, q, sigma, is_call):
    if T <= 0.0:
        if is_call:
            return max(S - K, 0.0)
        return max(K - S, 0.0)

    sqrt_T = sqrt(T)
    d1 = (log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T

    if is_call:
        return S * exp(-q * T) * norm.cdf(d1) - K * exp(-r * T) * norm.cdf(d2)
    return K * exp(-r * T) * norm.cdf(-d2) - S * exp(-q * T) * norm.cdf(-d1)


def _B(phi, S, K, H, T, r, q, sigma):
    sqrt_T = sqrt(T)
    vT = sigma * sqrt_T
    mu = (r - q + 0.5 * sigma * sigma) / (sigma * sigma)

    x = log(S / H) / vT + mu * vT
    return (phi * S * exp(-q * T) * norm.cdf(phi * x)
            - phi * K * exp(-r * T) * norm.cdf(phi * (x - vT)))


def _C(phi, eta, S, K, H, T, r, q, sigma):
    sqrt_T = sqrt(T)
    vT = sigma * sqrt_T
    mu = (r - q + 0.5 * sigma * sigma) / (sigma * sigma)

    y = log(H * H / (S * K)) / vT + mu * vT
    log_base = log(H / S)

    log1 = (log(S) - q * T
            + (2.0 * mu) * log_base
            + norm.logcdf(eta * y))
    log2 = (log(K) - r * T
            + (2.0 * mu - 2.0) * log_base
            + norm.logcdf(eta * (y - vT)))

    return phi * _exp_diff(log1, log2)


def _D(phi, eta, S, K, H, T, r, q, sigma):
    sqrt_T = sqrt(T)
    vT = sigma * sqrt_T
    mu = (r - q + 0.5 * sigma * sigma) / (sigma * sigma)

    y = log(H / S) / vT + mu * vT
    log_base = log(H / S)

    log1 = (log(S) - q * T
            + (2.0 * mu) * log_base
            + norm.logcdf(eta * y))
    log2 = (log(K) - r * T
            + (2.0 * mu - 2.0) * log_base
            + norm.logcdf(eta * (y - vT)))

    return phi * _exp_diff(log1, log2)


def barrier_price(S, K, H, T, r, q, sigma, is_call, barrier_type):
    """
    Price a continuously monitored European single-barrier option
    under Black-Scholes with continuous dividend yield q, no rebate.
    """
    # Already breached at inception
    if barrier_type in ("down-and-out", "down-and-in"):
        if S <= H:
            if barrier_type.endswith("out"):
                return 0.0
            return _vanilla_price(S, K, T, r, q, sigma, is_call)

    if barrier_type in ("up-and-out", "up-and-in"):
        if S >= H:
            if barrier_type.endswith("out"):
                return 0.0
            return _vanilla_price(S, K, T, r, q, sigma, is_call)

    phi = 1.0 if is_call else -1.0

    if barrier_type.startswith("down"):
        eta = 1.0
    else:
        eta = -1.0

    A = _vanilla_price(S, K, T, r, q, sigma, is_call)

    if barrier_type == "down-and-out":
        if is_call:
            if K >= H:
                return A - _C(1.0, eta, S, K, H, T, r, q, sigma)
            return _B(1.0, S, K, H, T, r, q, sigma) - _D(1.0, eta, S, K, H, T, r, q, sigma)
        else:
            if K >= H:
                return (A
                        - _B(-1.0, S, K, H, T, r, q, sigma)
                        + _C(-1.0, eta, S, K, H, T, r, q, sigma)
                        - _D(-1.0, eta, S, K, H, T, r, q, sigma))
            return 0.0

    elif barrier_type == "down-and-in":
        if is_call:
            if K >= H:
                return _C(1.0, eta, S, K, H, T, r, q, sigma)
            return A - _B(1.0, S, K, H, T, r, q, sigma) + _D(1.0, eta, S, K, H, T, r, q, sigma)
        else:
            if K >= H:
                return (_B(-1.0, S, K, H, T, r, q, sigma)
                        - _C(-1.0, eta, S, K, H, T, r, q, sigma)
                        + _D(-1.0, eta, S, K, H, T, r, q, sigma))
            return A

    elif barrier_type == "up-and-out":
        if is_call:
            if K >= H:
                return 0.0
            return (A
                    - _B(1.0, S, K, H, T, r, q, sigma)
                    + _C(1.0, eta, S, K, H, T, r, q, sigma)
                    - _D(1.0, eta, S, K, H, T, r, q, sigma))
        else:
            if K >= H:
                return _B(-1.0, S, K, H, T, r, q, sigma) - _D(-1.0, eta, S, K, H, T, r, q, sigma)
            return A - _C(-1.0, eta, S, K, H, T, r, q, sigma)

    elif barrier_type == "up-and-in":
        if is_call:
            if K >= H:
                return A
            return (_B(1.0, S, K, H, T, r, q, sigma)
                    - _C(1.0, eta, S, K, H, T, r, q, sigma)
                    + _D(1.0, eta, S, K, H, T, r, q, sigma))
        else:
            if K >= H:
                return A - _B(-1.0, S, K, H, T, r, q, sigma) + _D(-1.0, eta, S, K, H, T, r, q, sigma)
            return _C(-1.0, eta, S, K, H, T, r, q, sigma)

    raise ValueError("Unsupported barrier_type")
