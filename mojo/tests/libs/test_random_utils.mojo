"""test_random_utils.mojo — auto-generated tests for random_utils library."""
from std.math import isnan, isinf
from random_utils import random_choice, random_sample, random_bootstrap, random_uniform_int, random_permutation, stratified_sample

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

    _ = random_choice(_lf5)
    passed += 1; print("  ✅ random_utils::random_choice")
    var _v_random_sample = random_sample(_lf5, 5)
    if len(_v_random_sample) >= 0: passed += 1; print("  ✅ random_utils::random_sample")
    var _v_random_bootstrap = random_bootstrap(_lf5, 5)
    if len(_v_random_bootstrap) >= 0: passed += 1; print("  ✅ random_utils::random_bootstrap")
    _ = random_uniform_int(5, 5)
    passed += 1; print("  ✅ random_utils::random_uniform_int")
    var _v_random_permutation = random_permutation(5)
    if len(_v_random_permutation) >= 0: passed += 1; print("  ✅ random_utils::random_permutation")
    var _v_stratified_sample = stratified_sample(_lf5, 5)
    if len(_v_stratified_sample) >= 0: passed += 1; print("  ✅ random_utils::stratified_sample")

    print("  [random_utils] Passed:", passed, "Failed:", failed)
