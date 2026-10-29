import numpy as np
from scipy.stats import norm

def barrier_price(S, K, H, T, r, q, sigma, is_call, barrier_type):
    phi = 1 if is_call else -1
    
    if "down" in barrier_type:
        eta = 1
        is_breached = (S <= H)
    else:
        eta = -1
        is_breached = (S >= H)
        
    is_in = "in" in barrier_type
    
    b = r - q
    sig_sqrt_T = sigma * np.sqrt(T)
    
    d1 = (np.log(S / K) + (b + sigma**2 / 2) * T) / sig_sqrt_T
    d2 = d1 - sig_sqrt_T
    
    vanilla = phi * S * np.exp(-q * T) * norm.cdf(phi * d1) - phi * K * np.exp(-r * T) * norm.cdf(phi * d2)
    
    if is_breached:
        return vanilla if is_in else 0.0

    mu = (b - sigma**2 / 2) / sigma**2
    
    x1 = d1
    x2 = (np.log(S / H) + (b + sigma**2 / 2) * T) / sig_sqrt_T
    y1 = (np.log(H**2 / (S * K)) + (b + sigma**2 / 2) * T) / sig_sqrt_T
    y2 = (np.log(H / S) + (b + sigma**2 / 2) * T) / sig_sqrt_T
    
    A = vanilla
    B = phi * S * np.exp(-q * T) * norm.cdf(phi * x2) - phi * K * np.exp(-r * T) * norm.cdf(phi * (x2 - sig_sqrt_T))
    
    def safe_C_D(power1, power2, Z1, Z2):
        term1 = phi * S * np.exp(-q * T + power1 * np.log(H / S) + norm.logcdf(Z1))
        term2 = -phi * K * np.exp(-r * T + power2 * np.log(H / S) + norm.logcdf(Z2))
        return term1 + term2

    C = safe_C_D(2 * (mu + 1), 2 * mu, eta * y1, eta * (y1 - sig_sqrt_T))
    D = safe_C_D(2 * (mu + 1), 2 * mu, eta * y2, eta * (y2 - sig_sqrt_T))
    
    if is_call:
        if eta == 1:
            in_price = C if K >= H else A - B + D
        else:
            in_price = A if K >= H else B - C + D
    else:
        if eta == 1:
            in_price = B - C + D if K >= H else A
        else:
            in_price = A - B + D if K >= H else C
                
    if is_in:
        return in_price
    else:
        return A - in_price
