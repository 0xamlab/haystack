"""bench_crypto_chacha20.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from crypto.chacha20 import rotl32, quarter_round, chacha20_init_state, add_states, xor_states, chacha20_block, chacha20_encrypt, chacha20_decrypt
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_rotl32: Float64 = 0.0
    var _t0_rotl32 = perf_counter_ns()
    for _ in range(N):
        _acc_rotl32 += Float64(rotl32(5, 5))
    var _t1_rotl32 = perf_counter_ns()
    var _ns_rotl32 = Float64(_t1_rotl32 - _t0_rotl32) / Float64(N)
    print("MOJO_TIMING crypto_chacha20::rotl32", _ns_rotl32, _acc_rotl32)
    var _result_rotl32 = rotl32(5, 5)
    var _summary_rotl32 = _summary_int(_result_rotl32)
    print("MOJO_RESULT crypto_chacha20::rotl32", _summary_rotl32)
    var _acc_quarter_round: Float64 = 0.0
    var _t0_quarter_round = perf_counter_ns()
    for _ in range(N):
        _ = quarter_round(_li5, 5, 5, 5, 5)
    var _t1_quarter_round = perf_counter_ns()
    var _ns_quarter_round = Float64(_t1_quarter_round - _t0_quarter_round) / Float64(N)
    print("MOJO_TIMING crypto_chacha20::quarter_round", _ns_quarter_round, _acc_quarter_round)
    var _result_quarter_round = quarter_round(_li5, 5, 5, 5, 5)
    var _summary_quarter_round = "none"
    print("MOJO_RESULT crypto_chacha20::quarter_round", _summary_quarter_round)
    var _acc_chacha20_init_state: Float64 = 0.0
    var _t0_chacha20_init_state = perf_counter_ns()
    for _ in range(N):
        var _r_chacha20_init_state = chacha20_init_state(_li5, 5, _li5)
        _acc_chacha20_init_state += Float64(len(_r_chacha20_init_state))
    var _t1_chacha20_init_state = perf_counter_ns()
    var _ns_chacha20_init_state = Float64(_t1_chacha20_init_state - _t0_chacha20_init_state) / Float64(N)
    print("MOJO_TIMING crypto_chacha20::chacha20_init_state", _ns_chacha20_init_state, _acc_chacha20_init_state)
    var _result_chacha20_init_state = chacha20_init_state(_li5, 5, _li5)
    var _summary_chacha20_init_state = _summary_list_int(_result_chacha20_init_state)
    print("MOJO_RESULT crypto_chacha20::chacha20_init_state", _summary_chacha20_init_state)
    var _acc_add_states: Float64 = 0.0
    var _t0_add_states = perf_counter_ns()
    for _ in range(N):
        var _r_add_states = add_states(_li5, _li5)
        _acc_add_states += Float64(len(_r_add_states))
    var _t1_add_states = perf_counter_ns()
    var _ns_add_states = Float64(_t1_add_states - _t0_add_states) / Float64(N)
    print("MOJO_TIMING crypto_chacha20::add_states", _ns_add_states, _acc_add_states)
    var _result_add_states = add_states(_li5, _li5)
    var _summary_add_states = _summary_list_int(_result_add_states)
    print("MOJO_RESULT crypto_chacha20::add_states", _summary_add_states)
    var _acc_xor_states: Float64 = 0.0
    var _t0_xor_states = perf_counter_ns()
    for _ in range(N):
        var _r_xor_states = xor_states(_li5, _li5)
        _acc_xor_states += Float64(len(_r_xor_states))
    var _t1_xor_states = perf_counter_ns()
    var _ns_xor_states = Float64(_t1_xor_states - _t0_xor_states) / Float64(N)
    print("MOJO_TIMING crypto_chacha20::xor_states", _ns_xor_states, _acc_xor_states)
    var _result_xor_states = xor_states(_li5, _li5)
    var _summary_xor_states = _summary_list_int(_result_xor_states)
    print("MOJO_RESULT crypto_chacha20::xor_states", _summary_xor_states)
    var _acc_chacha20_block: Float64 = 0.0
    var _t0_chacha20_block = perf_counter_ns()
    for _ in range(N):
        var _r_chacha20_block = chacha20_block(_li5, 5, _li5)
        _acc_chacha20_block += Float64(len(_r_chacha20_block))
    var _t1_chacha20_block = perf_counter_ns()
    var _ns_chacha20_block = Float64(_t1_chacha20_block - _t0_chacha20_block) / Float64(N)
    print("MOJO_TIMING crypto_chacha20::chacha20_block", _ns_chacha20_block, _acc_chacha20_block)
    var _result_chacha20_block = chacha20_block(_li5, 5, _li5)
    var _summary_chacha20_block = _summary_list_int(_result_chacha20_block)
    print("MOJO_RESULT crypto_chacha20::chacha20_block", _summary_chacha20_block)
    var _acc_chacha20_encrypt: Float64 = 0.0
    var _t0_chacha20_encrypt = perf_counter_ns()
    for _ in range(N):
        var _r_chacha20_encrypt = chacha20_encrypt(_li5, _li5, _li5)
        _acc_chacha20_encrypt += Float64(len(_r_chacha20_encrypt))
    var _t1_chacha20_encrypt = perf_counter_ns()
    var _ns_chacha20_encrypt = Float64(_t1_chacha20_encrypt - _t0_chacha20_encrypt) / Float64(N)
    print("MOJO_TIMING crypto_chacha20::chacha20_encrypt", _ns_chacha20_encrypt, _acc_chacha20_encrypt)
    var _result_chacha20_encrypt = chacha20_encrypt(_li5, _li5, _li5)
    var _summary_chacha20_encrypt = _summary_list_int(_result_chacha20_encrypt)
    print("MOJO_RESULT crypto_chacha20::chacha20_encrypt", _summary_chacha20_encrypt)
    var _acc_chacha20_decrypt: Float64 = 0.0
    var _t0_chacha20_decrypt = perf_counter_ns()
    for _ in range(N):
        var _r_chacha20_decrypt = chacha20_decrypt(_li5, _li5, _li5)
        _acc_chacha20_decrypt += Float64(len(_r_chacha20_decrypt))
    var _t1_chacha20_decrypt = perf_counter_ns()
    var _ns_chacha20_decrypt = Float64(_t1_chacha20_decrypt - _t0_chacha20_decrypt) / Float64(N)
    print("MOJO_TIMING crypto_chacha20::chacha20_decrypt", _ns_chacha20_decrypt, _acc_chacha20_decrypt)
    var _result_chacha20_decrypt = chacha20_decrypt(_li5, _li5, _li5)
    var _summary_chacha20_decrypt = _summary_list_int(_result_chacha20_decrypt)
    print("MOJO_RESULT crypto_chacha20::chacha20_decrypt", _summary_chacha20_decrypt)
