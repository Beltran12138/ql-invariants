# Hegic (Arbitrum) — model-free audit of live and historical option quotes

Date: 2026-10-19. Read-only: public Arbitrum RPC (`eth_call` / `eth_getLogs`), Sourcify-verified sources, GitHub `hegic/contracts`
(last commit 2022-12-26). Nothing was sent to Hegic or posted anywhere.

## Result

No violation that a buyer could hit was found. Two kinds of violation exist in the price parameters, but neither was
purchasable: no position was opened at a violating period while a violating state was live.

## What is checkable on Hegic, and what is not

- **American ≥ intrinsic is vacuous by design.** Every product is struck at or out of the money at purchase (strike =
  Chainlink spot × 1.00 or × 1.10, adaptive put 90–95 % of spot), and `buy` and `payOff` use the same oracle price.
  At purchase the intrinsic value is 0. (Buying and exercising in one transaction is otherwise possible:
  `OperationalTreasury.payOff` only needs a positive payoff and an unexpired position; `exerciseWindowDuration` = 2^48−1.)
- **Premiums do not depend on spot.** Polynomial pricers quote a quartic in the period, in USDC per unit. They are
  re-fitted off-chain very often (ETH ATM call pricer: 11,903 `SetCoefficients` since 2022-10; the latest updates are
  hours apart), so the spot dependence lives in the keeper, not in the contract.
- What remains model-free for these one-sided ask quotes: price non-decreasing in the period (same payoff, longer
  American life); upper bounds; dominance between products (a pointwise-smaller payoff must not cost more).

## Checks and results

| Check | Scope | Result |
|---|---|---|
| Reimplementation of Polynomial/Combine pricers in Solidity integer semantics | 947 live quotes, block 516251308 | 947/947 identical |
| M1 period monotonicity, live | 15 quoting strategies, 6-hour grid; pricers' full 7–90 d range hourly | 0 violations; quartic turning points at 135–172 d, beyond the 90 d cap in `setPeriodLimits` |
| Bounds, dominance, live | 110 % call ≤ ATM call; spread ≤ ATM call; spread ≤ max payoff; strap = sum of legs | 0 violations (1,993 hourly periods) |
| Adaptive put (unverified pricer 0x3614…) in strike | 90–95 % in 5 bp steps × 30–60 d; 80–120 % coarse | monotone, slope ≤ 1, convex |
| H-M1, every historical coefficient state | ~36k `SetCoefficients` states of 5 live polynomial pricers | some states decrease in the period at 60–90 d, by ~0.003 USDC per unit |
| H-D1, 110 % call above ATM call | 20,918 joint states of the two ETH call pricers | 111 real states (995 more were the int256-max "kill switch", which reverts and quotes nothing). 5 reach ≤ 30 d; each lasted ≤ ~4 min (906 blocks in total). The long-lived ones only at ≥ 73 d |
| Was anything bought inside an H-D1 state? | mint blocks of all 16,689 positions | 174 positions minted inside H-D1 windows; none at a violating period (all long positions there ≤ 60 d; the 90 d ones are inverse strategies with a fixed 90 d lock). None inside the 5 short windows |
| Spread premium > max payoff | all 263 long bull-call-spread purchases (Acquired events); width measured per contract from `payOffAmount` | 247 with measured width: max premium / max payoff 0.663, none > 1. 16 with unknown width: ≤ 0.888 even at the smallest width seen (10 %) |

## Mistakes made along the way (kept because they changed conclusions)

- First pass flagged 1,106 H-D1 states; 995 were pricers set to int256 max (disabled) — my checker ignored Solidity overflow.
- First pass of the spread check found one purchase paying 1.017 × max payoff; that assumed a 10 % width for every
  contract. The contract (0xe3f6…) has a 20 % width, measured from its own payoff; ratio 0.51.
- An early note said spreads would exceed their max payoff if ETH fell below ~$1,419; that ignored the keeper refits.

## Not covered

- Bid/ask crossing between inverse (short) strategies and the matching long strategies: needs the history of several
  dozen retired pricers.
- Retired strategies' own pricers (only the 5 live polynomial pricers' histories were replayed).
- Oracle latency (buying an "ATM" option when Chainlink lags the market): not a model-free pricing property.

Code: `scan.py`, `check.py`, `poly_exact.py`, `dominance.py`, `scan_adaptive.py`, `pricer_history.py`, `history_check.py`,
`history_d1.py`, `positions.py`, `mints.py`, `spread_overpay.py`, `spread_width.py`. Data: the matching `.json` files.
