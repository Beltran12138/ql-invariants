"""Does the #930 signature still exist in QuantLib 1.44?

Bond: 10% semiannual, call at 100 (clean) on a single date close to today.
Model-free expectations (near-zero vol, flat 1% curve):
  - callable clean price <= straight clean price
  - if the call is certain (coupon 10% >> rate 1%), dirty price ~= PV of
    (100 + accrued coupon paid at call) -> clean price should sit near 100,
    certainly not ~5 points above it.
We sweep the call date day by day across a coupon date and print the price.
"""
import QuantLib as ql
from qlinv import bonds as B

today = ql.Date(3, 11, 2020)
B.setup(today)
curve = B.flat_curve(0.01)
sched = B.schedule(ql.Date(15, 5, 2016), ql.Date(15, 5, 2026))
straight = B.straight_bond(sched, 0.10)
s_clean, s_dirty = B.price_straight(straight, curve)
print(f"QuantLib {ql.__version__}  today={today}  straight clean={s_clean:.4f} dirty={s_dirty:.4f}")
print("next coupon dates:", [str(d) for d in sched if d > today][:2])
print(f"{'call date':>22} {'clean':>9} {'dirty':>9} {'clean-100':>10}")
for k in range(1, 22):
    cd = today + k
    bond = B.callable_bond(sched, 0.10, [cd])
    c, d = B.price_callable(bond, curve)
    flag = "  <-- coupon date" if cd in list(sched) else ""
    print(f"{str(cd):>22} {c:9.4f} {d:9.4f} {c-100:10.4f}{flag}")
