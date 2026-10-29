import math
import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq


def _intrinsic(S, K, is_call):
    return max(0.0, S - K if is_call else K - S)


def _bs_european(S, K, T, r, q, sigma, is_call):
    if T <= 0.0:
        return _intrinsic(S, K, is_call)

    sqrt_T = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / sqrt_T
    d2 = d1 - sqrt_T

    if is_call:
        return S * math.exp(-q * T) * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1)


def _deterministic_price(S, K, T, r, q, sigma, is_call):
    """Price when sigma == 0."""
    if T <= 0.0:
        return _intrinsic(S, K, is_call)

    f0 = S - K if is_call else K - S
    fT = (S * math.exp(-q * T) - K * math.exp(-r * T)) if is_call else (K * math.exp(-r * T) - S * math.exp(-q * T))
    vals = [0.0, f0, fT]

    if abs(r - q) > 1e-14:
        if is_call:
            if q != 0.0 and r != 0.0:
                z = (r * K) / (q * S)
                if z > 0.0:
                    tau = math.log(z) / (r - q)
                    if 0.0 < tau < T:
                        vals.append(S * math.exp(-q * tau) - K * math.exp(-r * tau))
        else:
            if q != 0.0 and r != 0.0:
                z = (q * S) / (r * K)
                if z > 0.0:
                    tau = math.log(z) / (r - q)
                    if 0.0 < tau < T:
                        vals.append(K * math.exp(-r * tau) - S * math.exp(-q * tau))

    return max(vals)


def _binomial_american(S, K, T, r, q, sigma, is_call, N=1000):
    """Fallback binomial tree with equal risk-neutral probabilities."""
    if T <= 0.0:
        return _intrinsic(S, K, is_call)

    dt = T / N
    nu = (r - q - 0.5 * sigma * sigma) * dt
    sqrt_dt = sigma * math.sqrt(dt)
    u = math.exp(nu + sqrt_dt)
    d = math.exp(nu - sqrt_dt)
    disc = math.exp(-r * dt)

    log_u = math.log(u)
    log_d = math.log(d)
    log_S = math.log(S)

    j = np.arange(N + 1, dtype=float)
    log_S_T = log_S + j * log_u + (N - j) * log_d
    S_T = np.exp(log_S_T)

    if is_call:
        V = np.maximum(0.0, S_T - K)
    else:
        V = np.maximum(0.0, K - S_T)

    for i in range(N - 1, -1, -1):
        V = disc * 0.5 * (V[1:] + V[:-1])

        j = np.arange(i + 1, dtype=float)
        S_i = np.exp(log_S + j * log_u + (i - j) * log_d)

        if is_call:
            V = np.maximum(V, S_i - K)
        else:
            V = np.maximum(V, K - S_i)

    return float(V[0])


def _find_root(F, x_start, decreasing):
    a = x_start
    b = x_start
    fa = F(a)
    fb = F(b)

    for _ in range(300):
        if abs(fa) < 1e-12:
            return a
        if abs(fb) < 1e-12:
            return b

        if not decreasing:
            if fa < 0.0 and fb > 0.0:
                return brentq(F, a, b, xtol=1e-10, maxiter=200)
            if fa >= 0.0:
                a *= 0.5
                fa = F(a)
                if a <= 1e-15:
                    break
            if fb <= 0.0:
                b *= 2.0
                fb = F(b)
                if b >= 1e15:
                    break
        else:
            if fa > 0.0 and fb < 0.0:
                return brentq(F, a, b, xtol=1e-10, maxiter=200)
            if fa <= 0.0:
                a *= 0.5
                fa = F(a)
                if a <= 1e-15:
                    break
            if fb >= 0.0:
                b *= 2.0
                fb = F(b)
                if b >= 1e15:
                    break

    raise ValueError("root not found")


