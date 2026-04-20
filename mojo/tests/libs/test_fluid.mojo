"""test_fluid.mojo — auto-generated tests for fluid library."""
from std.math import isnan, isinf
from fluid import reynolds_number, is_turbulent, bernoulli_velocity, friction_factor_laminar, darcy_weisbach, flow_rate, pipe_velocity, hydraulic_diameter, mach_number, drag_force, buoyancy_force, stokes_drag

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

    var _v_reynolds_number = reynolds_number(0.5, 0.5, 0.5)
    if is_finite(_v_reynolds_number): passed += 1; print("  ✅ fluid::reynolds_number =", _v_reynolds_number)
    else: failed += 1; print("  ❌ fluid::reynolds_number → non-finite:", _v_reynolds_number)
    _ = is_turbulent(0.5)
    passed += 1; print("  ✅ fluid::is_turbulent")
    var _v_bernoulli_velocity = bernoulli_velocity(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_bernoulli_velocity): passed += 1; print("  ✅ fluid::bernoulli_velocity =", _v_bernoulli_velocity)
    else: failed += 1; print("  ❌ fluid::bernoulli_velocity → non-finite:", _v_bernoulli_velocity)
    var _v_friction_factor_laminar = friction_factor_laminar(0.5)
    if is_finite(_v_friction_factor_laminar): passed += 1; print("  ✅ fluid::friction_factor_laminar =", _v_friction_factor_laminar)
    else: failed += 1; print("  ❌ fluid::friction_factor_laminar → non-finite:", _v_friction_factor_laminar)
    var _v_darcy_weisbach = darcy_weisbach(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_darcy_weisbach): passed += 1; print("  ✅ fluid::darcy_weisbach =", _v_darcy_weisbach)
    else: failed += 1; print("  ❌ fluid::darcy_weisbach → non-finite:", _v_darcy_weisbach)
    var _v_flow_rate = flow_rate(0.5, 0.5)
    if is_finite(_v_flow_rate): passed += 1; print("  ✅ fluid::flow_rate =", _v_flow_rate)
    else: failed += 1; print("  ❌ fluid::flow_rate → non-finite:", _v_flow_rate)
    var _v_pipe_velocity = pipe_velocity(0.5, 0.5)
    if is_finite(_v_pipe_velocity): passed += 1; print("  ✅ fluid::pipe_velocity =", _v_pipe_velocity)
    else: failed += 1; print("  ❌ fluid::pipe_velocity → non-finite:", _v_pipe_velocity)
    var _v_hydraulic_diameter = hydraulic_diameter(0.5, 0.5)
    if is_finite(_v_hydraulic_diameter): passed += 1; print("  ✅ fluid::hydraulic_diameter =", _v_hydraulic_diameter)
    else: failed += 1; print("  ❌ fluid::hydraulic_diameter → non-finite:", _v_hydraulic_diameter)
    var _v_mach_number = mach_number(0.5, 0.5)
    if is_finite(_v_mach_number): passed += 1; print("  ✅ fluid::mach_number =", _v_mach_number)
    else: failed += 1; print("  ❌ fluid::mach_number → non-finite:", _v_mach_number)
    var _v_drag_force = drag_force(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_drag_force): passed += 1; print("  ✅ fluid::drag_force =", _v_drag_force)
    else: failed += 1; print("  ❌ fluid::drag_force → non-finite:", _v_drag_force)
    var _v_buoyancy_force = buoyancy_force(0.5, 0.5, 0.5)
    if is_finite(_v_buoyancy_force): passed += 1; print("  ✅ fluid::buoyancy_force =", _v_buoyancy_force)
    else: failed += 1; print("  ❌ fluid::buoyancy_force → non-finite:", _v_buoyancy_force)
    var _v_stokes_drag = stokes_drag(0.5, 0.5, 0.5)
    if is_finite(_v_stokes_drag): passed += 1; print("  ✅ fluid::stokes_drag =", _v_stokes_drag)
    else: failed += 1; print("  ❌ fluid::stokes_drag → non-finite:", _v_stokes_drag)

    print("  [fluid] Passed:", passed, "Failed:", failed)
