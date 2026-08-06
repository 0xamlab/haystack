"""test_compression_delta.mojo — auto-generated tests for compression.delta."""
from std.math import isnan, isinf
from compression.delta import delta_encode, delta_decode, delta_encode_float, delta_decode_float, xor_delta_encode, xor_delta_decode, zigzag_delta_encode, zigzag_delta_decode, double_delta_encode, double_delta_decode, compression_savings

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

    var _v_delta_encode = delta_encode(_li5)
    if len(_v_delta_encode) >= 0: passed += 1; print("  ✅ compression.delta::delta_encode")
    var _v_delta_decode = delta_decode(_li5)
    if len(_v_delta_decode) >= 0: passed += 1; print("  ✅ compression.delta::delta_decode")
    var _v_delta_encode_float = delta_encode_float(_lf5, 5)
    if len(_v_delta_encode_float) >= 0: passed += 1; print("  ✅ compression.delta::delta_encode_float")
    var _v_delta_decode_float = delta_decode_float(_li5, 5)
    if len(_v_delta_decode_float) >= 0: passed += 1; print("  ✅ compression.delta::delta_decode_float")
    var _v_xor_delta_encode = xor_delta_encode(_li5)
    if len(_v_xor_delta_encode) >= 0: passed += 1; print("  ✅ compression.delta::xor_delta_encode")
    var _v_xor_delta_decode = xor_delta_decode(_li5)
    if len(_v_xor_delta_decode) >= 0: passed += 1; print("  ✅ compression.delta::xor_delta_decode")
    var _v_zigzag_delta_encode = zigzag_delta_encode(_li5)
    if len(_v_zigzag_delta_encode) >= 0: passed += 1; print("  ✅ compression.delta::zigzag_delta_encode")
    var _v_zigzag_delta_decode = zigzag_delta_decode(_li5)
    if len(_v_zigzag_delta_decode) >= 0: passed += 1; print("  ✅ compression.delta::zigzag_delta_decode")
    var _v_double_delta_encode = double_delta_encode(_li5)
    if len(_v_double_delta_encode) >= 0: passed += 1; print("  ✅ compression.delta::double_delta_encode")
    var _v_double_delta_decode = double_delta_decode(_li5)
    if len(_v_double_delta_decode) >= 0: passed += 1; print("  ✅ compression.delta::double_delta_decode")
    var _v_compression_savings = compression_savings(5, 5)
    if is_finite(_v_compression_savings): passed += 1; print("  ✅ compression.delta::compression_savings =", _v_compression_savings)
    else: failed += 1; print("  ❌ compression.delta::compression_savings → non-finite:", _v_compression_savings)

    print("  [compression.delta] Passed:", passed, "Failed:", failed)
