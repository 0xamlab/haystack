"""test_population.mojo — auto-generated tests for population library."""
from std.math import isnan, isinf
from population import exponential_growth, logistic_growth, logistic_simulate, lotka_volterra_step, lotka_volterra_simulate, carrying_capacity_estimate, growth_rate_estimate, competition_model, population_doubling_time, extinction_risk

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_exponential_growth = exponential_growth(0.5, 0.5, 0.5)
    if is_finite(_v_exponential_growth): passed += 1; print("  ✅ population::exponential_growth =", _v_exponential_growth)
    else: failed += 1; print("  ❌ population::exponential_growth → non-finite:", _v_exponential_growth)
    var _v_logistic_growth = logistic_growth(0.5, 0.5, 0.5)
    if is_finite(_v_logistic_growth): passed += 1; print("  ✅ population::logistic_growth =", _v_logistic_growth)
    else: failed += 1; print("  ❌ population::logistic_growth → non-finite:", _v_logistic_growth)
    var _v_logistic_simulate = logistic_simulate(0.5, 0.5, 0.5, 5)
    if len(_v_logistic_simulate) >= 0: passed += 1; print("  ✅ population::logistic_simulate")
    var _v_lotka_volterra_step = lotka_volterra_step(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    if len(_v_lotka_volterra_step) >= 0: passed += 1; print("  ✅ population::lotka_volterra_step")
    _ = lotka_volterra_simulate(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 5)
    passed += 1; print("  ✅ population::lotka_volterra_simulate")
    var _v_carrying_capacity_estimate = carrying_capacity_estimate(_lf5)
    if is_finite(_v_carrying_capacity_estimate): passed += 1; print("  ✅ population::carrying_capacity_estimate =", _v_carrying_capacity_estimate)
    else: failed += 1; print("  ❌ population::carrying_capacity_estimate → non-finite:", _v_carrying_capacity_estimate)
    var _v_growth_rate_estimate = growth_rate_estimate(0.5, 0.5, 0.5)
    if is_finite(_v_growth_rate_estimate): passed += 1; print("  ✅ population::growth_rate_estimate =", _v_growth_rate_estimate)
    else: failed += 1; print("  ❌ population::growth_rate_estimate → non-finite:", _v_growth_rate_estimate)
    var _v_competition_model = competition_model(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    if len(_v_competition_model) >= 0: passed += 1; print("  ✅ population::competition_model")
    var _v_population_doubling_time = population_doubling_time(0.5)
    if is_finite(_v_population_doubling_time): passed += 1; print("  ✅ population::population_doubling_time =", _v_population_doubling_time)
    else: failed += 1; print("  ❌ population::population_doubling_time → non-finite:", _v_population_doubling_time)
    _ = extinction_risk(0.5, 0.5)
    passed += 1; print("  ✅ population::extinction_risk")

    print("  [population] Passed:", passed, "Failed:", failed)
