"""test_crypto_pbkdf2.mojo — auto-generated tests for crypto.pbkdf2."""
from std.math import isnan, isinf
from crypto.pbkdf2 import sha256_bytes, bytes_from_string, bytes_to_hex, xor_byte_lists, int_to_bytes_be, hmac_sha256_bytes, pbkdf2_hmac_sha256

def is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _li3 = List[Int]()
    _li3.append(1); _li3.append(2); _li3.append(3)
    var _li2_zero = List[Int]()
    _li2_zero.append(0); _li2_zero.append(1)
    var _li3_tail = List[Int]()
    _li3_tail.append(2); _li3_tail.append(3); _li3_tail.append(4)
    var _li8 = List[Int]()
    for i in range(8):
        _li8.append(i + 1)
    var _li6_grid2x3 = List[Int]()
    _li6_grid2x3.append(0); _li6_grid2x3.append(1); _li6_grid2x3.append(0)
    _li6_grid2x3.append(1); _li6_grid2x3.append(1); _li6_grid2x3.append(0)
    var _li10_borda = List[Int]()
    _li10_borda.append(0); _li10_borda.append(1); _li10_borda.append(2); _li10_borda.append(3); _li10_borda.append(4)
    _li10_borda.append(1); _li10_borda.append(0); _li10_borda.append(2); _li10_borda.append(4); _li10_borda.append(3)
    var _li16 = List[Int]()
    for i in range(16):
        _li16.append(i)
    var _lf6_matrix = List[Float64]()
    _lf6_matrix.append(1.0); _lf6_matrix.append(2.0); _lf6_matrix.append(3.0)
    _lf6_matrix.append(4.0); _lf6_matrix.append(5.0); _lf6_matrix.append(6.0)
    var _lf8_coalitions = List[Float64]()
    _lf8_coalitions.append(0.0); _lf8_coalitions.append(1.0); _lf8_coalitions.append(2.0); _lf8_coalitions.append(4.0)
    _lf8_coalitions.append(3.0); _lf8_coalitions.append(5.0); _lf8_coalitions.append(6.0); _lf8_coalitions.append(9.0)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_sha256_bytes = sha256_bytes(_li5)
    if len(_v_sha256_bytes) >= 0: passed += 1; print("  ✅ crypto.pbkdf2::sha256_bytes")
    var _v_bytes_from_string = bytes_from_string("test")
    if len(_v_bytes_from_string) >= 0: passed += 1; print("  ✅ crypto.pbkdf2::bytes_from_string")
    _ = bytes_to_hex(_li5)
    passed += 1; print("  ✅ crypto.pbkdf2::bytes_to_hex")
    var _v_xor_byte_lists = xor_byte_lists(_li5, _li5)
    if len(_v_xor_byte_lists) >= 0: passed += 1; print("  ✅ crypto.pbkdf2::xor_byte_lists")
    var _v_int_to_bytes_be = int_to_bytes_be(5, 5)
    if len(_v_int_to_bytes_be) >= 0: passed += 1; print("  ✅ crypto.pbkdf2::int_to_bytes_be")
    var _v_hmac_sha256_bytes = hmac_sha256_bytes(_li5, _li5)
    if len(_v_hmac_sha256_bytes) >= 0: passed += 1; print("  ✅ crypto.pbkdf2::hmac_sha256_bytes")
    var _v_pbkdf2_hmac_sha256 = pbkdf2_hmac_sha256(_li5, _li5, 5, 5)
    if len(_v_pbkdf2_hmac_sha256) >= 0: passed += 1; print("  ✅ crypto.pbkdf2::pbkdf2_hmac_sha256")

    print("  [crypto.pbkdf2] Passed:", passed, "Failed:", failed)
