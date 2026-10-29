import math
import numpy as np
from scipy.special import ndtr

_erfc = math.erfc
_SQ2 = math.sqrt(0.5)


def _N(x):
    return 0.5 * _erfc(-x * _SQ2)


def _bs(S, K, T, r, q, sigma, phi):
    # 欧式 Black-Scholes（含连续股息率 q），phi=+1 看涨，-1 看跌
    sd = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / sd
    d2 = d1 - sd
    return phi * (S * math.exp(-q * T) * _N(phi * d1) - K * math.exp(-r * T) * _N(phi * d2))


def _bbs(S, K, T, r, q, sigma, phi, N):
    # Broadie-Detemple 平滑二叉树：p=0.5、漂移校正使均值精确，因此对任意 r、q、sigma 都不会出现概率越界
    dt = T / N
    a = sigma * math.sqrt(dt)
    md = (r - q) * dt - math.log(math.cosh(a))
    idx = np.arange(N + 1)
    pw = np.exp(2.0 * a * idx)
    g = md - a
    bases = (S * np.exp(g * idx)).tolist()
    # 第 N-1 层：用解析 BS 公式平滑 payoff
    n = N - 1
    lnS = math.log(S) + g * n + 2.0 * a * idx[:N]
    d1 = (lnS - math.log(K) + (r - q + 0.5 * sigma * sigma) * dt) / a
    d2 = d1 - a
    Sj = bases[n] * pw[:N]
    cont = phi * (Sj * math.exp(-q * dt) * ndtr(phi * d1) - K * math.exp(-r * dt) * ndtr(phi * d2))
    V = np.maximum(cont, phi * (Sj - K))
    c = 0.5 * math.exp(-r * dt)
    phiK = phi * K
    buf = np.empty(N)
    ex = np.empty(N)
    add, mul, sub, mx = np.add, np.multiply, np.subtract, np.maximum
    for i in range(N - 2, -1, -1):
        m = i + 1
        t = buf[:m]
        e = ex[:m]
        add(V[1:], V[:-1], out=t)
        mul(t, c, out=t)
        mul(pw[:m], phi * bases[i], out=e)
        sub(e, phiK, out=e)
        V = mx(t, e)
    return float(V[0])


def american_price(S, K, T, r, q, sigma, is_call):
    S = float(S); K = float(K); T = float(T); r = float(r); q = float(q); sigma = float(sigma)
    phi = 1.0 if is_call else -1.0
    eu = _bs(S, K, T, r, q, sigma, phi)
    intr = max(phi * (S - K), 0.0)
    # 由 Jensen 不等式：这些条件下提前行权不会更优，美式 = 欧式
    if is_call:
        no_ex = (q <= 0.0 and r >= 0.0)
    else:
        no_ex = (r <= 0.0 and q >= 0.0)
    if no_ex:
        return max(eu, intr)
    # BBSR：2*BBS(N) - BBS(N/2) 外推；高波动长期限时格点更粗，多用几步
    n = 56 if sigma * math.sqrt(T) > 2.0 else 40
    v = 2.0 * _bbs(S, K, T, r, q, sigma, phi, n) - _bbs(S, K, T, r, q, sigma, phi, n // 2)
    return max(v, eu, intr)
