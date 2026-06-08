"""bench_aerospace.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from aerospace import dynamic_pressure, lift_force, drag_force, lift_to_drag_ratio, thrust_required, specific_impulse, tsiolkovsky_delta_v, mach_number, speed_of_sound, orbital_velocity, escape_velocity, hohmann_delta_v
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

    var _acc_dynamic_pressure: Float64 = 0.0
    var _t0_dynamic_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_dynamic_pressure += dynamic_pressure(0.5, 0.5)
    var _t1_dynamic_pressure = perf_counter_ns()
    var _ns_dynamic_pressure = Float64(_t1_dynamic_pressure - _t0_dynamic_pressure) / Float64(N)
    print("MOJO_TIMING aerospace::dynamic_pressure", _ns_dynamic_pressure, _acc_dynamic_pressure)
    var _result_dynamic_pressure = dynamic_pressure(0.5, 0.5)
    var _summary_dynamic_pressure = _summary_float64(_result_dynamic_pressure)
    print("MOJO_RESULT aerospace::dynamic_pressure", _summary_dynamic_pressure)
    var _acc_lift_force: Float64 = 0.0
    var _t0_lift_force = perf_counter_ns()
    for _ in range(N):
        _acc_lift_force += lift_force(0.5, 0.5, 0.5)
    var _t1_lift_force = perf_counter_ns()
    var _ns_lift_force = Float64(_t1_lift_force - _t0_lift_force) / Float64(N)
    print("MOJO_TIMING aerospace::lift_force", _ns_lift_force, _acc_lift_force)
    var _result_lift_force = lift_force(0.5, 0.5, 0.5)
    var _summary_lift_force = _summary_float64(_result_lift_force)
    print("MOJO_RESULT aerospace::lift_force", _summary_lift_force)
    var _acc_drag_force: Float64 = 0.0
    var _t0_drag_force = perf_counter_ns()
    for _ in range(N):
        _acc_drag_force += drag_force(0.5, 0.5, 0.5)
    var _t1_drag_force = perf_counter_ns()
    var _ns_drag_force = Float64(_t1_drag_force - _t0_drag_force) / Float64(N)
    print("MOJO_TIMING aerospace::drag_force", _ns_drag_force, _acc_drag_force)
    var _result_drag_force = drag_force(0.5, 0.5, 0.5)
    var _summary_drag_force = _summary_float64(_result_drag_force)
    print("MOJO_RESULT aerospace::drag_force", _summary_drag_force)
    var _acc_lift_to_drag_ratio: Float64 = 0.0
    var _t0_lift_to_drag_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_lift_to_drag_ratio += lift_to_drag_ratio(0.5, 0.5)
    var _t1_lift_to_drag_ratio = perf_counter_ns()
    var _ns_lift_to_drag_ratio = Float64(_t1_lift_to_drag_ratio - _t0_lift_to_drag_ratio) / Float64(N)
    print("MOJO_TIMING aerospace::lift_to_drag_ratio", _ns_lift_to_drag_ratio, _acc_lift_to_drag_ratio)
    var _result_lift_to_drag_ratio = lift_to_drag_ratio(0.5, 0.5)
    var _summary_lift_to_drag_ratio = _summary_float64(_result_lift_to_drag_ratio)
    print("MOJO_RESULT aerospace::lift_to_drag_ratio", _summary_lift_to_drag_ratio)
    var _acc_thrust_required: Float64 = 0.0
    var _t0_thrust_required = perf_counter_ns()
    for _ in range(N):
        _acc_thrust_required += thrust_required(0.5, 0.5)
    var _t1_thrust_required = perf_counter_ns()
    var _ns_thrust_required = Float64(_t1_thrust_required - _t0_thrust_required) / Float64(N)
    print("MOJO_TIMING aerospace::thrust_required", _ns_thrust_required, _acc_thrust_required)
    var _result_thrust_required = thrust_required(0.5, 0.5)
    var _summary_thrust_required = _summary_float64(_result_thrust_required)
    print("MOJO_RESULT aerospace::thrust_required", _summary_thrust_required)
    var _acc_specific_impulse: Float64 = 0.0
    var _t0_specific_impulse = perf_counter_ns()
    for _ in range(N):
        _acc_specific_impulse += specific_impulse(0.5, 0.5)
    var _t1_specific_impulse = perf_counter_ns()
    var _ns_specific_impulse = Float64(_t1_specific_impulse - _t0_specific_impulse) / Float64(N)
    print("MOJO_TIMING aerospace::specific_impulse", _ns_specific_impulse, _acc_specific_impulse)
    var _result_specific_impulse = specific_impulse(0.5, 0.5)
    var _summary_specific_impulse = _summary_float64(_result_specific_impulse)
    print("MOJO_RESULT aerospace::specific_impulse", _summary_specific_impulse)
    var _acc_tsiolkovsky_delta_v: Float64 = 0.0
    var _t0_tsiolkovsky_delta_v = perf_counter_ns()
    for _ in range(N):
        _acc_tsiolkovsky_delta_v += tsiolkovsky_delta_v(0.5, 0.5, 0.5)
    var _t1_tsiolkovsky_delta_v = perf_counter_ns()
    var _ns_tsiolkovsky_delta_v = Float64(_t1_tsiolkovsky_delta_v - _t0_tsiolkovsky_delta_v) / Float64(N)
    print("MOJO_TIMING aerospace::tsiolkovsky_delta_v", _ns_tsiolkovsky_delta_v, _acc_tsiolkovsky_delta_v)
    var _result_tsiolkovsky_delta_v = tsiolkovsky_delta_v(0.5, 0.5, 0.5)
    var _summary_tsiolkovsky_delta_v = _summary_float64(_result_tsiolkovsky_delta_v)
    print("MOJO_RESULT aerospace::tsiolkovsky_delta_v", _summary_tsiolkovsky_delta_v)
    var _acc_mach_number: Float64 = 0.0
    var _t0_mach_number = perf_counter_ns()
    for _ in range(N):
        _acc_mach_number += mach_number(0.5, 0.5)
    var _t1_mach_number = perf_counter_ns()
    var _ns_mach_number = Float64(_t1_mach_number - _t0_mach_number) / Float64(N)
    print("MOJO_TIMING aerospace::mach_number", _ns_mach_number, _acc_mach_number)
    var _result_mach_number = mach_number(0.5, 0.5)
    var _summary_mach_number = _summary_float64(_result_mach_number)
    print("MOJO_RESULT aerospace::mach_number", _summary_mach_number)
    var _acc_speed_of_sound: Float64 = 0.0
    var _t0_speed_of_sound = perf_counter_ns()
    for _ in range(N):
        _acc_speed_of_sound += speed_of_sound(0.5, 0.5, 0.5)
    var _t1_speed_of_sound = perf_counter_ns()
    var _ns_speed_of_sound = Float64(_t1_speed_of_sound - _t0_speed_of_sound) / Float64(N)
    print("MOJO_TIMING aerospace::speed_of_sound", _ns_speed_of_sound, _acc_speed_of_sound)
    var _result_speed_of_sound = speed_of_sound(0.5, 0.5, 0.5)
    var _summary_speed_of_sound = _summary_float64(_result_speed_of_sound)
    print("MOJO_RESULT aerospace::speed_of_sound", _summary_speed_of_sound)
    var _acc_orbital_velocity: Float64 = 0.0
    var _t0_orbital_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_orbital_velocity += orbital_velocity(0.5, 0.5)
    var _t1_orbital_velocity = perf_counter_ns()
    var _ns_orbital_velocity = Float64(_t1_orbital_velocity - _t0_orbital_velocity) / Float64(N)
    print("MOJO_TIMING aerospace::orbital_velocity", _ns_orbital_velocity, _acc_orbital_velocity)
    var _result_orbital_velocity = orbital_velocity(0.5, 0.5)
    var _summary_orbital_velocity = _summary_float64(_result_orbital_velocity)
    print("MOJO_RESULT aerospace::orbital_velocity", _summary_orbital_velocity)
    var _acc_escape_velocity: Float64 = 0.0
    var _t0_escape_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_escape_velocity += escape_velocity(0.5, 0.5)
    var _t1_escape_velocity = perf_counter_ns()
    var _ns_escape_velocity = Float64(_t1_escape_velocity - _t0_escape_velocity) / Float64(N)
    print("MOJO_TIMING aerospace::escape_velocity", _ns_escape_velocity, _acc_escape_velocity)
    var _result_escape_velocity = escape_velocity(0.5, 0.5)
    var _summary_escape_velocity = _summary_float64(_result_escape_velocity)
    print("MOJO_RESULT aerospace::escape_velocity", _summary_escape_velocity)
    var _acc_hohmann_delta_v: Float64 = 0.0
    var _t0_hohmann_delta_v = perf_counter_ns()
    for _ in range(N):
        _acc_hohmann_delta_v += hohmann_delta_v(0.5, 0.5, 0.5)
    var _t1_hohmann_delta_v = perf_counter_ns()
    var _ns_hohmann_delta_v = Float64(_t1_hohmann_delta_v - _t0_hohmann_delta_v) / Float64(N)
    print("MOJO_TIMING aerospace::hohmann_delta_v", _ns_hohmann_delta_v, _acc_hohmann_delta_v)
    var _result_hohmann_delta_v = hohmann_delta_v(0.5, 0.5, 0.5)
    var _summary_hohmann_delta_v = _summary_float64(_result_hohmann_delta_v)
    print("MOJO_RESULT aerospace::hohmann_delta_v", _summary_hohmann_delta_v)
