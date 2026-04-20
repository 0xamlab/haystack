"""bench_data_csv_parser.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from data.csv_parser import _try_parse_float, _can_parse_float, _try_parse_int, _can_parse_int, _parse_fields, _split_csv_records, _escape_json_string
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

    var _acc__try_parse_float: Float64 = 0.0
    var _t0__try_parse_float = perf_counter_ns()
    for _ in range(N):
        _acc__try_parse_float += _try_parse_float("test")
    var _t1__try_parse_float = perf_counter_ns()
    var _ns__try_parse_float = Float64(_t1__try_parse_float - _t0__try_parse_float) / Float64(N)
    print("MOJO_TIMING data_csv_parser::_try_parse_float", _ns__try_parse_float, _acc__try_parse_float)
    var _acc__can_parse_float: Float64 = 0.0
    var _t0__can_parse_float = perf_counter_ns()
    for _ in range(N):
        _acc__can_parse_float += Float64(_can_parse_float("test"))
    var _t1__can_parse_float = perf_counter_ns()
    var _ns__can_parse_float = Float64(_t1__can_parse_float - _t0__can_parse_float) / Float64(N)
    print("MOJO_TIMING data_csv_parser::_can_parse_float", _ns__can_parse_float, _acc__can_parse_float)
    var _acc__try_parse_int: Float64 = 0.0
    var _t0__try_parse_int = perf_counter_ns()
    for _ in range(N):
        _acc__try_parse_int += Float64(_try_parse_int("test"))
    var _t1__try_parse_int = perf_counter_ns()
    var _ns__try_parse_int = Float64(_t1__try_parse_int - _t0__try_parse_int) / Float64(N)
    print("MOJO_TIMING data_csv_parser::_try_parse_int", _ns__try_parse_int, _acc__try_parse_int)
    var _acc__can_parse_int: Float64 = 0.0
    var _t0__can_parse_int = perf_counter_ns()
    for _ in range(N):
        _acc__can_parse_int += Float64(_can_parse_int("test"))
    var _t1__can_parse_int = perf_counter_ns()
    var _ns__can_parse_int = Float64(_t1__can_parse_int - _t0__can_parse_int) / Float64(N)
    print("MOJO_TIMING data_csv_parser::_can_parse_int", _ns__can_parse_int, _acc__can_parse_int)
    var _acc__parse_fields: Float64 = 0.0
    var _t0__parse_fields = perf_counter_ns()
    for _ in range(N):
        var _r__parse_fields = _parse_fields("test", 1)
        _acc__parse_fields += Float64(len(_r__parse_fields))
    var _t1__parse_fields = perf_counter_ns()
    var _ns__parse_fields = Float64(_t1__parse_fields - _t0__parse_fields) / Float64(N)
    print("MOJO_TIMING data_csv_parser::_parse_fields", _ns__parse_fields, _acc__parse_fields)
    var _acc__split_csv_records: Float64 = 0.0
    var _t0__split_csv_records = perf_counter_ns()
    for _ in range(N):
        var _r__split_csv_records = _split_csv_records("test")
        _acc__split_csv_records += Float64(len(_r__split_csv_records))
    var _t1__split_csv_records = perf_counter_ns()
    var _ns__split_csv_records = Float64(_t1__split_csv_records - _t0__split_csv_records) / Float64(N)
    print("MOJO_TIMING data_csv_parser::_split_csv_records", _ns__split_csv_records, _acc__split_csv_records)
    var _acc__escape_json_string: Float64 = 0.0
    var _t0__escape_json_string = perf_counter_ns()
    for _ in range(N):
        _ = _escape_json_string("test")
    var _t1__escape_json_string = perf_counter_ns()
    var _ns__escape_json_string = Float64(_t1__escape_json_string - _t0__escape_json_string) / Float64(N)
    print("MOJO_TIMING data_csv_parser::_escape_json_string", _ns__escape_json_string, _acc__escape_json_string)
