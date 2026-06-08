"""bench_units.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from units import convert_length, convert_mass, convert_temperature, convert_time, convert_area, convert_volume, convert_speed, convert_data
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

    var _acc_convert_length: Float64 = 0.0
    var _t0_convert_length = perf_counter_ns()
    for _ in range(N):
        _acc_convert_length += convert_length(0.5, "test", "test")
    var _t1_convert_length = perf_counter_ns()
    var _ns_convert_length = Float64(_t1_convert_length - _t0_convert_length) / Float64(N)
    print("MOJO_TIMING units::convert_length", _ns_convert_length, _acc_convert_length)
    var _result_convert_length = convert_length(0.5, "test", "test")
    var _summary_convert_length = _summary_float64(_result_convert_length)
    print("MOJO_RESULT units::convert_length", _summary_convert_length)
    var _acc_convert_mass: Float64 = 0.0
    var _t0_convert_mass = perf_counter_ns()
    for _ in range(N):
        _acc_convert_mass += convert_mass(0.5, "test", "test")
    var _t1_convert_mass = perf_counter_ns()
    var _ns_convert_mass = Float64(_t1_convert_mass - _t0_convert_mass) / Float64(N)
    print("MOJO_TIMING units::convert_mass", _ns_convert_mass, _acc_convert_mass)
    var _result_convert_mass = convert_mass(0.5, "test", "test")
    var _summary_convert_mass = _summary_float64(_result_convert_mass)
    print("MOJO_RESULT units::convert_mass", _summary_convert_mass)
    var _acc_convert_temperature: Float64 = 0.0
    var _t0_convert_temperature = perf_counter_ns()
    for _ in range(N):
        _acc_convert_temperature += convert_temperature(0.5, "test", "test")
    var _t1_convert_temperature = perf_counter_ns()
    var _ns_convert_temperature = Float64(_t1_convert_temperature - _t0_convert_temperature) / Float64(N)
    print("MOJO_TIMING units::convert_temperature", _ns_convert_temperature, _acc_convert_temperature)
    var _result_convert_temperature = convert_temperature(0.5, "test", "test")
    var _summary_convert_temperature = _summary_float64(_result_convert_temperature)
    print("MOJO_RESULT units::convert_temperature", _summary_convert_temperature)
    var _acc_convert_time: Float64 = 0.0
    var _t0_convert_time = perf_counter_ns()
    for _ in range(N):
        _acc_convert_time += convert_time(0.5, "test", "test")
    var _t1_convert_time = perf_counter_ns()
    var _ns_convert_time = Float64(_t1_convert_time - _t0_convert_time) / Float64(N)
    print("MOJO_TIMING units::convert_time", _ns_convert_time, _acc_convert_time)
    var _result_convert_time = convert_time(0.5, "test", "test")
    var _summary_convert_time = _summary_float64(_result_convert_time)
    print("MOJO_RESULT units::convert_time", _summary_convert_time)
    var _acc_convert_area: Float64 = 0.0
    var _t0_convert_area = perf_counter_ns()
    for _ in range(N):
        _acc_convert_area += convert_area(0.5, "test", "test")
    var _t1_convert_area = perf_counter_ns()
    var _ns_convert_area = Float64(_t1_convert_area - _t0_convert_area) / Float64(N)
    print("MOJO_TIMING units::convert_area", _ns_convert_area, _acc_convert_area)
    var _result_convert_area = convert_area(0.5, "test", "test")
    var _summary_convert_area = _summary_float64(_result_convert_area)
    print("MOJO_RESULT units::convert_area", _summary_convert_area)
    var _acc_convert_volume: Float64 = 0.0
    var _t0_convert_volume = perf_counter_ns()
    for _ in range(N):
        _acc_convert_volume += convert_volume(0.5, "test", "test")
    var _t1_convert_volume = perf_counter_ns()
    var _ns_convert_volume = Float64(_t1_convert_volume - _t0_convert_volume) / Float64(N)
    print("MOJO_TIMING units::convert_volume", _ns_convert_volume, _acc_convert_volume)
    var _result_convert_volume = convert_volume(0.5, "test", "test")
    var _summary_convert_volume = _summary_float64(_result_convert_volume)
    print("MOJO_RESULT units::convert_volume", _summary_convert_volume)
    var _acc_convert_speed: Float64 = 0.0
    var _t0_convert_speed = perf_counter_ns()
    for _ in range(N):
        _acc_convert_speed += convert_speed(0.5, "test", "test")
    var _t1_convert_speed = perf_counter_ns()
    var _ns_convert_speed = Float64(_t1_convert_speed - _t0_convert_speed) / Float64(N)
    print("MOJO_TIMING units::convert_speed", _ns_convert_speed, _acc_convert_speed)
    var _result_convert_speed = convert_speed(0.5, "test", "test")
    var _summary_convert_speed = _summary_float64(_result_convert_speed)
    print("MOJO_RESULT units::convert_speed", _summary_convert_speed)
    var _acc_convert_data: Float64 = 0.0
    var _t0_convert_data = perf_counter_ns()
    for _ in range(N):
        _acc_convert_data += convert_data(0.5, "test", "test")
    var _t1_convert_data = perf_counter_ns()
    var _ns_convert_data = Float64(_t1_convert_data - _t0_convert_data) / Float64(N)
    print("MOJO_TIMING units::convert_data", _ns_convert_data, _acc_convert_data)
    var _result_convert_data = convert_data(0.5, "test", "test")
    var _summary_convert_data = _summary_float64(_result_convert_data)
    print("MOJO_RESULT units::convert_data", _summary_convert_data)
