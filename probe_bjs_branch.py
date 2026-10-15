"""Replicate the branch selection in QuantLib v1.44 BjerksundStenslandApproximationEngine
(americanCallApproximation, bjerksundstenslandengine.cpp L176-216) for the put case,
which is priced as a call via put-call symmetry (spot<->strike, r<->q)."""
import math

S, K, r, q, vol = 100.0, 100.0, 0.0768, 0.0075, 0.0231
for days in [91, 120, 150, 182, 365]:
    T = days / 365
    # put -> call symmetry
    s, x = K, S
    rfD, dD = math.exp(-q * T), math.exp(-r * T)   # swapped discounts
    v = vol * vol * T
    bT = math.log(dD / rfD)
    rT = math.log(1.0 / rfD)
    beta = (0.5 - bT / v) + math.sqrt(max(0.0, (bT / v - 0.5) ** 2 + 2.0 * rT / v))
    Binf = beta / (beta - 1.0) * x
    B0 = x if bT == rT else max(x, rT / (rT - bT) * x)
    ht = -(bT + 2.0 * math.sqrt(v)) * B0 / (Binf - B0)
    I = B0 + (Binf - B0) * (1 - math.exp(ht))
    fwd = s * dD / rfD
    qq = math.log(I / fwd) / math.sqrt(v)
    branch = "immediate" if s >= I else ("EUROPEAN (q>12.5 'run away boundary')" if qq > 12.5 else "approx")
    print(f"T={days:4d}d beta={beta:9.3f} B0={B0:8.3f} Binf={Binf:8.3f} I={I:8.3f} fwd={fwd:8.3f} q={qq:7.2f} -> {branch}")
