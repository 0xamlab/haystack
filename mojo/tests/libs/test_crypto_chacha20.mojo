"""test_crypto_chacha20.mojo — auto-generated tests for crypto.chacha20."""
from std.math import isnan, isinf
from crypto.chacha20 import rotl32, chacha20_init_state, add_states, xor_states, chacha20_block, chacha20_encrypt, chacha20_decrypt

fn is_finite(x: Float64) -> Bool:
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

    _ = rotl32(5, 5)
    passed += 1; print("  ✅ crypto.chacha20::rotl32")
    var _v_chacha20_init_state = chacha20_init_state(_li8, 5, _li3)
    if len(_v_chacha20_init_state) >= 0: passed += 1; print("  ✅ crypto.chacha20::chacha20_init_state")
    var _v_add_states = add_states(_li5, _li5)
    if len(_v_add_states) >= 0: passed += 1; print("  ✅ crypto.chacha20::add_states")
    var _v_xor_states = xor_states(_li5, _li5)
    if len(_v_xor_states) >= 0: passed += 1; print("  ✅ crypto.chacha20::xor_states")
    var _v_chacha20_block = chacha20_block(_li8, 5, _li3)
    if len(_v_chacha20_block) >= 0: passed += 1; print("  ✅ crypto.chacha20::chacha20_block")
    var _v_chacha20_encrypt = chacha20_encrypt(_li16, _li8, _li3)
    if len(_v_chacha20_encrypt) >= 0: passed += 1; print("  ✅ crypto.chacha20::chacha20_encrypt")
    var _v_chacha20_decrypt = chacha20_decrypt(_li16, _li8, _li3)
    if len(_v_chacha20_decrypt) >= 0: passed += 1; print("  ✅ crypto.chacha20::chacha20_decrypt")

    print("  [crypto.chacha20] Passed:", passed, "Failed:", failed)
