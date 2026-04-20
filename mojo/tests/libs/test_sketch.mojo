"""test_sketch.mojo — auto-generated tests for sketch library."""
from std.math import isnan, isinf
from sketch import create_cms, cms_hash, create_hll, hll_hash, leading_zeros

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

    _ = create_cms(5, 5)
    passed += 1; print("  ✅ sketch::create_cms")
    _ = cms_hash(5, 5, 5)
    passed += 1; print("  ✅ sketch::cms_hash")
    _ = create_hll(5)
    passed += 1; print("  ✅ sketch::create_hll")
    _ = hll_hash(5)
    passed += 1; print("  ✅ sketch::hll_hash")
    _ = leading_zeros(5, 5)
    passed += 1; print("  ✅ sketch::leading_zeros")

    print("  [sketch] Passed:", passed, "Failed:", failed)
