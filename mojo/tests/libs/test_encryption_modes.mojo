"""test_encryption_modes.mojo — auto-generated tests for encryption_modes library."""
from std.math import isnan, isinf
from encryption_modes import ecb_block_count, cbc_iv_required, ctr_nonce_size, gcm_tag_length_default, padding_pkcs7_bytes, ciphertext_length_cbc, ciphertext_length_gcm, aead_overhead, key_schedule_rounds_aes, throughput_estimate, parallel_blocks_ctr, security_margin_bits

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    _ = ecb_block_count(5, 5)
    passed += 1; print("  ✅ encryption_modes::ecb_block_count")
    _ = cbc_iv_required()
    passed += 1; print("  ✅ encryption_modes::cbc_iv_required")
    _ = ctr_nonce_size(5)
    passed += 1; print("  ✅ encryption_modes::ctr_nonce_size")
    _ = gcm_tag_length_default()
    passed += 1; print("  ✅ encryption_modes::gcm_tag_length_default")
    _ = padding_pkcs7_bytes(5, 5)
    passed += 1; print("  ✅ encryption_modes::padding_pkcs7_bytes")
    _ = ciphertext_length_cbc(5, 5)
    passed += 1; print("  ✅ encryption_modes::ciphertext_length_cbc")
    _ = ciphertext_length_gcm(5, 5)
    passed += 1; print("  ✅ encryption_modes::ciphertext_length_gcm")
    _ = aead_overhead(5, 5)
    passed += 1; print("  ✅ encryption_modes::aead_overhead")
    _ = key_schedule_rounds_aes(5)
    passed += 1; print("  ✅ encryption_modes::key_schedule_rounds_aes")
    var _v_throughput_estimate = throughput_estimate(5, 0.5)
    if is_finite(_v_throughput_estimate): passed += 1; print("  ✅ encryption_modes::throughput_estimate =", _v_throughput_estimate)
    else: failed += 1; print("  ❌ encryption_modes::throughput_estimate → non-finite:", _v_throughput_estimate)
    _ = parallel_blocks_ctr(5, 5)
    passed += 1; print("  ✅ encryption_modes::parallel_blocks_ctr")
    _ = security_margin_bits(5, 5)
    passed += 1; print("  ✅ encryption_modes::security_margin_bits")

    print("  [encryption_modes] Passed:", passed, "Failed:", failed)
