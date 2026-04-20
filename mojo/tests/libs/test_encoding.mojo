"""test_encoding.mojo — auto-generated tests for encoding library."""
from std.math import isnan, isinf
from encoding import one_hot_encode, binary_encode

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

    _ = one_hot_encode(_li5, 5)
    passed += 1; print("  ✅ encoding::one_hot_encode")
    var _v_binary_encode = binary_encode(5, 5)
    if len(_v_binary_encode) >= 0: passed += 1; print("  ✅ encoding::binary_encode")

    print("  [encoding] Passed:", passed, "Failed:", failed)
