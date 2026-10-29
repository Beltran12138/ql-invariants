import math
import numpy as np
from scipy.stats import norm


def _bs_european(S, K, T, r, q, sigma, is_call):
    if T <= 0:
        return max(S - K, 0.0) if is_call else max(K - S, 0.0)
    if sigma <= 0:
        F = S * math.exp(-q * T)
        D = K * math.exp(-r * T)
        return max(F - D, 0.0) if is_call else max(D - F, 0.0)
    sq = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / sq
    d2 = d1 - sq
    if is_call:
        return S * math.exp(-q * T) * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1)


def _deterministic_american(S, K, T, r, q, is_call):
    # sigma = 0：标的沿确定路径漂移，在候选时点上取折现内在价值的最大值
    def val(t):
        f = S * math.exp(-q * t)
        k = K * math.exp(-r * t)
        return max(f - k, 0.0) if is_call else max(k - f, 0.0)

    cands = [0.0, T]
    if is_call and q > 0 and r > 0:
        x = q * S / (r * K)
        if x > 0:
            t = math.log(x) / (q - r) if q != r else None
            if t is not None and 0.0 < t < T:
                cands.append(t)
    elif (not is_call) and r > 0 and q > 0:
        x = r * K / (q * S)
        if x > 0 and q != r:
            t = math.log(x) / (q - r)
            if 0.0 < t < T:
                cands.append(t)
    return max(val(t) for t in cands)


def _crr(S, K, T, r, q, sigma, is_call, N):
    dt = T / N
    u = math.exp(sigma * math.sqrt(dt))
    d = 1.0 / u
    p = (math.exp((r - q) * dt) - d) / (u - d)
    p = min(max(p, 0.0), 1.0)
    disc = math.exp(-r * dt)
    pu, pd = disc * p, disc * (1.0 - p)
    sign = 1.0 if is_call else -1.0

    j = np.arange(N + 1)
    St = S * np.exp((2 * j - N) * sigma * math.sqrt(dt))
    Va = np.maximum(sign * (St - K), 0.0)
    Ve = Va.copy()
    for _ in range(N):
        Va = pu * Va[1:] + pd * Va[:-1]
        Ve = pu * Ve[1:] + pd * Ve[:-1]
        St = St[1:] * d
        Va = np.maximum(Va, sign * (St - K))
    return float(Va[0]), float(Ve[0])


def american_price(S, K, T, r, q, sigma, is_call):
    S, K, T, r, q, sigma = map(float, (S, K, T, r, q, sigma))
    is_call = bool(is_call)
    intrinsic = max(S - K, 0.0) if is_call else max(K - S, 0.0)
    if T <= 0:
        return intrinsic
    if sigma < 1e-8:
        return _deterministic_american(S, K, T, r, q, is_call)

    # 保证 CRR 风险中性概率落在 [0, 1] 内所需的最小步数
    b = r - q
    n_min = int(math.ceil(T * b * b / (sigma ** 2))) + 1
    N = min(max(2000, n_min), 20000)

    am, eu = _crr(S, K, T, r, q, sigma, is_call, N)
    # 以欧式期权为控制变量，消除树模型的离散化误差
    price = am - eu + _bs_european(S, K, T, r, q, sigma, is_call)
    return float(max(price, intrinsic, _bs_european(S, K, T, r, q, sigma, is_call)))
