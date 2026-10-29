import math
from scipy.special import log_ndtr


def barrier_price(S, K, H, T, r, q, sigma, is_call, barrier_type):
    S = float(S); K = float(K); H = float(H); T = float(T)
    r = float(r); q = float(q); sigma = float(sigma)
    bt = barrier_type.strip().lower().replace("_", "-").replace(" ", "-")
    if bt not in ("down-and-out", "down-and-in", "up-and-out", "up-and-in"):
        raise ValueError("invalid barrier_type: %r" % barrier_type)
    is_down = bt.startswith("down")
    is_out = bt.endswith("out")

    phi = 1.0 if is_call else -1.0
    eta = 1.0 if is_down else -1.0

    b = r - q
    sqT = math.sqrt(T)
    sq = sigma * sqT
    lnS = math.log(S)
    lnK = math.log(K)
    lnH = math.log(H)
    lS_disc = lnS - q * T
    lK_disc = lnK - r * T

    # (1 + mu) * sigma * sqrt(T), with mu = (b - sigma^2/2) / sigma^2
    m1 = (b / sigma + 0.5 * sigma) * sqT
    # exponents of (H/S)^(2mu) and (H/S)^(2(mu+1))
    lHS = lnH - lnS
    e_K = 2.0 * (b / (sigma * sigma) - 0.5) * lHS
    e_S = 2.0 * (b / (sigma * sigma) + 0.5) * lHS

    def piece(z, mult, extra_S, extra_K):
        # phi * [S e^{-qT} X_S N(mult*z) - K e^{-rT} X_K N(mult*(z - sq))], in log space
        t1 = math.exp(lS_disc + extra_S + float(log_ndtr(mult * z)))
        t2 = math.exp(lK_disc + extra_K + float(log_ndtr(mult * (z - sq))))
        return phi * (t1 - t2)

    def vanilla():
        x1 = (lnS - lnK) / sq + m1
        return max(piece(x1, phi, 0.0, 0.0), 0.0)

    # Barrier already breached at inception
    breached = (S <= H) if is_down else (S >= H)
    if breached:
        return 0.0 if is_out else vanilla()

    x1 = (lnS - lnK) / sq + m1
    x2 = (lnS - lnH) / sq + m1
    y1 = (2.0 * lnH - lnS - lnK) / sq + m1
    y2 = (lnH - lnS) / sq + m1

    A = lambda: piece(x1, phi, 0.0, 0.0)
    B = lambda: piece(x2, phi, 0.0, 0.0)
    C = lambda: piece(y1, eta, e_S, e_K)
    D = lambda: piece(y2, eta, e_S, e_K)

    K_above = K > H

    if is_call:
        if is_down:
            if is_out:
                price = (A() - C()) if K_above else (B() - D())
            else:
                price = C() if K_above else (A() - B() + D())
        else:
            if is_out:
                price = 0.0 if K_above else (A() - B() + C() - D())
            else:
                price = A() if K_above else (B() - C() + D())
    else:
        if is_down:
            if is_out:
                price = (A() - B() + C() - D()) if K_above else 0.0
            else:
                price = (B() - C() + D()) if K_above else A()
        else:
            if is_out:
                price = (B() - D()) if K_above else (A() - C())
            else:
                price = (A() - B() + D()) if K_above else C()

    v = vanilla()
    if not math.isfinite(price):
        price = 0.0 if is_out else v
    return float(min(max(price, 0.0), v))
