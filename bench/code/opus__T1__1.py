import math
from scipy.optimize import brentq

_SQRT2 = math.sqrt(2.0)
_INV_SQRT2PI = 1.0 / math.sqrt(2.0 * math.pi)


def _ncdf(x):
    return 0.5 * math.erfc(-x / _SQRT2)


def _npdf(x):
    return _INV_SQRT2PI * math.exp(-0.5 * x * x)


def _euro_put_terms(S, K, T, r, q, sigma, sqT, dfr, dfq):
    """European put price, theta (dP/dt, calendar time) and N(-d+)."""
    vs = sigma * sqT
    dp = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / vs
    dm = dp - vs
    n_mdp = _ncdf(-dp)
    n_mdm = _ncdf(-dm)
    p = K * dfr * n_mdm - S * dfq * n_mdp
    theta = (r * K * dfr * n_mdm - q * S * dfq * n_mdp
             - 0.5 * sigma * S * dfq * _npdf(dp) / sqT)
    return p, theta, n_mdp


def _american_put(S, K, T, r, q, sigma):
    intrinsic = K - S
    sqT = math.sqrt(T)
    dfr = math.exp(-r * T)
    dfq = math.exp(-q * T)
    p_S = _euro_put_terms(S, K, T, r, q, sigma, sqT, dfr, dfq)[0]

    # With r <= 0 a put has no single early-exercise boundary. The double-boundary
    # case (q < r < 0) is only handled by flooring at intrinsic value.
    if r <= 0.0 or r * T < 1e-12:
        return max(p_S, intrinsic)

    # QD+ approximation (Li 2010; as in Andersen-Lake-Offengenden 2016)
    s2 = sigma * sigma
    h = -math.expm1(-r * T)              # 1 - exp(-rT)
    alpha = 2.0 * r / s2
    wm1 = 2.0 * (r - q) / s2 - 1.0       # omega - 1
    sq = math.sqrt(wm1 * wm1 + 4.0 * alpha / h)
    lam = -0.5 * (wm1 + sq)
    lam_p = alpha / (h * h * sq)         # d lambda / dh
    k1 = alpha * dfr / sq                # alpha (1-h) / sq
    k2 = lam_p / sq - 1.0 / h
    k3 = 2.0 / (s2 * sq)

    def smooth_pasting(B):
        p, th, n = _euro_put_terms(B, K, T, r, q, sigma, sqT, dfr, dfq)
        G = K - B - p
        cG = -k1 * k2 * G - k3 * th      # c0 * G, written without dividing by G
        return (1.0 - dfq * n) * B + lam * G + cG

    lo = K * 1e-12
    hi = K
    f_lo = smooth_pasting(lo)
    if f_lo >= 0.0:
        B = lo
    elif smooth_pasting(hi) <= 0.0:
        B = hi
    else:
        B = brentq(smooth_pasting, lo, hi, xtol=1e-12 * K, rtol=1e-12, maxiter=100)

    if S <= B:
        return max(intrinsic, p_S)

    p_B, th_B, _ = _euro_put_terms(B, K, T, r, q, sigma, sqT, dfr, dfq)
    G = K - B - p_B
    if G <= 0.0:
        return max(p_S, intrinsic)

    c = (-k1 * k2 * G - k3 * th_B) / G
    b = -0.5 * k1 * lam_p
    x = math.log(S / B)
    den = 1.0 - b * x * x - c * x
    prem = G * math.exp(lam * x)
    if den > 0.0:
        prem /= den
    return max(p_S + prem, p_S, intrinsic)


def american_price(S, K, T, r, q, sigma, is_call):
    """American option price under Black-Scholes with continuous dividend yield q.

    Uses the QD+ approximation of the early-exercise boundary (Li 2010).
    Calls are priced with the McDonald-Schroder put-call symmetry:
    C(S, K, r, q) = P(K, S, q, r).
    """
    S = float(S); K = float(K); T = float(T)
    r = float(r); q = float(q); sigma = float(sigma)
    if T <= 0.0 or sigma <= 0.0:
        return max(S - K, 0.0) if is_call else max(K - S, 0.0)
    if is_call:
        return _american_put(K, S, T, q, r, sigma)
    return _american_put(S, K, T, r, q, sigma)
