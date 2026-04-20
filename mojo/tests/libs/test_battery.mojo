"""test_battery.mojo — auto-generated tests for battery library."""
from std.math import isnan, isinf
from battery import state_of_charge, depth_of_discharge, coulombic_efficiency, energy_density, power_density, c_rate, discharge_time, peukert_capacity, cycle_life_degradation, internal_resistance_from_voltage, battery_pack_voltage, battery_pack_capacity

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

    var _v_state_of_charge = state_of_charge(0.5, 0.5)
    if is_finite(_v_state_of_charge): passed += 1; print("  ✅ battery::state_of_charge =", _v_state_of_charge)
    else: failed += 1; print("  ❌ battery::state_of_charge → non-finite:", _v_state_of_charge)
    var _v_depth_of_discharge = depth_of_discharge(0.5)
    if is_finite(_v_depth_of_discharge): passed += 1; print("  ✅ battery::depth_of_discharge =", _v_depth_of_discharge)
    else: failed += 1; print("  ❌ battery::depth_of_discharge → non-finite:", _v_depth_of_discharge)
    var _v_coulombic_efficiency = coulombic_efficiency(0.5, 0.5)
    if is_finite(_v_coulombic_efficiency): passed += 1; print("  ✅ battery::coulombic_efficiency =", _v_coulombic_efficiency)
    else: failed += 1; print("  ❌ battery::coulombic_efficiency → non-finite:", _v_coulombic_efficiency)
    var _v_energy_density = energy_density(0.5, 0.5)
    if is_finite(_v_energy_density): passed += 1; print("  ✅ battery::energy_density =", _v_energy_density)
    else: failed += 1; print("  ❌ battery::energy_density → non-finite:", _v_energy_density)
    var _v_power_density = power_density(0.5, 0.5)
    if is_finite(_v_power_density): passed += 1; print("  ✅ battery::power_density =", _v_power_density)
    else: failed += 1; print("  ❌ battery::power_density → non-finite:", _v_power_density)
    var _v_c_rate = c_rate(0.5, 0.5)
    if is_finite(_v_c_rate): passed += 1; print("  ✅ battery::c_rate =", _v_c_rate)
    else: failed += 1; print("  ❌ battery::c_rate → non-finite:", _v_c_rate)
    var _v_discharge_time = discharge_time(0.5, 0.5)
    if is_finite(_v_discharge_time): passed += 1; print("  ✅ battery::discharge_time =", _v_discharge_time)
    else: failed += 1; print("  ❌ battery::discharge_time → non-finite:", _v_discharge_time)
    var _v_peukert_capacity = peukert_capacity(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_peukert_capacity): passed += 1; print("  ✅ battery::peukert_capacity =", _v_peukert_capacity)
    else: failed += 1; print("  ❌ battery::peukert_capacity → non-finite:", _v_peukert_capacity)
    var _v_cycle_life_degradation = cycle_life_degradation(0.5, 0.5, 0.5)
    if is_finite(_v_cycle_life_degradation): passed += 1; print("  ✅ battery::cycle_life_degradation =", _v_cycle_life_degradation)
    else: failed += 1; print("  ❌ battery::cycle_life_degradation → non-finite:", _v_cycle_life_degradation)
    var _v_internal_resistance_from_voltage = internal_resistance_from_voltage(0.5, 0.5, 0.5)
    if is_finite(_v_internal_resistance_from_voltage): passed += 1; print("  ✅ battery::internal_resistance_from_voltage =", _v_internal_resistance_from_voltage)
    else: failed += 1; print("  ❌ battery::internal_resistance_from_voltage → non-finite:", _v_internal_resistance_from_voltage)
    var _v_battery_pack_voltage = battery_pack_voltage(0.5, 0.5)
    if is_finite(_v_battery_pack_voltage): passed += 1; print("  ✅ battery::battery_pack_voltage =", _v_battery_pack_voltage)
    else: failed += 1; print("  ❌ battery::battery_pack_voltage → non-finite:", _v_battery_pack_voltage)
    var _v_battery_pack_capacity = battery_pack_capacity(0.5, 0.5)
    if is_finite(_v_battery_pack_capacity): passed += 1; print("  ✅ battery::battery_pack_capacity =", _v_battery_pack_capacity)
    else: failed += 1; print("  ❌ battery::battery_pack_capacity → non-finite:", _v_battery_pack_capacity)

    print("  [battery] Passed:", passed, "Failed:", failed)
