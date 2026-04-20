"""test_bloom_counting.mojo — auto-generated tests for bloom_counting library."""
from std.math import isnan, isinf
from bloom_counting import cb_create, cb_hash, cb_false_positive_rate, cb_optimal_hashes

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

    _ = cb_create(5, 5)
    passed += 1; print("  ✅ bloom_counting::cb_create")
    _ = cb_hash(5, 5, 5)
    passed += 1; print("  ✅ bloom_counting::cb_hash")
    var _v_cb_false_positive_rate = cb_false_positive_rate(5, 5, 5)
    if is_finite(_v_cb_false_positive_rate): passed += 1; print("  ✅ bloom_counting::cb_false_positive_rate =", _v_cb_false_positive_rate)
    else: failed += 1; print("  ❌ bloom_counting::cb_false_positive_rate → non-finite:", _v_cb_false_positive_rate)
    _ = cb_optimal_hashes(5, 5)
    passed += 1; print("  ✅ bloom_counting::cb_optimal_hashes")

    print("  [bloom_counting] Passed:", passed, "Failed:", failed)
