"""test_distillation.mojo — auto-generated tests for distillation library."""
from std.math import isnan, isinf
from distillation import relative_volatility, min_reflux_underwood, actual_reflux, fenske_min_stages, gilliland_stages, mccabe_thiele_operating_line_enriching, mccabe_thiele_operating_line_stripping, boiling_point_elevation, raoults_law_partial_pressure, daltons_law_total_pressure, stage_efficiency, heat_duty_condenser

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

    var _v_relative_volatility = relative_volatility(0.5, 0.5)
    if is_finite(_v_relative_volatility): passed += 1; print("  ✅ distillation::relative_volatility =", _v_relative_volatility)
    else: failed += 1; print("  ❌ distillation::relative_volatility → non-finite:", _v_relative_volatility)
    var _v_min_reflux_underwood = min_reflux_underwood(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_min_reflux_underwood): passed += 1; print("  ✅ distillation::min_reflux_underwood =", _v_min_reflux_underwood)
    else: failed += 1; print("  ❌ distillation::min_reflux_underwood → non-finite:", _v_min_reflux_underwood)
    var _v_actual_reflux = actual_reflux(0.5, 0.5)
    if is_finite(_v_actual_reflux): passed += 1; print("  ✅ distillation::actual_reflux =", _v_actual_reflux)
    else: failed += 1; print("  ❌ distillation::actual_reflux → non-finite:", _v_actual_reflux)
    var _v_fenske_min_stages = fenske_min_stages(0.5, 0.5, 0.5)
    if is_finite(_v_fenske_min_stages): passed += 1; print("  ✅ distillation::fenske_min_stages =", _v_fenske_min_stages)
    else: failed += 1; print("  ❌ distillation::fenske_min_stages → non-finite:", _v_fenske_min_stages)
    var _v_gilliland_stages = gilliland_stages(0.5, 0.5, 0.5)
    if is_finite(_v_gilliland_stages): passed += 1; print("  ✅ distillation::gilliland_stages =", _v_gilliland_stages)
    else: failed += 1; print("  ❌ distillation::gilliland_stages → non-finite:", _v_gilliland_stages)
    var _v_mccabe_thiele_operating_line_enriching = mccabe_thiele_operating_line_enriching(0.5, 0.5, 0.5)
    if is_finite(_v_mccabe_thiele_operating_line_enriching): passed += 1; print("  ✅ distillation::mccabe_thiele_operating_line_enriching =", _v_mccabe_thiele_operating_line_enriching)
    else: failed += 1; print("  ❌ distillation::mccabe_thiele_operating_line_enriching → non-finite:", _v_mccabe_thiele_operating_line_enriching)
    var _v_mccabe_thiele_operating_line_stripping = mccabe_thiele_operating_line_stripping(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_mccabe_thiele_operating_line_stripping): passed += 1; print("  ✅ distillation::mccabe_thiele_operating_line_stripping =", _v_mccabe_thiele_operating_line_stripping)
    else: failed += 1; print("  ❌ distillation::mccabe_thiele_operating_line_stripping → non-finite:", _v_mccabe_thiele_operating_line_stripping)
    var _v_boiling_point_elevation = boiling_point_elevation(0.5, 0.5)
    if is_finite(_v_boiling_point_elevation): passed += 1; print("  ✅ distillation::boiling_point_elevation =", _v_boiling_point_elevation)
    else: failed += 1; print("  ❌ distillation::boiling_point_elevation → non-finite:", _v_boiling_point_elevation)
    var _v_raoults_law_partial_pressure = raoults_law_partial_pressure(0.5, 0.5)
    if is_finite(_v_raoults_law_partial_pressure): passed += 1; print("  ✅ distillation::raoults_law_partial_pressure =", _v_raoults_law_partial_pressure)
    else: failed += 1; print("  ❌ distillation::raoults_law_partial_pressure → non-finite:", _v_raoults_law_partial_pressure)
    var _v_daltons_law_total_pressure = daltons_law_total_pressure(0.5, 0.5)
    if is_finite(_v_daltons_law_total_pressure): passed += 1; print("  ✅ distillation::daltons_law_total_pressure =", _v_daltons_law_total_pressure)
    else: failed += 1; print("  ❌ distillation::daltons_law_total_pressure → non-finite:", _v_daltons_law_total_pressure)
    var _v_stage_efficiency = stage_efficiency(0.5, 0.5, 0.5)
    if is_finite(_v_stage_efficiency): passed += 1; print("  ✅ distillation::stage_efficiency =", _v_stage_efficiency)
    else: failed += 1; print("  ❌ distillation::stage_efficiency → non-finite:", _v_stage_efficiency)
    var _v_heat_duty_condenser = heat_duty_condenser(0.5, 0.5)
    if is_finite(_v_heat_duty_condenser): passed += 1; print("  ✅ distillation::heat_duty_condenser =", _v_heat_duty_condenser)
    else: failed += 1; print("  ❌ distillation::heat_duty_condenser → non-finite:", _v_heat_duty_condenser)

    print("  [distillation] Passed:", passed, "Failed:", failed)
