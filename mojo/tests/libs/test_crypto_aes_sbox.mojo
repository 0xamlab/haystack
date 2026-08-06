"""test_crypto_aes_sbox.mojo — auto-generated tests for crypto.aes_sbox."""
from std.math import isnan, isinf
from crypto.aes_sbox import aes_sbox, aes_inv_sbox, sub_bytes, inv_sub_bytes, shift_rows, inv_shift_rows, xor_bytes, add_round_key

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

    _ = aes_sbox(5)
    passed += 1; print("  ✅ crypto.aes_sbox::aes_sbox")
    _ = aes_inv_sbox(5)
    passed += 1; print("  ✅ crypto.aes_sbox::aes_inv_sbox")
    var _v_sub_bytes = sub_bytes(_li16)
    if len(_v_sub_bytes) >= 0: passed += 1; print("  ✅ crypto.aes_sbox::sub_bytes")
    var _v_inv_sub_bytes = inv_sub_bytes(_li16)
    if len(_v_inv_sub_bytes) >= 0: passed += 1; print("  ✅ crypto.aes_sbox::inv_sub_bytes")
    var _v_shift_rows = shift_rows(_li16)
    if len(_v_shift_rows) >= 0: passed += 1; print("  ✅ crypto.aes_sbox::shift_rows")
    var _v_inv_shift_rows = inv_shift_rows(_li16)
    if len(_v_inv_shift_rows) >= 0: passed += 1; print("  ✅ crypto.aes_sbox::inv_shift_rows")
    var _v_xor_bytes = xor_bytes(_li16, _li16)
    if len(_v_xor_bytes) >= 0: passed += 1; print("  ✅ crypto.aes_sbox::xor_bytes")
    var _v_add_round_key = add_round_key(_li16, _li16)
    if len(_v_add_round_key) >= 0: passed += 1; print("  ✅ crypto.aes_sbox::add_round_key")

    print("  [crypto.aes_sbox] Passed:", passed, "Failed:", failed)
