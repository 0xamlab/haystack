"""bench_protocol.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from protocol import encode_varint, decode_varint, zigzag_encode, zigzag_decode, encode_field, decode_field, encode_string_field, decode_string_field, encode_message, decode_message
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

    var _acc_encode_varint: Float64 = 0.0
    var _t0_encode_varint = perf_counter_ns()
    for _ in range(N):
        var _r_encode_varint = encode_varint(5)
        _acc_encode_varint += Float64(len(_r_encode_varint))
    var _t1_encode_varint = perf_counter_ns()
    var _ns_encode_varint = Float64(_t1_encode_varint - _t0_encode_varint) / Float64(N)
    print("MOJO_TIMING protocol::encode_varint", _ns_encode_varint, _acc_encode_varint)
    var _acc_decode_varint: Float64 = 0.0
    var _t0_decode_varint = perf_counter_ns()
    for _ in range(N):
        var _r_decode_varint = decode_varint(_li5, 5)
        _acc_decode_varint += Float64(len(_r_decode_varint))
    var _t1_decode_varint = perf_counter_ns()
    var _ns_decode_varint = Float64(_t1_decode_varint - _t0_decode_varint) / Float64(N)
    print("MOJO_TIMING protocol::decode_varint", _ns_decode_varint, _acc_decode_varint)
    var _acc_zigzag_encode: Float64 = 0.0
    var _t0_zigzag_encode = perf_counter_ns()
    for _ in range(N):
        _acc_zigzag_encode += Float64(zigzag_encode(5))
    var _t1_zigzag_encode = perf_counter_ns()
    var _ns_zigzag_encode = Float64(_t1_zigzag_encode - _t0_zigzag_encode) / Float64(N)
    print("MOJO_TIMING protocol::zigzag_encode", _ns_zigzag_encode, _acc_zigzag_encode)
    var _acc_zigzag_decode: Float64 = 0.0
    var _t0_zigzag_decode = perf_counter_ns()
    for _ in range(N):
        _acc_zigzag_decode += Float64(zigzag_decode(5))
    var _t1_zigzag_decode = perf_counter_ns()
    var _ns_zigzag_decode = Float64(_t1_zigzag_decode - _t0_zigzag_decode) / Float64(N)
    print("MOJO_TIMING protocol::zigzag_decode", _ns_zigzag_decode, _acc_zigzag_decode)
    var _acc_encode_field: Float64 = 0.0
    var _t0_encode_field = perf_counter_ns()
    for _ in range(N):
        var _r_encode_field = encode_field(5, 5, 5)
        _acc_encode_field += Float64(len(_r_encode_field))
    var _t1_encode_field = perf_counter_ns()
    var _ns_encode_field = Float64(_t1_encode_field - _t0_encode_field) / Float64(N)
    print("MOJO_TIMING protocol::encode_field", _ns_encode_field, _acc_encode_field)
    var _acc_decode_field: Float64 = 0.0
    var _t0_decode_field = perf_counter_ns()
    for _ in range(N):
        var _r_decode_field = decode_field(_li5, 5)
        _acc_decode_field += Float64(len(_r_decode_field))
    var _t1_decode_field = perf_counter_ns()
    var _ns_decode_field = Float64(_t1_decode_field - _t0_decode_field) / Float64(N)
    print("MOJO_TIMING protocol::decode_field", _ns_decode_field, _acc_decode_field)
    var _acc_encode_string_field: Float64 = 0.0
    var _t0_encode_string_field = perf_counter_ns()
    for _ in range(N):
        var _r_encode_string_field = encode_string_field(5, "test")
        _acc_encode_string_field += Float64(len(_r_encode_string_field))
    var _t1_encode_string_field = perf_counter_ns()
    var _ns_encode_string_field = Float64(_t1_encode_string_field - _t0_encode_string_field) / Float64(N)
    print("MOJO_TIMING protocol::encode_string_field", _ns_encode_string_field, _acc_encode_string_field)
    var _acc_decode_string_field: Float64 = 0.0
    var _t0_decode_string_field = perf_counter_ns()
    for _ in range(N):
        var _r_decode_string_field = decode_string_field(_li5, 5)
        _acc_decode_string_field += Float64(len(_r_decode_string_field))
    var _t1_decode_string_field = perf_counter_ns()
    var _ns_decode_string_field = Float64(_t1_decode_string_field - _t0_decode_string_field) / Float64(N)
    print("MOJO_TIMING protocol::decode_string_field", _ns_decode_string_field, _acc_decode_string_field)
    var _acc_encode_message: Float64 = 0.0
    var _t0_encode_message = perf_counter_ns()
    for _ in range(N):
        var _r_encode_message = encode_message([[0,1,1],[1,0,1],[1,1,0]])
        _acc_encode_message += Float64(len(_r_encode_message))
    var _t1_encode_message = perf_counter_ns()
    var _ns_encode_message = Float64(_t1_encode_message - _t0_encode_message) / Float64(N)
    print("MOJO_TIMING protocol::encode_message", _ns_encode_message, _acc_encode_message)
    var _acc_decode_message: Float64 = 0.0
    var _t0_decode_message = perf_counter_ns()
    for _ in range(N):
        var _r_decode_message = decode_message(_li5)
        _acc_decode_message += Float64(len(_r_decode_message))
    var _t1_decode_message = perf_counter_ns()
    var _ns_decode_message = Float64(_t1_decode_message - _t0_decode_message) / Float64(N)
    print("MOJO_TIMING protocol::decode_message", _ns_decode_message, _acc_decode_message)
