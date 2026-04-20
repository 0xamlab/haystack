"""bench_aviation.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from aviation import lift_force, drag_force, lift_to_drag_ratio, thrust_required, range_breguet, endurance_breguet, indicated_airspeed, true_airspeed, mach_number, rate_of_climb
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

    var _acc_lift_force: Float64 = 0.0
    var _t0_lift_force = perf_counter_ns()
    for _ in range(N):
        _acc_lift_force += lift_force(0.5, 0.5, 0.5, 0.5)
    var _t1_lift_force = perf_counter_ns()
    var _ns_lift_force = Float64(_t1_lift_force - _t0_lift_force) / Float64(N)
    print("MOJO_TIMING aviation::lift_force", _ns_lift_force, _acc_lift_force)
    var _acc_drag_force: Float64 = 0.0
    var _t0_drag_force = perf_counter_ns()
    for _ in range(N):
        _acc_drag_force += drag_force(0.5, 0.5, 0.5, 0.5)
    var _t1_drag_force = perf_counter_ns()
    var _ns_drag_force = Float64(_t1_drag_force - _t0_drag_force) / Float64(N)
    print("MOJO_TIMING aviation::drag_force", _ns_drag_force, _acc_drag_force)
    var _acc_lift_to_drag_ratio: Float64 = 0.0
    var _t0_lift_to_drag_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_lift_to_drag_ratio += lift_to_drag_ratio(0.5, 0.5)
    var _t1_lift_to_drag_ratio = perf_counter_ns()
    var _ns_lift_to_drag_ratio = Float64(_t1_lift_to_drag_ratio - _t0_lift_to_drag_ratio) / Float64(N)
    print("MOJO_TIMING aviation::lift_to_drag_ratio", _ns_lift_to_drag_ratio, _acc_lift_to_drag_ratio)
    var _acc_thrust_required: Float64 = 0.0
    var _t0_thrust_required = perf_counter_ns()
    for _ in range(N):
        _acc_thrust_required += thrust_required(0.5, 0.5, 0.5)
    var _t1_thrust_required = perf_counter_ns()
    var _ns_thrust_required = Float64(_t1_thrust_required - _t0_thrust_required) / Float64(N)
    print("MOJO_TIMING aviation::thrust_required", _ns_thrust_required, _acc_thrust_required)
    var _acc_range_breguet: Float64 = 0.0
    var _t0_range_breguet = perf_counter_ns()
    for _ in range(N):
        _acc_range_breguet += range_breguet(0.5, 0.5, 0.5, 0.5)
    var _t1_range_breguet = perf_counter_ns()
    var _ns_range_breguet = Float64(_t1_range_breguet - _t0_range_breguet) / Float64(N)
    print("MOJO_TIMING aviation::range_breguet", _ns_range_breguet, _acc_range_breguet)
    var _acc_endurance_breguet: Float64 = 0.0
    var _t0_endurance_breguet = perf_counter_ns()
    for _ in range(N):
        _acc_endurance_breguet += endurance_breguet(0.5, 0.5, 0.5, 0.5)
    var _t1_endurance_breguet = perf_counter_ns()
    var _ns_endurance_breguet = Float64(_t1_endurance_breguet - _t0_endurance_breguet) / Float64(N)
    print("MOJO_TIMING aviation::endurance_breguet", _ns_endurance_breguet, _acc_endurance_breguet)
    var _acc_indicated_airspeed: Float64 = 0.0
    var _t0_indicated_airspeed = perf_counter_ns()
    for _ in range(N):
        _acc_indicated_airspeed += indicated_airspeed(0.5)
    var _t1_indicated_airspeed = perf_counter_ns()
    var _ns_indicated_airspeed = Float64(_t1_indicated_airspeed - _t0_indicated_airspeed) / Float64(N)
    print("MOJO_TIMING aviation::indicated_airspeed", _ns_indicated_airspeed, _acc_indicated_airspeed)
    var _acc_true_airspeed: Float64 = 0.0
    var _t0_true_airspeed = perf_counter_ns()
    for _ in range(N):
        _acc_true_airspeed += true_airspeed(0.5, 0.5)
    var _t1_true_airspeed = perf_counter_ns()
    var _ns_true_airspeed = Float64(_t1_true_airspeed - _t0_true_airspeed) / Float64(N)
    print("MOJO_TIMING aviation::true_airspeed", _ns_true_airspeed, _acc_true_airspeed)
    var _acc_mach_number: Float64 = 0.0
    var _t0_mach_number = perf_counter_ns()
    for _ in range(N):
        _acc_mach_number += mach_number(0.5, 0.5)
    var _t1_mach_number = perf_counter_ns()
    var _ns_mach_number = Float64(_t1_mach_number - _t0_mach_number) / Float64(N)
    print("MOJO_TIMING aviation::mach_number", _ns_mach_number, _acc_mach_number)
    var _acc_rate_of_climb: Float64 = 0.0
    var _t0_rate_of_climb = perf_counter_ns()
    for _ in range(N):
        _acc_rate_of_climb += rate_of_climb(0.5, 0.5, 0.5)
    var _t1_rate_of_climb = perf_counter_ns()
    var _ns_rate_of_climb = Float64(_t1_rate_of_climb - _t0_rate_of_climb) / Float64(N)
    print("MOJO_TIMING aviation::rate_of_climb", _ns_rate_of_climb, _acc_rate_of_climb)
