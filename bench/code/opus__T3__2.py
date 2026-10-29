import math
from scipy.special import log_ndtr


def barrier_price(S, K, H, T, r, q, sigma, is_call, barrier_type):
    S = float(S); K = float(K); H = float(H); T = float(T)
    r = float(r); q = float(q); sigma = float(sigma)

    bt = str(barrier_type).strip().lower().replace("_", "-").replace(" ", "-")
    if bt not in ("down-and-out", "down-and-in", "up-and-out", "up-and-in"):
        raise ValueError("invalid barrier_type: %r" % (barrier_type,))
    down = bt.startswith("down")
    knock_in = bt.endswith("in")
    phi = 1.0 if is_call else -1.0
    eta = 1.0 if down else -1.0

    def safe_exp(x):
        return math.exp(min(x, 709.0))

    lnS_disc = math.log(S) - q * T
    lnK_disc = math.log(K) - r * T

    # Degenerate maturity
    if T <= 0.0 or sigma <= 0.0:
        if T <= 0.0:
            vanilla = max(phi * (S - K), 0.0)
        else:
            fwd = safe_exp(lnS_disc)
            vanilla = max(phi * (fwd - safe_exp(lnK_disc)), 0.0)
        breached = (S <= H) if down else (S >= H)
        if breached:
            return vanilla if knock_in else 0.0
        return 0.0 if knock_in else vanilla

    sT = sigma * math.sqrt(T)

    def AB(x):
        return phi * (safe_exp(lnS_disc + log_ndtr(phi * x))
                      - safe_exp(lnK_disc + log_ndtr(phi * (x - sT))))

    x1 = math.log(S / K) / sT + (1.0 + ((r - q) / sigma ** 2 - 0.5)) * sT
    A = AB(x1)
    vanilla = max(A, 0.0)

    # Barrier already breached at inception
    breached = (S <= H) if down else (S >= H)
    if breached:
        return vanilla if knock_in else 0.0

    mu = (r - q) / sigma ** 2 - 0.5
    m = (1.0 + mu) * sT
    h = math.log(H / S)
    lnSK = math.log(S / K)

    x2 = -h / sT + m
    y1 = (2.0 * h + lnSK) / sT + m
    y2 = h / sT + m

    def CD(y):
        t1 = safe_exp(lnS_disc + 2.0 * (mu + 1.0) * h + log_ndtr(eta * y))
        t2 = safe_exp(lnK_disc + 2.0 * mu * h + log_ndtr(eta * (y - sT)))
        return phi * (t1 - t2)

    B = AB(x2)
    C = CD(y1)
    D = CD(y2)

    k_above = K >= H
    if is_call and down:
        if k_above:
            out_v, in_v = A - C, C
        else:
            out_v, in_v = B - D, A - B + D
    elif is_call and not down:
        if k_above:
            out_v, in_v = 0.0, A
        else:
            out_v, in_v = A - B + C - D, B - C + D
    elif (not is_call) and down:
        if k_above:
            out_v, in_v = A - B + C - D, B - C + D
        else:
            out_v, in_v = 0.0, A
    else:  # up put
        if k_above:
            out_v, in_v = B - D, A - B + D
        else:
            out_v, in_v = A - C, C

    in_c = min(max(in_v, 0.0), vanilla)
    out_c = min(max(out_v, 0.0), vanilla)

    # Use the smaller (more accurately computed) leg directly and enforce
    # in/out parity exactly for the other one.
    if knock_in:
        return in_c if in_c <= out_c else max(vanilla - out_c, 0.0)
    else:
        return out_c if out_c <= in_c else max(vanilla - in_c, 0.0)
