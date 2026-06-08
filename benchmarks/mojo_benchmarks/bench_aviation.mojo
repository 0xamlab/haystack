"""bench_aviation.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from aviation import lift_force, drag_force, lift_to_drag_ratio, thrust_required, range_breguet, endurance_breguet, indicated_airspeed, true_airspeed, mach_number, rate_of_climb
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))


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
    var _result_lift_force = lift_force(0.5, 0.5, 0.5, 0.5)
    var _summary_lift_force = _summary_float64(_result_lift_force)
    print("MOJO_RESULT aviation::lift_force", _summary_lift_force)
    var _acc_drag_force: Float64 = 0.0
    var _t0_drag_force = perf_counter_ns()
    for _ in range(N):
        _acc_drag_force += drag_force(0.5, 0.5, 0.5, 0.5)
    var _t1_drag_force = perf_counter_ns()
    var _ns_drag_force = Float64(_t1_drag_force - _t0_drag_force) / Float64(N)
    print("MOJO_TIMING aviation::drag_force", _ns_drag_force, _acc_drag_force)
    var _result_drag_force = drag_force(0.5, 0.5, 0.5, 0.5)
    var _summary_drag_force = _summary_float64(_result_drag_force)
    print("MOJO_RESULT aviation::drag_force", _summary_drag_force)
    var _acc_lift_to_drag_ratio: Float64 = 0.0
    var _t0_lift_to_drag_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_lift_to_drag_ratio += lift_to_drag_ratio(0.5, 0.5)
    var _t1_lift_to_drag_ratio = perf_counter_ns()
    var _ns_lift_to_drag_ratio = Float64(_t1_lift_to_drag_ratio - _t0_lift_to_drag_ratio) / Float64(N)
    print("MOJO_TIMING aviation::lift_to_drag_ratio", _ns_lift_to_drag_ratio, _acc_lift_to_drag_ratio)
    var _result_lift_to_drag_ratio = lift_to_drag_ratio(0.5, 0.5)
    var _summary_lift_to_drag_ratio = _summary_float64(_result_lift_to_drag_ratio)
    print("MOJO_RESULT aviation::lift_to_drag_ratio", _summary_lift_to_drag_ratio)
    var _acc_thrust_required: Float64 = 0.0
    var _t0_thrust_required = perf_counter_ns()
    for _ in range(N):
        _acc_thrust_required += thrust_required(0.5, 0.5, 0.5)
    var _t1_thrust_required = perf_counter_ns()
    var _ns_thrust_required = Float64(_t1_thrust_required - _t0_thrust_required) / Float64(N)
    print("MOJO_TIMING aviation::thrust_required", _ns_thrust_required, _acc_thrust_required)
    var _result_thrust_required = thrust_required(0.5, 0.5, 0.5)
    var _summary_thrust_required = _summary_float64(_result_thrust_required)
    print("MOJO_RESULT aviation::thrust_required", _summary_thrust_required)
    var _acc_range_breguet: Float64 = 0.0
    var _t0_range_breguet = perf_counter_ns()
    for _ in range(N):
        _acc_range_breguet += range_breguet(0.5, 0.5, 0.5, 0.5)
    var _t1_range_breguet = perf_counter_ns()
    var _ns_range_breguet = Float64(_t1_range_breguet - _t0_range_breguet) / Float64(N)
    print("MOJO_TIMING aviation::range_breguet", _ns_range_breguet, _acc_range_breguet)
    var _result_range_breguet = range_breguet(0.5, 0.5, 0.5, 0.5)
    var _summary_range_breguet = _summary_float64(_result_range_breguet)
    print("MOJO_RESULT aviation::range_breguet", _summary_range_breguet)
    var _acc_endurance_breguet: Float64 = 0.0
    var _t0_endurance_breguet = perf_counter_ns()
    for _ in range(N):
        _acc_endurance_breguet += endurance_breguet(0.5, 0.5, 0.5, 0.5)
    var _t1_endurance_breguet = perf_counter_ns()
    var _ns_endurance_breguet = Float64(_t1_endurance_breguet - _t0_endurance_breguet) / Float64(N)
    print("MOJO_TIMING aviation::endurance_breguet", _ns_endurance_breguet, _acc_endurance_breguet)
    var _result_endurance_breguet = endurance_breguet(0.5, 0.5, 0.5, 0.5)
    var _summary_endurance_breguet = _summary_float64(_result_endurance_breguet)
    print("MOJO_RESULT aviation::endurance_breguet", _summary_endurance_breguet)
    var _acc_indicated_airspeed: Float64 = 0.0
    var _t0_indicated_airspeed = perf_counter_ns()
    for _ in range(N):
        _acc_indicated_airspeed += indicated_airspeed(0.5)
    var _t1_indicated_airspeed = perf_counter_ns()
    var _ns_indicated_airspeed = Float64(_t1_indicated_airspeed - _t0_indicated_airspeed) / Float64(N)
    print("MOJO_TIMING aviation::indicated_airspeed", _ns_indicated_airspeed, _acc_indicated_airspeed)
    var _result_indicated_airspeed = indicated_airspeed(0.5)
    var _summary_indicated_airspeed = _summary_float64(_result_indicated_airspeed)
    print("MOJO_RESULT aviation::indicated_airspeed", _summary_indicated_airspeed)
    var _acc_true_airspeed: Float64 = 0.0
    var _t0_true_airspeed = perf_counter_ns()
    for _ in range(N):
        _acc_true_airspeed += true_airspeed(0.5, 0.5)
    var _t1_true_airspeed = perf_counter_ns()
    var _ns_true_airspeed = Float64(_t1_true_airspeed - _t0_true_airspeed) / Float64(N)
    print("MOJO_TIMING aviation::true_airspeed", _ns_true_airspeed, _acc_true_airspeed)
    var _result_true_airspeed = true_airspeed(0.5, 0.5)
    var _summary_true_airspeed = _summary_float64(_result_true_airspeed)
    print("MOJO_RESULT aviation::true_airspeed", _summary_true_airspeed)
    var _acc_mach_number: Float64 = 0.0
    var _t0_mach_number = perf_counter_ns()
    for _ in range(N):
        _acc_mach_number += mach_number(0.5, 0.5)
    var _t1_mach_number = perf_counter_ns()
    var _ns_mach_number = Float64(_t1_mach_number - _t0_mach_number) / Float64(N)
    print("MOJO_TIMING aviation::mach_number", _ns_mach_number, _acc_mach_number)
    var _result_mach_number = mach_number(0.5, 0.5)
    var _summary_mach_number = _summary_float64(_result_mach_number)
    print("MOJO_RESULT aviation::mach_number", _summary_mach_number)
    var _acc_rate_of_climb: Float64 = 0.0
    var _t0_rate_of_climb = perf_counter_ns()
    for _ in range(N):
        _acc_rate_of_climb += rate_of_climb(0.5, 0.5, 0.5)
    var _t1_rate_of_climb = perf_counter_ns()
    var _ns_rate_of_climb = Float64(_t1_rate_of_climb - _t0_rate_of_climb) / Float64(N)
    print("MOJO_TIMING aviation::rate_of_climb", _ns_rate_of_climb, _acc_rate_of_climb)
    var _result_rate_of_climb = rate_of_climb(0.5, 0.5, 0.5)
    var _summary_rate_of_climb = _summary_float64(_result_rate_of_climb)
    print("MOJO_RESULT aviation::rate_of_climb", _summary_rate_of_climb)
