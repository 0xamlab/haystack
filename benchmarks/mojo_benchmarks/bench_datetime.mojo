"""bench_datetime.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from datetime import now_epoch, is_leap_year, year, month, day, hour, minute, second, epoch_to_iso, iso_to_epoch, format_duration_ms, days_between, add_days, day_of_week
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

    var _acc_now_epoch: Float64 = 0.0
    var _t0_now_epoch = perf_counter_ns()
    for _ in range(N):
        _acc_now_epoch += Float64(now_epoch())
    var _t1_now_epoch = perf_counter_ns()
    var _ns_now_epoch = Float64(_t1_now_epoch - _t0_now_epoch) / Float64(N)
    print("MOJO_TIMING datetime::now_epoch", _ns_now_epoch, _acc_now_epoch)
    var _acc_is_leap_year: Float64 = 0.0
    var _t0_is_leap_year = perf_counter_ns()
    for _ in range(N):
        _acc_is_leap_year += Float64(is_leap_year(5))
    var _t1_is_leap_year = perf_counter_ns()
    var _ns_is_leap_year = Float64(_t1_is_leap_year - _t0_is_leap_year) / Float64(N)
    print("MOJO_TIMING datetime::is_leap_year", _ns_is_leap_year, _acc_is_leap_year)
    var _acc_year: Float64 = 0.0
    var _t0_year = perf_counter_ns()
    for _ in range(N):
        _acc_year += Float64(year(5))
    var _t1_year = perf_counter_ns()
    var _ns_year = Float64(_t1_year - _t0_year) / Float64(N)
    print("MOJO_TIMING datetime::year", _ns_year, _acc_year)
    var _acc_month: Float64 = 0.0
    var _t0_month = perf_counter_ns()
    for _ in range(N):
        _acc_month += Float64(month(5))
    var _t1_month = perf_counter_ns()
    var _ns_month = Float64(_t1_month - _t0_month) / Float64(N)
    print("MOJO_TIMING datetime::month", _ns_month, _acc_month)
    var _acc_day: Float64 = 0.0
    var _t0_day = perf_counter_ns()
    for _ in range(N):
        _acc_day += Float64(day(5))
    var _t1_day = perf_counter_ns()
    var _ns_day = Float64(_t1_day - _t0_day) / Float64(N)
    print("MOJO_TIMING datetime::day", _ns_day, _acc_day)
    var _acc_hour: Float64 = 0.0
    var _t0_hour = perf_counter_ns()
    for _ in range(N):
        _acc_hour += Float64(hour(5))
    var _t1_hour = perf_counter_ns()
    var _ns_hour = Float64(_t1_hour - _t0_hour) / Float64(N)
    print("MOJO_TIMING datetime::hour", _ns_hour, _acc_hour)
    var _acc_minute: Float64 = 0.0
    var _t0_minute = perf_counter_ns()
    for _ in range(N):
        _acc_minute += Float64(minute(5))
    var _t1_minute = perf_counter_ns()
    var _ns_minute = Float64(_t1_minute - _t0_minute) / Float64(N)
    print("MOJO_TIMING datetime::minute", _ns_minute, _acc_minute)
    var _acc_second: Float64 = 0.0
    var _t0_second = perf_counter_ns()
    for _ in range(N):
        _acc_second += Float64(second(5))
    var _t1_second = perf_counter_ns()
    var _ns_second = Float64(_t1_second - _t0_second) / Float64(N)
    print("MOJO_TIMING datetime::second", _ns_second, _acc_second)
    var _acc_epoch_to_iso: Float64 = 0.0
    var _t0_epoch_to_iso = perf_counter_ns()
    for _ in range(N):
        _ = epoch_to_iso(5)
    var _t1_epoch_to_iso = perf_counter_ns()
    var _ns_epoch_to_iso = Float64(_t1_epoch_to_iso - _t0_epoch_to_iso) / Float64(N)
    print("MOJO_TIMING datetime::epoch_to_iso", _ns_epoch_to_iso, _acc_epoch_to_iso)
    var _acc_iso_to_epoch: Float64 = 0.0
    var _t0_iso_to_epoch = perf_counter_ns()
    for _ in range(N):
        _acc_iso_to_epoch += Float64(iso_to_epoch("test"))
    var _t1_iso_to_epoch = perf_counter_ns()
    var _ns_iso_to_epoch = Float64(_t1_iso_to_epoch - _t0_iso_to_epoch) / Float64(N)
    print("MOJO_TIMING datetime::iso_to_epoch", _ns_iso_to_epoch, _acc_iso_to_epoch)
    var _acc_format_duration_ms: Float64 = 0.0
    var _t0_format_duration_ms = perf_counter_ns()
    for _ in range(N):
        _ = format_duration_ms(5)
    var _t1_format_duration_ms = perf_counter_ns()
    var _ns_format_duration_ms = Float64(_t1_format_duration_ms - _t0_format_duration_ms) / Float64(N)
    print("MOJO_TIMING datetime::format_duration_ms", _ns_format_duration_ms, _acc_format_duration_ms)
    var _acc_days_between: Float64 = 0.0
    var _t0_days_between = perf_counter_ns()
    for _ in range(N):
        _acc_days_between += Float64(days_between(5, 5))
    var _t1_days_between = perf_counter_ns()
    var _ns_days_between = Float64(_t1_days_between - _t0_days_between) / Float64(N)
    print("MOJO_TIMING datetime::days_between", _ns_days_between, _acc_days_between)
    var _acc_add_days: Float64 = 0.0
    var _t0_add_days = perf_counter_ns()
    for _ in range(N):
        _acc_add_days += Float64(add_days(5, 5))
    var _t1_add_days = perf_counter_ns()
    var _ns_add_days = Float64(_t1_add_days - _t0_add_days) / Float64(N)
    print("MOJO_TIMING datetime::add_days", _ns_add_days, _acc_add_days)
    var _acc_day_of_week: Float64 = 0.0
    var _t0_day_of_week = perf_counter_ns()
    for _ in range(N):
        _acc_day_of_week += Float64(day_of_week(5))
    var _t1_day_of_week = perf_counter_ns()
    var _ns_day_of_week = Float64(_t1_day_of_week - _t0_day_of_week) / Float64(N)
    print("MOJO_TIMING datetime::day_of_week", _ns_day_of_week, _acc_day_of_week)
