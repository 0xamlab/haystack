"""bench_network_protocol.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from network_protocol import http_status_text, is_success, is_redirect, is_client_error, is_server_error, mime_type, parse_content_type, is_json_type, is_text_type, build_query_string, parse_query_string
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

    var _acc_http_status_text: Float64 = 0.0
    var _t0_http_status_text = perf_counter_ns()
    for _ in range(N):
        _ = http_status_text(5)
    var _t1_http_status_text = perf_counter_ns()
    var _ns_http_status_text = Float64(_t1_http_status_text - _t0_http_status_text) / Float64(N)
    print("MOJO_TIMING network_protocol::http_status_text", _ns_http_status_text, _acc_http_status_text)
    var _acc_is_success: Float64 = 0.0
    var _t0_is_success = perf_counter_ns()
    for _ in range(N):
        _acc_is_success += Float64(is_success(5))
    var _t1_is_success = perf_counter_ns()
    var _ns_is_success = Float64(_t1_is_success - _t0_is_success) / Float64(N)
    print("MOJO_TIMING network_protocol::is_success", _ns_is_success, _acc_is_success)
    var _acc_is_redirect: Float64 = 0.0
    var _t0_is_redirect = perf_counter_ns()
    for _ in range(N):
        _acc_is_redirect += Float64(is_redirect(5))
    var _t1_is_redirect = perf_counter_ns()
    var _ns_is_redirect = Float64(_t1_is_redirect - _t0_is_redirect) / Float64(N)
    print("MOJO_TIMING network_protocol::is_redirect", _ns_is_redirect, _acc_is_redirect)
    var _acc_is_client_error: Float64 = 0.0
    var _t0_is_client_error = perf_counter_ns()
    for _ in range(N):
        _acc_is_client_error += Float64(is_client_error(5))
    var _t1_is_client_error = perf_counter_ns()
    var _ns_is_client_error = Float64(_t1_is_client_error - _t0_is_client_error) / Float64(N)
    print("MOJO_TIMING network_protocol::is_client_error", _ns_is_client_error, _acc_is_client_error)
    var _acc_is_server_error: Float64 = 0.0
    var _t0_is_server_error = perf_counter_ns()
    for _ in range(N):
        _acc_is_server_error += Float64(is_server_error(5))
    var _t1_is_server_error = perf_counter_ns()
    var _ns_is_server_error = Float64(_t1_is_server_error - _t0_is_server_error) / Float64(N)
    print("MOJO_TIMING network_protocol::is_server_error", _ns_is_server_error, _acc_is_server_error)
    var _acc_mime_type: Float64 = 0.0
    var _t0_mime_type = perf_counter_ns()
    for _ in range(N):
        _ = mime_type("test")
    var _t1_mime_type = perf_counter_ns()
    var _ns_mime_type = Float64(_t1_mime_type - _t0_mime_type) / Float64(N)
    print("MOJO_TIMING network_protocol::mime_type", _ns_mime_type, _acc_mime_type)
    var _acc_parse_content_type: Float64 = 0.0
    var _t0_parse_content_type = perf_counter_ns()
    for _ in range(N):
        _ = parse_content_type("test")
    var _t1_parse_content_type = perf_counter_ns()
    var _ns_parse_content_type = Float64(_t1_parse_content_type - _t0_parse_content_type) / Float64(N)
    print("MOJO_TIMING network_protocol::parse_content_type", _ns_parse_content_type, _acc_parse_content_type)
    var _acc_is_json_type: Float64 = 0.0
    var _t0_is_json_type = perf_counter_ns()
    for _ in range(N):
        _acc_is_json_type += Float64(is_json_type("test"))
    var _t1_is_json_type = perf_counter_ns()
    var _ns_is_json_type = Float64(_t1_is_json_type - _t0_is_json_type) / Float64(N)
    print("MOJO_TIMING network_protocol::is_json_type", _ns_is_json_type, _acc_is_json_type)
    var _acc_is_text_type: Float64 = 0.0
    var _t0_is_text_type = perf_counter_ns()
    for _ in range(N):
        _acc_is_text_type += Float64(is_text_type("test"))
    var _t1_is_text_type = perf_counter_ns()
    var _ns_is_text_type = Float64(_t1_is_text_type - _t0_is_text_type) / Float64(N)
    print("MOJO_TIMING network_protocol::is_text_type", _ns_is_text_type, _acc_is_text_type)
    var _acc_build_query_string: Float64 = 0.0
    var _t0_build_query_string = perf_counter_ns()
    for _ in range(N):
        _ = build_query_string(["a","b","c","d","e"], ["a","b","c","d","e"])
    var _t1_build_query_string = perf_counter_ns()
    var _ns_build_query_string = Float64(_t1_build_query_string - _t0_build_query_string) / Float64(N)
    print("MOJO_TIMING network_protocol::build_query_string", _ns_build_query_string, _acc_build_query_string)
    var _acc_parse_query_string: Float64 = 0.0
    var _t0_parse_query_string = perf_counter_ns()
    for _ in range(N):
        var _r_parse_query_string = parse_query_string("test")
        _acc_parse_query_string += Float64(len(_r_parse_query_string))
    var _t1_parse_query_string = perf_counter_ns()
    var _ns_parse_query_string = Float64(_t1_parse_query_string - _t0_parse_query_string) / Float64(N)
    print("MOJO_TIMING network_protocol::parse_query_string", _ns_parse_query_string, _acc_parse_query_string)
