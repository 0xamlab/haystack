"""bench_crypto_aes_sbox.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from crypto.aes_sbox import aes_sbox, aes_inv_sbox, sub_bytes, inv_sub_bytes, shift_rows, inv_shift_rows, xor_bytes, add_round_key
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

    var _acc_aes_sbox: Float64 = 0.0
    var _t0_aes_sbox = perf_counter_ns()
    for _ in range(N):
        _acc_aes_sbox += Float64(aes_sbox(5))
    var _t1_aes_sbox = perf_counter_ns()
    var _ns_aes_sbox = Float64(_t1_aes_sbox - _t0_aes_sbox) / Float64(N)
    print("MOJO_TIMING crypto_aes_sbox::aes_sbox", _ns_aes_sbox, _acc_aes_sbox)
    var _result_aes_sbox = aes_sbox(5)
    var _summary_aes_sbox = _summary_int(_result_aes_sbox)
    print("MOJO_RESULT crypto_aes_sbox::aes_sbox", _summary_aes_sbox)
    var _acc_aes_inv_sbox: Float64 = 0.0
    var _t0_aes_inv_sbox = perf_counter_ns()
    for _ in range(N):
        _acc_aes_inv_sbox += Float64(aes_inv_sbox(5))
    var _t1_aes_inv_sbox = perf_counter_ns()
    var _ns_aes_inv_sbox = Float64(_t1_aes_inv_sbox - _t0_aes_inv_sbox) / Float64(N)
    print("MOJO_TIMING crypto_aes_sbox::aes_inv_sbox", _ns_aes_inv_sbox, _acc_aes_inv_sbox)
    var _result_aes_inv_sbox = aes_inv_sbox(5)
    var _summary_aes_inv_sbox = _summary_int(_result_aes_inv_sbox)
    print("MOJO_RESULT crypto_aes_sbox::aes_inv_sbox", _summary_aes_inv_sbox)
    var _acc_sub_bytes: Float64 = 0.0
    var _t0_sub_bytes = perf_counter_ns()
    for _ in range(N):
        var _r_sub_bytes = sub_bytes(_li5)
        _acc_sub_bytes += Float64(len(_r_sub_bytes))
    var _t1_sub_bytes = perf_counter_ns()
    var _ns_sub_bytes = Float64(_t1_sub_bytes - _t0_sub_bytes) / Float64(N)
    print("MOJO_TIMING crypto_aes_sbox::sub_bytes", _ns_sub_bytes, _acc_sub_bytes)
    var _result_sub_bytes = sub_bytes(_li5)
    var _summary_sub_bytes = _summary_list_int(_result_sub_bytes)
    print("MOJO_RESULT crypto_aes_sbox::sub_bytes", _summary_sub_bytes)
    var _acc_inv_sub_bytes: Float64 = 0.0
    var _t0_inv_sub_bytes = perf_counter_ns()
    for _ in range(N):
        var _r_inv_sub_bytes = inv_sub_bytes(_li5)
        _acc_inv_sub_bytes += Float64(len(_r_inv_sub_bytes))
    var _t1_inv_sub_bytes = perf_counter_ns()
    var _ns_inv_sub_bytes = Float64(_t1_inv_sub_bytes - _t0_inv_sub_bytes) / Float64(N)
    print("MOJO_TIMING crypto_aes_sbox::inv_sub_bytes", _ns_inv_sub_bytes, _acc_inv_sub_bytes)
    var _result_inv_sub_bytes = inv_sub_bytes(_li5)
    var _summary_inv_sub_bytes = _summary_list_int(_result_inv_sub_bytes)
    print("MOJO_RESULT crypto_aes_sbox::inv_sub_bytes", _summary_inv_sub_bytes)
    var _acc_shift_rows: Float64 = 0.0
    var _t0_shift_rows = perf_counter_ns()
    for _ in range(N):
        var _r_shift_rows = shift_rows(_li5)
        _acc_shift_rows += Float64(len(_r_shift_rows))
    var _t1_shift_rows = perf_counter_ns()
    var _ns_shift_rows = Float64(_t1_shift_rows - _t0_shift_rows) / Float64(N)
    print("MOJO_TIMING crypto_aes_sbox::shift_rows", _ns_shift_rows, _acc_shift_rows)
    var _result_shift_rows = shift_rows(_li5)
    var _summary_shift_rows = _summary_list_int(_result_shift_rows)
    print("MOJO_RESULT crypto_aes_sbox::shift_rows", _summary_shift_rows)
    var _acc_inv_shift_rows: Float64 = 0.0
    var _t0_inv_shift_rows = perf_counter_ns()
    for _ in range(N):
        var _r_inv_shift_rows = inv_shift_rows(_li5)
        _acc_inv_shift_rows += Float64(len(_r_inv_shift_rows))
    var _t1_inv_shift_rows = perf_counter_ns()
    var _ns_inv_shift_rows = Float64(_t1_inv_shift_rows - _t0_inv_shift_rows) / Float64(N)
    print("MOJO_TIMING crypto_aes_sbox::inv_shift_rows", _ns_inv_shift_rows, _acc_inv_shift_rows)
    var _result_inv_shift_rows = inv_shift_rows(_li5)
    var _summary_inv_shift_rows = _summary_list_int(_result_inv_shift_rows)
    print("MOJO_RESULT crypto_aes_sbox::inv_shift_rows", _summary_inv_shift_rows)
    var _acc_xor_bytes: Float64 = 0.0
    var _t0_xor_bytes = perf_counter_ns()
    for _ in range(N):
        var _r_xor_bytes = xor_bytes(_li5, _li5)
        _acc_xor_bytes += Float64(len(_r_xor_bytes))
    var _t1_xor_bytes = perf_counter_ns()
    var _ns_xor_bytes = Float64(_t1_xor_bytes - _t0_xor_bytes) / Float64(N)
    print("MOJO_TIMING crypto_aes_sbox::xor_bytes", _ns_xor_bytes, _acc_xor_bytes)
    var _result_xor_bytes = xor_bytes(_li5, _li5)
    var _summary_xor_bytes = _summary_list_int(_result_xor_bytes)
    print("MOJO_RESULT crypto_aes_sbox::xor_bytes", _summary_xor_bytes)
    var _acc_add_round_key: Float64 = 0.0
    var _t0_add_round_key = perf_counter_ns()
    for _ in range(N):
        var _r_add_round_key = add_round_key(_li5, _li5)
        _acc_add_round_key += Float64(len(_r_add_round_key))
    var _t1_add_round_key = perf_counter_ns()
    var _ns_add_round_key = Float64(_t1_add_round_key - _t0_add_round_key) / Float64(N)
    print("MOJO_TIMING crypto_aes_sbox::add_round_key", _ns_add_round_key, _acc_add_round_key)
    var _result_add_round_key = add_round_key(_li5, _li5)
    var _summary_add_round_key = _summary_list_int(_result_add_round_key)
    print("MOJO_RESULT crypto_aes_sbox::add_round_key", _summary_add_round_key)
