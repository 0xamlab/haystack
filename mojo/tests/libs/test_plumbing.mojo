"""test_plumbing.mojo — auto-generated tests for plumbing library."""
from std.math import isnan, isinf
from plumbing import pipe_flow_velocity, reynolds_number, friction_factor_laminar, head_loss_darcy, head_loss_minor, total_dynamic_head, pump_power, water_demand_fixture_units, pipe_sizing_velocity_method, thermal_expansion_pipe, water_hammer_pressure, drainage_slope_minimum

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

    var _v_pipe_flow_velocity = pipe_flow_velocity(0.5, 0.5)
    if is_finite(_v_pipe_flow_velocity): passed += 1; print("  ✅ plumbing::pipe_flow_velocity =", _v_pipe_flow_velocity)
    else: failed += 1; print("  ❌ plumbing::pipe_flow_velocity → non-finite:", _v_pipe_flow_velocity)
    var _v_reynolds_number = reynolds_number(0.5, 0.5, 0.5)
    if is_finite(_v_reynolds_number): passed += 1; print("  ✅ plumbing::reynolds_number =", _v_reynolds_number)
    else: failed += 1; print("  ❌ plumbing::reynolds_number → non-finite:", _v_reynolds_number)
    var _v_friction_factor_laminar = friction_factor_laminar(0.5)
    if is_finite(_v_friction_factor_laminar): passed += 1; print("  ✅ plumbing::friction_factor_laminar =", _v_friction_factor_laminar)
    else: failed += 1; print("  ❌ plumbing::friction_factor_laminar → non-finite:", _v_friction_factor_laminar)
    var _v_head_loss_darcy = head_loss_darcy(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_head_loss_darcy): passed += 1; print("  ✅ plumbing::head_loss_darcy =", _v_head_loss_darcy)
    else: failed += 1; print("  ❌ plumbing::head_loss_darcy → non-finite:", _v_head_loss_darcy)
    var _v_head_loss_minor = head_loss_minor(0.5, 0.5, 0.5)
    if is_finite(_v_head_loss_minor): passed += 1; print("  ✅ plumbing::head_loss_minor =", _v_head_loss_minor)
    else: failed += 1; print("  ❌ plumbing::head_loss_minor → non-finite:", _v_head_loss_minor)
    var _v_total_dynamic_head = total_dynamic_head(0.5, 0.5, 0.5)
    if is_finite(_v_total_dynamic_head): passed += 1; print("  ✅ plumbing::total_dynamic_head =", _v_total_dynamic_head)
    else: failed += 1; print("  ❌ plumbing::total_dynamic_head → non-finite:", _v_total_dynamic_head)
    var _v_pump_power = pump_power(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_pump_power): passed += 1; print("  ✅ plumbing::pump_power =", _v_pump_power)
    else: failed += 1; print("  ❌ plumbing::pump_power → non-finite:", _v_pump_power)
    var _v_water_demand_fixture_units = water_demand_fixture_units(0.5, 0.5)
    if is_finite(_v_water_demand_fixture_units): passed += 1; print("  ✅ plumbing::water_demand_fixture_units =", _v_water_demand_fixture_units)
    else: failed += 1; print("  ❌ plumbing::water_demand_fixture_units → non-finite:", _v_water_demand_fixture_units)
    var _v_pipe_sizing_velocity_method = pipe_sizing_velocity_method(0.5, 0.5)
    if is_finite(_v_pipe_sizing_velocity_method): passed += 1; print("  ✅ plumbing::pipe_sizing_velocity_method =", _v_pipe_sizing_velocity_method)
    else: failed += 1; print("  ❌ plumbing::pipe_sizing_velocity_method → non-finite:", _v_pipe_sizing_velocity_method)
    var _v_thermal_expansion_pipe = thermal_expansion_pipe(0.5, 0.5, 0.5)
    if is_finite(_v_thermal_expansion_pipe): passed += 1; print("  ✅ plumbing::thermal_expansion_pipe =", _v_thermal_expansion_pipe)
    else: failed += 1; print("  ❌ plumbing::thermal_expansion_pipe → non-finite:", _v_thermal_expansion_pipe)
    var _v_water_hammer_pressure = water_hammer_pressure(0.5, 0.5, 0.5)
    if is_finite(_v_water_hammer_pressure): passed += 1; print("  ✅ plumbing::water_hammer_pressure =", _v_water_hammer_pressure)
    else: failed += 1; print("  ❌ plumbing::water_hammer_pressure → non-finite:", _v_water_hammer_pressure)
    var _v_drainage_slope_minimum = drainage_slope_minimum(0.5)
    if is_finite(_v_drainage_slope_minimum): passed += 1; print("  ✅ plumbing::drainage_slope_minimum =", _v_drainage_slope_minimum)
    else: failed += 1; print("  ❌ plumbing::drainage_slope_minimum → non-finite:", _v_drainage_slope_minimum)

    print("  [plumbing] Passed:", passed, "Failed:", failed)
