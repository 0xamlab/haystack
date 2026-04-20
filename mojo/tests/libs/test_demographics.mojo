"""test_demographics.mojo — auto-generated tests for demographics library."""
from std.math import isnan, isinf
from demographics import crude_birth_rate, crude_death_rate, natural_increase_rate, total_fertility_rate, infant_mortality_rate, life_expectancy_approx, dependency_ratio, sex_ratio, population_growth_rate, doubling_time, urbanization_rate, median_age_estimate

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

    var _v_crude_birth_rate = crude_birth_rate(0.5, 0.5)
    if is_finite(_v_crude_birth_rate): passed += 1; print("  ✅ demographics::crude_birth_rate =", _v_crude_birth_rate)
    else: failed += 1; print("  ❌ demographics::crude_birth_rate → non-finite:", _v_crude_birth_rate)
    var _v_crude_death_rate = crude_death_rate(0.5, 0.5)
    if is_finite(_v_crude_death_rate): passed += 1; print("  ✅ demographics::crude_death_rate =", _v_crude_death_rate)
    else: failed += 1; print("  ❌ demographics::crude_death_rate → non-finite:", _v_crude_death_rate)
    var _v_natural_increase_rate = natural_increase_rate(0.5, 0.5)
    if is_finite(_v_natural_increase_rate): passed += 1; print("  ✅ demographics::natural_increase_rate =", _v_natural_increase_rate)
    else: failed += 1; print("  ❌ demographics::natural_increase_rate → non-finite:", _v_natural_increase_rate)
    var _v_total_fertility_rate = total_fertility_rate(0.5, 0.5)
    if is_finite(_v_total_fertility_rate): passed += 1; print("  ✅ demographics::total_fertility_rate =", _v_total_fertility_rate)
    else: failed += 1; print("  ❌ demographics::total_fertility_rate → non-finite:", _v_total_fertility_rate)
    var _v_infant_mortality_rate = infant_mortality_rate(0.5, 0.5)
    if is_finite(_v_infant_mortality_rate): passed += 1; print("  ✅ demographics::infant_mortality_rate =", _v_infant_mortality_rate)
    else: failed += 1; print("  ❌ demographics::infant_mortality_rate → non-finite:", _v_infant_mortality_rate)
    var _v_life_expectancy_approx = life_expectancy_approx(0.5, 0.5)
    if is_finite(_v_life_expectancy_approx): passed += 1; print("  ✅ demographics::life_expectancy_approx =", _v_life_expectancy_approx)
    else: failed += 1; print("  ❌ demographics::life_expectancy_approx → non-finite:", _v_life_expectancy_approx)
    var _v_dependency_ratio = dependency_ratio(0.5, 0.5, 0.5)
    if is_finite(_v_dependency_ratio): passed += 1; print("  ✅ demographics::dependency_ratio =", _v_dependency_ratio)
    else: failed += 1; print("  ❌ demographics::dependency_ratio → non-finite:", _v_dependency_ratio)
    var _v_sex_ratio = sex_ratio(0.5, 0.5)
    if is_finite(_v_sex_ratio): passed += 1; print("  ✅ demographics::sex_ratio =", _v_sex_ratio)
    else: failed += 1; print("  ❌ demographics::sex_ratio → non-finite:", _v_sex_ratio)
    var _v_population_growth_rate = population_growth_rate(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_population_growth_rate): passed += 1; print("  ✅ demographics::population_growth_rate =", _v_population_growth_rate)
    else: failed += 1; print("  ❌ demographics::population_growth_rate → non-finite:", _v_population_growth_rate)
    var _v_doubling_time = doubling_time(0.5)
    if is_finite(_v_doubling_time): passed += 1; print("  ✅ demographics::doubling_time =", _v_doubling_time)
    else: failed += 1; print("  ❌ demographics::doubling_time → non-finite:", _v_doubling_time)
    var _v_urbanization_rate = urbanization_rate(0.5, 0.5)
    if is_finite(_v_urbanization_rate): passed += 1; print("  ✅ demographics::urbanization_rate =", _v_urbanization_rate)
    else: failed += 1; print("  ❌ demographics::urbanization_rate → non-finite:", _v_urbanization_rate)
    var _v_median_age_estimate = median_age_estimate(0.5, 0.5)
    if is_finite(_v_median_age_estimate): passed += 1; print("  ✅ demographics::median_age_estimate =", _v_median_age_estimate)
    else: failed += 1; print("  ❌ demographics::median_age_estimate → non-finite:", _v_median_age_estimate)

    print("  [demographics] Passed:", passed, "Failed:", failed)
