"""test_hydrology.mojo — auto-generated tests for hydrology library."""
from std.math import isnan, isinf
from hydrology import manning_velocity, manning_discharge, hydraulic_radius, froude_number, reynolds_number_pipe, darcy_weisbach_head_loss, rational_method_peak_flow, time_of_concentration_kirpich, curve_number_runoff, evapotranspiration_hargreaves, specific_yield, darcy_groundwater_velocity

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

    var _v_manning_velocity = manning_velocity(0.5, 0.5, 0.5)
    if is_finite(_v_manning_velocity): passed += 1; print("  ✅ hydrology::manning_velocity =", _v_manning_velocity)
    else: failed += 1; print("  ❌ hydrology::manning_velocity → non-finite:", _v_manning_velocity)
    var _v_manning_discharge = manning_discharge(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_manning_discharge): passed += 1; print("  ✅ hydrology::manning_discharge =", _v_manning_discharge)
    else: failed += 1; print("  ❌ hydrology::manning_discharge → non-finite:", _v_manning_discharge)
    var _v_hydraulic_radius = hydraulic_radius(0.5, 0.5)
    if is_finite(_v_hydraulic_radius): passed += 1; print("  ✅ hydrology::hydraulic_radius =", _v_hydraulic_radius)
    else: failed += 1; print("  ❌ hydrology::hydraulic_radius → non-finite:", _v_hydraulic_radius)
    var _v_froude_number = froude_number(0.5, 0.5, 0.5)
    if is_finite(_v_froude_number): passed += 1; print("  ✅ hydrology::froude_number =", _v_froude_number)
    else: failed += 1; print("  ❌ hydrology::froude_number → non-finite:", _v_froude_number)
    var _v_reynolds_number_pipe = reynolds_number_pipe(0.5, 0.5, 0.5)
    if is_finite(_v_reynolds_number_pipe): passed += 1; print("  ✅ hydrology::reynolds_number_pipe =", _v_reynolds_number_pipe)
    else: failed += 1; print("  ❌ hydrology::reynolds_number_pipe → non-finite:", _v_reynolds_number_pipe)
    var _v_darcy_weisbach_head_loss = darcy_weisbach_head_loss(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_darcy_weisbach_head_loss): passed += 1; print("  ✅ hydrology::darcy_weisbach_head_loss =", _v_darcy_weisbach_head_loss)
    else: failed += 1; print("  ❌ hydrology::darcy_weisbach_head_loss → non-finite:", _v_darcy_weisbach_head_loss)
    var _v_rational_method_peak_flow = rational_method_peak_flow(0.5, 0.5, 0.5)
    if is_finite(_v_rational_method_peak_flow): passed += 1; print("  ✅ hydrology::rational_method_peak_flow =", _v_rational_method_peak_flow)
    else: failed += 1; print("  ❌ hydrology::rational_method_peak_flow → non-finite:", _v_rational_method_peak_flow)
    var _v_time_of_concentration_kirpich = time_of_concentration_kirpich(0.5, 0.5)
    if is_finite(_v_time_of_concentration_kirpich): passed += 1; print("  ✅ hydrology::time_of_concentration_kirpich =", _v_time_of_concentration_kirpich)
    else: failed += 1; print("  ❌ hydrology::time_of_concentration_kirpich → non-finite:", _v_time_of_concentration_kirpich)
    var _v_curve_number_runoff = curve_number_runoff(0.5, 0.5)
    if is_finite(_v_curve_number_runoff): passed += 1; print("  ✅ hydrology::curve_number_runoff =", _v_curve_number_runoff)
    else: failed += 1; print("  ❌ hydrology::curve_number_runoff → non-finite:", _v_curve_number_runoff)
    var _v_evapotranspiration_hargreaves = evapotranspiration_hargreaves(0.5, 0.5, 0.5)
    if is_finite(_v_evapotranspiration_hargreaves): passed += 1; print("  ✅ hydrology::evapotranspiration_hargreaves =", _v_evapotranspiration_hargreaves)
    else: failed += 1; print("  ❌ hydrology::evapotranspiration_hargreaves → non-finite:", _v_evapotranspiration_hargreaves)
    var _v_specific_yield = specific_yield(0.5, 0.5)
    if is_finite(_v_specific_yield): passed += 1; print("  ✅ hydrology::specific_yield =", _v_specific_yield)
    else: failed += 1; print("  ❌ hydrology::specific_yield → non-finite:", _v_specific_yield)
    var _v_darcy_groundwater_velocity = darcy_groundwater_velocity(0.5, 0.5)
    if is_finite(_v_darcy_groundwater_velocity): passed += 1; print("  ✅ hydrology::darcy_groundwater_velocity =", _v_darcy_groundwater_velocity)
    else: failed += 1; print("  ❌ hydrology::darcy_groundwater_velocity → non-finite:", _v_darcy_groundwater_velocity)

    print("  [hydrology] Passed:", passed, "Failed:", failed)
