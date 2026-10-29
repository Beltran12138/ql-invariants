import numpy as np
from scipy.stats import norm


def _bs_european(S, K, T, r, q, sigma, is_call):
    sq = sigma * np.sqrt(T)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / sq
    d2 = d1 - sq
    if is_call:
        return S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    return K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1)


def _deterministic(S, K, T, r, q, is_call):
    # sigma -> 0:现货沿 S*exp((r-q)t) 确定性演化,取各可行权时点折现内在价值的最大值
    def val(t):
        fwd = S * np.exp(-q * t)
        disc_k = K * np.exp(-r * t)
        return max(fwd - disc_k, 0.0) if is_call else max(disc_k - fwd, 0.0)

    cands = [0.0, T]
    if q > 0 and r > 0 and S > 0 and K > 0 and q != r:
        tc = np.log(q * S / (r * K)) / (q - r)
        if 0.0 < tc < T:
            cands.append(tc)
    return max(val(t) for t in cands)


def _pp_inversion(z, n):
    # Peizer-Pratt 方法 2 反演
    x = z / (n + 1.0 / 3.0 + 0.1 / (n + 1.0))
    return 0.5 + np.sign(z) * 0.5 * np.sqrt(1.0 - np.exp(-x * x * (n + 1.0 / 6.0)))


def _lr_tree(S, K, T, r, q, sigma, is_call, n):
    if n % 2 == 0:
        n += 1
    dt = T / n
    sq = sigma * np.sqrt(T)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / sq
    d2 = d1 - sq
    p = _pp_inversion(d2, n)
    pbar = _pp_inversion(d1, n)
    growth = np.exp((r - q) * dt)
    u = growth * pbar / p
    d = (growth - p * u) / (1.0 - p)
    disc = np.exp(-r * dt)
    lnu, lnd = np.log(u), np.log(d)
    sign = 1.0 if is_call else -1.0

    j = np.arange(n + 1)
    V = np.maximum(sign * (S * np.exp(j * lnu + (n - j) * lnd) - K), 0.0)
    for i in range(n - 1, -1, -1):
        j = np.arange(i + 1)
        cont = disc * (p * V[1:i + 2] + (1.0 - p) * V[:i + 1])
        ex = sign * (S * np.exp(j * lnu + (i - j) * lnd) - K)
        V = np.maximum(cont, ex)
    return float(V[0])


def american_price(S, K, T, r, q, sigma, is_call):
    S, K, T, r, q, sigma = (float(x) for x in (S, K, T, r, q, sigma))
    is_call = bool(is_call)
    intrinsic = max(S - K, 0.0) if is_call else max(K - S, 0.0)

    if T <= 0.0:
        return intrinsic
    if S <= 0.0:
        return float(K) if not is_call else 0.0
    if K <= 0.0:
        return S if is_call else 0.0
    if sigma * np.sqrt(T) < 1e-8:
        return float(_deterministic(S, K, T, r, q, is_call))

    # 无提前行权价值的情形:欧式即美式
    if (is_call and q <= 0.0) or ((not is_call) and r <= 0.0):
        return float(max(_bs_european(S, K, T, r, q, sigma, is_call), intrinsic))

    # Leisen-Reimer 二叉树,对 n 与 n/2 做 Richardson 外推(二阶收敛)
    n = 1601
    p_fine = _lr_tree(S, K, T, r, q, sigma, is_call, n)
    p_coarse = _lr_tree(S, K, T, r, q, sigma, is_call, n // 2)
    price = (4.0 * p_fine - p_coarse) / 3.0

    euro = _bs_european(S, K, T, r, q, sigma, is_call)
    return float(max(price, euro, intrinsic))
