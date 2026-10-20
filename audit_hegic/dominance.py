"""Dominance checks between products (one-sided ask quotes: a payoff that is pointwise <= another available payoff,
same asset, same period, must not cost more). Uses the exact reimplementation in poly_exact.premium.
  D1  110% call <= ATM call
  D2  bull call spread (ATM / 110%, payoff <= 0.1 S) <= ATM call, and <= 0.1 S
  D3  strap and strangle legs: bundle <= sum of separately available legs (equality = no bundle discount)
Spot is the scan block's Chainlink price (premiums of these pricers do not depend on it).
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import poly_exact as px

ETH_ATM_CALL, ETH_OTM_CALL, ETH_ATM_PUT = "0xc62a0b7e480a23bdcfe13ea08bdacedc278a14c1", "0x6316bc5f5df141ae88c436fe6047d334f1b7e485", "0xb72fc913e45522cd721252476fefb7f50a65e23a"
SPREAD, STRAP, STRANGLE = "0x3bc74c993e1e85ffb5e242402aec3e90dcfa249f", "0x4093df7bcb6a0ef34e5d56a8b05bd7966e2f6549", "0xe76245e5a95f2a6ed154a6d8f1b66f0b5dd772e5"
S = px.Q["feeds"]["0x639fe6ab55c921f74e7fac1ee960c0b6293ba612"]["answer"] / 1e8
pr = lambda p, t: px.premium(p, t, 10 ** 18, 18) / 1e6
v = {k: 0 for k in ["D1", "D2a", "D2b", "D3"]}
n = 0
for t in range(7 * 86400, 90 * 86400 + 1, 3600):
    n += 1
    atm, otm, put = pr(ETH_ATM_CALL, t), pr(ETH_OTM_CALL, t), pr(ETH_ATM_PUT, t)
    v["D1"] += otm > atm
    v["D2a"] += pr(SPREAD, t) > atm
    v["D2b"] += pr(SPREAD, t) > 0.1 * S
    v["D3"] += pr(STRAP, t) > put + 2 * atm + 1e-6
for t in (7, 14, 30, 60, 90):
    T = t * 86400
    print(f"{t:3d}d  ATM call {pr(ETH_ATM_CALL, T):8.2f}  110% call {pr(ETH_OTM_CALL, T):7.2f}  spread {pr(SPREAD, T):7.2f} "
          f"(cap 0.1S = {0.1 * S:.2f}; ATM-OTM = {pr(ETH_ATM_CALL, T) - pr(ETH_OTM_CALL, T):.2f})  ATM put {pr(ETH_ATM_PUT, T):8.2f}  strap {pr(STRAP, T):8.2f}")
print(f"\nhourly 7-90d, {n} periods: violations {v}")
