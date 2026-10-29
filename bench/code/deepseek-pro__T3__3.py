import numpy as np
from scipy.special import ndtr, log_ndtr
from math import log, exp, sqrt, inf


def _log_norm_diff(z_u, z_l):
    """log(Phi(z_u) - Phi(z_l)) for z_u > z_l."""
    if z_u == inf:
        return log_ndtr(-z_l)
    if z_l == -inf:
        return log_ndtr(z_u)
    if z_u <= z_l:
        return -inf

    # If both CDFs are close to 1, use the upper tail to avoid cancellation.
    if z_l > 0.0:
        a = -z_u
        b = -z_l
        log_b = log_ndtr(b)
        log_a = log_ndtr(a)
        # Phi(z_u)-Phi(z_l) = Phi(b)-Phi(a), with a < b.
        return log_b + np.log1p(-np.exp(log_a - log_b))

    log_u = log_ndtr(z_u)
    log_l = log_ndtr(z_l)
    return log_u + np.log1p(-np.exp(log_l - log_u))


def _mul_exp_norm_diff(log_coef, z_u, z_l):
    """exp(log_coef) * (Phi(z_u) - Phi(z_l))."""
    if z_u <= z_l:
        return 0.0
    log_delta = _log_norm_diff(z_u, z_l)
    val = log_coef + log_delta
    if val > 709.0:
        return float("inf")
    if val < -745.0:
        return 0.0
    return exp(val)


def _ko_price(S, K, H, T, r, q, sigma, is_call, direction):
    """Knock-out price when barrier is not breached at inception."""
    sqrtT = sqrt(T)
    s = sigma * sqrtT
    mu = r - q - 0.5 * sigma * sigma
    a = log(H / S)
    k = log(K / S)
    lam = (r - q + 0.5 * sigma * sigma) / (sigma * sigma)

    if direction == "down":
        if is_call:
            L = max(a, k)
            U = inf
        else:
            if k <= a:
                return 0.0
            L = a
            U = k
    else:  # up
        if is_call:
            if k >= a:
                return 0.0
            L = k
            U = a
        else:
            L = -inf
            U = min(a, k)

    m0 = mu * T
    m1 = (mu + sigma * sigma) * T
    m_bar = 2.0 * a + mu * T
    m_bar1 = m_bar + sigma * sigma * T

    log_S0 = log(S) - q * T
    log_K0 = log(K) - r * T
    log_S_ref = log_S0 + 2.0 * lam * a
    log_K_ref = log_K0 + (2.0 * lam - 2.0) * a

    S0 = _mul_exp_norm_diff(log_S0, (U - m1) / s, (L - m1) / s)
    K0 = _mul_exp_norm_diff(log_K0, (U - m0) / s, (L - m0) / s)

    S_ref = _mul_exp_norm_diff(log_S_ref, (U - m_bar1) / s, (L - m_bar1) / s)
    K_ref = _mul_exp_norm_diff(log_K_ref, (U - m_bar) / s, (L - m_bar) / s)

    call_integral = (S0 - K0) - (S_ref - K_ref)
    return call_integral if is_call else -call_integral


def barrier_price(S, K, H, T, r, q, sigma, is_call, barrier_type):
    """Price of a continuously monitored European single-barrier option."""
    sqrtT = sqrt(T)
    s = sigma * sqrtT
    d1 = (log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / s
    d2 = d1 - s

    if is_call:
        vanilla = S * exp(-q * T) * ndtr(d1) - K * exp(-r * T) * ndtr(d2)
    else:
        vanilla = K * exp(-r * T) * ndtr(-d2) - S * exp(-q * T) * ndtr(-d1)
    vanilla = max(vanilla, 0.0)

    if barrier_type in ("down-and-out", "down-and-in"):
        direction = "down"
        breached = (S <= H)
    else:
        direction = "up"
        breached = (S >= H)

    if breached:
        if barrier_type.endswith("in"):
            return vanilla
        return 0.0

    ko = _ko_price(S, K, H, T, r, q, sigma, is_call, direction)
    ko = max(ko, 0.0)
    ko = min(ko, vanilla)

    if barrier_type.endswith("in"):
        return max(vanilla - ko, 0.0)
    return ko
