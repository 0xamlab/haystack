"""test_combustion.mojo — auto-generated tests for combustion library."""
from std.math import isnan, isinf
from combustion import stoichiometric_air_fuel_ratio, equivalence_ratio, excess_air_percentage, adiabatic_flame_temp_estimate, lower_heating_value_methane, thermal_efficiency, carnot_efficiency, brake_specific_fuel_consumption, combustion_efficiency, flame_speed_laminar, nox_formation_rate, heat_release_rate

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

    var _v_stoichiometric_air_fuel_ratio = stoichiometric_air_fuel_ratio(0.5, 0.5, 0.5)
    if is_finite(_v_stoichiometric_air_fuel_ratio): passed += 1; print("  ✅ combustion::stoichiometric_air_fuel_ratio =", _v_stoichiometric_air_fuel_ratio)
    else: failed += 1; print("  ❌ combustion::stoichiometric_air_fuel_ratio → non-finite:", _v_stoichiometric_air_fuel_ratio)
    var _v_equivalence_ratio = equivalence_ratio(0.5, 0.5)
    if is_finite(_v_equivalence_ratio): passed += 1; print("  ✅ combustion::equivalence_ratio =", _v_equivalence_ratio)
    else: failed += 1; print("  ❌ combustion::equivalence_ratio → non-finite:", _v_equivalence_ratio)
    var _v_excess_air_percentage = excess_air_percentage(0.5)
    if is_finite(_v_excess_air_percentage): passed += 1; print("  ✅ combustion::excess_air_percentage =", _v_excess_air_percentage)
    else: failed += 1; print("  ❌ combustion::excess_air_percentage → non-finite:", _v_excess_air_percentage)
    var _v_adiabatic_flame_temp_estimate = adiabatic_flame_temp_estimate(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_adiabatic_flame_temp_estimate): passed += 1; print("  ✅ combustion::adiabatic_flame_temp_estimate =", _v_adiabatic_flame_temp_estimate)
    else: failed += 1; print("  ❌ combustion::adiabatic_flame_temp_estimate → non-finite:", _v_adiabatic_flame_temp_estimate)
    var _v_lower_heating_value_methane = lower_heating_value_methane()
    if is_finite(_v_lower_heating_value_methane): passed += 1; print("  ✅ combustion::lower_heating_value_methane =", _v_lower_heating_value_methane)
    else: failed += 1; print("  ❌ combustion::lower_heating_value_methane → non-finite:", _v_lower_heating_value_methane)
    var _v_thermal_efficiency = thermal_efficiency(0.5, 0.5)
    if is_finite(_v_thermal_efficiency): passed += 1; print("  ✅ combustion::thermal_efficiency =", _v_thermal_efficiency)
    else: failed += 1; print("  ❌ combustion::thermal_efficiency → non-finite:", _v_thermal_efficiency)
    var _v_carnot_efficiency = carnot_efficiency(0.5, 0.5)
    if is_finite(_v_carnot_efficiency): passed += 1; print("  ✅ combustion::carnot_efficiency =", _v_carnot_efficiency)
    else: failed += 1; print("  ❌ combustion::carnot_efficiency → non-finite:", _v_carnot_efficiency)
    var _v_brake_specific_fuel_consumption = brake_specific_fuel_consumption(0.5, 0.5)
    if is_finite(_v_brake_specific_fuel_consumption): passed += 1; print("  ✅ combustion::brake_specific_fuel_consumption =", _v_brake_specific_fuel_consumption)
    else: failed += 1; print("  ❌ combustion::brake_specific_fuel_consumption → non-finite:", _v_brake_specific_fuel_consumption)
    var _v_combustion_efficiency = combustion_efficiency(0.5, 0.5)
    if is_finite(_v_combustion_efficiency): passed += 1; print("  ✅ combustion::combustion_efficiency =", _v_combustion_efficiency)
    else: failed += 1; print("  ❌ combustion::combustion_efficiency → non-finite:", _v_combustion_efficiency)
    var _v_flame_speed_laminar = flame_speed_laminar(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_flame_speed_laminar): passed += 1; print("  ✅ combustion::flame_speed_laminar =", _v_flame_speed_laminar)
    else: failed += 1; print("  ❌ combustion::flame_speed_laminar → non-finite:", _v_flame_speed_laminar)
    var _v_nox_formation_rate = nox_formation_rate(0.5, 0.5)
    if is_finite(_v_nox_formation_rate): passed += 1; print("  ✅ combustion::nox_formation_rate =", _v_nox_formation_rate)
    else: failed += 1; print("  ❌ combustion::nox_formation_rate → non-finite:", _v_nox_formation_rate)
    var _v_heat_release_rate = heat_release_rate(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_heat_release_rate): passed += 1; print("  ✅ combustion::heat_release_rate =", _v_heat_release_rate)
    else: failed += 1; print("  ❌ combustion::heat_release_rate → non-finite:", _v_heat_release_rate)

    print("  [combustion] Passed:", passed, "Failed:", failed)
