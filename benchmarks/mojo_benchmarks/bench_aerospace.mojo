"""bench_aerospace.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from aerospace import dynamic_pressure, lift_force, drag_force, lift_to_drag_ratio, thrust_required, specific_impulse, tsiolkovsky_delta_v, mach_number, speed_of_sound, orbital_velocity, escape_velocity, hohmann_delta_v
from std.time import perf_counter_ns

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var _lub5 = List[UInt8]()
    _lub5.append(1); _lub5.append(2); _lub5.append(3)
    _lub5.append(4); _lub5.append(5)
    var _llf3 = List[List[Float64]]()
    _llf3.append(List[Float64]()); _llf3.append(List[Float64]()); _llf3.append(List[Float64]())
    _llf3[0].append(4.0); _llf3[0].append(0.0); _llf3[0].append(5.0)
    _llf3[1].append(0.0); _llf3[1].append(3.0); _llf3[1].append(4.0)
    _llf3[2].append(3.0); _llf3[2].append(4.0); _llf3[2].append(0.0)
    var N: Int = 10000

    var _acc_dynamic_pressure: Float64 = 0.0
    var _t0_dynamic_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_dynamic_pressure += dynamic_pressure(0.5, 0.5)
    var _t1_dynamic_pressure = perf_counter_ns()
    var _ns_dynamic_pressure = Float64(_t1_dynamic_pressure - _t0_dynamic_pressure) / Float64(N)
    print("MOJO_TIMING aerospace::dynamic_pressure", _ns_dynamic_pressure, _acc_dynamic_pressure)
    var _acc_lift_force: Float64 = 0.0
    var _t0_lift_force = perf_counter_ns()
    for _ in range(N):
        _acc_lift_force += lift_force(0.5, 0.5, 0.5)
    var _t1_lift_force = perf_counter_ns()
    var _ns_lift_force = Float64(_t1_lift_force - _t0_lift_force) / Float64(N)
    print("MOJO_TIMING aerospace::lift_force", _ns_lift_force, _acc_lift_force)
    var _acc_drag_force: Float64 = 0.0
    var _t0_drag_force = perf_counter_ns()
    for _ in range(N):
        _acc_drag_force += drag_force(0.5, 0.5, 0.5)
    var _t1_drag_force = perf_counter_ns()
    var _ns_drag_force = Float64(_t1_drag_force - _t0_drag_force) / Float64(N)
    print("MOJO_TIMING aerospace::drag_force", _ns_drag_force, _acc_drag_force)
    var _acc_lift_to_drag_ratio: Float64 = 0.0
    var _t0_lift_to_drag_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_lift_to_drag_ratio += lift_to_drag_ratio(0.5, 0.5)
    var _t1_lift_to_drag_ratio = perf_counter_ns()
    var _ns_lift_to_drag_ratio = Float64(_t1_lift_to_drag_ratio - _t0_lift_to_drag_ratio) / Float64(N)
    print("MOJO_TIMING aerospace::lift_to_drag_ratio", _ns_lift_to_drag_ratio, _acc_lift_to_drag_ratio)
    var _acc_thrust_required: Float64 = 0.0
    var _t0_thrust_required = perf_counter_ns()
    for _ in range(N):
        _acc_thrust_required += thrust_required(0.5, 0.5)
    var _t1_thrust_required = perf_counter_ns()
    var _ns_thrust_required = Float64(_t1_thrust_required - _t0_thrust_required) / Float64(N)
    print("MOJO_TIMING aerospace::thrust_required", _ns_thrust_required, _acc_thrust_required)
    var _acc_specific_impulse: Float64 = 0.0
    var _t0_specific_impulse = perf_counter_ns()
    for _ in range(N):
        _acc_specific_impulse += specific_impulse(0.5, 0.5)
    var _t1_specific_impulse = perf_counter_ns()
    var _ns_specific_impulse = Float64(_t1_specific_impulse - _t0_specific_impulse) / Float64(N)
    print("MOJO_TIMING aerospace::specific_impulse", _ns_specific_impulse, _acc_specific_impulse)
    var _acc_tsiolkovsky_delta_v: Float64 = 0.0
    var _t0_tsiolkovsky_delta_v = perf_counter_ns()
    for _ in range(N):
        _acc_tsiolkovsky_delta_v += tsiolkovsky_delta_v(0.5, 0.5, 0.5)
    var _t1_tsiolkovsky_delta_v = perf_counter_ns()
    var _ns_tsiolkovsky_delta_v = Float64(_t1_tsiolkovsky_delta_v - _t0_tsiolkovsky_delta_v) / Float64(N)
    print("MOJO_TIMING aerospace::tsiolkovsky_delta_v", _ns_tsiolkovsky_delta_v, _acc_tsiolkovsky_delta_v)
    var _acc_mach_number: Float64 = 0.0
    var _t0_mach_number = perf_counter_ns()
    for _ in range(N):
        _acc_mach_number += mach_number(0.5, 0.5)
    var _t1_mach_number = perf_counter_ns()
    var _ns_mach_number = Float64(_t1_mach_number - _t0_mach_number) / Float64(N)
    print("MOJO_TIMING aerospace::mach_number", _ns_mach_number, _acc_mach_number)
    var _acc_speed_of_sound: Float64 = 0.0
    var _t0_speed_of_sound = perf_counter_ns()
    for _ in range(N):
        _acc_speed_of_sound += speed_of_sound(0.5, 0.5, 0.5)
    var _t1_speed_of_sound = perf_counter_ns()
    var _ns_speed_of_sound = Float64(_t1_speed_of_sound - _t0_speed_of_sound) / Float64(N)
    print("MOJO_TIMING aerospace::speed_of_sound", _ns_speed_of_sound, _acc_speed_of_sound)
    var _acc_orbital_velocity: Float64 = 0.0
    var _t0_orbital_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_orbital_velocity += orbital_velocity(0.5, 0.5)
    var _t1_orbital_velocity = perf_counter_ns()
    var _ns_orbital_velocity = Float64(_t1_orbital_velocity - _t0_orbital_velocity) / Float64(N)
    print("MOJO_TIMING aerospace::orbital_velocity", _ns_orbital_velocity, _acc_orbital_velocity)
    var _acc_escape_velocity: Float64 = 0.0
    var _t0_escape_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_escape_velocity += escape_velocity(0.5, 0.5)
    var _t1_escape_velocity = perf_counter_ns()
    var _ns_escape_velocity = Float64(_t1_escape_velocity - _t0_escape_velocity) / Float64(N)
    print("MOJO_TIMING aerospace::escape_velocity", _ns_escape_velocity, _acc_escape_velocity)
    var _acc_hohmann_delta_v: Float64 = 0.0
    var _t0_hohmann_delta_v = perf_counter_ns()
    for _ in range(N):
        _acc_hohmann_delta_v += hohmann_delta_v(0.5, 0.5, 0.5)
    var _t1_hohmann_delta_v = perf_counter_ns()
    var _ns_hohmann_delta_v = Float64(_t1_hohmann_delta_v - _t0_hohmann_delta_v) / Float64(N)
    print("MOJO_TIMING aerospace::hohmann_delta_v", _ns_hohmann_delta_v, _acc_hohmann_delta_v)
