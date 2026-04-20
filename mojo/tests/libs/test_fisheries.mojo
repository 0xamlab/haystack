"""test_fisheries.mojo — auto-generated tests for fisheries library."""
from std.math import isnan, isinf
from fisheries import catch_per_unit_effort, maximum_sustainable_yield, biomass_at_msy, schaefer_surplus_production, fishing_mortality, total_mortality, exploitation_rate, survival_rate, von_bertalanffy_length, condition_factor, gonadosomatic_index, stock_recruitment_bevholt

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

    var _v_catch_per_unit_effort = catch_per_unit_effort(0.5, 0.5)
    if is_finite(_v_catch_per_unit_effort): passed += 1; print("  ✅ fisheries::catch_per_unit_effort =", _v_catch_per_unit_effort)
    else: failed += 1; print("  ❌ fisheries::catch_per_unit_effort → non-finite:", _v_catch_per_unit_effort)
    var _v_maximum_sustainable_yield = maximum_sustainable_yield(0.5, 0.5)
    if is_finite(_v_maximum_sustainable_yield): passed += 1; print("  ✅ fisheries::maximum_sustainable_yield =", _v_maximum_sustainable_yield)
    else: failed += 1; print("  ❌ fisheries::maximum_sustainable_yield → non-finite:", _v_maximum_sustainable_yield)
    var _v_biomass_at_msy = biomass_at_msy(0.5)
    if is_finite(_v_biomass_at_msy): passed += 1; print("  ✅ fisheries::biomass_at_msy =", _v_biomass_at_msy)
    else: failed += 1; print("  ❌ fisheries::biomass_at_msy → non-finite:", _v_biomass_at_msy)
    var _v_schaefer_surplus_production = schaefer_surplus_production(0.5, 0.5, 0.5)
    if is_finite(_v_schaefer_surplus_production): passed += 1; print("  ✅ fisheries::schaefer_surplus_production =", _v_schaefer_surplus_production)
    else: failed += 1; print("  ❌ fisheries::schaefer_surplus_production → non-finite:", _v_schaefer_surplus_production)
    var _v_fishing_mortality = fishing_mortality(0.5, 0.5)
    if is_finite(_v_fishing_mortality): passed += 1; print("  ✅ fisheries::fishing_mortality =", _v_fishing_mortality)
    else: failed += 1; print("  ❌ fisheries::fishing_mortality → non-finite:", _v_fishing_mortality)
    var _v_total_mortality = total_mortality(0.5, 0.5)
    if is_finite(_v_total_mortality): passed += 1; print("  ✅ fisheries::total_mortality =", _v_total_mortality)
    else: failed += 1; print("  ❌ fisheries::total_mortality → non-finite:", _v_total_mortality)
    var _v_exploitation_rate = exploitation_rate(0.5, 0.5)
    if is_finite(_v_exploitation_rate): passed += 1; print("  ✅ fisheries::exploitation_rate =", _v_exploitation_rate)
    else: failed += 1; print("  ❌ fisheries::exploitation_rate → non-finite:", _v_exploitation_rate)
    var _v_survival_rate = survival_rate(0.5)
    if is_finite(_v_survival_rate): passed += 1; print("  ✅ fisheries::survival_rate =", _v_survival_rate)
    else: failed += 1; print("  ❌ fisheries::survival_rate → non-finite:", _v_survival_rate)
    var _v_von_bertalanffy_length = von_bertalanffy_length(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_von_bertalanffy_length): passed += 1; print("  ✅ fisheries::von_bertalanffy_length =", _v_von_bertalanffy_length)
    else: failed += 1; print("  ❌ fisheries::von_bertalanffy_length → non-finite:", _v_von_bertalanffy_length)
    var _v_condition_factor = condition_factor(0.5, 0.5)
    if is_finite(_v_condition_factor): passed += 1; print("  ✅ fisheries::condition_factor =", _v_condition_factor)
    else: failed += 1; print("  ❌ fisheries::condition_factor → non-finite:", _v_condition_factor)
    var _v_gonadosomatic_index = gonadosomatic_index(0.5, 0.5)
    if is_finite(_v_gonadosomatic_index): passed += 1; print("  ✅ fisheries::gonadosomatic_index =", _v_gonadosomatic_index)
    else: failed += 1; print("  ❌ fisheries::gonadosomatic_index → non-finite:", _v_gonadosomatic_index)
    var _v_stock_recruitment_bevholt = stock_recruitment_bevholt(0.5, 0.5, 0.5)
    if is_finite(_v_stock_recruitment_bevholt): passed += 1; print("  ✅ fisheries::stock_recruitment_bevholt =", _v_stock_recruitment_bevholt)
    else: failed += 1; print("  ❌ fisheries::stock_recruitment_bevholt → non-finite:", _v_stock_recruitment_bevholt)

    print("  [fisheries] Passed:", passed, "Failed:", failed)
