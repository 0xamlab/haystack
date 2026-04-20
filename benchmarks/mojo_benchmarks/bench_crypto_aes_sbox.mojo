"""bench_crypto_aes_sbox.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from crypto.aes_sbox import aes_sbox, aes_inv_sbox, sub_bytes, inv_sub_bytes, shift_rows, inv_shift_rows, xor_bytes, add_round_key
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

    var _acc_aes_sbox: Float64 = 0.0
    var _t0_aes_sbox = perf_counter_ns()
    for _ in range(N):
        _acc_aes_sbox += Float64(aes_sbox(5))
    var _t1_aes_sbox = perf_counter_ns()
    var _ns_aes_sbox = Float64(_t1_aes_sbox - _t0_aes_sbox) / Float64(N)
    print("MOJO_TIMING crypto_aes_sbox::aes_sbox", _ns_aes_sbox, _acc_aes_sbox)
    var _acc_aes_inv_sbox: Float64 = 0.0
    var _t0_aes_inv_sbox = perf_counter_ns()
    for _ in range(N):
        _acc_aes_inv_sbox += Float64(aes_inv_sbox(5))
    var _t1_aes_inv_sbox = perf_counter_ns()
    var _ns_aes_inv_sbox = Float64(_t1_aes_inv_sbox - _t0_aes_inv_sbox) / Float64(N)
    print("MOJO_TIMING crypto_aes_sbox::aes_inv_sbox", _ns_aes_inv_sbox, _acc_aes_inv_sbox)
    var _acc_sub_bytes: Float64 = 0.0
    var _t0_sub_bytes = perf_counter_ns()
    for _ in range(N):
        var _r_sub_bytes = sub_bytes(_li5)
        _acc_sub_bytes += Float64(len(_r_sub_bytes))
    var _t1_sub_bytes = perf_counter_ns()
    var _ns_sub_bytes = Float64(_t1_sub_bytes - _t0_sub_bytes) / Float64(N)
    print("MOJO_TIMING crypto_aes_sbox::sub_bytes", _ns_sub_bytes, _acc_sub_bytes)
    var _acc_inv_sub_bytes: Float64 = 0.0
    var _t0_inv_sub_bytes = perf_counter_ns()
    for _ in range(N):
        var _r_inv_sub_bytes = inv_sub_bytes(_li5)
        _acc_inv_sub_bytes += Float64(len(_r_inv_sub_bytes))
    var _t1_inv_sub_bytes = perf_counter_ns()
    var _ns_inv_sub_bytes = Float64(_t1_inv_sub_bytes - _t0_inv_sub_bytes) / Float64(N)
    print("MOJO_TIMING crypto_aes_sbox::inv_sub_bytes", _ns_inv_sub_bytes, _acc_inv_sub_bytes)
    var _acc_shift_rows: Float64 = 0.0
    var _t0_shift_rows = perf_counter_ns()
    for _ in range(N):
        var _r_shift_rows = shift_rows(_li5)
        _acc_shift_rows += Float64(len(_r_shift_rows))
    var _t1_shift_rows = perf_counter_ns()
    var _ns_shift_rows = Float64(_t1_shift_rows - _t0_shift_rows) / Float64(N)
    print("MOJO_TIMING crypto_aes_sbox::shift_rows", _ns_shift_rows, _acc_shift_rows)
    var _acc_inv_shift_rows: Float64 = 0.0
    var _t0_inv_shift_rows = perf_counter_ns()
    for _ in range(N):
        var _r_inv_shift_rows = inv_shift_rows(_li5)
        _acc_inv_shift_rows += Float64(len(_r_inv_shift_rows))
    var _t1_inv_shift_rows = perf_counter_ns()
    var _ns_inv_shift_rows = Float64(_t1_inv_shift_rows - _t0_inv_shift_rows) / Float64(N)
    print("MOJO_TIMING crypto_aes_sbox::inv_shift_rows", _ns_inv_shift_rows, _acc_inv_shift_rows)
    var _acc_xor_bytes: Float64 = 0.0
    var _t0_xor_bytes = perf_counter_ns()
    for _ in range(N):
        var _r_xor_bytes = xor_bytes(_li5, _li5)
        _acc_xor_bytes += Float64(len(_r_xor_bytes))
    var _t1_xor_bytes = perf_counter_ns()
    var _ns_xor_bytes = Float64(_t1_xor_bytes - _t0_xor_bytes) / Float64(N)
    print("MOJO_TIMING crypto_aes_sbox::xor_bytes", _ns_xor_bytes, _acc_xor_bytes)
    var _acc_add_round_key: Float64 = 0.0
    var _t0_add_round_key = perf_counter_ns()
    for _ in range(N):
        var _r_add_round_key = add_round_key(_li5, _li5)
        _acc_add_round_key += Float64(len(_r_add_round_key))
    var _t1_add_round_key = perf_counter_ns()
    var _ns_add_round_key = Float64(_t1_add_round_key - _t0_add_round_key) / Float64(N)
    print("MOJO_TIMING crypto_aes_sbox::add_round_key", _ns_add_round_key, _acc_add_round_key)
