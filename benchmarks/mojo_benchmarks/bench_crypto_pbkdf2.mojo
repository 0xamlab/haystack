"""bench_crypto_pbkdf2.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from crypto.pbkdf2 import sha256_bytes, bytes_from_string, bytes_to_hex, xor_byte_lists, int_to_bytes_be, hmac_sha256_bytes, pbkdf2_hmac_sha256
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

    var _acc_sha256_bytes: Float64 = 0.0
    var _t0_sha256_bytes = perf_counter_ns()
    for _ in range(N):
        var _r_sha256_bytes = sha256_bytes(_li5)
        _acc_sha256_bytes += Float64(len(_r_sha256_bytes))
    var _t1_sha256_bytes = perf_counter_ns()
    var _ns_sha256_bytes = Float64(_t1_sha256_bytes - _t0_sha256_bytes) / Float64(N)
    print("MOJO_TIMING crypto_pbkdf2::sha256_bytes", _ns_sha256_bytes, _acc_sha256_bytes)
    var _acc_bytes_from_string: Float64 = 0.0
    var _t0_bytes_from_string = perf_counter_ns()
    for _ in range(N):
        var _r_bytes_from_string = bytes_from_string("test")
        _acc_bytes_from_string += Float64(len(_r_bytes_from_string))
    var _t1_bytes_from_string = perf_counter_ns()
    var _ns_bytes_from_string = Float64(_t1_bytes_from_string - _t0_bytes_from_string) / Float64(N)
    print("MOJO_TIMING crypto_pbkdf2::bytes_from_string", _ns_bytes_from_string, _acc_bytes_from_string)
    var _acc_bytes_to_hex: Float64 = 0.0
    var _t0_bytes_to_hex = perf_counter_ns()
    for _ in range(N):
        _ = bytes_to_hex(_li5)
    var _t1_bytes_to_hex = perf_counter_ns()
    var _ns_bytes_to_hex = Float64(_t1_bytes_to_hex - _t0_bytes_to_hex) / Float64(N)
    print("MOJO_TIMING crypto_pbkdf2::bytes_to_hex", _ns_bytes_to_hex, _acc_bytes_to_hex)
    var _acc_xor_byte_lists: Float64 = 0.0
    var _t0_xor_byte_lists = perf_counter_ns()
    for _ in range(N):
        var _r_xor_byte_lists = xor_byte_lists(_li5, _li5)
        _acc_xor_byte_lists += Float64(len(_r_xor_byte_lists))
    var _t1_xor_byte_lists = perf_counter_ns()
    var _ns_xor_byte_lists = Float64(_t1_xor_byte_lists - _t0_xor_byte_lists) / Float64(N)
    print("MOJO_TIMING crypto_pbkdf2::xor_byte_lists", _ns_xor_byte_lists, _acc_xor_byte_lists)
    var _acc_int_to_bytes_be: Float64 = 0.0
    var _t0_int_to_bytes_be = perf_counter_ns()
    for _ in range(N):
        var _r_int_to_bytes_be = int_to_bytes_be(5, 5)
        _acc_int_to_bytes_be += Float64(len(_r_int_to_bytes_be))
    var _t1_int_to_bytes_be = perf_counter_ns()
    var _ns_int_to_bytes_be = Float64(_t1_int_to_bytes_be - _t0_int_to_bytes_be) / Float64(N)
    print("MOJO_TIMING crypto_pbkdf2::int_to_bytes_be", _ns_int_to_bytes_be, _acc_int_to_bytes_be)
    var _acc_hmac_sha256_bytes: Float64 = 0.0
    var _t0_hmac_sha256_bytes = perf_counter_ns()
    for _ in range(N):
        var _r_hmac_sha256_bytes = hmac_sha256_bytes(_li5, _li5)
        _acc_hmac_sha256_bytes += Float64(len(_r_hmac_sha256_bytes))
    var _t1_hmac_sha256_bytes = perf_counter_ns()
    var _ns_hmac_sha256_bytes = Float64(_t1_hmac_sha256_bytes - _t0_hmac_sha256_bytes) / Float64(N)
    print("MOJO_TIMING crypto_pbkdf2::hmac_sha256_bytes", _ns_hmac_sha256_bytes, _acc_hmac_sha256_bytes)
    var _acc_pbkdf2_hmac_sha256: Float64 = 0.0
    var _t0_pbkdf2_hmac_sha256 = perf_counter_ns()
    for _ in range(N):
        var _r_pbkdf2_hmac_sha256 = pbkdf2_hmac_sha256(_li5, _li5, 5, 5)
        _acc_pbkdf2_hmac_sha256 += Float64(len(_r_pbkdf2_hmac_sha256))
    var _t1_pbkdf2_hmac_sha256 = perf_counter_ns()
    var _ns_pbkdf2_hmac_sha256 = Float64(_t1_pbkdf2_hmac_sha256 - _t0_pbkdf2_hmac_sha256) / Float64(N)
    print("MOJO_TIMING crypto_pbkdf2::pbkdf2_hmac_sha256", _ns_pbkdf2_hmac_sha256, _acc_pbkdf2_hmac_sha256)
