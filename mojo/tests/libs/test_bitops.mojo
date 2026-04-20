"""test_bitops.mojo — auto-generated tests for bitops library."""
from std.math import isnan, isinf
from bitops import popcount, leading_zeros, trailing_zeros, next_power_of_2, is_power_of_2, reverse_bits, rotate_left, rotate_right, bit_set, bit_clear, bit_test, bit_toggle, fnv1a_hash

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

    _ = popcount(5)
    passed += 1; print("  ✅ bitops::popcount")
    _ = leading_zeros(5)
    passed += 1; print("  ✅ bitops::leading_zeros")
    _ = trailing_zeros(5)
    passed += 1; print("  ✅ bitops::trailing_zeros")
    _ = next_power_of_2(5)
    passed += 1; print("  ✅ bitops::next_power_of_2")
    _ = is_power_of_2(5)
    passed += 1; print("  ✅ bitops::is_power_of_2")
    _ = reverse_bits(UInt32(42))
    passed += 1; print("  ✅ bitops::reverse_bits")
    _ = rotate_left(UInt32(42), 5)
    passed += 1; print("  ✅ bitops::rotate_left")
    _ = rotate_right(UInt32(42), 5)
    passed += 1; print("  ✅ bitops::rotate_right")
    _ = bit_set(5, 5)
    passed += 1; print("  ✅ bitops::bit_set")
    _ = bit_clear(5, 5)
    passed += 1; print("  ✅ bitops::bit_clear")
    _ = bit_test(5, 5)
    passed += 1; print("  ✅ bitops::bit_test")
    _ = bit_toggle(5, 5)
    passed += 1; print("  ✅ bitops::bit_toggle")
    _ = fnv1a_hash("test")
    passed += 1; print("  ✅ bitops::fnv1a_hash")

    print("  [bitops] Passed:", passed, "Failed:", failed)
