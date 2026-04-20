"""test_hydraulics.mojo — auto-generated tests for hydraulics library."""
from std.math import isnan, isinf
from hydraulics import pascals_law_force, pascals_law_pressure, hydraulic_advantage, flow_rate_cylinder, cylinder_velocity, pump_displacement, hydraulic_power, system_pressure_loss, accumulator_volume, relief_valve_flow, oil_compressibility, cylinder_bore_from_force

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

    var _v_pascals_law_force = pascals_law_force(0.5, 0.5)
    if is_finite(_v_pascals_law_force): passed += 1; print("  ✅ hydraulics::pascals_law_force =", _v_pascals_law_force)
    else: failed += 1; print("  ❌ hydraulics::pascals_law_force → non-finite:", _v_pascals_law_force)
    var _v_pascals_law_pressure = pascals_law_pressure(0.5, 0.5)
    if is_finite(_v_pascals_law_pressure): passed += 1; print("  ✅ hydraulics::pascals_law_pressure =", _v_pascals_law_pressure)
    else: failed += 1; print("  ❌ hydraulics::pascals_law_pressure → non-finite:", _v_pascals_law_pressure)
    var _v_hydraulic_advantage = hydraulic_advantage(0.5, 0.5)
    if is_finite(_v_hydraulic_advantage): passed += 1; print("  ✅ hydraulics::hydraulic_advantage =", _v_hydraulic_advantage)
    else: failed += 1; print("  ❌ hydraulics::hydraulic_advantage → non-finite:", _v_hydraulic_advantage)
    var _v_flow_rate_cylinder = flow_rate_cylinder(0.5, 0.5)
    if is_finite(_v_flow_rate_cylinder): passed += 1; print("  ✅ hydraulics::flow_rate_cylinder =", _v_flow_rate_cylinder)
    else: failed += 1; print("  ❌ hydraulics::flow_rate_cylinder → non-finite:", _v_flow_rate_cylinder)
    var _v_cylinder_velocity = cylinder_velocity(0.5, 0.5)
    if is_finite(_v_cylinder_velocity): passed += 1; print("  ✅ hydraulics::cylinder_velocity =", _v_cylinder_velocity)
    else: failed += 1; print("  ❌ hydraulics::cylinder_velocity → non-finite:", _v_cylinder_velocity)
    var _v_pump_displacement = pump_displacement(0.5, 0.5)
    if is_finite(_v_pump_displacement): passed += 1; print("  ✅ hydraulics::pump_displacement =", _v_pump_displacement)
    else: failed += 1; print("  ❌ hydraulics::pump_displacement → non-finite:", _v_pump_displacement)
    var _v_hydraulic_power = hydraulic_power(0.5, 0.5)
    if is_finite(_v_hydraulic_power): passed += 1; print("  ✅ hydraulics::hydraulic_power =", _v_hydraulic_power)
    else: failed += 1; print("  ❌ hydraulics::hydraulic_power → non-finite:", _v_hydraulic_power)
    var _v_system_pressure_loss = system_pressure_loss(0.5, 0.5)
    if is_finite(_v_system_pressure_loss): passed += 1; print("  ✅ hydraulics::system_pressure_loss =", _v_system_pressure_loss)
    else: failed += 1; print("  ❌ hydraulics::system_pressure_loss → non-finite:", _v_system_pressure_loss)
    var _v_accumulator_volume = accumulator_volume(0.5, 0.5, 0.5)
    if is_finite(_v_accumulator_volume): passed += 1; print("  ✅ hydraulics::accumulator_volume =", _v_accumulator_volume)
    else: failed += 1; print("  ❌ hydraulics::accumulator_volume → non-finite:", _v_accumulator_volume)
    var _v_relief_valve_flow = relief_valve_flow(0.5, 0.5, 0.5)
    if is_finite(_v_relief_valve_flow): passed += 1; print("  ✅ hydraulics::relief_valve_flow =", _v_relief_valve_flow)
    else: failed += 1; print("  ❌ hydraulics::relief_valve_flow → non-finite:", _v_relief_valve_flow)
    var _v_oil_compressibility = oil_compressibility(0.5, 0.5, 0.5)
    if is_finite(_v_oil_compressibility): passed += 1; print("  ✅ hydraulics::oil_compressibility =", _v_oil_compressibility)
    else: failed += 1; print("  ❌ hydraulics::oil_compressibility → non-finite:", _v_oil_compressibility)
    var _v_cylinder_bore_from_force = cylinder_bore_from_force(0.5, 0.5)
    if is_finite(_v_cylinder_bore_from_force): passed += 1; print("  ✅ hydraulics::cylinder_bore_from_force =", _v_cylinder_bore_from_force)
    else: failed += 1; print("  ❌ hydraulics::cylinder_bore_from_force → non-finite:", _v_cylinder_bore_from_force)

    print("  [hydraulics] Passed:", passed, "Failed:", failed)
