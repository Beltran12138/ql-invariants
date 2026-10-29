import math
from scipy.integrate import quad
from scipy.special import ndtr


def _vanilla_price(S, K, T, r, q, sigma, is_call):
    if T <= 0.0:
        if is_call:
            return max(S - K, 0.0)
        return max(K - S, 0.0)

    s = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / s
    d2 = d1 - s

    if is_call:
        price = S * math.exp(-q * T) * ndtr(d1) - K * math.exp(-r * T) * ndtr(d2)
    else:
        price = K * math.exp(-r * T) * ndtr(-d2) - S * math.exp(-q * T) * ndtr(-d1)

    return max(price, 0.0)


def _barrier_out_price(S, K, H, T, r, q, sigma, is_call, is_down):
    sqrt_t = math.sqrt(T)
    s = sigma * sqrt_t
    mu = r - q - 0.5 * sigma * sigma
    mu_t = mu * T

    b = math.log(H / S)
    c = 2.0 * b / s
    log_c = 2.0 * mu * b / (sigma * sigma)

    log_s = math.log(S)
    log_k = math.log(K)
    half_log_2pi = 0.5 * math.log(2.0 * math.pi)

    def integrand(z):
        log_ratio = log_c + z * c - 0.5 * c * c

        if log_ratio >= 0.0:
            return 0.0

        factor = -math.expm1(log_ratio)
        if factor <= 0.0:
            return 0.0

        log_factor = math.log(factor)
        log_phi = -0.5 * z * z - half_log_2pi
        log_v = log_s + mu_t + s * z

        if is_call:
            if log_v <= log_k:
                return 0.0
            log_term1 = log_v + log_phi + log_factor
            log_term2 = log_k + log_phi + log_factor
            term1 = math.exp(log_term1) if log_term1 > -745.0 else 0.0
            term2 = math.exp(log_term2) if log_term2 > -745.0 else 0.0
            value = term1 - term2
        else:
            if log_v >= log_k:
                return 0.0
            log_term1 = log_k + log_phi + log_factor
            log_term2 = log_v + log_phi + log_factor
            term1 = math.exp(log_term1) if log_term1 > -745.0 else 0.0
            term2 = math.exp(log_term2) if log_term2 > -745.0 else 0.0
            value = term1 - term2

        return value if value > 0.0 else 0.0

    z_k = (log_k - log_s - mu_t) / s

    if is_call:
        integral, _ = quad(
            integrand, z_k, math.inf,
            epsabs=1e-13, epsrel=1e-10, limit=200
        )
    else:
        integral, _ = quad(
            integrand, -math.inf, z_k,
            epsabs=1e-13, epsrel=1e-10, limit=200
        )

    return math.exp(-r * T) * integral


def barrier_price(S, K, H, T, r, q, sigma, is_call, barrier_type):
    is_in = barrier_type.endswith("in")
    is_down = barrier_type.startswith("down")

    vanilla = _vanilla_price(S, K, T, r, q, sigma, is_call)

    breached = (S <= H) if is_down else (S >= H)

    if breached:
        return vanilla if is_in else 0.0

    out_price = _barrier_out_price(S, K, H, T, r, q, sigma, is_call, is_down)

    if out_price < 0.0:
        out_price = 0.0
    if out_price > vanilla:
        out_price = vanilla

    if is_in:
        in_price = vanilla - out_price
        if in_price < 0.0:
            in_price = 0.0
        if in_price > vanilla:
            in_price = vanilla
        return in_price

    return out_price
