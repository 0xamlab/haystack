"""test_adhesives.mojo — auto-generated tests for adhesives library."""
from std.math import isnan, isinf
from adhesives import lap_shear_strength, peel_strength, bond_line_thickness, coverage_rate, pot_life_temperature_adjusted, cure_time_temperature, joint_efficiency, thermal_cycle_life, viscosity_temperature, surface_energy_contact_angle, open_time_estimate, bond_area_from_load

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

    var _v_lap_shear_strength = lap_shear_strength(0.5, 0.5)
    if is_finite(_v_lap_shear_strength): passed += 1; print("  ✅ adhesives::lap_shear_strength =", _v_lap_shear_strength)
    else: failed += 1; print("  ❌ adhesives::lap_shear_strength → non-finite:", _v_lap_shear_strength)
    var _v_peel_strength = peel_strength(0.5, 0.5)
    if is_finite(_v_peel_strength): passed += 1; print("  ✅ adhesives::peel_strength =", _v_peel_strength)
    else: failed += 1; print("  ❌ adhesives::peel_strength → non-finite:", _v_peel_strength)
    var _v_bond_line_thickness = bond_line_thickness(0.5)
    if is_finite(_v_bond_line_thickness): passed += 1; print("  ✅ adhesives::bond_line_thickness =", _v_bond_line_thickness)
    else: failed += 1; print("  ❌ adhesives::bond_line_thickness → non-finite:", _v_bond_line_thickness)
    var _v_coverage_rate = coverage_rate(0.5, 0.5)
    if is_finite(_v_coverage_rate): passed += 1; print("  ✅ adhesives::coverage_rate =", _v_coverage_rate)
    else: failed += 1; print("  ❌ adhesives::coverage_rate → non-finite:", _v_coverage_rate)
    var _v_pot_life_temperature_adjusted = pot_life_temperature_adjusted(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_pot_life_temperature_adjusted): passed += 1; print("  ✅ adhesives::pot_life_temperature_adjusted =", _v_pot_life_temperature_adjusted)
    else: failed += 1; print("  ❌ adhesives::pot_life_temperature_adjusted → non-finite:", _v_pot_life_temperature_adjusted)
    var _v_cure_time_temperature = cure_time_temperature(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_cure_time_temperature): passed += 1; print("  ✅ adhesives::cure_time_temperature =", _v_cure_time_temperature)
    else: failed += 1; print("  ❌ adhesives::cure_time_temperature → non-finite:", _v_cure_time_temperature)
    var _v_joint_efficiency = joint_efficiency(0.5, 0.5)
    if is_finite(_v_joint_efficiency): passed += 1; print("  ✅ adhesives::joint_efficiency =", _v_joint_efficiency)
    else: failed += 1; print("  ❌ adhesives::joint_efficiency → non-finite:", _v_joint_efficiency)
    var _v_thermal_cycle_life = thermal_cycle_life(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_thermal_cycle_life): passed += 1; print("  ✅ adhesives::thermal_cycle_life =", _v_thermal_cycle_life)
    else: failed += 1; print("  ❌ adhesives::thermal_cycle_life → non-finite:", _v_thermal_cycle_life)
    var _v_viscosity_temperature = viscosity_temperature(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_viscosity_temperature): passed += 1; print("  ✅ adhesives::viscosity_temperature =", _v_viscosity_temperature)
    else: failed += 1; print("  ❌ adhesives::viscosity_temperature → non-finite:", _v_viscosity_temperature)
    var _v_surface_energy_contact_angle = surface_energy_contact_angle(0.5, 0.5)
    if is_finite(_v_surface_energy_contact_angle): passed += 1; print("  ✅ adhesives::surface_energy_contact_angle =", _v_surface_energy_contact_angle)
    else: failed += 1; print("  ❌ adhesives::surface_energy_contact_angle → non-finite:", _v_surface_energy_contact_angle)
    var _v_open_time_estimate = open_time_estimate(0.5, 0.5)
    if is_finite(_v_open_time_estimate): passed += 1; print("  ✅ adhesives::open_time_estimate =", _v_open_time_estimate)
    else: failed += 1; print("  ❌ adhesives::open_time_estimate → non-finite:", _v_open_time_estimate)
    var _v_bond_area_from_load = bond_area_from_load(0.5, 0.5, 0.5)
    if is_finite(_v_bond_area_from_load): passed += 1; print("  ✅ adhesives::bond_area_from_load =", _v_bond_area_from_load)
    else: failed += 1; print("  ❌ adhesives::bond_area_from_load → non-finite:", _v_bond_area_from_load)

    print("  [adhesives] Passed:", passed, "Failed:", failed)
