"""test_geotechnical.mojo — auto-generated tests for geotechnical library."""
from std.math import isnan, isinf
from geotechnical import bearing_capacity_terzaghi, effective_stress, overburden_pressure, coefficient_of_earth_pressure_at_rest, rankine_ka, rankine_kp, active_earth_pressure, settlement_elastic, factor_of_safety_slope, void_ratio, porosity_from_void_ratio, degree_of_saturation

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

    var _v_bearing_capacity_terzaghi = bearing_capacity_terzaghi(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_bearing_capacity_terzaghi): passed += 1; print("  ✅ geotechnical::bearing_capacity_terzaghi =", _v_bearing_capacity_terzaghi)
    else: failed += 1; print("  ❌ geotechnical::bearing_capacity_terzaghi → non-finite:", _v_bearing_capacity_terzaghi)
    var _v_effective_stress = effective_stress(0.5, 0.5)
    if is_finite(_v_effective_stress): passed += 1; print("  ✅ geotechnical::effective_stress =", _v_effective_stress)
    else: failed += 1; print("  ❌ geotechnical::effective_stress → non-finite:", _v_effective_stress)
    var _v_overburden_pressure = overburden_pressure(0.5, 0.5)
    if is_finite(_v_overburden_pressure): passed += 1; print("  ✅ geotechnical::overburden_pressure =", _v_overburden_pressure)
    else: failed += 1; print("  ❌ geotechnical::overburden_pressure → non-finite:", _v_overburden_pressure)
    var _v_coefficient_of_earth_pressure_at_rest = coefficient_of_earth_pressure_at_rest(0.5)
    if is_finite(_v_coefficient_of_earth_pressure_at_rest): passed += 1; print("  ✅ geotechnical::coefficient_of_earth_pressure_at_rest =", _v_coefficient_of_earth_pressure_at_rest)
    else: failed += 1; print("  ❌ geotechnical::coefficient_of_earth_pressure_at_rest → non-finite:", _v_coefficient_of_earth_pressure_at_rest)
    var _v_rankine_ka = rankine_ka(0.5)
    if is_finite(_v_rankine_ka): passed += 1; print("  ✅ geotechnical::rankine_ka =", _v_rankine_ka)
    else: failed += 1; print("  ❌ geotechnical::rankine_ka → non-finite:", _v_rankine_ka)
    var _v_rankine_kp = rankine_kp(0.5)
    if is_finite(_v_rankine_kp): passed += 1; print("  ✅ geotechnical::rankine_kp =", _v_rankine_kp)
    else: failed += 1; print("  ❌ geotechnical::rankine_kp → non-finite:", _v_rankine_kp)
    var _v_active_earth_pressure = active_earth_pressure(0.5, 0.5, 0.5)
    if is_finite(_v_active_earth_pressure): passed += 1; print("  ✅ geotechnical::active_earth_pressure =", _v_active_earth_pressure)
    else: failed += 1; print("  ❌ geotechnical::active_earth_pressure → non-finite:", _v_active_earth_pressure)
    var _v_settlement_elastic = settlement_elastic(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_settlement_elastic): passed += 1; print("  ✅ geotechnical::settlement_elastic =", _v_settlement_elastic)
    else: failed += 1; print("  ❌ geotechnical::settlement_elastic → non-finite:", _v_settlement_elastic)
    var _v_factor_of_safety_slope = factor_of_safety_slope(0.5, 0.5)
    if is_finite(_v_factor_of_safety_slope): passed += 1; print("  ✅ geotechnical::factor_of_safety_slope =", _v_factor_of_safety_slope)
    else: failed += 1; print("  ❌ geotechnical::factor_of_safety_slope → non-finite:", _v_factor_of_safety_slope)
    var _v_void_ratio = void_ratio(0.5)
    if is_finite(_v_void_ratio): passed += 1; print("  ✅ geotechnical::void_ratio =", _v_void_ratio)
    else: failed += 1; print("  ❌ geotechnical::void_ratio → non-finite:", _v_void_ratio)
    var _v_porosity_from_void_ratio = porosity_from_void_ratio(0.5)
    if is_finite(_v_porosity_from_void_ratio): passed += 1; print("  ✅ geotechnical::porosity_from_void_ratio =", _v_porosity_from_void_ratio)
    else: failed += 1; print("  ❌ geotechnical::porosity_from_void_ratio → non-finite:", _v_porosity_from_void_ratio)
    var _v_degree_of_saturation = degree_of_saturation(0.5, 0.5, 0.5)
    if is_finite(_v_degree_of_saturation): passed += 1; print("  ✅ geotechnical::degree_of_saturation =", _v_degree_of_saturation)
    else: failed += 1; print("  ❌ geotechnical::degree_of_saturation → non-finite:", _v_degree_of_saturation)

    print("  [geotechnical] Passed:", passed, "Failed:", failed)
