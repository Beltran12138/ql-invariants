import math
import numpy as np
from scipy.optimize import brentq

def _single_american_price(S, K, T, r, q, sigma, is_call):
    if is_call:
        return _single_american_price(K, S, T, q, r, sigma, False)
        
    S = float(S)
    K = float(K)
    T = float(T)
    r = float(r)
    q = float(q)
    sigma = float(sigma)
    
    if T <= 1e-5:
        return max(K - S, 0.0)

    sqrt_T = math.sqrt(T)
    sig_sqrt_T = sigma * sqrt_T
    sig2 = sigma**2
    r_q = r - q
    
    if abs(r) < 1e-7:
        H = T - 0.5 * r * T**2
    else:
        H = (1.0 - math.exp(-r * T)) / r
        
    N_val = 2.0 * r_q / sig2
    K_factor = 2.0 / (sig2 * H)
    
    q1 = 0.5 * (1.0 - N_val - math.sqrt((N_val - 1.0)**2 + 4.0 * K_factor))
    if q1 > -1e-9:
        q1 = -1e-9
        
    exp_qT = math.exp(-q * T)
    exp_rT = math.exp(-r * T)
    
    SQRT_2 = 1.4142135623730951
    def ncdf(x):
        return 0.5 * (1.0 + math.erf(x / SQRT_2))

    def calc_d1_d2(S_val):
        d1 = (math.log(S_val / K) + (r_q + 0.5 * sig2) * T) / sig_sqrt_T
        d2 = d1 - sig_sqrt_T
        return d1, d2

    def f(S_val):
        d1, d2 = calc_d1_d2(S_val)
        nd1 = ncdf(-d1)
        nd2 = ncdf(-d2)
        p = K * exp_rT * nd2 - S_val * exp_qT * nd1
        X = 1.0 - exp_qT * nd1
        return K - S_val - p + (S_val / q1) * X
        
    S_high = K
    f_high = f(S_high)
    
    if f_high >= 0.0:
        S_star = K
    else:
        S_low = 1e-5 * K
        f_low = f(S_low)
        if f_low <= 0.0:
            S_star = 0.0
        else:
            try:
                S_star = brentq(f, S_low, S_high, xtol=1e-6)
            except ValueError:
                S_star = 0.0
                
    if S <= S_star:
        return max(K - S, 0.0)
    else:
        d1, d2 = calc_d1_d2(S)
        nd1 = ncdf(-d1)
        nd2 = ncdf(-d2)
        p = K * exp_rT * nd2 - S * exp_qT * nd1
        
        if S_star > 0.0:
            d1_star, _ = calc_d1_d2(S_star)
            nd1_star = ncdf(-d1_star)
            X_star = 1.0 - exp_qT * nd1_star
            A1 = - (S_star / q1) * X_star
            ratio = S / S_star
            return p + A1 * (ratio ** q1)
        else:
            return p

def american_price(S, K, T, r, q, sigma, is_call):
    try:
        return _single_american_price(S, K, T, r, q, sigma, is_call)
    except (TypeError, ValueError):
        vec_func = np.vectorize(_single_american_price)
        return vec_func(S, K, T, r, q, sigma, is_call)
