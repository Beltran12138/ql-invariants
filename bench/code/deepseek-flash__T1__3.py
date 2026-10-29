import math

_SQRT2 = math.sqrt(2.0)
_SQRT2PI = math.sqrt(2.0 * math.pi)

def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / _SQRT2))

def _bs_call(S, K, T, r, q, sigma):
    if T <= 0.0:
        return S - K if S > K else 0.0
    sqrtT = math.sqrt(T)
    vol_sqrtT = sigma * sqrtT
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / vol_sqrtT
    d2 = d1 - vol_sqrtT
    return S * math.exp(-q * T) * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)

def _bs_put(S, K, T, r, q, sigma):
    if T <= 0.0:
        return K - S if K > S else 0.0
    sqrtT = math.sqrt(T)
    vol_sqrtT = sigma * sqrtT
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / vol_sqrtT
    d2 = d1 - vol_sqrtT
    return K * math.exp(-r * T) * _norm_cdf(-d2) - S * math.exp(-q * T) * _norm_cdf(-d1)

def _baw_call(S, K, T, r, q, sigma):
    if q <= 0.0:
        return _bs_call(S, K, T, r, q, sigma)
    if T <= 0.0:
        return S - K if S > K else 0.0
    if q < 1e-10:
        return _bs_call(S, K, T, r, q, sigma)
    v = sigma * sigma
    sqrtT = math.sqrt(T)
    b = r - q
    if r > 1e-12:
        M = 2.0 * r / v
        N = 2.0 * b / v
        Kappa = -math.expm1(-r * T)
        if Kappa < 1e-12:
            Kappa = r * T
        disc = (N - 1.0) ** 2 + 4.0 * M / Kappa
    else:
        N = 2.0 * b / v
        disc = (N - 1.0) ** 2 + 8.0 / (v * T)
    if disc < 0.0:
        disc = 0.0
    q2 = (-(N - 1.0) + math.sqrt(disc)) / 2.0
    if q2 <= 0.0:
        return _bs_call(S, K, T, r, q, sigma)
    bv = b / v
    beta = (0.5 - bv) + math.sqrt((bv - 0.5) ** 2 + 2.0 * r / v)
    if beta > 1.0:
        B_inf = beta / (beta - 1.0) * K
    else:
        B_inf = K * 10.0
    S_star = 0.5 * (K + B_inf)
    if S_star <= K:
        S_star = K * 1.1
    exp_qT = math.exp(-q * T)
    exp_rT = math.exp(-r * T)
    for _ in range(20):
        d1 = (math.log(S_star / K) + (r - q + 0.5 * v) * T) / (sigma * sqrtT)
        d2 = d1 - sigma * sqrtT
        N_d1 = _norm_cdf(d1)
        N_d2 = _norm_cdf(d2)
        C_E = S_star * exp_qT * N_d1 - K * exp_rT * N_d2
        A2 = (S_star / q2) * (1.0 - exp_qT * N_d1)
        f = S_star - K - C_E - A2
        phi_d1 = math.exp(-0.5 * d1 * d1) / _SQRT2PI
        df = (1.0 - 1.0 / q2) * (1.0 - exp_qT * N_d1) + exp_qT * phi_d1 / (q2 * sigma * sqrtT)
        if abs(f) < 1e-8 * K:
            break
        if abs(df) < 1e-14:
            break
        S_new = S_star - f / df
        if S_new <= K:
            S_new = (S_star + K) * 0.5
        if S_new > B_inf:
            S_new = (S_star + B_inf) * 0.5
        if abs(S_new - S_star) < 1e-8 * K:
            S_star = S_new
            break
        S_star = S_new
    if not (S_star > K and S_star <= B_inf):
        S_star = 0.5 * (K + B_inf)
    if S >= S_star:
        return S - K
    d1_star = (math.log(S_star / K) + (r - q + 0.5 * v) * T) / (sigma * sqrtT)
    N_d1_star = _norm_cdf(d1_star)
    A2 = (S_star / q2) * (1.0 - exp_qT * N_d1_star)
    C_E = _bs_call(S, K, T, r, q, sigma)
    price = C_E + A2 * (S / S_star) ** q2
    intrinsic = S - K if S > K else 0.0
    if price < C_E:
        price = C_E
    if price < intrinsic:
        price = intrinsic
    return price

def _american_crr(S, K, T, r, q, sigma, is_call, n=101):
    if T <= 0.0:
        return max(S - K, 0.0) if is_call else max(K - S, 0.0)
    dt = T / n
    sqrt_dt = math.sqrt(dt)
    u = math.exp(sigma * sqrt_dt)
    d = 1.0 / u
    disc = math.exp(-r * dt)
    p = (math.exp((r - q) * dt) - d) / (u - d)
    if p < 0.0: p = 0.0
    if p > 1.0: p = 1.0
    values = [0.0] * (n + 1)
    spot = S * (d ** n)
    ratio = u / d
    if is_call:
        for i in range(n + 1):
            payoff = spot - K
            values[i] = payoff if payoff > 0.0 else 0.0
            spot *= ratio
    else:
        for i in range(n + 1):
            payoff = K - spot
            values[i] = payoff if payoff > 0.0 else 0.0
            spot *= ratio
    disc_p = disc * p
    disc_1mp = disc * (1.0 - p)
    for step in range(n - 1, -1, -1):
        spot = S * (d ** step)
        if is_call:
            for i in range(step + 1):
                cont = disc_p * values[i+1] + disc_1mp * values[i]
                intrinsic = spot - K
                if intrinsic < 0.0: intrinsic = 0.0
                if cont < intrinsic:
                    values[i] = intrinsic
                else:
                    values[i] = cont
                spot *= ratio
        else:
            for i in range(step + 1):
                cont = disc_p * values[i+1] + disc_1mp * values[i]
                intrinsic = K - spot
                if intrinsic < 0.0: intrinsic = 0.0
                if cont < intrinsic:
                    values[i] = intrinsic
                else:
                    values[i] = cont
                spot *= ratio
    return values[0]

def american_price(S, K, T, r, q, sigma, is_call):
    if T <= 0.0:
        return max(S - K, 0.0) if is_call else max(K - S, 0.0)
    if sigma <= 0.0:
        return max(S - K, 0.0) if is_call else max(K - S, 0.0)
    if is_call:
        if r < 0.0:
            return _american_crr(S, K, T, r, q, sigma, True, 101)
        if q <= 0.0:
            return _bs_call(S, K, T, r, q, sigma)
        return _baw_call(S, K, T, r, q, sigma)
    else:
        if r <= 0.0 or q < 0.0:
            return _american_crr(S, K, T, r, q, sigma, False, 101)
        return _baw_call(K, S, T, q, r, sigma)
