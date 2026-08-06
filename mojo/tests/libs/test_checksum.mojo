"""test_checksum.mojo — auto-generated tests for checksum."""
from std.math import isnan, isinf
from checksum import adler32, fletcher16, luhn_check, luhn_checksum, isbn10_check, isbn13_check, xor_checksum, modular_sum, parity_bit, internet_checksum, verhoeff_check

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

    _ = adler32(_li5)
    passed += 1; print("  ✅ checksum::adler32")
    _ = fletcher16(_li5)
    passed += 1; print("  ✅ checksum::fletcher16")
    _ = luhn_check(_li5)
    passed += 1; print("  ✅ checksum::luhn_check")
    _ = luhn_checksum(_li5)
    passed += 1; print("  ✅ checksum::luhn_checksum")
    _ = isbn10_check(_li5)
    passed += 1; print("  ✅ checksum::isbn10_check")
    _ = isbn13_check(_li5)
    passed += 1; print("  ✅ checksum::isbn13_check")
    _ = xor_checksum(_li5)
    passed += 1; print("  ✅ checksum::xor_checksum")
    _ = modular_sum(_li5, 5)
    passed += 1; print("  ✅ checksum::modular_sum")
    _ = parity_bit(_li5)
    passed += 1; print("  ✅ checksum::parity_bit")
    _ = internet_checksum(_li5)
    passed += 1; print("  ✅ checksum::internet_checksum")
    _ = verhoeff_check(_li5)
    passed += 1; print("  ✅ checksum::verhoeff_check")

    print("  [checksum] Passed:", passed, "Failed:", failed)
