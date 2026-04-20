"""test_aerospace.mojo — auto-generated tests for aerospace library."""
from std.math import isnan, isinf
from aerospace import dynamic_pressure, lift_force, drag_force, lift_to_drag_ratio, thrust_required, specific_impulse, tsiolkovsky_delta_v, mach_number, speed_of_sound, orbital_velocity, escape_velocity, hohmann_delta_v

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

    var _v_dynamic_pressure = dynamic_pressure(0.5, 0.5)
    if is_finite(_v_dynamic_pressure): passed += 1; print("  ✅ aerospace::dynamic_pressure =", _v_dynamic_pressure)
    else: failed += 1; print("  ❌ aerospace::dynamic_pressure → non-finite:", _v_dynamic_pressure)
    var _v_lift_force = lift_force(0.5, 0.5, 0.5)
    if is_finite(_v_lift_force): passed += 1; print("  ✅ aerospace::lift_force =", _v_lift_force)
    else: failed += 1; print("  ❌ aerospace::lift_force → non-finite:", _v_lift_force)
    var _v_drag_force = drag_force(0.5, 0.5, 0.5)
    if is_finite(_v_drag_force): passed += 1; print("  ✅ aerospace::drag_force =", _v_drag_force)
    else: failed += 1; print("  ❌ aerospace::drag_force → non-finite:", _v_drag_force)
    var _v_lift_to_drag_ratio = lift_to_drag_ratio(0.5, 0.5)
    if is_finite(_v_lift_to_drag_ratio): passed += 1; print("  ✅ aerospace::lift_to_drag_ratio =", _v_lift_to_drag_ratio)
    else: failed += 1; print("  ❌ aerospace::lift_to_drag_ratio → non-finite:", _v_lift_to_drag_ratio)
    var _v_thrust_required = thrust_required(0.5, 0.5)
    if is_finite(_v_thrust_required): passed += 1; print("  ✅ aerospace::thrust_required =", _v_thrust_required)
    else: failed += 1; print("  ❌ aerospace::thrust_required → non-finite:", _v_thrust_required)
    var _v_specific_impulse = specific_impulse(0.5, 0.5)
    if is_finite(_v_specific_impulse): passed += 1; print("  ✅ aerospace::specific_impulse =", _v_specific_impulse)
    else: failed += 1; print("  ❌ aerospace::specific_impulse → non-finite:", _v_specific_impulse)
    var _v_tsiolkovsky_delta_v = tsiolkovsky_delta_v(0.5, 0.5, 0.5)
    if is_finite(_v_tsiolkovsky_delta_v): passed += 1; print("  ✅ aerospace::tsiolkovsky_delta_v =", _v_tsiolkovsky_delta_v)
    else: failed += 1; print("  ❌ aerospace::tsiolkovsky_delta_v → non-finite:", _v_tsiolkovsky_delta_v)
    var _v_mach_number = mach_number(0.5, 0.5)
    if is_finite(_v_mach_number): passed += 1; print("  ✅ aerospace::mach_number =", _v_mach_number)
    else: failed += 1; print("  ❌ aerospace::mach_number → non-finite:", _v_mach_number)
    var _v_speed_of_sound = speed_of_sound(0.5, 0.5, 0.5)
    if is_finite(_v_speed_of_sound): passed += 1; print("  ✅ aerospace::speed_of_sound =", _v_speed_of_sound)
    else: failed += 1; print("  ❌ aerospace::speed_of_sound → non-finite:", _v_speed_of_sound)
    var _v_orbital_velocity = orbital_velocity(0.5, 0.5)
    if is_finite(_v_orbital_velocity): passed += 1; print("  ✅ aerospace::orbital_velocity =", _v_orbital_velocity)
    else: failed += 1; print("  ❌ aerospace::orbital_velocity → non-finite:", _v_orbital_velocity)
    var _v_escape_velocity = escape_velocity(0.5, 0.5)
    if is_finite(_v_escape_velocity): passed += 1; print("  ✅ aerospace::escape_velocity =", _v_escape_velocity)
    else: failed += 1; print("  ❌ aerospace::escape_velocity → non-finite:", _v_escape_velocity)
    var _v_hohmann_delta_v = hohmann_delta_v(0.5, 0.5, 0.5)
    if is_finite(_v_hohmann_delta_v): passed += 1; print("  ✅ aerospace::hohmann_delta_v =", _v_hohmann_delta_v)
    else: failed += 1; print("  ❌ aerospace::hohmann_delta_v → non-finite:", _v_hohmann_delta_v)

    print("  [aerospace] Passed:", passed, "Failed:", failed)
