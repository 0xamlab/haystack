"""bench_datetime.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from datetime import now_epoch, is_leap_year, year, month, day, hour, minute, second, epoch_to_iso, iso_to_epoch, format_duration_ms, days_between, add_days, day_of_week
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

    var _acc_now_epoch: Float64 = 0.0
    var _t0_now_epoch = perf_counter_ns()
    for _ in range(N):
        _acc_now_epoch += Float64(now_epoch())
    var _t1_now_epoch = perf_counter_ns()
    var _ns_now_epoch = Float64(_t1_now_epoch - _t0_now_epoch) / Float64(N)
    print("MOJO_TIMING datetime::now_epoch", _ns_now_epoch, _acc_now_epoch)
    var _result_now_epoch = now_epoch()
    var _summary_now_epoch = _summary_int(_result_now_epoch)
    print("MOJO_RESULT datetime::now_epoch", _summary_now_epoch)
    var _acc_is_leap_year: Float64 = 0.0
    var _t0_is_leap_year = perf_counter_ns()
    for _ in range(N):
        _acc_is_leap_year += Float64(is_leap_year(5))
    var _t1_is_leap_year = perf_counter_ns()
    var _ns_is_leap_year = Float64(_t1_is_leap_year - _t0_is_leap_year) / Float64(N)
    print("MOJO_TIMING datetime::is_leap_year", _ns_is_leap_year, _acc_is_leap_year)
    var _result_is_leap_year = is_leap_year(5)
    var _summary_is_leap_year = _summary_bool(_result_is_leap_year)
    print("MOJO_RESULT datetime::is_leap_year", _summary_is_leap_year)
    var _acc_year: Float64 = 0.0
    var _t0_year = perf_counter_ns()
    for _ in range(N):
        _acc_year += Float64(year(5))
    var _t1_year = perf_counter_ns()
    var _ns_year = Float64(_t1_year - _t0_year) / Float64(N)
    print("MOJO_TIMING datetime::year", _ns_year, _acc_year)
    var _result_year = year(5)
    var _summary_year = _summary_int(_result_year)
    print("MOJO_RESULT datetime::year", _summary_year)
    var _acc_month: Float64 = 0.0
    var _t0_month = perf_counter_ns()
    for _ in range(N):
        _acc_month += Float64(month(5))
    var _t1_month = perf_counter_ns()
    var _ns_month = Float64(_t1_month - _t0_month) / Float64(N)
    print("MOJO_TIMING datetime::month", _ns_month, _acc_month)
    var _result_month = month(5)
    var _summary_month = _summary_int(_result_month)
    print("MOJO_RESULT datetime::month", _summary_month)
    var _acc_day: Float64 = 0.0
    var _t0_day = perf_counter_ns()
    for _ in range(N):
        _acc_day += Float64(day(5))
    var _t1_day = perf_counter_ns()
    var _ns_day = Float64(_t1_day - _t0_day) / Float64(N)
    print("MOJO_TIMING datetime::day", _ns_day, _acc_day)
    var _result_day = day(5)
    var _summary_day = _summary_int(_result_day)
    print("MOJO_RESULT datetime::day", _summary_day)
    var _acc_hour: Float64 = 0.0
    var _t0_hour = perf_counter_ns()
    for _ in range(N):
        _acc_hour += Float64(hour(5))
    var _t1_hour = perf_counter_ns()
    var _ns_hour = Float64(_t1_hour - _t0_hour) / Float64(N)
    print("MOJO_TIMING datetime::hour", _ns_hour, _acc_hour)
    var _result_hour = hour(5)
    var _summary_hour = _summary_int(_result_hour)
    print("MOJO_RESULT datetime::hour", _summary_hour)
    var _acc_minute: Float64 = 0.0
    var _t0_minute = perf_counter_ns()
    for _ in range(N):
        _acc_minute += Float64(minute(5))
    var _t1_minute = perf_counter_ns()
    var _ns_minute = Float64(_t1_minute - _t0_minute) / Float64(N)
    print("MOJO_TIMING datetime::minute", _ns_minute, _acc_minute)
    var _result_minute = minute(5)
    var _summary_minute = _summary_int(_result_minute)
    print("MOJO_RESULT datetime::minute", _summary_minute)
    var _acc_second: Float64 = 0.0
    var _t0_second = perf_counter_ns()
    for _ in range(N):
        _acc_second += Float64(second(5))
    var _t1_second = perf_counter_ns()
    var _ns_second = Float64(_t1_second - _t0_second) / Float64(N)
    print("MOJO_TIMING datetime::second", _ns_second, _acc_second)
    var _result_second = second(5)
    var _summary_second = _summary_int(_result_second)
    print("MOJO_RESULT datetime::second", _summary_second)
    var _acc_epoch_to_iso: Float64 = 0.0
    var _t0_epoch_to_iso = perf_counter_ns()
    for _ in range(N):
        _ = epoch_to_iso(5)
    var _t1_epoch_to_iso = perf_counter_ns()
    var _ns_epoch_to_iso = Float64(_t1_epoch_to_iso - _t0_epoch_to_iso) / Float64(N)
    print("MOJO_TIMING datetime::epoch_to_iso", _ns_epoch_to_iso, _acc_epoch_to_iso)
    var _result_epoch_to_iso = epoch_to_iso(5)
    var _summary_epoch_to_iso = _summary_string(_result_epoch_to_iso)
    print("MOJO_RESULT datetime::epoch_to_iso", _summary_epoch_to_iso)
    var _acc_iso_to_epoch: Float64 = 0.0
    var _t0_iso_to_epoch = perf_counter_ns()
    for _ in range(N):
        _acc_iso_to_epoch += Float64(iso_to_epoch("test"))
    var _t1_iso_to_epoch = perf_counter_ns()
    var _ns_iso_to_epoch = Float64(_t1_iso_to_epoch - _t0_iso_to_epoch) / Float64(N)
    print("MOJO_TIMING datetime::iso_to_epoch", _ns_iso_to_epoch, _acc_iso_to_epoch)
    var _result_iso_to_epoch = iso_to_epoch("test")
    var _summary_iso_to_epoch = _summary_int(_result_iso_to_epoch)
    print("MOJO_RESULT datetime::iso_to_epoch", _summary_iso_to_epoch)
    var _acc_format_duration_ms: Float64 = 0.0
    var _t0_format_duration_ms = perf_counter_ns()
    for _ in range(N):
        _ = format_duration_ms(5)
    var _t1_format_duration_ms = perf_counter_ns()
    var _ns_format_duration_ms = Float64(_t1_format_duration_ms - _t0_format_duration_ms) / Float64(N)
    print("MOJO_TIMING datetime::format_duration_ms", _ns_format_duration_ms, _acc_format_duration_ms)
    var _result_format_duration_ms = format_duration_ms(5)
    var _summary_format_duration_ms = _summary_string(_result_format_duration_ms)
    print("MOJO_RESULT datetime::format_duration_ms", _summary_format_duration_ms)
    var _acc_days_between: Float64 = 0.0
    var _t0_days_between = perf_counter_ns()
    for _ in range(N):
        _acc_days_between += Float64(days_between(5, 5))
    var _t1_days_between = perf_counter_ns()
    var _ns_days_between = Float64(_t1_days_between - _t0_days_between) / Float64(N)
    print("MOJO_TIMING datetime::days_between", _ns_days_between, _acc_days_between)
    var _result_days_between = days_between(5, 5)
    var _summary_days_between = _summary_int(_result_days_between)
    print("MOJO_RESULT datetime::days_between", _summary_days_between)
    var _acc_add_days: Float64 = 0.0
    var _t0_add_days = perf_counter_ns()
    for _ in range(N):
        _acc_add_days += Float64(add_days(5, 5))
    var _t1_add_days = perf_counter_ns()
    var _ns_add_days = Float64(_t1_add_days - _t0_add_days) / Float64(N)
    print("MOJO_TIMING datetime::add_days", _ns_add_days, _acc_add_days)
    var _result_add_days = add_days(5, 5)
    var _summary_add_days = _summary_int(_result_add_days)
    print("MOJO_RESULT datetime::add_days", _summary_add_days)
    var _acc_day_of_week: Float64 = 0.0
    var _t0_day_of_week = perf_counter_ns()
    for _ in range(N):
        _acc_day_of_week += Float64(day_of_week(5))
    var _t1_day_of_week = perf_counter_ns()
    var _ns_day_of_week = Float64(_t1_day_of_week - _t0_day_of_week) / Float64(N)
    print("MOJO_TIMING datetime::day_of_week", _ns_day_of_week, _acc_day_of_week)
    var _result_day_of_week = day_of_week(5)
    var _summary_day_of_week = _summary_int(_result_day_of_week)
    print("MOJO_RESULT datetime::day_of_week", _summary_day_of_week)
