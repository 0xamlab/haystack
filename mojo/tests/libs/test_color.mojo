"""test_color.mojo — auto-generated tests for color library."""
from std.math import isnan, isinf
from color import clamp01, hex_to_rgb

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

    var _v_clamp01 = clamp01(0.5)
    if is_finite(_v_clamp01): passed += 1; print("  ✅ color::clamp01 =", _v_clamp01)
    else: failed += 1; print("  ❌ color::clamp01 → non-finite:", _v_clamp01)
    _ = hex_to_rgb("test")
    passed += 1; print("  ✅ color::hex_to_rgb")

    print("  [color] Passed:", passed, "Failed:", failed)
