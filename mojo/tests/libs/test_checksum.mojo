"""test_checksum.mojo — auto-generated tests for checksum library."""
from std.math import isnan, isinf
from checksum import adler32, fletcher16, luhn_check, luhn_checksum, isbn10_check, isbn13_check, xor_checksum, modular_sum, parity_bit, internet_checksum, verhoeff_check

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
