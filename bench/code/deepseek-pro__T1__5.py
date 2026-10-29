import math

def _N(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))

def _pdf(x):
    return 1.0 / math.sqrt(2.0 * math.pi) * math.exp(-0.5 * x * x)

def _european(S, K, T, r, q, sigma, is_call):
    b = r - q
    sqrtT = math.sqrt(T)
    vol = sigma * sqrtT
    d1 = (math.log(S / K) + (b + 0.5 * sigma * sigma) * T) / vol
    d2 = d1 - vol
    if is_call:
        return S * math.exp(-q * T) * _N(d1) - K * math.exp(-r * T) * _N(d2)
    else:
        return K * math.exp(-r * T) * _N(-d2) - S * math.exp(-q * T) * _N(-d1)

def _q_roots(r, b, sigma, T):
    N = 2.0 * b / (sigma * sigma)
    if abs(r * T) < 1e-12:
        term = 8.0 / (sigma * sigma * T)
    else:
        denom = -math.expm1(-r * T)
        term = 8.0 * r / (sigma * sigma * denom)
    sqrt_term = math.sqrt((N - 1.0) * (N - 1.0) + term)
    q2 = (-(N - 1.0) + sqrt_term) / 2.0
    q1 = (-(N - 1.0) - sqrt_term) / 2.0
    return q2, q1

def _solve_root(f, fp, low, high, x0):
    x = x0
    if x <= low or x >= high:
        x = 0.5 * (low + high)

    for _ in range(40):
        fx = f(x)
        if abs(fx) < 1e-10:
            return x
        fpx = fp(x)
        if fpx == 0.0 or math.isnan(fpx):
            break
        x_new = x - fx / fpx
        if x_new <= low or x_new >= high:
            break
        x = x_new

    lo, hi = low, high
    flo = f(lo)
    fhi = f(hi)

    if abs(flo) < 1e-12:
        return lo
    if abs(fhi) < 1e-12:
        return hi
    if flo * fhi > 0.0:
        return None

    for _ in range(80):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if abs(fm) < 1e-10:
            return mid
        if flo * fm <= 0.0:
            hi = mid
            fhi = fm
        else:
            lo = mid
            flo = fm
    return 0.5 * (lo + hi)

def _call_critical(K, T, r, q, sigma, q2):
    b = r - q
    sqrtT = math.sqrt(T)
    vol = sigma * sqrtT
    expqT = math.exp(-q * T)
    exprT = math.exp(-r * T)

    def f(S):
        d1 = (math.log(S / K) + (b + 0.5 * sigma * sigma) * T) / vol
        d2 = d1 - vol
        Nd1 = _N(d1)
        C = S * expqT * Nd1 - K * exprT * _N(d2)
        H = 1.0 - expqT * Nd1
        return S - K - C - (S / q2) * H

    def fp(S):
        d1 = (math.log(S / K) + (b + 0.5 * sigma * sigma) * T) / vol
        Nd1 = _N(d1)
        H = 1.0 - expqT * Nd1
        pdf1 = _pdf(d1)
        return 1.0 - expqT * Nd1 - H / q2 + expqT * pdf1 / (q2 * vol)

    low = K
    x0 = K * q2 / (q2 - 1.0)
    if x0 <= low:
        x0 = low * 1.1

    high = max(x0, low * 1.1)
    for _ in range(20):
        if f(high) > 0.0:
            break
        high *= 1.5

    return _solve_root(f, fp, low, high, x0)

