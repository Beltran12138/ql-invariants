import math
import numpy as np

def american_price(S, K, T, r, q, sigma, is_call):
    N = 100
    dt = T / N
    
    drift = (r - q - 0.5 * sigma**2) * dt
    vdt = sigma * math.sqrt(dt)
    u = math.exp(drift + vdt)
    d = math.exp(drift - vdt)
    inv_d = 1.0 / d
    p_df = 0.5 * math.exp(-r * dt)
    
    idx = np.arange(N + 1)
    ratio = u * inv_d
    S_t = (S * (d ** N)) * (ratio ** idx)
    
    if is_call:
        V = np.maximum(0.0, S_t - K)
        V_eur = V.copy()
        for _ in range(N):
            V = V[1:] + V[:-1]
            V *= p_df
            V_eur = V_eur[1:] + V_eur[:-1]
            V_eur *= p_df
            S_t = S_t[:-1] * inv_d
            np.maximum(V, S_t - K, out=V)
    else:
        V = np.maximum(0.0, K - S_t)
        V_eur = V.copy()
        for _ in range(N):
            V = V[1:] + V[:-1]
            V *= p_df
            V_eur = V_eur[1:] + V_eur[:-1]
            V_eur *= p_df
            S_t = S_t[:-1] * inv_d
            np.maximum(V, K - S_t, out=V)
            
    sqT = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / sqT
    d2 = d1 - sqT
    
    inv_sqrt2 = 0.7071067811865476
    
    if is_call:
        nd1 = 0.5 * (1.0 + math.erf(d1 * inv_sqrt2))
        nd2 = 0.5 * (1.0 + math.erf(d2 * inv_sqrt2))
        bs_eur = S * math.exp(-q * T) * nd1 - K * math.exp(-r * T) * nd2
    else:
        nd1 = 0.5 * (1.0 + math.erf(-d1 * inv_sqrt2))
        nd2 = 0.5 * (1.0 + math.erf(-d2 * inv_sqrt2))
        bs_eur = K * math.exp(-r * T) * nd2 - S * math.exp(-q * T) * nd1
        
    return bs_eur + float(V[0] - V_eur[0])
