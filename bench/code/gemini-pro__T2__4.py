import numpy as np

def american_price(S, K, T, r, q, sigma, is_call):
    if T <= 0.0:
        return float(max(S - K, 0.0) if is_call else max(K - S, 0.0))
        
    if sigma <= 1e-8:
        if is_call:
            return float(max(S * np.exp(-q * T) - K * np.exp(-r * T), S - K, 0.0))
        else:
            return float(max(K * np.exp(-r * T) - S * np.exp(-q * T), K - S, 0.0))

    N = 1000
    dt = T / N
    u = np.exp(sigma * np.sqrt(dt))
    d = 1.0 / u
    p = (np.exp((r - q) * dt) - d) / (u - d)
    df = np.exp(-r * dt)

    j = np.arange(N + 1)
    S_t = S * (u ** (2 * j - N))

    if is_call:
        V = np.maximum(S_t - K, 0.0)
    else:
        V = np.maximum(K - S_t, 0.0)

    for i in range(N - 1, -1, -1):
        V = df * (p * V[1:i+2] + (1.0 - p) * V[0:i+1])
        S_t = S * (u ** (2 * np.arange(i + 1) - i))
        if is_call:
            V = np.maximum(V, S_t - K)
        else:
            V = np.maximum(V, K - S_t)

    return float(V[0])
