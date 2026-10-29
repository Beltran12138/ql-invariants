import numpy as np
from scipy.special import ndtr


def _bs_price(S, K, T, r, q, sigma, is_call):
    """欧式 Black-Scholes 价格,S 可以是 numpy 数组。"""
    sqrt_T = np.sqrt(T)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    dfq, dfr = np.exp(-q * T), np.exp(-r * T)
    if is_call:
        return S * dfq * ndtr(d1) - K * dfr * ndtr(d2)
    return K * dfr * ndtr(-d2) - S * dfq * ndtr(-d1)


def _peizer_pratt(z, n):
    """Peizer-Pratt 方法 2 反演。"""
    a = (z / (n + 1.0 / 3.0 + 0.1 / (n + 1.0))) ** 2 * (n + 1.0 / 6.0)
    return 0.5 + np.sign(z) * np.sqrt(0.25 - 0.25 * np.exp(-a))


def _tree_price(S, K, T, r, q, sigma, is_call, n):
    """Leisen-Reimer 二叉树 + 最后一步用 BS 解析值替代 (Broadie-Detemple)。"""
    if n % 2 == 0:
        n += 1
    dt = T / n
    sqrt_T = np.sqrt(T)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    growth = np.exp((r - q) * dt)
    p = _peizer_pratt(d2, n)
    pbar = _peizer_pratt(d1, n)
    u = growth * pbar / p
    d = (growth - p * u) / (1.0 - p)
    if not (0.0 < p < 1.0 and u > 0.0 and d > 0.0 and u > d):
        # 极端参数下退化为 CRR
        u = np.exp(sigma * np.sqrt(dt))
        d = 1.0 / u
        p = (growth - d) / (u - d)
    lu, ld = np.log(u), np.log(d)
    disc = np.exp(-r * dt)
    sign = 1.0 if is_call else -1.0

    # 第 n-1 步的节点:继续持有价值用 BS(到期时间 dt) 解析值
    j = np.arange(n)
    nodes = S * np.exp(j * lu + (n - 1 - j) * ld)
    cont = _bs_price(nodes, K, dt, r, q, sigma, is_call)
    V = np.maximum(cont, sign * (nodes - K))

    for i in range(n - 2, -1, -1):
        cont = disc * (p * V[1:] + (1.0 - p) * V[:-1])
        j = np.arange(i + 1)
        nodes = S * np.exp(j * lu + (i - j) * ld)
        V = np.maximum(cont, sign * (nodes - K))
    return float(V[0])


def american_price(S, K, T, r, q, sigma, is_call):
    """连续股息率 q 下的 Black-Scholes 美式期权价格。"""
    S, K, T, r, q, sigma = map(float, (S, K, T, r, q, sigma))
    sign = 1.0 if is_call else -1.0
    intrinsic = max(sign * (S - K), 0.0)

    if T <= 0.0:
        return intrinsic
    if S <= 0.0:
        return max(sign * (0.0 - K), 0.0) if not is_call else 0.0
    if K <= 0.0:
        return intrinsic if not is_call else S

    if sigma <= 1e-10:
        # 确定性路径:在 [0, T] 上取折现内在价值的最大值
        t = np.linspace(0.0, T, 20001)
        vals = sign * (S * np.exp(-q * t) - K * np.exp(-r * t))
        return float(max(vals.max(), 0.0))

    # 无提前行权价值的情形:直接用欧式价格
    if is_call and q <= 0.0 and r >= 0.0:
        return float(_bs_price(S, K, T, r, q, sigma, True))
    if (not is_call) and r <= 0.0 and q <= 0.0:
        return float(_bs_price(S, K, T, r, q, sigma, False))

    # 对 N 与 N+2 的结果做 Richardson 外推以提高精度
    n = 1001
    v1 = _tree_price(S, K, T, r, q, sigma, is_call, n)
    v2 = _tree_price(S, K, T, r, q, sigma, is_call, 2 * n + 1)
    price = 2.0 * v2 - v1 if False else v2  # LR 树本身二阶收敛,直接取更细的网格
    return float(max(price, intrinsic))
