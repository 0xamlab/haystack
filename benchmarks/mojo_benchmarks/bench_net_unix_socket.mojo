"""bench_net_unix_socket.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from net.unix_socket import encode_u32_be, decode_u32_be, encode_frame, decode_frame_length, libc_socket_unix, libc_bind_unix, libc_listen, libc_accept, libc_close, libc_unlink, libc_path_exists, recv_exact, recv_frame, send_frame
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

    var _acc_encode_u32_be: Float64 = 0.0
    var _t0_encode_u32_be = perf_counter_ns()
    for _ in range(N):
        var _r_encode_u32_be = encode_u32_be(5)
        _acc_encode_u32_be += Float64(len(_r_encode_u32_be))
    var _t1_encode_u32_be = perf_counter_ns()
    var _ns_encode_u32_be = Float64(_t1_encode_u32_be - _t0_encode_u32_be) / Float64(N)
    print("MOJO_TIMING net_unix_socket::encode_u32_be", _ns_encode_u32_be, _acc_encode_u32_be)
    var _acc_decode_u32_be: Float64 = 0.0
    var _t0_decode_u32_be = perf_counter_ns()
    for _ in range(N):
        _acc_decode_u32_be += Float64(decode_u32_be(_lub5))
    var _t1_decode_u32_be = perf_counter_ns()
    var _ns_decode_u32_be = Float64(_t1_decode_u32_be - _t0_decode_u32_be) / Float64(N)
    print("MOJO_TIMING net_unix_socket::decode_u32_be", _ns_decode_u32_be, _acc_decode_u32_be)
    var _result_decode_u32_be = decode_u32_be(_lub5)
    var _summary_decode_u32_be = _summary_int(_result_decode_u32_be)
    print("MOJO_RESULT net_unix_socket::decode_u32_be", _summary_decode_u32_be)
    var _acc_encode_frame: Float64 = 0.0
    var _t0_encode_frame = perf_counter_ns()
    for _ in range(N):
        var _r_encode_frame = encode_frame("test")
        _acc_encode_frame += Float64(len(_r_encode_frame))
    var _t1_encode_frame = perf_counter_ns()
    var _ns_encode_frame = Float64(_t1_encode_frame - _t0_encode_frame) / Float64(N)
    print("MOJO_TIMING net_unix_socket::encode_frame", _ns_encode_frame, _acc_encode_frame)
    var _acc_decode_frame_length: Float64 = 0.0
    var _t0_decode_frame_length = perf_counter_ns()
    for _ in range(N):
        _acc_decode_frame_length += Float64(decode_frame_length(_lub5))
    var _t1_decode_frame_length = perf_counter_ns()
    var _ns_decode_frame_length = Float64(_t1_decode_frame_length - _t0_decode_frame_length) / Float64(N)
    print("MOJO_TIMING net_unix_socket::decode_frame_length", _ns_decode_frame_length, _acc_decode_frame_length)
    var _result_decode_frame_length = decode_frame_length(_lub5)
    var _summary_decode_frame_length = _summary_int(_result_decode_frame_length)
    print("MOJO_RESULT net_unix_socket::decode_frame_length", _summary_decode_frame_length)
    var _acc_libc_socket_unix: Float64 = 0.0
    var _t0_libc_socket_unix = perf_counter_ns()
    for _ in range(N):
        _acc_libc_socket_unix += Float64(libc_socket_unix())
    var _t1_libc_socket_unix = perf_counter_ns()
    var _ns_libc_socket_unix = Float64(_t1_libc_socket_unix - _t0_libc_socket_unix) / Float64(N)
    print("MOJO_TIMING net_unix_socket::libc_socket_unix", _ns_libc_socket_unix, _acc_libc_socket_unix)
    var _result_libc_socket_unix = libc_socket_unix()
    var _summary_libc_socket_unix = _summary_int(_result_libc_socket_unix)
    print("MOJO_RESULT net_unix_socket::libc_socket_unix", _summary_libc_socket_unix)
    var _acc_libc_bind_unix: Float64 = 0.0
    var _t0_libc_bind_unix = perf_counter_ns()
    for _ in range(N):
        _ = libc_bind_unix(5, "test")
    var _t1_libc_bind_unix = perf_counter_ns()
    var _ns_libc_bind_unix = Float64(_t1_libc_bind_unix - _t0_libc_bind_unix) / Float64(N)
    print("MOJO_TIMING net_unix_socket::libc_bind_unix", _ns_libc_bind_unix, _acc_libc_bind_unix)
    var _result_libc_bind_unix = libc_bind_unix(5, "test")
    var _summary_libc_bind_unix = "none"
    print("MOJO_RESULT net_unix_socket::libc_bind_unix", _summary_libc_bind_unix)
    var _acc_libc_listen: Float64 = 0.0
    var _t0_libc_listen = perf_counter_ns()
    for _ in range(N):
        _ = libc_listen(5, 5)
    var _t1_libc_listen = perf_counter_ns()
    var _ns_libc_listen = Float64(_t1_libc_listen - _t0_libc_listen) / Float64(N)
    print("MOJO_TIMING net_unix_socket::libc_listen", _ns_libc_listen, _acc_libc_listen)
    var _result_libc_listen = libc_listen(5, 5)
    var _summary_libc_listen = "none"
    print("MOJO_RESULT net_unix_socket::libc_listen", _summary_libc_listen)
    var _acc_libc_accept: Float64 = 0.0
    var _t0_libc_accept = perf_counter_ns()
    for _ in range(N):
        _acc_libc_accept += Float64(libc_accept(5))
    var _t1_libc_accept = perf_counter_ns()
    var _ns_libc_accept = Float64(_t1_libc_accept - _t0_libc_accept) / Float64(N)
    print("MOJO_TIMING net_unix_socket::libc_accept", _ns_libc_accept, _acc_libc_accept)
    var _result_libc_accept = libc_accept(5)
    var _summary_libc_accept = _summary_int(_result_libc_accept)
    print("MOJO_RESULT net_unix_socket::libc_accept", _summary_libc_accept)
    var _acc_libc_close: Float64 = 0.0
    var _t0_libc_close = perf_counter_ns()
    for _ in range(N):
        _ = libc_close(5)
    var _t1_libc_close = perf_counter_ns()
    var _ns_libc_close = Float64(_t1_libc_close - _t0_libc_close) / Float64(N)
    print("MOJO_TIMING net_unix_socket::libc_close", _ns_libc_close, _acc_libc_close)
    var _result_libc_close = libc_close(5)
    var _summary_libc_close = "none"
    print("MOJO_RESULT net_unix_socket::libc_close", _summary_libc_close)
    var _acc_libc_unlink: Float64 = 0.0
    var _t0_libc_unlink = perf_counter_ns()
    for _ in range(N):
        _ = libc_unlink("test")
    var _t1_libc_unlink = perf_counter_ns()
    var _ns_libc_unlink = Float64(_t1_libc_unlink - _t0_libc_unlink) / Float64(N)
    print("MOJO_TIMING net_unix_socket::libc_unlink", _ns_libc_unlink, _acc_libc_unlink)
    var _result_libc_unlink = libc_unlink("test")
    var _summary_libc_unlink = "none"
    print("MOJO_RESULT net_unix_socket::libc_unlink", _summary_libc_unlink)
    var _acc_libc_path_exists: Float64 = 0.0
    var _t0_libc_path_exists = perf_counter_ns()
    for _ in range(N):
        _acc_libc_path_exists += Float64(libc_path_exists("test"))
    var _t1_libc_path_exists = perf_counter_ns()
    var _ns_libc_path_exists = Float64(_t1_libc_path_exists - _t0_libc_path_exists) / Float64(N)
    print("MOJO_TIMING net_unix_socket::libc_path_exists", _ns_libc_path_exists, _acc_libc_path_exists)
    var _result_libc_path_exists = libc_path_exists("test")
    var _summary_libc_path_exists = _summary_bool(_result_libc_path_exists)
    print("MOJO_RESULT net_unix_socket::libc_path_exists", _summary_libc_path_exists)
    var _acc_recv_exact: Float64 = 0.0
    var _t0_recv_exact = perf_counter_ns()
    for _ in range(N):
        var _r_recv_exact = recv_exact(5, 5)
        _acc_recv_exact += Float64(len(_r_recv_exact))
    var _t1_recv_exact = perf_counter_ns()
    var _ns_recv_exact = Float64(_t1_recv_exact - _t0_recv_exact) / Float64(N)
    print("MOJO_TIMING net_unix_socket::recv_exact", _ns_recv_exact, _acc_recv_exact)
    var _acc_recv_frame: Float64 = 0.0
    var _t0_recv_frame = perf_counter_ns()
    for _ in range(N):
        _ = recv_frame(5)
    var _t1_recv_frame = perf_counter_ns()
    var _ns_recv_frame = Float64(_t1_recv_frame - _t0_recv_frame) / Float64(N)
    print("MOJO_TIMING net_unix_socket::recv_frame", _ns_recv_frame, _acc_recv_frame)
    var _result_recv_frame = recv_frame(5)
    var _summary_recv_frame = _summary_string(_result_recv_frame)
    print("MOJO_RESULT net_unix_socket::recv_frame", _summary_recv_frame)
    var _acc_send_frame: Float64 = 0.0
    var _t0_send_frame = perf_counter_ns()
    for _ in range(N):
        _ = send_frame(5, "test")
    var _t1_send_frame = perf_counter_ns()
    var _ns_send_frame = Float64(_t1_send_frame - _t0_send_frame) / Float64(N)
    print("MOJO_TIMING net_unix_socket::send_frame", _ns_send_frame, _acc_send_frame)
    var _result_send_frame = send_frame(5, "test")
    var _summary_send_frame = "none"
    print("MOJO_RESULT net_unix_socket::send_frame", _summary_send_frame)
