"""bench_time_zone.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from time_zone import utc_offset, is_valid_zone, is_dst, effective_offset, time_difference, format_offset, convert_time, local_to_utc, utc_to_local, overlap_hours
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

    var _acc_utc_offset: Float64 = 0.0
    var _t0_utc_offset = perf_counter_ns()
    for _ in range(N):
        _acc_utc_offset += utc_offset("test")
    var _t1_utc_offset = perf_counter_ns()
    var _ns_utc_offset = Float64(_t1_utc_offset - _t0_utc_offset) / Float64(N)
    print("MOJO_TIMING time_zone::utc_offset", _ns_utc_offset, _acc_utc_offset)
    var _result_utc_offset = utc_offset("test")
    var _summary_utc_offset = _summary_float64(_result_utc_offset)
    print("MOJO_RESULT time_zone::utc_offset", _summary_utc_offset)
    var _acc_is_valid_zone: Float64 = 0.0
    var _t0_is_valid_zone = perf_counter_ns()
    for _ in range(N):
        _acc_is_valid_zone += Float64(is_valid_zone("test"))
    var _t1_is_valid_zone = perf_counter_ns()
    var _ns_is_valid_zone = Float64(_t1_is_valid_zone - _t0_is_valid_zone) / Float64(N)
    print("MOJO_TIMING time_zone::is_valid_zone", _ns_is_valid_zone, _acc_is_valid_zone)
    var _result_is_valid_zone = is_valid_zone("test")
    var _summary_is_valid_zone = _summary_bool(_result_is_valid_zone)
    print("MOJO_RESULT time_zone::is_valid_zone", _summary_is_valid_zone)
    var _acc_is_dst: Float64 = 0.0
    var _t0_is_dst = perf_counter_ns()
    for _ in range(N):
        _acc_is_dst += Float64(is_dst(5, "test"))
    var _t1_is_dst = perf_counter_ns()
    var _ns_is_dst = Float64(_t1_is_dst - _t0_is_dst) / Float64(N)
    print("MOJO_TIMING time_zone::is_dst", _ns_is_dst, _acc_is_dst)
    var _result_is_dst = is_dst(5, "test")
    var _summary_is_dst = _summary_bool(_result_is_dst)
    print("MOJO_RESULT time_zone::is_dst", _summary_is_dst)
    var _acc_effective_offset: Float64 = 0.0
    var _t0_effective_offset = perf_counter_ns()
    for _ in range(N):
        _acc_effective_offset += effective_offset("test", 5)
    var _t1_effective_offset = perf_counter_ns()
    var _ns_effective_offset = Float64(_t1_effective_offset - _t0_effective_offset) / Float64(N)
    print("MOJO_TIMING time_zone::effective_offset", _ns_effective_offset, _acc_effective_offset)
    var _result_effective_offset = effective_offset("test", 5)
    var _summary_effective_offset = _summary_float64(_result_effective_offset)
    print("MOJO_RESULT time_zone::effective_offset", _summary_effective_offset)
    var _acc_time_difference: Float64 = 0.0
    var _t0_time_difference = perf_counter_ns()
    for _ in range(N):
        _acc_time_difference += time_difference("test", "test")
    var _t1_time_difference = perf_counter_ns()
    var _ns_time_difference = Float64(_t1_time_difference - _t0_time_difference) / Float64(N)
    print("MOJO_TIMING time_zone::time_difference", _ns_time_difference, _acc_time_difference)
    var _result_time_difference = time_difference("test", "test")
    var _summary_time_difference = _summary_float64(_result_time_difference)
    print("MOJO_RESULT time_zone::time_difference", _summary_time_difference)
    var _acc_format_offset: Float64 = 0.0
    var _t0_format_offset = perf_counter_ns()
    for _ in range(N):
        _ = format_offset(0.5)
    var _t1_format_offset = perf_counter_ns()
    var _ns_format_offset = Float64(_t1_format_offset - _t0_format_offset) / Float64(N)
    print("MOJO_TIMING time_zone::format_offset", _ns_format_offset, _acc_format_offset)
    var _result_format_offset = format_offset(0.5)
    var _summary_format_offset = _summary_string(_result_format_offset)
    print("MOJO_RESULT time_zone::format_offset", _summary_format_offset)
    var _acc_convert_time: Float64 = 0.0
    var _t0_convert_time = perf_counter_ns()
    for _ in range(N):
        var _r_convert_time = convert_time(5, 5, "test", "test")
        _acc_convert_time += Float64(len(_r_convert_time))
    var _t1_convert_time = perf_counter_ns()
    var _ns_convert_time = Float64(_t1_convert_time - _t0_convert_time) / Float64(N)
    print("MOJO_TIMING time_zone::convert_time", _ns_convert_time, _acc_convert_time)
    var _result_convert_time = convert_time(5, 5, "test", "test")
    var _summary_convert_time = _summary_list_int(_result_convert_time)
    print("MOJO_RESULT time_zone::convert_time", _summary_convert_time)
    var _acc_local_to_utc: Float64 = 0.0
    var _t0_local_to_utc = perf_counter_ns()
    for _ in range(N):
        var _r_local_to_utc = local_to_utc(5, 5, "test")
        _acc_local_to_utc += Float64(len(_r_local_to_utc))
    var _t1_local_to_utc = perf_counter_ns()
    var _ns_local_to_utc = Float64(_t1_local_to_utc - _t0_local_to_utc) / Float64(N)
    print("MOJO_TIMING time_zone::local_to_utc", _ns_local_to_utc, _acc_local_to_utc)
    var _result_local_to_utc = local_to_utc(5, 5, "test")
    var _summary_local_to_utc = _summary_list_int(_result_local_to_utc)
    print("MOJO_RESULT time_zone::local_to_utc", _summary_local_to_utc)
    var _acc_utc_to_local: Float64 = 0.0
    var _t0_utc_to_local = perf_counter_ns()
    for _ in range(N):
        var _r_utc_to_local = utc_to_local(5, 5, "test")
        _acc_utc_to_local += Float64(len(_r_utc_to_local))
    var _t1_utc_to_local = perf_counter_ns()
    var _ns_utc_to_local = Float64(_t1_utc_to_local - _t0_utc_to_local) / Float64(N)
    print("MOJO_TIMING time_zone::utc_to_local", _ns_utc_to_local, _acc_utc_to_local)
    var _result_utc_to_local = utc_to_local(5, 5, "test")
    var _summary_utc_to_local = _summary_list_int(_result_utc_to_local)
    print("MOJO_RESULT time_zone::utc_to_local", _summary_utc_to_local)
    var _acc_overlap_hours: Float64 = 0.0
    var _t0_overlap_hours = perf_counter_ns()
    for _ in range(N):
        _acc_overlap_hours += Float64(overlap_hours("test", "test", 5, 5))
    var _t1_overlap_hours = perf_counter_ns()
    var _ns_overlap_hours = Float64(_t1_overlap_hours - _t0_overlap_hours) / Float64(N)
    print("MOJO_TIMING time_zone::overlap_hours", _ns_overlap_hours, _acc_overlap_hours)
    var _result_overlap_hours = overlap_hours("test", "test", 5, 5)
    var _summary_overlap_hours = _summary_int(_result_overlap_hours)
    print("MOJO_RESULT time_zone::overlap_hours", _summary_overlap_hours)
