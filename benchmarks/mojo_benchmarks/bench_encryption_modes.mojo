"""bench_encryption_modes.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from encryption_modes import ecb_block_count, cbc_iv_required, ctr_nonce_size, gcm_tag_length_default, padding_pkcs7_bytes, ciphertext_length_cbc, ciphertext_length_gcm, aead_overhead, key_schedule_rounds_aes, throughput_estimate, parallel_blocks_ctr, security_margin_bits
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

    var _acc_ecb_block_count: Float64 = 0.0
    var _t0_ecb_block_count = perf_counter_ns()
    for _ in range(N):
        _acc_ecb_block_count += Float64(ecb_block_count(5, 5))
    var _t1_ecb_block_count = perf_counter_ns()
    var _ns_ecb_block_count = Float64(_t1_ecb_block_count - _t0_ecb_block_count) / Float64(N)
    print("MOJO_TIMING encryption_modes::ecb_block_count", _ns_ecb_block_count, _acc_ecb_block_count)
    var _acc_cbc_iv_required: Float64 = 0.0
    var _t0_cbc_iv_required = perf_counter_ns()
    for _ in range(N):
        _acc_cbc_iv_required += Float64(cbc_iv_required())
    var _t1_cbc_iv_required = perf_counter_ns()
    var _ns_cbc_iv_required = Float64(_t1_cbc_iv_required - _t0_cbc_iv_required) / Float64(N)
    print("MOJO_TIMING encryption_modes::cbc_iv_required", _ns_cbc_iv_required, _acc_cbc_iv_required)
    var _acc_ctr_nonce_size: Float64 = 0.0
    var _t0_ctr_nonce_size = perf_counter_ns()
    for _ in range(N):
        _acc_ctr_nonce_size += Float64(ctr_nonce_size(5))
    var _t1_ctr_nonce_size = perf_counter_ns()
    var _ns_ctr_nonce_size = Float64(_t1_ctr_nonce_size - _t0_ctr_nonce_size) / Float64(N)
    print("MOJO_TIMING encryption_modes::ctr_nonce_size", _ns_ctr_nonce_size, _acc_ctr_nonce_size)
    var _acc_gcm_tag_length_default: Float64 = 0.0
    var _t0_gcm_tag_length_default = perf_counter_ns()
    for _ in range(N):
        _acc_gcm_tag_length_default += Float64(gcm_tag_length_default())
    var _t1_gcm_tag_length_default = perf_counter_ns()
    var _ns_gcm_tag_length_default = Float64(_t1_gcm_tag_length_default - _t0_gcm_tag_length_default) / Float64(N)
    print("MOJO_TIMING encryption_modes::gcm_tag_length_default", _ns_gcm_tag_length_default, _acc_gcm_tag_length_default)
    var _acc_padding_pkcs7_bytes: Float64 = 0.0
    var _t0_padding_pkcs7_bytes = perf_counter_ns()
    for _ in range(N):
        _acc_padding_pkcs7_bytes += Float64(padding_pkcs7_bytes(5, 5))
    var _t1_padding_pkcs7_bytes = perf_counter_ns()
    var _ns_padding_pkcs7_bytes = Float64(_t1_padding_pkcs7_bytes - _t0_padding_pkcs7_bytes) / Float64(N)
    print("MOJO_TIMING encryption_modes::padding_pkcs7_bytes", _ns_padding_pkcs7_bytes, _acc_padding_pkcs7_bytes)
    var _acc_ciphertext_length_cbc: Float64 = 0.0
    var _t0_ciphertext_length_cbc = perf_counter_ns()
    for _ in range(N):
        _acc_ciphertext_length_cbc += Float64(ciphertext_length_cbc(5, 5))
    var _t1_ciphertext_length_cbc = perf_counter_ns()
    var _ns_ciphertext_length_cbc = Float64(_t1_ciphertext_length_cbc - _t0_ciphertext_length_cbc) / Float64(N)
    print("MOJO_TIMING encryption_modes::ciphertext_length_cbc", _ns_ciphertext_length_cbc, _acc_ciphertext_length_cbc)
    var _acc_ciphertext_length_gcm: Float64 = 0.0
    var _t0_ciphertext_length_gcm = perf_counter_ns()
    for _ in range(N):
        _acc_ciphertext_length_gcm += Float64(ciphertext_length_gcm(5, 5))
    var _t1_ciphertext_length_gcm = perf_counter_ns()
    var _ns_ciphertext_length_gcm = Float64(_t1_ciphertext_length_gcm - _t0_ciphertext_length_gcm) / Float64(N)
    print("MOJO_TIMING encryption_modes::ciphertext_length_gcm", _ns_ciphertext_length_gcm, _acc_ciphertext_length_gcm)
    var _acc_aead_overhead: Float64 = 0.0
    var _t0_aead_overhead = perf_counter_ns()
    for _ in range(N):
        _acc_aead_overhead += Float64(aead_overhead(5, 5))
    var _t1_aead_overhead = perf_counter_ns()
    var _ns_aead_overhead = Float64(_t1_aead_overhead - _t0_aead_overhead) / Float64(N)
    print("MOJO_TIMING encryption_modes::aead_overhead", _ns_aead_overhead, _acc_aead_overhead)
    var _acc_key_schedule_rounds_aes: Float64 = 0.0
    var _t0_key_schedule_rounds_aes = perf_counter_ns()
    for _ in range(N):
        _acc_key_schedule_rounds_aes += Float64(key_schedule_rounds_aes(5))
    var _t1_key_schedule_rounds_aes = perf_counter_ns()
    var _ns_key_schedule_rounds_aes = Float64(_t1_key_schedule_rounds_aes - _t0_key_schedule_rounds_aes) / Float64(N)
    print("MOJO_TIMING encryption_modes::key_schedule_rounds_aes", _ns_key_schedule_rounds_aes, _acc_key_schedule_rounds_aes)
    var _acc_throughput_estimate: Float64 = 0.0
    var _t0_throughput_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_throughput_estimate += throughput_estimate(5, 0.5)
    var _t1_throughput_estimate = perf_counter_ns()
    var _ns_throughput_estimate = Float64(_t1_throughput_estimate - _t0_throughput_estimate) / Float64(N)
    print("MOJO_TIMING encryption_modes::throughput_estimate", _ns_throughput_estimate, _acc_throughput_estimate)
    var _acc_parallel_blocks_ctr: Float64 = 0.0
    var _t0_parallel_blocks_ctr = perf_counter_ns()
    for _ in range(N):
        _acc_parallel_blocks_ctr += Float64(parallel_blocks_ctr(5, 5))
    var _t1_parallel_blocks_ctr = perf_counter_ns()
    var _ns_parallel_blocks_ctr = Float64(_t1_parallel_blocks_ctr - _t0_parallel_blocks_ctr) / Float64(N)
    print("MOJO_TIMING encryption_modes::parallel_blocks_ctr", _ns_parallel_blocks_ctr, _acc_parallel_blocks_ctr)
    var _acc_security_margin_bits: Float64 = 0.0
    var _t0_security_margin_bits = perf_counter_ns()
    for _ in range(N):
        _acc_security_margin_bits += Float64(security_margin_bits(5, 5))
    var _t1_security_margin_bits = perf_counter_ns()
    var _ns_security_margin_bits = Float64(_t1_security_margin_bits - _t0_security_margin_bits) / Float64(N)
    print("MOJO_TIMING encryption_modes::security_margin_bits", _ns_security_margin_bits, _acc_security_margin_bits)
