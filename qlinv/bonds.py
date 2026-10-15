"""Callable / straight fixed-rate bond pricers on a flat curve (QuantLib Python)."""
import QuantLib as ql

CAL = ql.NullCalendar()  # no holiday adjustment unless a test asks for one


def setup(eval_date):
    ql.Settings.instance().evaluationDate = eval_date


def schedule(issue, maturity, tenor=ql.Period(ql.Semiannual), cal=CAL,
             conv=ql.Unadjusted):
    return ql.Schedule(issue, maturity, tenor, cal, conv, conv,
                       ql.DateGeneration.Backward, False)


def flat_curve(rate, dc=ql.Actual365Fixed()):
    today = ql.Settings.instance().evaluationDate
    return ql.YieldTermStructureHandle(ql.FlatForward(today, rate, dc, ql.Continuous))


def callability(call_dates, price=100.0, kind=ql.Callability.Call):
    cs = ql.CallabilitySchedule()
    for d in call_dates:
        cs.append(ql.Callability(ql.BondPrice(price, ql.BondPrice.Clean), kind, d))
    return cs


def callable_bond(sched, coupon, call_dates, call_price=100.0, settle_days=0,
                  dc=ql.ActualActual(ql.ActualActual.Bond), kind=ql.Callability.Call):
    return ql.CallableFixedRateBond(settle_days, 100.0, sched, [coupon], dc,
                                    ql.Unadjusted, 100.0, sched.startDate(),
                                    callability(call_dates, call_price, kind))


def straight_bond(sched, coupon, settle_days=0, dc=ql.ActualActual(ql.ActualActual.Bond)):
    return ql.FixedRateBond(settle_days, 100.0, sched, [coupon], dc)


def tree_engine(curve, a=0.03, sigma=1e-6, grid=200):
    model = ql.HullWhite(curve, a, sigma)
    return ql.TreeCallableFixedRateBondEngine(model, grid)


def price_callable(bond, curve, **eng):
    bond.setPricingEngine(tree_engine(curve, **eng))
    return bond.cleanPrice(), bond.dirtyPrice()


def price_straight(bond, curve):
    bond.setPricingEngine(ql.DiscountingBondEngine(curve))
    return bond.cleanPrice(), bond.dirtyPrice()
