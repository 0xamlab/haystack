"""bench_network_protocol.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from network_protocol import http_status_text, is_success, is_redirect, is_client_error, is_server_error, mime_type, parse_content_type, is_json_type, is_text_type, build_query_string, parse_query_string
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

    var _acc_http_status_text: Float64 = 0.0
    var _t0_http_status_text = perf_counter_ns()
    for _ in range(N):
        _ = http_status_text(5)
    var _t1_http_status_text = perf_counter_ns()
    var _ns_http_status_text = Float64(_t1_http_status_text - _t0_http_status_text) / Float64(N)
    print("MOJO_TIMING network_protocol::http_status_text", _ns_http_status_text, _acc_http_status_text)
    var _result_http_status_text = http_status_text(5)
    var _summary_http_status_text = _summary_string(_result_http_status_text)
    print("MOJO_RESULT network_protocol::http_status_text", _summary_http_status_text)
    var _acc_is_success: Float64 = 0.0
    var _t0_is_success = perf_counter_ns()
    for _ in range(N):
        _acc_is_success += Float64(is_success(5))
    var _t1_is_success = perf_counter_ns()
    var _ns_is_success = Float64(_t1_is_success - _t0_is_success) / Float64(N)
    print("MOJO_TIMING network_protocol::is_success", _ns_is_success, _acc_is_success)
    var _result_is_success = is_success(5)
    var _summary_is_success = _summary_bool(_result_is_success)
    print("MOJO_RESULT network_protocol::is_success", _summary_is_success)
    var _acc_is_redirect: Float64 = 0.0
    var _t0_is_redirect = perf_counter_ns()
    for _ in range(N):
        _acc_is_redirect += Float64(is_redirect(5))
    var _t1_is_redirect = perf_counter_ns()
    var _ns_is_redirect = Float64(_t1_is_redirect - _t0_is_redirect) / Float64(N)
    print("MOJO_TIMING network_protocol::is_redirect", _ns_is_redirect, _acc_is_redirect)
    var _result_is_redirect = is_redirect(5)
    var _summary_is_redirect = _summary_bool(_result_is_redirect)
    print("MOJO_RESULT network_protocol::is_redirect", _summary_is_redirect)
    var _acc_is_client_error: Float64 = 0.0
    var _t0_is_client_error = perf_counter_ns()
    for _ in range(N):
        _acc_is_client_error += Float64(is_client_error(5))
    var _t1_is_client_error = perf_counter_ns()
    var _ns_is_client_error = Float64(_t1_is_client_error - _t0_is_client_error) / Float64(N)
    print("MOJO_TIMING network_protocol::is_client_error", _ns_is_client_error, _acc_is_client_error)
    var _result_is_client_error = is_client_error(5)
    var _summary_is_client_error = _summary_bool(_result_is_client_error)
    print("MOJO_RESULT network_protocol::is_client_error", _summary_is_client_error)
    var _acc_is_server_error: Float64 = 0.0
    var _t0_is_server_error = perf_counter_ns()
    for _ in range(N):
        _acc_is_server_error += Float64(is_server_error(5))
    var _t1_is_server_error = perf_counter_ns()
    var _ns_is_server_error = Float64(_t1_is_server_error - _t0_is_server_error) / Float64(N)
    print("MOJO_TIMING network_protocol::is_server_error", _ns_is_server_error, _acc_is_server_error)
    var _result_is_server_error = is_server_error(5)
    var _summary_is_server_error = _summary_bool(_result_is_server_error)
    print("MOJO_RESULT network_protocol::is_server_error", _summary_is_server_error)
    var _acc_mime_type: Float64 = 0.0
    var _t0_mime_type = perf_counter_ns()
    for _ in range(N):
        _ = mime_type("test")
    var _t1_mime_type = perf_counter_ns()
    var _ns_mime_type = Float64(_t1_mime_type - _t0_mime_type) / Float64(N)
    print("MOJO_TIMING network_protocol::mime_type", _ns_mime_type, _acc_mime_type)
    var _result_mime_type = mime_type("test")
    var _summary_mime_type = _summary_string(_result_mime_type)
    print("MOJO_RESULT network_protocol::mime_type", _summary_mime_type)
    var _acc_parse_content_type: Float64 = 0.0
    var _t0_parse_content_type = perf_counter_ns()
    for _ in range(N):
        _ = parse_content_type("test")
    var _t1_parse_content_type = perf_counter_ns()
    var _ns_parse_content_type = Float64(_t1_parse_content_type - _t0_parse_content_type) / Float64(N)
    print("MOJO_TIMING network_protocol::parse_content_type", _ns_parse_content_type, _acc_parse_content_type)
    var _result_parse_content_type = parse_content_type("test")
    var _summary_parse_content_type = _summary_string(_result_parse_content_type)
    print("MOJO_RESULT network_protocol::parse_content_type", _summary_parse_content_type)
    var _acc_is_json_type: Float64 = 0.0
    var _t0_is_json_type = perf_counter_ns()
    for _ in range(N):
        _acc_is_json_type += Float64(is_json_type("test"))
    var _t1_is_json_type = perf_counter_ns()
    var _ns_is_json_type = Float64(_t1_is_json_type - _t0_is_json_type) / Float64(N)
    print("MOJO_TIMING network_protocol::is_json_type", _ns_is_json_type, _acc_is_json_type)
    var _result_is_json_type = is_json_type("test")
    var _summary_is_json_type = _summary_bool(_result_is_json_type)
    print("MOJO_RESULT network_protocol::is_json_type", _summary_is_json_type)
    var _acc_is_text_type: Float64 = 0.0
    var _t0_is_text_type = perf_counter_ns()
    for _ in range(N):
        _acc_is_text_type += Float64(is_text_type("test"))
    var _t1_is_text_type = perf_counter_ns()
    var _ns_is_text_type = Float64(_t1_is_text_type - _t0_is_text_type) / Float64(N)
    print("MOJO_TIMING network_protocol::is_text_type", _ns_is_text_type, _acc_is_text_type)
    var _result_is_text_type = is_text_type("test")
    var _summary_is_text_type = _summary_bool(_result_is_text_type)
    print("MOJO_RESULT network_protocol::is_text_type", _summary_is_text_type)
    var _acc_build_query_string: Float64 = 0.0
    var _t0_build_query_string = perf_counter_ns()
    for _ in range(N):
        _ = build_query_string(["a","b","c","d","e"], ["a","b","c","d","e"])
    var _t1_build_query_string = perf_counter_ns()
    var _ns_build_query_string = Float64(_t1_build_query_string - _t0_build_query_string) / Float64(N)
    print("MOJO_TIMING network_protocol::build_query_string", _ns_build_query_string, _acc_build_query_string)
    var _result_build_query_string = build_query_string(["a","b","c","d","e"], ["a","b","c","d","e"])
    var _summary_build_query_string = _summary_string(_result_build_query_string)
    print("MOJO_RESULT network_protocol::build_query_string", _summary_build_query_string)
    var _acc_parse_query_string: Float64 = 0.0
    var _t0_parse_query_string = perf_counter_ns()
    for _ in range(N):
        var _r_parse_query_string = parse_query_string("test")
        _acc_parse_query_string += Float64(len(_r_parse_query_string))
    var _t1_parse_query_string = perf_counter_ns()
    var _ns_parse_query_string = Float64(_t1_parse_query_string - _t0_parse_query_string) / Float64(N)
    print("MOJO_TIMING network_protocol::parse_query_string", _ns_parse_query_string, _acc_parse_query_string)
    var _result_parse_query_string = parse_query_string("test")
    var _summary_parse_query_string = _summary_list_list_string(_result_parse_query_string)
    print("MOJO_RESULT network_protocol::parse_query_string", _summary_parse_query_string)
