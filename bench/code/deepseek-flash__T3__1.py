import math
import numpy as np
from scipy.special import ndtr, log_ndtr


def _logdiffexp_pos(a, b):
    """log(exp(a) - exp(b)), assuming a >= b."""
    if a == -math.inf:
        return -math.inf
    if b == -math.inf:
        return a
    if b > a:
        return -math.inf
    if b == a:
        return -math.inf
    delta = b - a
    if delta >= 0.0:
        return -math.inf
    return a + math.log(-math.expm1(delta))


def _log_cdf_interval(zlo, zhi):
    """log(Phi(zhi) - Phi(zlo)); None denotes -inf or +inf."""
    if zlo is not None and zhi is not None and zlo >= zhi:
        return -math.inf
    if zlo is None:
        if zhi is None:
            return 0.0
        return float(log_ndtr(zhi))
    if zhi is None:
        return float(log_ndtr(-zlo))

    a = float(log_ndtr(zhi))
    b = float(log_ndtr(zlo))

    if b == -math.inf:
        return a
    if a == -math.inf:
        return -math.inf
    if b >= a:
        return -math.inf

    delta = b - a
    return a + math.log(-math.expm1(delta))


def _log_payoff_integral(L, U, m, s, K, payoff):
    """
    log of integral over (L, U) of payoff(y) * normal_density(y; m, s^2),
    where payoff is either 'call': (e^y - K)^+ or 'put': (K - e^y)^+.
    The limits are chosen so that the payoff is positive throughout.
    """
    if L is not None and U is not None and L >= U:
        return -math.inf

    zlo = None if L is None else (L - m) / s
    zhi = None if U is None else (U - m) / s

    logP = _log_cdf_interval(zlo, zhi)
    if logP == -math.inf:
        return -math.inf

    zlo2 = None if zlo is None else zlo - s
    zhi2 = None if zhi is None else zhi - s

    logP2 = _log_cdf_interval(zlo2, zhi2)
    if logP2 == -math.inf:
        return -math.inf

    logE = m + 0.5 * s * s + logP2
    logKP = math.log(K) + logP

    if payoff == "call":
        return _logdiffexp_pos(logE, logKP)
    else:
        return _logdiffexp_pos(logKP, logE)


def _bs_price(S, K, T, r, q, sigma, is_call):
    if T <= 0.0:
        if is_call:
            return max(S - K, 0.0)
        return max(K - S, 0.0)

    vol = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / vol
    d2 = d1 - vol

    if is_call:
        return S * math.exp(-q * T) * ndtr(d1) - K * math.exp(-r * T) * ndtr(d2)
    else:
        return K * math.exp(-r * T) * ndtr(-d2) - S * math.exp(-q * T) * ndtr(-d1)


def barrier_price(S, K, H, T, r, q, sigma, is_call, barrier_type):
    valid = {
        "down-and-out",
        "down-and-in",
        "up-and-out",
        "up-and-in",
    }
    if barrier_type not in valid:
        raise ValueError("invalid barrier_type")

    is_down = barrier_type.startswith("down")
    is_out = barrier_type.endswith("out")

    breached = (S <= H) if is_down else (S >= H)

    if breached:
        if is_out:
            return 0.0
        return _bs_price(S, K, T, r, q, sigma, is_call)

    if T <= 0.0:
        vanilla = max(S - K, 0.0) if is_call else max(K - S, 0.0)
        return vanilla if is_out else 0.0

    vanilla = _bs_price(S, K, T, r, q, sigma, is_call)

    x = math.log(S)
    b = math.log(H)
    k = math.log(K)

    nu = r - q - 0.5 * sigma * sigma
    s = sigma * math.sqrt(T)

    m1 = x + nu * T
    m2 = 2.0 * b - x + nu * T

    logA = 2.0 * nu * math.log(H / S) / (sigma * sigma)

    out_price = 0.0
    nonzero = True

    if is_down and is_call:
        L = max(b, k)
        U = None
        payoff = "call"
    elif is_down and not is_call:
        if b < k:
            L = b
            U = k
            payoff = "put"
        else:
            nonzero = False
            L = U = None
            payoff = "put"
    elif not is_down and is_call:
        if b > k:
            L = k
            U = b
            payoff = "call"
        else:
            nonzero = False
            L = U = None
            payoff = "call"
    else:
        L = None
        U = min(b, k)
        payoff = "put"

    if nonzero:
        logI1 = _log_payoff_integral(L, U, m1, s, K, payoff)

        if logI1 != -math.inf:
            logI2 = _log_payoff_integral(L, U, m2, s, K, payoff)

            if logI2 == -math.inf:
                logTerm2 = -math.inf
            else:
                logTerm2 = logA + logI2

            logOutIntegral = _logdiffexp_pos(logI1, logTerm2)

            if logOutIntegral != -math.inf:
                logOutPrice = -r * T + logOutIntegral
                if logOutPrice > 709.0:
                    out_price = float("inf")
                else:
                    out_price = math.exp(logOutPrice)

    if is_out:
        return out_price

    price = vanilla - out_price
    if price < 0.0 and price > -1e-10 * max(1.0, abs(vanilla)):
        price = 0.0
    return price
