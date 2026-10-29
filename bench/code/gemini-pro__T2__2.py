import numpy as np

def american_price(S, K, T, r, q, sigma, is_call, N=1000):
    if T <= 0:
        return float(max(S - K, 0.0) if is_call else max(K - S, 0.0))
    
    sigma = max(sigma, 1e-8)
    dt = T / N
    u = np.exp(sigma * np.sqrt(dt))
    d = 1.0 / u
    p = (np.exp((r - q) * dt) - d) / (u - d)
    discount = np.exp(-r * dt)
    
    i = np.arange(N + 1)
    S_t = S * (u ** (N - i)) * (d ** i)
    
    if is_call:
        V = np.maximum(S_t - K, 0.0)
    else:
        V = np.maximum(K - S_t, 0.0)
        
    for _ in range(N):
        S_t = S_t[:-1] * d
        V = discount * (p * V[:-1] + (1 - p) * V[1:])
        if is_call:
            V = np.maximum(V, S_t - K)
        else:
            V = np.maximum(V, K - S_t)
            
    return float(V[0])
