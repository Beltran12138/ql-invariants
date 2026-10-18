"""Independent check of the fix proposed on QuantLib#2903 (2026-10-18): Bjerksund-Stensland 1993 is the
exact value of exercising at a flat trigger I, so maximise it over I in [I_formula, B_inf].

Own implementation of BJS 1993 (Haug, The Complete Guide to Option Pricing Formulas, 2nd ed., 3.2.1),
with the trigger as in QuantLib's americanCallApproximation. Compared with QuantLib's own BJS engine
(must agree at I = I_formula) and with QdFp.
"""
import math
from scipy.optimize import minimize_scalar
from scipy.stats import norm
import QuantLib as ql


def _logphi(S, T, gamma, H, I, r, b, v, scale_by_I):
    """log of phi, optionally times I^-gamma (needed when gamma = beta is large)."""
    sq = v * math.sqrt(T)
    lam = (-r + gamma * b + 0.5 * gamma * (gamma - 1) * v * v) * T
    d = -(math.log(S / H) + (b + (gamma - 0.5) * v * v) * T) / sq
    kappa = 2 * b / (v * v) + (2 * gamma - 1)
    base = lam + gamma * (math.log(S / I) if scale_by_I else math.log(S))
    t1 = norm.logcdf(d)
    t2 = kappa * math.log(I / S) + norm.logcdf(d - 2 * math.log(I / S) / sq)
    if t1 <= t2:   # difference would be <= 0 (only by rounding when H = I); return -inf
        return -math.inf, 0.0
    return base + t1 + math.log1p(-math.exp(t2 - t1)), 1.0


def phi(S, T, gamma, H, I, r, b, v, scale_by_I=False):
    lv, sign = _logphi(S, T, gamma, H, I, r, b, v, scale_by_I)
    return sign * math.exp(lv) if lv > -math.inf else 0.0


def call_given_I(S, X, T, r, b, v, I):
    if S >= I:
        return S - X
    beta = (0.5 - b / v**2) + math.sqrt((b / v**2 - 0.5) ** 2 + 2 * r / v**2)
    # alpha * S^beta and alpha * phi(beta) with alpha = (I - X) I^-beta, computed relative to I
    a_term = (I - X) * math.exp(beta * math.log(S / I))
    return (a_term - (I - X) * phi(S, T, beta, I, I, r, b, v, scale_by_I=True) + phi(S, T, 1, I, I, r, b, v)
            - phi(S, T, 1, X, I, r, b, v) - X * phi(S, T, 0, I, I, r, b, v) + X * phi(S, T, 0, X, I, r, b, v))


def trigger(X, T, r, b, v):
    beta = (0.5 - b / v**2) + math.sqrt((b / v**2 - 0.5) ** 2 + 2 * r / v**2)
    Binf = beta / (beta - 1) * X
    B0 = max(X, r / (r - b) * X)
    ht = -(b * T + 2 * v * math.sqrt(T)) * B0 / (Binf - B0)
    return B0 + (Binf - B0) * (1 - math.exp(ht)), B0, Binf, ht


def american(S, X, T, r, q, v, is_call, maximise):
    if not is_call:   # put-call transformation: P(S, X, r, b) = C(X, S, r - b, -b)
        S, X, r, b = X, S, q, -(r - q)
    else:
        b = r - q
    I, B0, Binf, ht = trigger(X, T, r, b, v)
    base = call_given_I(S, X, T, r, b, v, I)
    if not maximise:
        return base, I, ht
    res = minimize_scalar(lambda x: -call_given_I(S, X, T, r, b, v, x), bounds=(I, Binf), method="bounded",
                          options={"xatol": 1e-10 * X})
    return max(base, -res.fun), res.x, ht


TODAY = ql.Date(18, 10, 2026); ql.Settings.instance().evaluationDate = TODAY
DC = ql.Actual365Fixed()


def ql_prices(S, K, days, r, q, v, is_call):
    p = ql.BlackScholesMertonProcess(ql.QuoteHandle(ql.SimpleQuote(S)),
        ql.YieldTermStructureHandle(ql.FlatForward(TODAY, q, DC)), ql.YieldTermStructureHandle(ql.FlatForward(TODAY, r, DC)),
        ql.BlackVolTermStructureHandle(ql.BlackConstantVol(TODAY, ql.NullCalendar(), v, DC)))
    o = ql.VanillaOption(ql.PlainVanillaPayoff(ql.Option.Call if is_call else ql.Option.Put, K), ql.AmericanExercise(TODAY, TODAY + days))
    o.setPricingEngine(ql.BjerksundStenslandApproximationEngine(p)); bjs = o.NPV()
    o.setPricingEngine(ql.QdFpAmericanEngine(p, ql.QdFpAmericanEngine.highPrecisionScheme())); qd = o.NPV()
    return bjs, qd


if __name__ == "__main__":
    print("1) Reproduction check: own BJS at I_formula vs QuantLib BJS, and maximised vs QdFp")
    cases = [("put r=40% q=5% s=15%", 100, 100, 0.40, 0.05, 0.15, False, [182, 365, 730]),
             ("put r=7.68% q=0.75% s=2.31%", 100, 100, 0.0768, 0.0075, 0.0231, False, [91, 120, 140, 155, 160, 182]),
             ("call r=5% q=1% s=25% (normal)", 100, 100, 0.05, 0.01, 0.25, True, [365])]
    for name, S, K, r, q, v, c, days in cases:
        print("  ", name)
        for d in days:
            T = d / 365.0
            mine, I, ht = american(S, K, T, r, q, v, c, False)
            mx, Imax, _ = american(S, K, T, r, q, v, c, True)
            bjs, qd = ql_prices(S, K, d, r, q, v, c)
            print(f"     {d:4d}d ht={ht:+.2f}  own {mine:.6f}  QL-BJS {bjs:.6f}  | max-I {mx:.6f} (I {I:.3f}->{Imax:.3f})  QdFp {qd:.6f}  err {mx / qd - 1:+.3%}")
