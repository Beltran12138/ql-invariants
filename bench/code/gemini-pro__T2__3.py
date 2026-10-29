import numpy as np

def american_price(S, K, T, r, q, sigma, is_call):
    if T <= 0.0:
        return float(max(S - K, 0.0) if is_call else max(K - S, 0.0))
    
    sigma = max(sigma, 1e-8)
    N = 1000
    dt = T / N
    u = np.exp(sigma * np.sqrt(dt))
    d = 1.0 / u
    p = (np.exp((r - q) * dt) - d) / (u - d)
    df = np.exp(-r * dt)
    
    j = np.arange(N + 1)
    ST = S * (d ** (N - j)) * (u ** j)
    
    if is_call:
        V = np.maximum(ST - K, 0.0)
    else:
        V = np.maximum(K - ST, 0.0)
        
    for _ in range(N - 1, -1, -1):
        V = df * (p * V[1:] + (1.0 - p) * V[:-1])
        ST = ST[1:] * d
        if is_call:
            V = np.maximum(V, ST - K)
        else:
            V = np.maximum(V, K - ST)
            
    return float(V[0])
