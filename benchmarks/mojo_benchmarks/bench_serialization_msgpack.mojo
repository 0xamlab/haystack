"""bench_serialization_msgpack.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from serialization.msgpack import msgpack_encode_int, msgpack_encode_float, msgpack_encode_string, msgpack_encode_bool, msgpack_encode_nil, msgpack_encode_array_header, msgpack_encode_map_header, msgpack_decode_int, msgpack_decode_float, msgpack_decode_string, MsgPackFloatResult, MsgPackIntResult, MsgPackStringResult
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

    var _acc_msgpack_encode_int: Float64 = 0.0
    var _t0_msgpack_encode_int = perf_counter_ns()
    for _ in range(N):
        var _r_msgpack_encode_int = msgpack_encode_int(5)
        _acc_msgpack_encode_int += Float64(len(_r_msgpack_encode_int))
    var _t1_msgpack_encode_int = perf_counter_ns()
    var _ns_msgpack_encode_int = Float64(_t1_msgpack_encode_int - _t0_msgpack_encode_int) / Float64(N)
    print("MOJO_TIMING serialization_msgpack::msgpack_encode_int", _ns_msgpack_encode_int, _acc_msgpack_encode_int)
    var _acc_msgpack_encode_float: Float64 = 0.0
    var _t0_msgpack_encode_float = perf_counter_ns()
    for _ in range(N):
        var _r_msgpack_encode_float = msgpack_encode_float(0.5)
        _acc_msgpack_encode_float += Float64(len(_r_msgpack_encode_float))
    var _t1_msgpack_encode_float = perf_counter_ns()
    var _ns_msgpack_encode_float = Float64(_t1_msgpack_encode_float - _t0_msgpack_encode_float) / Float64(N)
    print("MOJO_TIMING serialization_msgpack::msgpack_encode_float", _ns_msgpack_encode_float, _acc_msgpack_encode_float)
    var _acc_msgpack_encode_string: Float64 = 0.0
    var _t0_msgpack_encode_string = perf_counter_ns()
    for _ in range(N):
        var _r_msgpack_encode_string = msgpack_encode_string("test")
        _acc_msgpack_encode_string += Float64(len(_r_msgpack_encode_string))
    var _t1_msgpack_encode_string = perf_counter_ns()
    var _ns_msgpack_encode_string = Float64(_t1_msgpack_encode_string - _t0_msgpack_encode_string) / Float64(N)
    print("MOJO_TIMING serialization_msgpack::msgpack_encode_string", _ns_msgpack_encode_string, _acc_msgpack_encode_string)
    var _acc_msgpack_encode_bool: Float64 = 0.0
    var _t0_msgpack_encode_bool = perf_counter_ns()
    for _ in range(N):
        var _r_msgpack_encode_bool = msgpack_encode_bool(True)
        _acc_msgpack_encode_bool += Float64(len(_r_msgpack_encode_bool))
    var _t1_msgpack_encode_bool = perf_counter_ns()
    var _ns_msgpack_encode_bool = Float64(_t1_msgpack_encode_bool - _t0_msgpack_encode_bool) / Float64(N)
    print("MOJO_TIMING serialization_msgpack::msgpack_encode_bool", _ns_msgpack_encode_bool, _acc_msgpack_encode_bool)
    var _acc_msgpack_encode_nil: Float64 = 0.0
    var _t0_msgpack_encode_nil = perf_counter_ns()
    for _ in range(N):
        var _r_msgpack_encode_nil = msgpack_encode_nil()
        _acc_msgpack_encode_nil += Float64(len(_r_msgpack_encode_nil))
    var _t1_msgpack_encode_nil = perf_counter_ns()
    var _ns_msgpack_encode_nil = Float64(_t1_msgpack_encode_nil - _t0_msgpack_encode_nil) / Float64(N)
    print("MOJO_TIMING serialization_msgpack::msgpack_encode_nil", _ns_msgpack_encode_nil, _acc_msgpack_encode_nil)
    var _acc_msgpack_encode_array_header: Float64 = 0.0
    var _t0_msgpack_encode_array_header = perf_counter_ns()
    for _ in range(N):
        var _r_msgpack_encode_array_header = msgpack_encode_array_header(5)
        _acc_msgpack_encode_array_header += Float64(len(_r_msgpack_encode_array_header))
    var _t1_msgpack_encode_array_header = perf_counter_ns()
    var _ns_msgpack_encode_array_header = Float64(_t1_msgpack_encode_array_header - _t0_msgpack_encode_array_header) / Float64(N)
    print("MOJO_TIMING serialization_msgpack::msgpack_encode_array_header", _ns_msgpack_encode_array_header, _acc_msgpack_encode_array_header)
    var _acc_msgpack_encode_map_header: Float64 = 0.0
    var _t0_msgpack_encode_map_header = perf_counter_ns()
    for _ in range(N):
        var _r_msgpack_encode_map_header = msgpack_encode_map_header(5)
        _acc_msgpack_encode_map_header += Float64(len(_r_msgpack_encode_map_header))
    var _t1_msgpack_encode_map_header = perf_counter_ns()
    var _ns_msgpack_encode_map_header = Float64(_t1_msgpack_encode_map_header - _t0_msgpack_encode_map_header) / Float64(N)
    print("MOJO_TIMING serialization_msgpack::msgpack_encode_map_header", _ns_msgpack_encode_map_header, _acc_msgpack_encode_map_header)
    var _keeper_msgpack_decode_int = List[MsgPackIntResult]()
    _keeper_msgpack_decode_int.append(msgpack_decode_int(_lub5, 5))
    var _acc_msgpack_decode_int: Float64 = 0.0
    var _t0_msgpack_decode_int = perf_counter_ns()
    for _ in range(N):
        _keeper_msgpack_decode_int[0] = msgpack_decode_int(_lub5, 5)
        _acc_msgpack_decode_int += Float64(len(_keeper_msgpack_decode_int))
    var _t1_msgpack_decode_int = perf_counter_ns()
    var _ns_msgpack_decode_int = Float64(_t1_msgpack_decode_int - _t0_msgpack_decode_int) / Float64(N)
    print("MOJO_TIMING serialization_msgpack::msgpack_decode_int", _ns_msgpack_decode_int, _acc_msgpack_decode_int)
    var _keeper_msgpack_decode_float = List[MsgPackFloatResult]()
    _keeper_msgpack_decode_float.append(msgpack_decode_float(_lub5, 5))
    var _acc_msgpack_decode_float: Float64 = 0.0
    var _t0_msgpack_decode_float = perf_counter_ns()
    for _ in range(N):
        _keeper_msgpack_decode_float[0] = msgpack_decode_float(_lub5, 5)
        _acc_msgpack_decode_float += Float64(len(_keeper_msgpack_decode_float))
    var _t1_msgpack_decode_float = perf_counter_ns()
    var _ns_msgpack_decode_float = Float64(_t1_msgpack_decode_float - _t0_msgpack_decode_float) / Float64(N)
    print("MOJO_TIMING serialization_msgpack::msgpack_decode_float", _ns_msgpack_decode_float, _acc_msgpack_decode_float)
    var _keeper_msgpack_decode_string = List[MsgPackStringResult]()
    _keeper_msgpack_decode_string.append(msgpack_decode_string(_lub5, 5))
    var _acc_msgpack_decode_string: Float64 = 0.0
    var _t0_msgpack_decode_string = perf_counter_ns()
    for _ in range(N):
        _keeper_msgpack_decode_string[0] = msgpack_decode_string(_lub5, 5)
        _acc_msgpack_decode_string += Float64(len(_keeper_msgpack_decode_string))
    var _t1_msgpack_decode_string = perf_counter_ns()
    var _ns_msgpack_decode_string = Float64(_t1_msgpack_decode_string - _t0_msgpack_decode_string) / Float64(N)
    print("MOJO_TIMING serialization_msgpack::msgpack_decode_string", _ns_msgpack_decode_string, _acc_msgpack_decode_string)
