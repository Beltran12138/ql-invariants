import numpy as np

def american_price(S, K, T, r, q, sigma, is_call):
    if T <= 0.0:
        return max(0.0, S - K if is_call else K - S)
    if S <= 0.0:
        return 0.0 if is_call else K
    if K <= 0.0:
        return S if is_call else 0.0

    if sigma <= 0.0:
        ts = np.linspace(0.0, T, 20000)
        stock = S * np.exp((r - q) * ts)
        if is_call:
            vals = np.maximum(stock - K, 0.0) * np.exp(-r * ts)
        else:
            vals = np.maximum(K - stock, 0.0) * np.exp(-r * ts)
        return float(np.max(vals))

    N = max(2000, int(np.ceil(sigma * sigma * T / 4.0)) + 1)
    dt = T / N
    s = sigma * np.sqrt(dt)
    m = (r - q - 0.5 * sigma * sigma) * dt

    u = np.exp(m + s)
    d = np.exp(m - s)

    p = (np.exp((r - q) * dt) - d) / (u - d)
    p = np.clip(p, 0.0, 1.0)

    disc = np.exp(-r * dt)
    omega = 1.0 if is_call else -1.0

    upow = u ** np.arange(N + 1)
    dpow = d ** np.arange(N + 1)

    S_arr = S * upow * dpow[::-1]
    V = np.maximum(omega * (S_arr - K), 0.0)

    for _ in range(N):
        S_arr = S_arr[:-1] / d
        intrinsic = np.maximum(omega * (S_arr - K), 0.0)
        continuation = disc * (p * V[1:] + (1.0 - p) * V[:-1])
        V = np.maximum(intrinsic, continuation)

    return float(V[0])
