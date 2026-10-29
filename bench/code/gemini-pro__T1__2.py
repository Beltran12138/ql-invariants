import numpy as np
from scipy.special import ndtr

def american_price(S, K, T, r, q, sigma, is_call):
    if not is_call:
        return american_price(K, S, T, q, r, sigma, True)

    b = r - q
    sqrt_T = np.sqrt(T)
    sig_sqrt_T = sigma * sqrt_T

    if q <= 0:
        d1 = (np.log(S / K) + (b + 0.5 * sigma**2) * T) / sig_sqrt_T
        d2 = d1 - sig_sqrt_T
        return S * np.exp(-q * T) * ndtr(d1) - K * np.exp(-r * T) * ndtr(d2)

    if abs(r) < 1e-9:
        M_KT = 2.0 / (sigma**2 * T)
    else:
        M_KT = 2.0 * r / (sigma**2 * (1.0 - np.exp(-r * T)))

    N_b = 2.0 * b / sigma**2
    alpha = (N_b - 1.0) / 2.0

    if alpha > 0:
        q_2 = M_KT / (alpha + np.sqrt(alpha**2 + M_KT))
    else:
        q_2 = -alpha + np.sqrt(alpha**2 + M_KT)

    exp_qT = np.exp(-q * T)
    exp_rT = np.exp(-r * T)

    S_star = K * (1.0 + 1.0 / q_2)
    inv_sqrt_2pi = 0.3989422804014327
    tolerance = 1e-6 * K

    for _ in range(100):
        d1 = (np.log(S_star / K) + (b + 0.5 * sigma**2) * T) / sig_sqrt_T
        Nd1 = ndtr(d1)
        nd1 = inv_sqrt_2pi * np.exp(-0.5 * d1**2)

        c_val = S_star * exp_qT * Nd1 - K * exp_rT * ndtr(d1 - sig_sqrt_T)
        A2 = (S_star / q_2) * (1.0 - exp_qT * Nd1)

        f_val = S_star - K - c_val - A2

        if abs(f_val) < tolerance:
            break

        f_prime = (1.0 - 1.0 / q_2) * (1.0 - exp_qT * Nd1) + exp_qT * nd1 / (q_2 * sig_sqrt_T)
        S_star -= f_val / f_prime

        if S_star <= K:
            S_star = K * 1.00001

    if S >= S_star:
        return S - K

    d1 = (np.log(S / K) + (b + 0.5 * sigma**2) * T) / sig_sqrt_T
    d2 = d1 - sig_sqrt_T
    c = S * exp_qT * ndtr(d1) - K * exp_rT * ndtr(d2)

    d1_star = (np.log(S_star / K) + (b + 0.5 * sigma**2) * T) / sig_sqrt_T
    A2_star = (S_star / q_2) * (1.0 - exp_qT * ndtr(d1_star))

    return c + A2_star * (S / S_star)**q_2
