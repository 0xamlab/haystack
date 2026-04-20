"""bench_net_unix_socket.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from net.unix_socket import encode_u32_be, decode_u32_be, encode_frame, decode_frame_length, libc_socket_unix, libc_bind_unix, libc_listen, libc_accept, libc_close, libc_unlink, libc_path_exists, recv_exact, recv_frame, send_frame
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
    var _acc_libc_socket_unix: Float64 = 0.0
    var _t0_libc_socket_unix = perf_counter_ns()
    for _ in range(N):
        _acc_libc_socket_unix += Float64(libc_socket_unix())
    var _t1_libc_socket_unix = perf_counter_ns()
    var _ns_libc_socket_unix = Float64(_t1_libc_socket_unix - _t0_libc_socket_unix) / Float64(N)
    print("MOJO_TIMING net_unix_socket::libc_socket_unix", _ns_libc_socket_unix, _acc_libc_socket_unix)
    var _acc_libc_bind_unix: Float64 = 0.0
    var _t0_libc_bind_unix = perf_counter_ns()
    for _ in range(N):
        _ = libc_bind_unix(5, "test")
    var _t1_libc_bind_unix = perf_counter_ns()
    var _ns_libc_bind_unix = Float64(_t1_libc_bind_unix - _t0_libc_bind_unix) / Float64(N)
    print("MOJO_TIMING net_unix_socket::libc_bind_unix", _ns_libc_bind_unix, _acc_libc_bind_unix)
    var _acc_libc_listen: Float64 = 0.0
    var _t0_libc_listen = perf_counter_ns()
    for _ in range(N):
        _ = libc_listen(5, 5)
    var _t1_libc_listen = perf_counter_ns()
    var _ns_libc_listen = Float64(_t1_libc_listen - _t0_libc_listen) / Float64(N)
    print("MOJO_TIMING net_unix_socket::libc_listen", _ns_libc_listen, _acc_libc_listen)
    var _acc_libc_accept: Float64 = 0.0
    var _t0_libc_accept = perf_counter_ns()
    for _ in range(N):
        _acc_libc_accept += Float64(libc_accept(5))
    var _t1_libc_accept = perf_counter_ns()
    var _ns_libc_accept = Float64(_t1_libc_accept - _t0_libc_accept) / Float64(N)
    print("MOJO_TIMING net_unix_socket::libc_accept", _ns_libc_accept, _acc_libc_accept)
    var _acc_libc_close: Float64 = 0.0
    var _t0_libc_close = perf_counter_ns()
    for _ in range(N):
        _ = libc_close(5)
    var _t1_libc_close = perf_counter_ns()
    var _ns_libc_close = Float64(_t1_libc_close - _t0_libc_close) / Float64(N)
    print("MOJO_TIMING net_unix_socket::libc_close", _ns_libc_close, _acc_libc_close)
    var _acc_libc_unlink: Float64 = 0.0
    var _t0_libc_unlink = perf_counter_ns()
    for _ in range(N):
        _ = libc_unlink("test")
    var _t1_libc_unlink = perf_counter_ns()
    var _ns_libc_unlink = Float64(_t1_libc_unlink - _t0_libc_unlink) / Float64(N)
    print("MOJO_TIMING net_unix_socket::libc_unlink", _ns_libc_unlink, _acc_libc_unlink)
    var _acc_libc_path_exists: Float64 = 0.0
    var _t0_libc_path_exists = perf_counter_ns()
    for _ in range(N):
        _acc_libc_path_exists += Float64(libc_path_exists("test"))
    var _t1_libc_path_exists = perf_counter_ns()
    var _ns_libc_path_exists = Float64(_t1_libc_path_exists - _t0_libc_path_exists) / Float64(N)
    print("MOJO_TIMING net_unix_socket::libc_path_exists", _ns_libc_path_exists, _acc_libc_path_exists)
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
    var _acc_send_frame: Float64 = 0.0
    var _t0_send_frame = perf_counter_ns()
    for _ in range(N):
        _ = send_frame(5, "test")
    var _t1_send_frame = perf_counter_ns()
    var _ns_send_frame = Float64(_t1_send_frame - _t0_send_frame) / Float64(N)
    print("MOJO_TIMING net_unix_socket::send_frame", _ns_send_frame, _acc_send_frame)