def _put_critical(K, T, r, q, sigma, q1):
    b = r - q
    sqrtT = math.sqrt(T)
    vol = sigma * sqrtT
    expqT = math.exp(-q * T)
    exprT = math.exp(-r * T)

    def f(S):
        d1 = (math.log(S / K) + (b + 0.5 * sigma * sigma) * T) / vol
        d2 = d1 - vol
        Nm1 = _N(-d1)
        P = K * exprT * _N(-d2) - S * expqT * Nm1
        H = 1.0 - expqT * Nm1
        return K - S - P + (S / q1) * H

    def fp(S):
        d1 = (math.log(S / K) + (b + 0.5 * sigma * sigma) * T) / vol
        Nm1 = _N(-d1)
        H = 1.0 - expqT * Nm1
        pdf1 = _pdf(d1)
        return -1.0 + expqT * Nm1 + H / q1 + expqT * pdf1 / (q1 * vol)

    low = 0.0
    high = K
    flo = K * (1.0 - math.exp(-r * T))
    fhi = f(high)

    if flo <= 0.0 and fhi <= 0.0:
        return None

    x0 = K * q1 / (q1 - 1.0)
    if x0 <= low or x0 >= high:
        x0 = 0.5 * K

    return _solve_root(f, fp, low, high, x0)

def _baw_call(S, K, T, r, q, sigma):
    b = r - q
    q2, _ = _q_roots(r, b, sigma, T)
    S_star = _call_critical(K, T, r, q, sigma, q2)

    if S_star is None:
        return _european(S, K, T, r, q, sigma, True)

    if S >= S_star:
        return S - K

    C = _european(S, K, T, r, q, sigma, True)
    sqrtT = math.sqrt(T)
    vol = sigma * sqrtT
    d1 = (math.log(S_star / K) + (b + 0.5 * sigma * sigma) * T) / vol
    H = 1.0 - math.exp(-q * T) * _N(d1)
    A2 = (S_star / q2) * H

    return C + A2 * (S / S_star) ** q2

def _baw_put(S, K, T, r, q, sigma):
    b = r - q
    q1, _ = _q_roots(r, b, sigma, T)
    S_star = _put_critical(K, T, r, q, sigma, q1)

    if S_star is None or S_star <= 0.0:
        return _european(S, K, T, r, q, sigma, False)

    if S <= S_star:
        return K - S

    P = _european(S, K, T, r, q, sigma, False)
    sqrtT = math.sqrt(T)
    vol = sigma * sqrtT
    d1 = (math.log(S_star / K) + (b + 0.5 * sigma * sigma) * T) / vol
    H = 1.0 - math.exp(-q * T) * _N(-d1)
    A1 = -(S_star / q1) * H

    return P + A1 * (S / S_star) ** q1

def _binomial_tree(S, K, T, r, q, sigma, is_call, N=150):
    dt = T / N
    u = math.exp(sigma * math.sqrt(dt))
    d = 1.0 / u
    pu = (math.exp((r - q) * dt) - d) / (u - d)
    if pu <= 0.0:
        pu = 0.0
    elif pu >= 1.0:
        pu = 1.0
    pd = 1.0 - pu
    disc = math.exp(-r * dt)

    prices = [0.0] * (N + 1)
    p = S * (u ** N)
    inv_u2 = 1.0 / (u * u)
    for i in range(N + 1):
        prices[i] = p
        p *= inv_u2

    V = [0.0] * (N + 1)
    if is_call:
        for i in range(N + 1):
            payoff = prices[i] - K
            V[i] = payoff if payoff > 0.0 else 0.0
    else:
        for i in range(N + 1):
            payoff = K - prices[i]
            V[i] = payoff if payoff > 0.0 else 0.0

    inv_u = 1.0 / u
    for m in range(N - 1, -1, -1):
        for i in range(m + 1):
            cont = disc * (pu * V[i] + pd * V[i + 1])
            S_i = prices[i] * inv_u
            if is_call:
                ex = S_i - K
            else:
                ex = K - S_i
            if ex > cont:
                V[i] = ex
            else:
                V[i] = cont
            prices[i] = S_i

    return V[0]

def american_price(S, K, T, r, q, sigma, is_call):
    if is_call:
        b = r - q
        if b >= r:
            return _european(S, K, T, r, q, sigma, True)
        try:
            return _baw_call(S, K, T, r, q, sigma)
        except Exception:
            return _binomial_tree(S, K, T, r, q, sigma, True)
    else:
        if q < 0.0:
            return _binomial_tree(S, K, T, r, q, sigma, False)
        try:
            return _baw_put(S, K, T, r, q, sigma)
        except Exception:
            return _binomial_tree(S, K, T, r, q, sigma, False)
