"""bench_encryption_modes.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from encryption_modes import ecb_block_count, cbc_iv_required, ctr_nonce_size, gcm_tag_length_default, padding_pkcs7_bytes, ciphertext_length_cbc, ciphertext_length_gcm, aead_overhead, key_schedule_rounds_aes, throughput_estimate, parallel_blocks_ctr, security_margin_bits
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

    var _acc_ecb_block_count: Float64 = 0.0
    var _t0_ecb_block_count = perf_counter_ns()
    for _ in range(N):
        _acc_ecb_block_count += Float64(ecb_block_count(5, 5))
    var _t1_ecb_block_count = perf_counter_ns()
    var _ns_ecb_block_count = Float64(_t1_ecb_block_count - _t0_ecb_block_count) / Float64(N)
    print("MOJO_TIMING encryption_modes::ecb_block_count", _ns_ecb_block_count, _acc_ecb_block_count)
    var _result_ecb_block_count = ecb_block_count(5, 5)
    var _summary_ecb_block_count = _summary_int(_result_ecb_block_count)
    print("MOJO_RESULT encryption_modes::ecb_block_count", _summary_ecb_block_count)
    var _acc_cbc_iv_required: Float64 = 0.0
    var _t0_cbc_iv_required = perf_counter_ns()
    for _ in range(N):
        _acc_cbc_iv_required += Float64(cbc_iv_required())
    var _t1_cbc_iv_required = perf_counter_ns()
    var _ns_cbc_iv_required = Float64(_t1_cbc_iv_required - _t0_cbc_iv_required) / Float64(N)
    print("MOJO_TIMING encryption_modes::cbc_iv_required", _ns_cbc_iv_required, _acc_cbc_iv_required)
    var _result_cbc_iv_required = cbc_iv_required()
    var _summary_cbc_iv_required = _summary_bool(_result_cbc_iv_required)
    print("MOJO_RESULT encryption_modes::cbc_iv_required", _summary_cbc_iv_required)
    var _acc_ctr_nonce_size: Float64 = 0.0
    var _t0_ctr_nonce_size = perf_counter_ns()
    for _ in range(N):
        _acc_ctr_nonce_size += Float64(ctr_nonce_size(5))
    var _t1_ctr_nonce_size = perf_counter_ns()
    var _ns_ctr_nonce_size = Float64(_t1_ctr_nonce_size - _t0_ctr_nonce_size) / Float64(N)
    print("MOJO_TIMING encryption_modes::ctr_nonce_size", _ns_ctr_nonce_size, _acc_ctr_nonce_size)
    var _result_ctr_nonce_size = ctr_nonce_size(5)
    var _summary_ctr_nonce_size = _summary_int(_result_ctr_nonce_size)
    print("MOJO_RESULT encryption_modes::ctr_nonce_size", _summary_ctr_nonce_size)
    var _acc_gcm_tag_length_default: Float64 = 0.0
    var _t0_gcm_tag_length_default = perf_counter_ns()
    for _ in range(N):
        _acc_gcm_tag_length_default += Float64(gcm_tag_length_default())
    var _t1_gcm_tag_length_default = perf_counter_ns()
    var _ns_gcm_tag_length_default = Float64(_t1_gcm_tag_length_default - _t0_gcm_tag_length_default) / Float64(N)
    print("MOJO_TIMING encryption_modes::gcm_tag_length_default", _ns_gcm_tag_length_default, _acc_gcm_tag_length_default)
    var _result_gcm_tag_length_default = gcm_tag_length_default()
    var _summary_gcm_tag_length_default = _summary_int(_result_gcm_tag_length_default)
    print("MOJO_RESULT encryption_modes::gcm_tag_length_default", _summary_gcm_tag_length_default)
    var _acc_padding_pkcs7_bytes: Float64 = 0.0
    var _t0_padding_pkcs7_bytes = perf_counter_ns()
    for _ in range(N):
        _acc_padding_pkcs7_bytes += Float64(padding_pkcs7_bytes(5, 5))
    var _t1_padding_pkcs7_bytes = perf_counter_ns()
    var _ns_padding_pkcs7_bytes = Float64(_t1_padding_pkcs7_bytes - _t0_padding_pkcs7_bytes) / Float64(N)
    print("MOJO_TIMING encryption_modes::padding_pkcs7_bytes", _ns_padding_pkcs7_bytes, _acc_padding_pkcs7_bytes)
    var _result_padding_pkcs7_bytes = padding_pkcs7_bytes(5, 5)
    var _summary_padding_pkcs7_bytes = _summary_int(_result_padding_pkcs7_bytes)
    print("MOJO_RESULT encryption_modes::padding_pkcs7_bytes", _summary_padding_pkcs7_bytes)
    var _acc_ciphertext_length_cbc: Float64 = 0.0
    var _t0_ciphertext_length_cbc = perf_counter_ns()
    for _ in range(N):
        _acc_ciphertext_length_cbc += Float64(ciphertext_length_cbc(5, 5))
    var _t1_ciphertext_length_cbc = perf_counter_ns()
    var _ns_ciphertext_length_cbc = Float64(_t1_ciphertext_length_cbc - _t0_ciphertext_length_cbc) / Float64(N)
    print("MOJO_TIMING encryption_modes::ciphertext_length_cbc", _ns_ciphertext_length_cbc, _acc_ciphertext_length_cbc)
    var _result_ciphertext_length_cbc = ciphertext_length_cbc(5, 5)
    var _summary_ciphertext_length_cbc = _summary_int(_result_ciphertext_length_cbc)
    print("MOJO_RESULT encryption_modes::ciphertext_length_cbc", _summary_ciphertext_length_cbc)
    var _acc_ciphertext_length_gcm: Float64 = 0.0
    var _t0_ciphertext_length_gcm = perf_counter_ns()
    for _ in range(N):
        _acc_ciphertext_length_gcm += Float64(ciphertext_length_gcm(5, 5))
    var _t1_ciphertext_length_gcm = perf_counter_ns()
    var _ns_ciphertext_length_gcm = Float64(_t1_ciphertext_length_gcm - _t0_ciphertext_length_gcm) / Float64(N)
    print("MOJO_TIMING encryption_modes::ciphertext_length_gcm", _ns_ciphertext_length_gcm, _acc_ciphertext_length_gcm)
    var _result_ciphertext_length_gcm = ciphertext_length_gcm(5, 5)
    var _summary_ciphertext_length_gcm = _summary_int(_result_ciphertext_length_gcm)
    print("MOJO_RESULT encryption_modes::ciphertext_length_gcm", _summary_ciphertext_length_gcm)
    var _acc_aead_overhead: Float64 = 0.0
    var _t0_aead_overhead = perf_counter_ns()
    for _ in range(N):
        _acc_aead_overhead += Float64(aead_overhead(5, 5))
    var _t1_aead_overhead = perf_counter_ns()
    var _ns_aead_overhead = Float64(_t1_aead_overhead - _t0_aead_overhead) / Float64(N)
    print("MOJO_TIMING encryption_modes::aead_overhead", _ns_aead_overhead, _acc_aead_overhead)
    var _result_aead_overhead = aead_overhead(5, 5)
    var _summary_aead_overhead = _summary_int(_result_aead_overhead)
    print("MOJO_RESULT encryption_modes::aead_overhead", _summary_aead_overhead)
    var _acc_key_schedule_rounds_aes: Float64 = 0.0
    var _t0_key_schedule_rounds_aes = perf_counter_ns()
    for _ in range(N):
        _acc_key_schedule_rounds_aes += Float64(key_schedule_rounds_aes(5))
    var _t1_key_schedule_rounds_aes = perf_counter_ns()
    var _ns_key_schedule_rounds_aes = Float64(_t1_key_schedule_rounds_aes - _t0_key_schedule_rounds_aes) / Float64(N)
    print("MOJO_TIMING encryption_modes::key_schedule_rounds_aes", _ns_key_schedule_rounds_aes, _acc_key_schedule_rounds_aes)
    var _result_key_schedule_rounds_aes = key_schedule_rounds_aes(5)
    var _summary_key_schedule_rounds_aes = _summary_int(_result_key_schedule_rounds_aes)
    print("MOJO_RESULT encryption_modes::key_schedule_rounds_aes", _summary_key_schedule_rounds_aes)
    var _acc_throughput_estimate: Float64 = 0.0
    var _t0_throughput_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_throughput_estimate += throughput_estimate(5, 0.5)
    var _t1_throughput_estimate = perf_counter_ns()
    var _ns_throughput_estimate = Float64(_t1_throughput_estimate - _t0_throughput_estimate) / Float64(N)
    print("MOJO_TIMING encryption_modes::throughput_estimate", _ns_throughput_estimate, _acc_throughput_estimate)
    var _result_throughput_estimate = throughput_estimate(5, 0.5)
    var _summary_throughput_estimate = _summary_float64(_result_throughput_estimate)
    print("MOJO_RESULT encryption_modes::throughput_estimate", _summary_throughput_estimate)
    var _acc_parallel_blocks_ctr: Float64 = 0.0
    var _t0_parallel_blocks_ctr = perf_counter_ns()
    for _ in range(N):
        _acc_parallel_blocks_ctr += Float64(parallel_blocks_ctr(5, 5))
    var _t1_parallel_blocks_ctr = perf_counter_ns()
    var _ns_parallel_blocks_ctr = Float64(_t1_parallel_blocks_ctr - _t0_parallel_blocks_ctr) / Float64(N)
    print("MOJO_TIMING encryption_modes::parallel_blocks_ctr", _ns_parallel_blocks_ctr, _acc_parallel_blocks_ctr)
    var _result_parallel_blocks_ctr = parallel_blocks_ctr(5, 5)
    var _summary_parallel_blocks_ctr = _summary_int(_result_parallel_blocks_ctr)
    print("MOJO_RESULT encryption_modes::parallel_blocks_ctr", _summary_parallel_blocks_ctr)
    var _acc_security_margin_bits: Float64 = 0.0
    var _t0_security_margin_bits = perf_counter_ns()
    for _ in range(N):
        _acc_security_margin_bits += Float64(security_margin_bits(5, 5))
    var _t1_security_margin_bits = perf_counter_ns()
    var _ns_security_margin_bits = Float64(_t1_security_margin_bits - _t0_security_margin_bits) / Float64(N)
    print("MOJO_TIMING encryption_modes::security_margin_bits", _ns_security_margin_bits, _acc_security_margin_bits)
    var _result_security_margin_bits = security_margin_bits(5, 5)
    var _summary_security_margin_bits = _summary_int(_result_security_margin_bits)
    print("MOJO_RESULT encryption_modes::security_margin_bits", _summary_security_margin_bits)