def _baw_call(S, K, T, r, q, sigma):
    b = r - q
    M = 2.0 * r / (sigma * sigma)
    N = 2.0 * b / (sigma * sigma)

    if abs(r) < 1e-14:
        G = 2.0 / (sigma * sigma * T)
    else:
        H = 1.0 - math.exp(-r * T)
        if abs(H) < 1e-14:
            G = 2.0 / (sigma * sigma * T)
        else:
            G = (2.0 * r / (sigma * sigma)) / H

    q2 = 0.5 * (-(N - 1.0) + math.sqrt((N - 1.0) ** 2 + 4.0 * G))
    if q2 <= 1e-12:
        raise ValueError("invalid q2")

    sqrt_T = sigma * math.sqrt(T)

    def F_call(Sv):
        if Sv <= 0.0:
            return -K
        d1 = (math.log(Sv / K) + (b + 0.5 * sigma * sigma) * T) / sqrt_T
        d2 = d1 - sqrt_T
        c = Sv * math.exp(-q * T) * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
        premium = (Sv / q2) * (1.0 - math.exp(-q * T) * norm.cdf(d1))
        return Sv - K - c - premium

    S_star = _find_root(F_call, K, decreasing=False)

    d1 = (math.log(S_star / K) + (b + 0.5 * sigma * sigma) * T) / sqrt_T
    A2 = (S_star / q2) * (1.0 - math.exp(-q * T) * norm.cdf(d1))

    if S >= S_star:
        return S - K

    c = _bs_european(S, K, T, r, q, sigma, True)
    return c + A2 * (S / S_star) ** q2


def _baw_put(S, K, T, r, q, sigma):
    b = r - q
    M = 2.0 * r / (sigma * sigma)
    N = 2.0 * b / (sigma * sigma)

    if abs(r) < 1e-14:
        G = 2.0 / (sigma * sigma * T)
    else:
        H = 1.0 - math.exp(-r * T)
        if abs(H) < 1e-14:
            G = 2.0 / (sigma * sigma * T)
        else:
            G = (2.0 * r / (sigma * sigma)) / H

    q1 = 0.5 * (-(N - 1.0) - math.sqrt((N - 1.0) ** 2 + 4.0 * G))
    if q1 >= -1e-12:
        raise ValueError("invalid q1")

    sqrt_T = sigma * math.sqrt(T)

    def F_put(Sv):
        if Sv <= 0.0:
            return K - K * math.exp(-r * T)
        d1 = (math.log(Sv / K) + (b + 0.5 * sigma * sigma) * T) / sqrt_T
        d2 = d1 - sqrt_T
        p = K * math.exp(-r * T) * norm.cdf(-d2) - Sv * math.exp(-q * T) * norm.cdf(-d1)
        premium = (Sv / q1) * (1.0 - math.exp(-q * T) * norm.cdf(-d1))
        return K - Sv - p + premium

    S_star = _find_root(F_put, K, decreasing=True)

    d1 = (math.log(S_star / K) + (b + 0.5 * sigma * sigma) * T) / sqrt_T
    A1 = -(S_star / q1) * (1.0 - math.exp(-q * T) * norm.cdf(-d1))

    if S <= S_star:
        return K - S

    p = _bs_european(S, K, T, r, q, sigma, False)
    return p + A1 * (S / S_star) ** q1


def american_price(S, K, T, r, q, sigma, is_call):
    if T <= 0.0 or S <= 0.0 or K <= 0.0:
        return _intrinsic(S, K, is_call)

    if sigma <= 0.0:
        return _deterministic_price(S, K, T, r, q, sigma, is_call)

    try:
        if is_call:
            if q <= 0.0:
                return _bs_european(S, K, T, r, q, sigma, True)
            price = _baw_call(S, K, T, r, q, sigma)
        else:
            if r <= 0.0 and q >= 0.0:
                return _bs_european(S, K, T, r, q, sigma, False)
            price = _baw_put(S, K, T, r, q, sigma)

        if not math.isfinite(price):
            raise ValueError("non-finite price")

        euro = _bs_european(S, K, T, r, q, sigma, is_call)
        return max(price, euro, _intrinsic(S, K, is_call))

    except Exception:
        return _binomial_american(S, K, T, r, q, sigma, is_call)
