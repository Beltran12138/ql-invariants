import math
import numpy as np
from scipy.special import ndtr

# American option pricing under Black-Scholes with continuous dividend yield.
# Main engine: Andersen-Lake-Offengenden spectral collocation of the early-exercise
# boundary (fixed-point system FP-B, Chebyshev interpolation in sqrt(tau), Gauss-Legendre
# quadrature). Calls map to puts through McDonald-Schroder symmetry. The negative-rate
# double-boundary regime (q < r <= 0 for the put) uses a CRR tree with a European
# control variate.

_N_CHEB = 16      # Chebyshev-Lobatto intervals for the boundary (n+1 nodes)
_N_GL = 32        # quadrature points for boundary integrals
_N_GL_F = 64      # quadrature points for the final premium integral
_MAX_IT = 20
_TOL = 1e-10
_INV_SQ2PI = 1.0 / math.sqrt(2.0 * math.pi)
_SQRT2 = math.sqrt(2.0)


def _bary_matrix(pts, nodes):
    n = len(nodes) - 1
    w = (-1.0) ** np.arange(n + 1)
    w[0] *= 0.5
    w[-1] *= 0.5
    diff = pts[:, None] - nodes[None, :]
    exact = np.abs(diff) < 1e-14
    diff[exact] = 1.0
    m = w / diff
    m /= m.sum(axis=1, keepdims=True)
    rows = exact.any(axis=1)
    m[rows] = exact[rows].astype(float)
    return m


# Precomputed (parameter-independent) collocation / quadrature structures.
# Boundary node i sits at sqrt(tau_i) = sqrt(T) * (1 + x_i) / 2, x_0 = 1 (tau=T), x_n = -1 (tau=0).
_X = np.cos(np.pi * np.arange(_N_CHEB + 1) / _N_CHEB)
_G = 0.5 * (1.0 + _X[:-1])
_Y, _W = np.polynomial.legendre.leggauss(_N_GL)
_ZF = 0.5 * (1.0 + _Y)
_CF = np.sqrt(1.0 - _ZF ** 2)
_LB = _bary_matrix(((1.0 + _X[:-1, None]) * _CF[None, :] - 1.0).ravel(), _X)[:, :-1].copy()
_YF, _WF = np.polynomial.legendre.leggauss(_N_GL_F)
_ZFF = 0.5 * (1.0 + _YF)
_WFZ = _WF * _ZFF
_LF = _bary_matrix(2.0 * np.sqrt(1.0 - _ZFF ** 2) - 1.0, _X)[:, :-1].copy()


def _ncdf(x):
    return 0.5 * math.erfc(-x / _SQRT2)


def _euro_put(S, K, T, r, q, sigma):
    sT = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / sT
    d2 = d1 - sT
    return K * math.exp(-r * T) * _ncdf(-d2) - S * math.exp(-q * T) * _ncdf(-d1)


def _tree_put(S, K, T, r, q, sigma, euro, n=200):
    dt = T / n
    a = sigma * math.sqrt(dt)
    u = math.exp(a)
    d = 1.0 / u
    p = (math.exp((r - q) * dt) - d) / (u - d)
    p = min(max(p, 0.0), 1.0)
    disc = math.exp(-r * dt)
    pu, pd = disc * p, disc * (1.0 - p)
    ex = K - S * np.exp(a * np.arange(-n, n + 1))
    v = np.empty((2, n + 1))
    v[:] = np.maximum(ex[::2], 0.0)
    for i in range(n - 1, -1, -1):
        v = pd * v[:, :-1] + pu * v[:, 1:]
        np.maximum(v[0], ex[n - i:n + i + 1:2], out=v[0])
    return max(v[0, 0] - v[1, 0] + euro, K - S, euro)


