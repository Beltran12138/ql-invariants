import math
import numpy as np
from scipy.special import ndtr

_N = 12       # Chebyshev collocation intervals for the exercise boundary
_M = 24       # Gauss-Legendre nodes for the boundary integrals
_MP = 64      # Gauss-Legendre nodes for the early-exercise premium
_ITER = 6     # fixed-point (FP-A) iterations
_TREE_N = 64  # steps for the double-boundary fallback tree

_z = -np.cos(np.arange(_N + 1) * np.pi / _N)
_xi = 0.5 * (1.0 + _z)
_bw = (-1.0) ** np.arange(_N + 1)
_bw[0] *= 0.5
_bw[-1] *= 0.5


def _interp_matrix(x):
    zx = 2.0 * np.asarray(x) - 1.0
    diff = zx[:, None] - _z[None, :]
    exact = np.abs(diff) < 1e-14
    diff[exact] = 1.0
    c = _bw / diff
    c /= c.sum(axis=1, keepdims=True)
    rows = exact.any(axis=1)
    c[rows] = exact[rows].astype(float)
    return c


def _gl(m):
    x, w = np.polynomial.legendre.leggauss(m)
    return 0.5 * (x + 1.0), 0.5 * w


_gw, _gwt = _gl(_M)
_MB = np.ascontiguousarray(_interp_matrix((_xi[1:, None] * np.sqrt(1.0 - _gw[None, :] ** 2)).ravel())[:, 1:])
_pw, _pwt = _gl(_MP)
_MPX = np.ascontiguousarray(_interp_matrix(np.sqrt(1.0 - _pw ** 2))[:, 1:])
_XI2 = _xi[1:] ** 2
_W2 = _gw ** 2
_PW2 = _pw ** 2
_PWW = _pw * _pwt
_GWW = _gw * _gwt
_SQ2 = math.sqrt(2.0)


def _ncdf(x):
    return 0.5 * math.erfc(-x / _SQ2)


def _euro_put(S, K, T, r, q, sigma):
    st = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / st
    return K * math.exp(-r * T) * _ncdf(st - d1) - S * math.exp(-q * T) * _ncdf(-d1)


def _put_alo(S, K, T, r, q, sigma):
    # Andersen-Lake-Offengelt fixed-point method (FP-A form), valid for r > 0.
    X = K if q <= r else K * r / q
    s2 = sigma * sigma
    b = r - q
    mu = b + 0.5 * s2
    tau = T * _XI2
    st = sigma * np.sqrt(tau)

    # initial guess: interpolation between X and the perpetual boundary
    be = 2.0 * b / s2
    lam = 0.5 * (1.0 - be - math.sqrt((be - 1.0) ** 2 + 8.0 * r / s2))
    c0 = K / X
    ci = (lam - 1.0) / lam
    h = (max(-b, 0.0) * tau + 2.0 * st) * (-c0 / (ci - c0))
    y = np.log(c0 / (ci - (ci - c0) * np.exp(h)))
    np.minimum(y, 0.0, out=y)

    sq = np.empty((_N, _M + 1))
    np.multiply(st[:, None], _gw, out=sq[:, :_M])
    sq[:, _M] = st
    inv = 1.0 / sq
    lkx = math.log(K / X)
    cst = np.empty((2, _N, _M + 1))
    np.multiply(sq, mu / s2, out=cst[1])
    cst[0] = cst[1] - sq
    ts = tau[:, None] * (1.0 - _W2)
    tw = (2.0 * tau)[:, None] * _GWW
    W = np.empty((2, _N, _M + 1))
    W[0, :, :_M] = (r * tw) * np.exp(r * ts)
    W[1, :, :_M] = (q * tw) * np.exp(q * ts)
    W[:, :, _M] = 1.0
    Yq = np.empty((_N, _M + 1))
    Yq[:, _M] = lkx
    off = lkx - b * tau
    yq = Yq[:, :_M]

    with np.errstate(all='ignore'):
        for _ in range(_ITER):
            np.sqrt(np.maximum(_MB @ (y * y), 0.0).reshape(_N, _M), out=yq)
            np.negative(yq, out=yq)
            nd = np.einsum('kij,kij->ki', ndtr((y[:, None] - Yq) * inv + cst), W)
            y = np.log(nd[0] / nd[1])
            y += off
            np.minimum(y, 0.0, out=y)
            np.maximum(y, -60.0, out=y)

    if S <= X * math.exp(y[-1]):
        return K - S
    yp = np.sqrt(np.maximum(_MPX @ (y * y), 0.0))
    sqp = sigma * math.sqrt(T) * _pw
    d1 = (math.log(S / X) + yp + (mu * T) * _PW2) / sqp
    integ = (r * K) * np.exp((-r * T) * _PW2) * ndtr(sqp - d1) - (q * S) * np.exp((-q * T) * _PW2) * ndtr(-d1)
    prem = 2.0 * T * float(integ @ _PWW)
    return max(_euro_put(S, K, T, r, q, sigma) + prem, K - S)


def _tree_put_once(S, K, T, r, q, sigma, n):
    dt = T / n
    dx = sigma * math.sqrt(dt)
    nudt = (r - q - 0.5 * sigma * sigma) * dt
    u = math.exp(nudt + dx)
    d = math.exp(nudt - dx)
    p = (math.exp((r - q) * dt) - d) / (u - d)
    disc = math.exp(-r * dt)
    pd = disc * (1.0 - p)
    rho = p / (1.0 - p)
    i = np.arange(n)
    St = S * np.exp(np.add.outer(i * (nudt - dx), i * (2.0 * dx)))
    # values are carried as V_k / pd**(n-1-k) so that one step is U[:k] + rho * U[1:]
    scale = np.exp(-math.log(pd) * (n - 1 - i))
    E = (K - St) * scale[:, None]
    Sn = St[n - 1]
    with np.errstate(divide='ignore'):
        d1 = (np.log(Sn / K) + (r - q + 0.5 * sigma * sigma) * dt) / dx
    V = K * math.exp(-r * dt) * ndtr(dx - d1) - Sn * math.exp(-q * dt) * ndtr(-d1)
    V = np.maximum(V, E[n - 1])
    for k in range(n - 1, 0, -1):
        W = V[1:] * rho
        W += V[:k]
        V = np.maximum(W, E[k - 1, :k], out=W)
    return float(V[0]) / scale[0]


def _tree_put(S, K, T, r, q, sigma):
    a = _tree_put_once(S, K, T, r, q, sigma, _TREE_N)
    b = _tree_put_once(S, K, T, r, q, sigma, _TREE_N // 2)
    lo = max(_euro_put(S, K, T, r, q, sigma), K - S, 0.0)
    hi = K * max(1.0, math.exp(-r * T))
    return min(max(2.0 * a - b, lo), hi)


def _put(S, K, T, r, q, sigma):
    if r > 0.0:
        return _put_alo(S, K, T, r, q, sigma)
    if q >= r:
        # r <= 0 and q >= r: early exercise is never optimal
        return _euro_put(S, K, T, r, q, sigma)
    # q < r <= 0: double exercise boundary
    return _tree_put(S, K, T, r, q, sigma)


def american_price(S, K, T, r, q, sigma, is_call):
    S = float(S)
    K = float(K)
    T = float(T)
    r = float(r)
    q = float(q)
    sigma = float(sigma)
    if T <= 0.0:
        return max(S - K, 0.0) if is_call else max(K - S, 0.0)
    if is_call:
        # McDonald-Schroder put-call symmetry
        return _put(K, S, T, q, r, sigma)
    return _put(S, K, T, r, q, sigma)
