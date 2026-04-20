"""test_welding.mojo — auto-generated tests for welding library."""
from std.math import isnan, isinf
from welding import heat_input, heat_input_kj, preheat_carbon_equivalent, cooling_rate_2d, weld_dilution, electrode_consumption, welding_speed_from_deposition, joint_efficiency, throat_thickness_fillet, allowable_shear_fillet, interpass_temperature_max, hydrogen_cracking_risk

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

    var _v_heat_input = heat_input(0.5, 0.5, 0.5)
    if is_finite(_v_heat_input): passed += 1; print("  ✅ welding::heat_input =", _v_heat_input)
    else: failed += 1; print("  ❌ welding::heat_input → non-finite:", _v_heat_input)
    var _v_heat_input_kj = heat_input_kj(0.5, 0.5, 0.5)
    if is_finite(_v_heat_input_kj): passed += 1; print("  ✅ welding::heat_input_kj =", _v_heat_input_kj)
    else: failed += 1; print("  ❌ welding::heat_input_kj → non-finite:", _v_heat_input_kj)
    var _v_preheat_carbon_equivalent = preheat_carbon_equivalent(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_preheat_carbon_equivalent): passed += 1; print("  ✅ welding::preheat_carbon_equivalent =", _v_preheat_carbon_equivalent)
    else: failed += 1; print("  ❌ welding::preheat_carbon_equivalent → non-finite:", _v_preheat_carbon_equivalent)
    var _v_cooling_rate_2d = cooling_rate_2d(0.5, 0.5, 0.5)
    if is_finite(_v_cooling_rate_2d): passed += 1; print("  ✅ welding::cooling_rate_2d =", _v_cooling_rate_2d)
    else: failed += 1; print("  ❌ welding::cooling_rate_2d → non-finite:", _v_cooling_rate_2d)
    var _v_weld_dilution = weld_dilution(0.5, 0.5)
    if is_finite(_v_weld_dilution): passed += 1; print("  ✅ welding::weld_dilution =", _v_weld_dilution)
    else: failed += 1; print("  ❌ welding::weld_dilution → non-finite:", _v_weld_dilution)
    var _v_electrode_consumption = electrode_consumption(0.5, 0.5)
    if is_finite(_v_electrode_consumption): passed += 1; print("  ✅ welding::electrode_consumption =", _v_electrode_consumption)
    else: failed += 1; print("  ❌ welding::electrode_consumption → non-finite:", _v_electrode_consumption)
    var _v_welding_speed_from_deposition = welding_speed_from_deposition(0.5, 0.5, 0.5)
    if is_finite(_v_welding_speed_from_deposition): passed += 1; print("  ✅ welding::welding_speed_from_deposition =", _v_welding_speed_from_deposition)
    else: failed += 1; print("  ❌ welding::welding_speed_from_deposition → non-finite:", _v_welding_speed_from_deposition)
    var _v_joint_efficiency = joint_efficiency(0.5, 0.5)
    if is_finite(_v_joint_efficiency): passed += 1; print("  ✅ welding::joint_efficiency =", _v_joint_efficiency)
    else: failed += 1; print("  ❌ welding::joint_efficiency → non-finite:", _v_joint_efficiency)
    var _v_throat_thickness_fillet = throat_thickness_fillet(0.5)
    if is_finite(_v_throat_thickness_fillet): passed += 1; print("  ✅ welding::throat_thickness_fillet =", _v_throat_thickness_fillet)
    else: failed += 1; print("  ❌ welding::throat_thickness_fillet → non-finite:", _v_throat_thickness_fillet)
    var _v_allowable_shear_fillet = allowable_shear_fillet(0.5, 0.5, 0.5)
    if is_finite(_v_allowable_shear_fillet): passed += 1; print("  ✅ welding::allowable_shear_fillet =", _v_allowable_shear_fillet)
    else: failed += 1; print("  ❌ welding::allowable_shear_fillet → non-finite:", _v_allowable_shear_fillet)
    var _v_interpass_temperature_max = interpass_temperature_max(0.5)
    if is_finite(_v_interpass_temperature_max): passed += 1; print("  ✅ welding::interpass_temperature_max =", _v_interpass_temperature_max)
    else: failed += 1; print("  ❌ welding::interpass_temperature_max → non-finite:", _v_interpass_temperature_max)
    var _v_hydrogen_cracking_risk = hydrogen_cracking_risk(0.5, 0.5, 0.5)
    if is_finite(_v_hydrogen_cracking_risk): passed += 1; print("  ✅ welding::hydrogen_cracking_risk =", _v_hydrogen_cracking_risk)
    else: failed += 1; print("  ❌ welding::hydrogen_cracking_risk → non-finite:", _v_hydrogen_cracking_risk)

    print("  [welding] Passed:", passed, "Failed:", failed)
