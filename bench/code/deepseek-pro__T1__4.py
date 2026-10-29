import math

SQRT2 = math.sqrt(2.0)
GOLDEN = 0.5 * (math.sqrt(5.0) - 1.0)

def norm_cdf(x):
    return 0.5 * math.erfc(-x / SQRT2)

def _bs_call(S, K, T, r, q, sigma):
    if T <= 0.0:
        return max(S - K, 0.0)
    sqrtT = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / sqrtT
    d2 = d1 - sqrtT
    return S * math.exp(-q * T) * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)

def _phi(S, T, gamma, H, I, b, r, sigma, sigma2):
    sqrtT = sigma * math.sqrt(T)
    kappa = 2.0 * b / sigma2 + (2.0 * gamma - 1.0)
    lam = -r + gamma * b + 0.5 * gamma * (gamma - 1.0) * sigma2
    d1 = -(math.log(S / H) + (b + (gamma - 0.5) * sigma2) * T) / sqrtT
    d2 = d1 - sqrtT

    n1 = norm_cdf(d1)
    if n1 == 0.0:
        return 0.0
    n2 = norm_cdf(d2)

    log_pre = lam * T + gamma * math.log(S)
    logA = log_pre + math.log(n1)

    if n2 == 0.0:
        logB = -math.inf
    else:
        logG = kappa * math.log(I / S)
        logB = log_pre + logG + math.log(n2)

    if logA <= -745.0:
        if logB <= -745.0:
            return 0.0
        return -math.exp(logB)
    if logB <= -745.0:
        return math.exp(logA)

    return math.exp(logA) - math.exp(logB)

def _american_call(S, K, T, r, q, sigma):
    if T <= 0.0 or S <= 0.0 or K <= 0.0:
        return max(S - K, 0.0)

    b = r - q
    if b >= r:
        return _bs_call(S, K, T, r, q, sigma)

    X = 1.0
    x = S / K
    sigma2 = sigma * sigma

    beta = (0.5 - b / sigma2) + math.sqrt((b / sigma2 - 0.5) ** 2 + 2.0 * r / sigma2)
    BInf = beta / (beta - 1.0) * X
    B0 = max(X, r / q * X)  # q > 0 here
    denom = BInf - B0

    if denom <= 1e-12:
        I1 = I2 = BInf
        alpha = (I1 - X) * I1 ** (-beta)
        if x >= I1:
            return S - K
        price = K * alpha * x ** beta
        intrinsic = max(S - K, 0.0)
        european = _bs_call(S, K, T, r, q, sigma)
        return max(price, european, intrinsic)

    t1 = GOLDEN * T
    sqrt_t1 = math.sqrt(t1)

    h1 = -(b * t1 + 2.0 * sigma * sqrt_t1) * X / denom
    h2 = -(b * t1 - 2.0 * sigma * sqrt_t1) * X / denom

    I1 = B0 + denom * (1.0 - math.exp(h1))
    I2 = B0 + denom * (1.0 - math.exp(h2))

    if I1 < X:
        I1 = BInf
    if I2 <= 0.0:
        I2 = X

    alpha = (I1 - X) * I1 ** (-beta)

    if x >= I1:
        return S - K

    phi_b_I1_I1 = _phi(x, t1, beta, I1, I1, b, r, sigma, sigma2)
    phi_1_I1_I1 = _phi(x, t1, 1.0, I1, I1, b, r, sigma, sigma2)
    phi_1_I2_I1 = _phi(x, t1, 1.0, I2, I1, b, r, sigma, sigma2)
    phi_0_I1_I1 = _phi(x, t1, 0.0, I1, I1, b, r, sigma, sigma2)
    phi_0_I2_I1 = _phi(x, t1, 0.0, I2, I1, b, r, sigma, sigma2)
    phi_b_I2_I1 = _phi(x, t1, beta, I2, I1, b, r, sigma, sigma2)
    phi_b_I2_I2 = _phi(x, t1, beta, I2, I2, b, r, sigma, sigma2)
    phi_1_I2_I2 = _phi(x, t1, 1.0, I2, I2, b, r, sigma, sigma2)
    phi_0_I2_I2 = _phi(x, t1, 0.0, I2, I2, b, r, sigma, sigma2)

    C = (alpha * x ** beta
         - alpha * phi_b_I1_I1
         + phi_1_I1_I1
         - 2.0 * phi_1_I2_I1
         - X * phi_0_I1_I1
         + 2.0 * X * phi_0_I2_I1
         + alpha * phi_b_I2_I1
         - alpha * phi_b_I2_I2
         + phi_1_I2_I2
         - X * phi_0_I2_I2)

    price = K * C
    intrinsic = max(S - K, 0.0)
    european = _bs_call(S, K, T, r, q, sigma)
    floor = max(european, intrinsic)

    if not math.isfinite(price) or price < floor:
        return floor
    return price

def american_price(S, K, T, r, q, sigma, is_call):
    if is_call:
        return _american_call(S, K, T, r, q, sigma)
    else:
        return _american_call(K, S, T, q, r, sigma)
