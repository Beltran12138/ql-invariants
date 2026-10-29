import math
import numpy as np
from scipy.special import log_ndtr


def barrier_price(S, K, H, T, r, q, sigma, is_call, barrier_type):
    S = float(S); K = float(K); H = float(H); T = float(T)
    r = float(r); q = float(q); sigma = float(sigma)
    if barrier_type not in ("down-and-out", "down-and-in", "up-and-out", "up-and-in"):
        raise ValueError("invalid barrier_type: %r" % (barrier_type,))

    is_down = barrier_type.startswith("down")
    is_in = barrier_type.endswith("-in")
    phi = 1.0 if is_call else -1.0
    eta = 1.0 if is_down else -1.0

    b = r - q
    st = sigma * math.sqrt(T)
    lnS = math.log(S)
    lnK = math.log(K)
    lnHS = math.log(H / S)
    mu = (b - 0.5 * sigma * sigma) / (sigma * sigma)
    c = (1.0 + mu) * st

    # 所有项在对数空间计算, 避免 (H/S)^(2*mu) 溢出 / 下溢
    def term(sign, log_mag):
        return sign * math.exp(log_mag)

    def vanilla_term(x):
        t1 = term(phi, lnS + (b - r) * T + float(log_ndtr(phi * x)))
        t2 = term(phi, lnK - r * T + float(log_ndtr(phi * x - phi * st)))
        return t1 - t2

    def reflected_term(y):
        t1 = term(phi, lnS + (b - r) * T + 2.0 * (mu + 1.0) * lnHS
                  + float(log_ndtr(eta * y)))
        t2 = term(phi, lnK - r * T + 2.0 * mu * lnHS
                  + float(log_ndtr(eta * y - eta * st)))
        return t1 - t2

    def vanilla():
        x1 = (lnS - lnK) / st + c
        return vanilla_term(x1)

    breached = (S <= H) if is_down else (S >= H)
    if breached:
        return 0.0 if not is_in else max(0.0, vanilla())

    x1 = (lnS - lnK) / st + c
    x2 = (lnS - math.log(H)) / st + c
    y1 = (2.0 * math.log(H) - lnS - lnK) / st + c
    y2 = lnHS / st + c

    A = vanilla_term(x1)
    B = vanilla_term(x2)
    C = reflected_term(y1)
    D = reflected_term(y2)

    K_above = K > H
    if is_call:
        if is_down:
            knock_in = C if K_above else A - B + D
        else:
            knock_in = A if K_above else B - C + D
    else:
        if is_down:
            knock_in = B - C + D if K_above else A
        else:
            knock_in = A - B + D if K_above else C

    van = A
    if is_in:
        price = knock_in
        price = min(max(price, 0.0), max(van, 0.0))
    else:
        price = van - knock_in
        price = min(max(price, 0.0), max(van, 0.0))
    return float(price)
