import math

def american_price(S, K, T, r, q, sigma, is_call):
    if T <= 0.0:
        return max(S - K, 0.0) if is_call else max(K - S, 0.0)
    sqrtT = math.sqrt(T)
    sig_sqrtT = sigma * sqrtT
    inv_sig_sqrtT = 1.0 / sig_sqrtT
    b = r - q
    exp_qT = math.exp(-q * T)
    exp_rT = math.exp(-r * T)
    inv_sqrt2 = 0.7071067811865476
    sigma2 = sigma * sigma
    const_term = (b + 0.5 * sigma2) * T

    d1_S = (math.log(S / K) + const_term) * inv_sig_sqrtT
    d2_S = d1_S - sig_sqrtT
    if is_call:
        N1_S = 0.5 * math.erfc(-d1_S * inv_sqrt2)
        N2_S = 0.5 * math.erfc(-d2_S * inv_sqrt2)
        euro = S * exp_qT * N1_S - K * exp_rT * N2_S
    else:
        N_neg_d1 = 0.5 * math.erfc(d1_S * inv_sqrt2)
        N_neg_d2 = 0.5 * math.erfc(d2_S * inv_sqrt2)
        euro = K * exp_rT * N_neg_d2 - S * exp_qT * N_neg_d1

    if is_call:
        if not (q > 1e-12 or (abs(q) <= 1e-12 and r < 0.0)):
            return euro
        M = 2.0 * r / sigma2
        N = 2.0 * b / sigma2
        if abs(r) < 1e-8:
            M_over_K = 2.0 / (sigma2 * T)
        else:
            Kappa = 1.0 - math.exp(-r * T)
            M_over_K = M / Kappa
        disc = (N - 1.0) * (N - 1.0) + 4.0 * M_over_K
        if disc < 0.0:
            disc = 0.0
        q2 = (-(N - 1.0) + math.sqrt(disc)) / 2.0

        def f_call(x):
            d1 = (math.log(x / K) + const_term) * inv_sig_sqrtT
            d2 = d1 - sig_sqrtT
            N1 = 0.5 * math.erfc(-d1 * inv_sqrt2)
            N2 = 0.5 * math.erfc(-d2 * inv_sqrt2)
            c = x * exp_qT * N1 - K * exp_rT * N2
            B = 1.0 - exp_qT * N1
            return x - K - c - (x / q2) * B

        low = K
        high = K * 2.0
        while f_call(high) < 0.0 and high < K * 1e6:
            high *= 2.0
        if f_call(high) < 0.0:
            return euro
        for _ in range(50):
            mid = 0.5 * (low + high)
            if f_call(mid) < 0.0:
                low = mid
            else:
                high = mid
        S_star = 0.5 * (low + high)
        d1_star = (math.log(S_star / K) + const_term) * inv_sig_sqrtT
        N1_star = 0.5 * math.erfc(-d1_star * inv_sqrt2)
        B_star = 1.0 - exp_qT * N1_star
        A2 = S_star / q2 * B_star
        if S < S_star:
            return euro + A2 * (S / S_star) ** q2
        else:
            return S - K
    else:
        if not (r > 1e-12 or (abs(r) <= 1e-12 and q < 0.0)):
            return euro
        M = 2.0 * r / sigma2
        N = 2.0 * b / sigma2
        if abs(r) < 1e-8:
            M_over_K = 2.0 / (sigma2 * T)
        else:
            Kappa = 1.0 - math.exp(-r * T)
            M_over_K = M / Kappa
        disc = (N - 1.0) * (N - 1.0) + 4.0 * M_over_K
        if disc < 0.0:
            disc = 0.0
        q1 = (-(N - 1.0) - math.sqrt(disc)) / 2.0

        def f_put(x):
            d1 = (math.log(x / K) + const_term) * inv_sig_sqrtT
            d2 = d1 - sig_sqrtT
            N_neg_d1 = 0.5 * math.erfc(d1 * inv_sqrt2)
            N_neg_d2 = 0.5 * math.erfc(d2 * inv_sqrt2)
            p = K * exp_rT * N_neg_d2 - x * exp_qT * N_neg_d1
            Bp = 1.0 - exp_qT * N_neg_d1
            return K - x - p + (x / q1) * Bp

        low = K * 1e-10
        high = K
        while f_put(low) < 0.0 and low > K * 1e-15:
            low *= 0.1
        if f_put(low) < 0.0:
            return euro
        for _ in range(50):
            mid = 0.5 * (low + high)
            if f_put(mid) > 0.0:
                low = mid
            else:
                high = mid
        S_star = 0.5 * (low + high)
        d1_star = (math.log(S_star / K) + const_term) * inv_sig_sqrtT
        N_neg_d1_star = 0.5 * math.erfc(d1_star * inv_sqrt2)
        Bp_star = 1.0 - exp_qT * N_neg_d1_star
        A1 = - S_star / q1 * Bp_star
        if S > S_star:
            return euro + A1 * (S / S_star) ** q1
        else:
            return K - S
