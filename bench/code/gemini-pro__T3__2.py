import numpy as np
from scipy.stats import norm

def barrier_price(S, K, H, T, r, q, sigma, is_call, barrier_type):
    is_down = "down" in barrier_type
    is_in = "in" in barrier_type
    phi = 1 if is_call else -1
    eta = 1 if is_down else -1
    
    sigma_sqT = sigma * np.sqrt(T)
    mu = (r - q - 0.5 * sigma**2) / (sigma**2)
    
    x1 = (np.log(S / K) / sigma_sqT) + (1 + mu) * sigma_sqT
    
    def get_A():
        return phi * S * np.exp(-q * T) * norm.cdf(phi * x1) - phi * K * np.exp(-r * T) * norm.cdf(phi * (x1 - sigma_sqT))
        
    if is_down and S <= H:
        return get_A() if is_in else 0.0
    if not is_down and S >= H:
        return get_A() if is_in else 0.0
        
    x2 = (np.log(S / H) / sigma_sqT) + (1 + mu) * sigma_sqT
    y1 = (np.log(H**2 / (S * K)) / sigma_sqT) + (1 + mu) * sigma_sqT
    y2 = (np.log(H / S) / sigma_sqT) + (1 + mu) * sigma_sqT
    
    def get_B():
        return phi * S * np.exp(-q * T) * norm.cdf(phi * x2) - phi * K * np.exp(-r * T) * norm.cdf(phi * (x2 - sigma_sqT))
        
    def get_C():
        log_term1 = 2 * (mu + 1) * np.log(H / S) + norm.logcdf(eta * y1)
        term1 = S * np.exp(-q * T) * np.exp(log_term1)
        
        log_term2 = 2 * mu * np.log(H / S) + norm.logcdf(eta * (y1 - sigma_sqT))
        term2 = K * np.exp(-r * T) * np.exp(log_term2)
        
        return phi * (term1 - term2)
        
    def get_D():
        log_term1 = 2 * (mu + 1) * np.log(H / S) + norm.logcdf(eta * y2)
        term1 = S * np.exp(-q * T) * np.exp(log_term1)
        
        log_term2 = 2 * mu * np.log(H / S) + norm.logcdf(eta * (y2 - sigma_sqT))
        term2 = K * np.exp(-r * T) * np.exp(log_term2)
        
        return phi * (term1 - term2)

    if is_call:
        if is_down:
            if is_in:
                return get_C() if K >= H else get_A() - get_B() + get_D()
            else:
                return get_A() - get_C() if K >= H else get_B() - get_D()
        else:
            if is_in:
                return get_A() if K >= H else get_B() - get_C() + get_D()
            else:
                return 0.0 if K >= H else get_A() - get_B() + get_C() - get_D()
    else:
        if is_down:
            if is_in:
                return get_B() - get_C() + get_D() if K >= H else get_A()
            else:
                return get_A() - get_B() + get_C() - get_D() if K >= H else 0.0
        else:
            if is_in:
                return get_A() - get_B() + get_D() if K >= H else get_C()
            else:
                return get_B() - get_D() if K >= H else get_A() - get_C()
