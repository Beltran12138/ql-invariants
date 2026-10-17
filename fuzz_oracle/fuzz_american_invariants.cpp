/*
 Draft for QuantLib's fuzz-test-suite. NOT COMPILED YET (no C++ toolchain on the
 machine it was written on); the same checks, tolerances and input domain were
 calibrated in Python against QuantLib 1.44 in calibrate.py / triage.py:
 13000 samples, 0 false positives on QdFp, QdPlus and BAW; flags the
 Bjerksund-Stensland negative-carry fallback (#2903) and Ju below European
 (#2904).

 This file is part of QuantLib, a free-software/open-source library
 for financial quantitative analysts and developers - http://quantlib.org/

 QuantLib is free software: you can redistribute it and/or modify it
 under the terms of the QuantLib license.  You should have received a
 copy of the license along with this program; if not, please email
 <quantlib-dev@lists.sf.net>. The license is also available online at
 <https://www.quantlib.org/license.shtml>.

 This program is distributed in the hope that it will be useful, but WITHOUT
 ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 FOR A PARTICULAR PURPOSE.  See the license for more details.
*/

// Unlike fuzz_vanilla_option.cpp, which only checks that NPV() does not
// crash, this fuzzer checks properties that every arbitrage-free American
// price satisfies under any model:
//   1. A(T) >= exercise value
//   2. A(T) >= European value E(T)
//   3. A(T2) >= A(T) for T2 > T (an option with a later expiry can be
//      exercised as the earlier one); 1% relative slack for the
//      approximations' own small non-monotonicity
//   4. A(T) <= S for a call, A(T) <= K max(1, e^{-rT}) for a put
// A violation calls abort(), so it is reported like a crash.

#include <ql/exercise.hpp>
#include <ql/instruments/vanillaoption.hpp>
#include <ql/pricingengines/vanilla/analyticeuropeanengine.hpp>
#include <ql/pricingengines/vanilla/baroneadesiwhaleyengine.hpp>
#include <ql/pricingengines/vanilla/bjerksundstenslandengine.hpp>
#include <ql/pricingengines/vanilla/juquadraticengine.hpp>
#include <ql/pricingengines/vanilla/qdplusamericanengine.hpp>
#include <ql/processes/blackscholesprocess.hpp>
#include <ql/quotes/simplequote.hpp>
#include <ql/settings.hpp>
#include <ql/termstructures/volatility/equityfx/blackconstantvol.hpp>
#include <ql/termstructures/yield/flatforward.hpp>
#include <ql/time/calendars/nullcalendar.hpp>
#include <ql/time/daycounters/actual360.hpp>
#include <fuzzer/FuzzedDataProvider.h>
#include <algorithm>
#include <cmath>
#include <cstdlib>

using namespace QuantLib;

namespace {

    Real npv(const ext::shared_ptr<PricingEngine>& engine,
             const ext::shared_ptr<StrikedTypePayoff>& payoff,
             const ext::shared_ptr<Exercise>& exercise) {
        VanillaOption option(payoff, exercise);
        option.setPricingEngine(engine);
        return option.NPV();
    }

}

extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
    FuzzedDataProvider fdp(data, size);
    SavedSettings saved_settings;

    // same domain as fuzz_vanilla_option.cpp
    auto type = fdp.PickValueInArray({Option::Put, Option::Call});
    Real strike = fdp.ConsumeFloatingPointInRange<Real>(1.0, 500.0);
    Real spot = fdp.ConsumeFloatingPointInRange<Real>(1.0, 500.0);
    Rate r = fdp.ConsumeFloatingPointInRange<Real>(-0.02, 0.15);
    Rate q = fdp.ConsumeFloatingPointInRange<Real>(0.0, 0.10);
    Volatility vol = fdp.ConsumeFloatingPointInRange<Volatility>(0.01, 3.0);
    auto maturityDays = fdp.ConsumeIntegralInRange<int>(7, 3650);
    auto engineChoice = fdp.ConsumeIntegralInRange<int>(0, 3);

    Date today(15, January, 2025);
    Settings::instance().evaluationDate() = today;
    DayCounter dc = Actual360();

    auto process = ext::make_shared<BlackScholesMertonProcess>(
        Handle<Quote>(ext::make_shared<SimpleQuote>(spot)),
        Handle<YieldTermStructure>(ext::make_shared<FlatForward>(today, q, dc)),
        Handle<YieldTermStructure>(ext::make_shared<FlatForward>(today, r, dc)),
        Handle<BlackVolTermStructure>(
            ext::make_shared<BlackConstantVol>(today, NullCalendar(), vol, dc)));

    ext::shared_ptr<PricingEngine> engine;
    switch (engineChoice) {
      case 0:
        engine = ext::make_shared<BaroneAdesiWhaleyApproximationEngine>(process);
        break;
      case 1:
        engine = ext::make_shared<BjerksundStenslandApproximationEngine>(process);
        break;
      case 2:
        engine = ext::make_shared<JuQuadraticApproximationEngine>(process);
        break;
      default:
        engine = ext::make_shared<QdPlusAmericanEngine>(process);
        break;
    }

    auto payoff = ext::make_shared<PlainVanillaPayoff>(type, strike);
    Date exDate = today + maturityDays;
    Date laterDate = today + (maturityDays + std::max(1, maturityDays / 10));

    Real american = 0.0, americanLater = 0.0, european = 0.0;
    try {
        american = npv(engine, payoff,
                       ext::make_shared<AmericanExercise>(today, exDate));
        americanLater = npv(engine, payoff,
                            ext::make_shared<AmericanExercise>(today, laterDate));
        european = npv(ext::make_shared<AnalyticEuropeanEngine>(process), payoff,
                       ext::make_shared<EuropeanExercise>(exDate));
    } catch (const std::exception&) {
        // engines refuse some inputs by design (e.g. BAW with r < 0)
        return 0;
    }

    const Real floor = 1.0e-8 * std::max(spot, strike);
    const Real exerciseValue = (*payoff)(spot);
    const Time T = dc.yearFraction(today, exDate);
    const Real upper = type == Option::Call
                           ? spot
                           : strike * std::max(1.0, std::exp(-r * T));

    if (!std::isfinite(american) || !std::isfinite(americanLater))
        std::abort();
    if (american < exerciseValue - floor)
        std::abort();
    if (american < european - floor)
        std::abort();
    if (americanLater < american * (1.0 - 0.01) - floor)
        std::abort();
    if (american > upper + floor)
        std::abort();

    return 0;
}
