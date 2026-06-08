"""bench_data_csv_parser.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from data.csv_parser import _try_parse_float, _can_parse_float, _try_parse_int, _can_parse_int, _parse_fields, _split_csv_records, _escape_json_string
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

    var _acc__try_parse_float: Float64 = 0.0
    var _t0__try_parse_float = perf_counter_ns()
    for _ in range(N):
        _acc__try_parse_float += _try_parse_float("test")
    var _t1__try_parse_float = perf_counter_ns()
    var _ns__try_parse_float = Float64(_t1__try_parse_float - _t0__try_parse_float) / Float64(N)
    print("MOJO_TIMING data_csv_parser::_try_parse_float", _ns__try_parse_float, _acc__try_parse_float)
    var _result__try_parse_float = _try_parse_float("test")
    var _summary__try_parse_float = _summary_float64(_result__try_parse_float)
    print("MOJO_RESULT data_csv_parser::_try_parse_float", _summary__try_parse_float)
    var _acc__can_parse_float: Float64 = 0.0
    var _t0__can_parse_float = perf_counter_ns()
    for _ in range(N):
        _acc__can_parse_float += Float64(_can_parse_float("test"))
    var _t1__can_parse_float = perf_counter_ns()
    var _ns__can_parse_float = Float64(_t1__can_parse_float - _t0__can_parse_float) / Float64(N)
    print("MOJO_TIMING data_csv_parser::_can_parse_float", _ns__can_parse_float, _acc__can_parse_float)
    var _result__can_parse_float = _can_parse_float("test")
    var _summary__can_parse_float = _summary_bool(_result__can_parse_float)
    print("MOJO_RESULT data_csv_parser::_can_parse_float", _summary__can_parse_float)
    var _acc__try_parse_int: Float64 = 0.0
    var _t0__try_parse_int = perf_counter_ns()
    for _ in range(N):
        _acc__try_parse_int += Float64(_try_parse_int("test"))
    var _t1__try_parse_int = perf_counter_ns()
    var _ns__try_parse_int = Float64(_t1__try_parse_int - _t0__try_parse_int) / Float64(N)
    print("MOJO_TIMING data_csv_parser::_try_parse_int", _ns__try_parse_int, _acc__try_parse_int)
    var _result__try_parse_int = _try_parse_int("test")
    var _summary__try_parse_int = _summary_int(_result__try_parse_int)
    print("MOJO_RESULT data_csv_parser::_try_parse_int", _summary__try_parse_int)
    var _acc__can_parse_int: Float64 = 0.0
    var _t0__can_parse_int = perf_counter_ns()
    for _ in range(N):
        _acc__can_parse_int += Float64(_can_parse_int("test"))
    var _t1__can_parse_int = perf_counter_ns()
    var _ns__can_parse_int = Float64(_t1__can_parse_int - _t0__can_parse_int) / Float64(N)
    print("MOJO_TIMING data_csv_parser::_can_parse_int", _ns__can_parse_int, _acc__can_parse_int)
    var _result__can_parse_int = _can_parse_int("test")
    var _summary__can_parse_int = _summary_bool(_result__can_parse_int)
    print("MOJO_RESULT data_csv_parser::_can_parse_int", _summary__can_parse_int)
    var _acc__parse_fields: Float64 = 0.0
    var _t0__parse_fields = perf_counter_ns()
    for _ in range(N):
        var _r__parse_fields = _parse_fields("test", 1)
        _acc__parse_fields += Float64(len(_r__parse_fields))
    var _t1__parse_fields = perf_counter_ns()
    var _ns__parse_fields = Float64(_t1__parse_fields - _t0__parse_fields) / Float64(N)
    print("MOJO_TIMING data_csv_parser::_parse_fields", _ns__parse_fields, _acc__parse_fields)
    var _result__parse_fields = _parse_fields("test", 1)
    var _summary__parse_fields = _summary_list_string(_result__parse_fields)
    print("MOJO_RESULT data_csv_parser::_parse_fields", _summary__parse_fields)
    var _acc__split_csv_records: Float64 = 0.0
    var _t0__split_csv_records = perf_counter_ns()
    for _ in range(N):
        var _r__split_csv_records = _split_csv_records("test")
        _acc__split_csv_records += Float64(len(_r__split_csv_records))
    var _t1__split_csv_records = perf_counter_ns()
    var _ns__split_csv_records = Float64(_t1__split_csv_records - _t0__split_csv_records) / Float64(N)
    print("MOJO_TIMING data_csv_parser::_split_csv_records", _ns__split_csv_records, _acc__split_csv_records)
    var _result__split_csv_records = _split_csv_records("test")
    var _summary__split_csv_records = _summary_list_string(_result__split_csv_records)
    print("MOJO_RESULT data_csv_parser::_split_csv_records", _summary__split_csv_records)
    var _acc__escape_json_string: Float64 = 0.0
    var _t0__escape_json_string = perf_counter_ns()
    for _ in range(N):
        _ = _escape_json_string("test")
    var _t1__escape_json_string = perf_counter_ns()
    var _ns__escape_json_string = Float64(_t1__escape_json_string - _t0__escape_json_string) / Float64(N)
    print("MOJO_TIMING data_csv_parser::_escape_json_string", _ns__escape_json_string, _acc__escape_json_string)
    var _result__escape_json_string = _escape_json_string("test")
    var _summary__escape_json_string = _summary_string(_result__escape_json_string)
    print("MOJO_RESULT data_csv_parser::_escape_json_string", _summary__escape_json_string)
