"""bench_net_url.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from net.url import url_parse, url_encode, url_decode, query_parse, query_get, URL
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

    var _keeper_url_parse = List[URL]()
    _keeper_url_parse.append(url_parse("test"))
    var _acc_url_parse: Float64 = 0.0
    var _t0_url_parse = perf_counter_ns()
    for _ in range(N):
        _keeper_url_parse[0] = url_parse("test")
        _acc_url_parse += Float64(len(_keeper_url_parse))
    var _t1_url_parse = perf_counter_ns()
    var _ns_url_parse = Float64(_t1_url_parse - _t0_url_parse) / Float64(N)
    print("MOJO_TIMING net_url::url_parse", _ns_url_parse, _acc_url_parse)
    var _acc_url_encode: Float64 = 0.0
    var _t0_url_encode = perf_counter_ns()
    for _ in range(N):
        _ = url_encode("test")
    var _t1_url_encode = perf_counter_ns()
    var _ns_url_encode = Float64(_t1_url_encode - _t0_url_encode) / Float64(N)
    print("MOJO_TIMING net_url::url_encode", _ns_url_encode, _acc_url_encode)
    var _acc_url_decode: Float64 = 0.0
    var _t0_url_decode = perf_counter_ns()
    for _ in range(N):
        _ = url_decode("test")
    var _t1_url_decode = perf_counter_ns()
    var _ns_url_decode = Float64(_t1_url_decode - _t0_url_decode) / Float64(N)
    print("MOJO_TIMING net_url::url_decode", _ns_url_decode, _acc_url_decode)
    var _acc_query_parse: Float64 = 0.0
    var _t0_query_parse = perf_counter_ns()
    for _ in range(N):
        var _r_query_parse = query_parse("test")
        _acc_query_parse += Float64(len(_r_query_parse))
    var _t1_query_parse = perf_counter_ns()
    var _ns_query_parse = Float64(_t1_query_parse - _t0_query_parse) / Float64(N)
    print("MOJO_TIMING net_url::query_parse", _ns_query_parse, _acc_query_parse)
    var _acc_query_get: Float64 = 0.0
    var _t0_query_get = perf_counter_ns()
    for _ in range(N):
        _ = query_get("test", "test")
    var _t1_query_get = perf_counter_ns()
    var _ns_query_get = Float64(_t1_query_get - _t0_query_get) / Float64(N)
    print("MOJO_TIMING net_url::query_get", _ns_query_get, _acc_query_get)