def _alo_put(S, K, T, r, q, sigma, euro):
    b = r - q
    X = K * min(1.0, r / q) if q > 0.0 else K
    lnX, lnK = math.log(X), math.log(K)
    s2 = sigma * sigma
    mu = b - 0.5 * s2
    sT = math.sqrt(T)

    sq = sT * _G
    tau = sq * sq
    Z = sq[:, None] * _ZF
    Tt = Z * Z
    U = tau[:, None] - Tt
    Wsq = _W * sq[:, None]
    Ar = (r / sigma * _INV_SQ2PI) * Wsq * np.exp(r * U)
    Aq = q * Wsq * np.exp(q * U)
    sZ = sigma * Z
    inv_sZ = 1.0 / sZ
    driftZ = mu * Tt
    ssq = sigma * sq
    c0 = mu * tau / ssq
    lead = _INV_SQ2PI / ssq
    lnKdisc = lnK - b * tau - lnX

    # Initial guess: perpetual boundary blended with BAW-style decay
    lam = (-mu - math.sqrt(mu * mu + 2.0 * s2 * r)) / s2
    binf = min(K * lam / (lam - 1.0), X)
    gap = max(X - binf, X * 1e-300)
    B0 = binf + (X - binf) * np.exp(-2.0 * ssq * X / gap)
    L = np.minimum(np.log(np.maximum(B0, X * 1e-300) / X), 0.0)  # L = ln(B/X) <= 0

    eta, prev = 1.0, np.inf
    for _ in range(_MAX_IT):
        sH = -L
        sHq = np.sqrt(np.maximum(_LB @ (L * L), 0.0)).reshape(Z.shape)
        dm = (sHq - sH[:, None] + driftZ) * inv_sZ
        dp = dm + sZ
        Nint = (Ar * np.exp(-0.5 * dm * dm)).sum(axis=1)
        Dint = (Aq * (Z * ndtr(dp) + (_INV_SQ2PI / sigma) * np.exp(-0.5 * dp * dp))).sum(axis=1)
        dm0 = (-sH + (lnX - lnK)) / ssq + c0
        dp0 = dm0 + ssq
        N = lead * np.exp(-0.5 * dm0 * dm0) + Nint
        D = lead * np.exp(-0.5 * dp0 * dp0) + ndtr(dp0) + Dint
        ok = (N > 0.0) & (D > 0.0) & np.isfinite(N) & np.isfinite(D)
        Lnew = lnKdisc + np.log(np.where(ok, N, 1.0)) - np.log(np.where(ok, D, 1.0))
        Lnew = np.where(ok, np.clip(Lnew, -690.0, 0.0), L)
        diff = Lnew - L
        err = np.max(np.abs(diff))
        if err > prev:
            eta = max(0.5 * eta, 0.125)
        L = L + eta * diff
        prev = err
        if err < _TOL:
            break

    if S <= X * math.exp(L[0]):
        return K - S

    sHf = np.sqrt(np.maximum(_LF @ (L * L), 0.0))
    Zf = sT * _ZFF
    Tf = Zf * Zf
    sZf = sigma * Zf
    dmf = (math.log(S) - lnX + sHf + mu * Tf) / sZf
    dpf = dmf + sZf
    integ = r * K * np.exp(-r * Tf) * ndtr(-dmf) - q * S * np.exp(-q * Tf) * ndtr(-dpf)
    prem = T * float(np.dot(_WFZ, integ))
    price = euro + prem
    if not math.isfinite(price):
        return _tree_put(S, K, T, r, q, sigma, euro)
    return max(price, K - S, euro)


def american_price(S, K, T, r, q, sigma, is_call):
    S, K, T, r, q, sigma = float(S), float(K), float(T), float(r), float(q), float(sigma)
    if is_call:
        # McDonald-Schroder symmetry: C(S, K, r, q) = P(K, S, q, r)
        S, K, r, q = K, S, q, r
    if T <= 0.0:
        return max(K - S, 0.0)
    euro = _euro_put(S, K, T, r, q, sigma)
    if r > 0.0:
        return _alo_put(S, K, T, r, q, sigma, euro)
    if q >= r:
        return euro  # early exercise never optimal
    return _tree_put(S, K, T, r, q, sigma, euro)  # double-boundary regime q < r <= 0
