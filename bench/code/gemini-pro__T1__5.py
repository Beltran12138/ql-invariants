import math
import numpy as np
from scipy.special import ndtr

def american_price(S, K, T, r, q, sigma, is_call):
    N = 400
    dt = T / N
    nu = r - q - 0.5 * sigma**2
    dx = sigma * math.sqrt(dt)

    disc_half = math.exp(-r * dt) * 0.5
    factor = math.exp(-nu * dt + dx)

    k = np.arange(N)
    ST = S * np.exp((N - 1) * nu * dt + (2 * k - (N - 1)) * dx)
    
    d1 = (np.log(ST / K) + (r - q + 0.5 * sigma**2) * dt) / dx
    d2 = d1 - dx
    
    if is_call:
        V = ST * math.exp(-q * dt) * ndtr(d1) - K * math.exp(-r * dt) * ndtr(d2)
        np.maximum(V, ST - K, out=V)
        
        diff = np.empty(N)
        for i in range(N - 1, 0, -1):
            V[:-1] += V[1:]
            V[:-1] *= disc_half
            V = V[:-1]
            
            ST[:-1] *= factor
            ST = ST[:-1]
            
            diff_i = diff[:i]
            np.subtract(ST, K, out=diff_i)
            np.maximum(V, diff_i, out=V)
    else:
        V = K * math.exp(-r * dt) * ndtr(-d2) - ST * math.exp(-q * dt) * ndtr(-d1)
        np.maximum(V, K - ST, out=V)
        
        diff = np.empty(N)
        for i in range(N - 1, 0, -1):
            V[:-1] += V[1:]
            V[:-1] *= disc_half
            V = V[:-1]
            
            ST[:-1] *= factor
            ST = ST[:-1]
            
            diff_i = diff[:i]
            np.subtract(K, ST, out=diff_i)
            np.maximum(V, diff_i, out=V)

    return float(V[0])
