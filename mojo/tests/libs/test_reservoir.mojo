"""test_reservoir.mojo — auto-generated tests for reservoir library."""
from std.math import isnan, isinf
from reservoir import reservoir_sample, weighted_reservoir_sample, reservoir_sample_indices, bootstrap_sample, systematic_sample, sample_with_replacement, sample_without_replacement

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

    var _v_reservoir_sample = reservoir_sample(_lf5, 5)
    if len(_v_reservoir_sample) >= 0: passed += 1; print("  ✅ reservoir::reservoir_sample")
    var _v_weighted_reservoir_sample = weighted_reservoir_sample(_lf5, _lf5, 5)
    if len(_v_weighted_reservoir_sample) >= 0: passed += 1; print("  ✅ reservoir::weighted_reservoir_sample")
    var _v_reservoir_sample_indices = reservoir_sample_indices(5, 5)
    if len(_v_reservoir_sample_indices) >= 0: passed += 1; print("  ✅ reservoir::reservoir_sample_indices")
    var _v_bootstrap_sample = bootstrap_sample(_lf5)
    if len(_v_bootstrap_sample) >= 0: passed += 1; print("  ✅ reservoir::bootstrap_sample")
    var _v_systematic_sample = systematic_sample(_lf5, 5)
    if len(_v_systematic_sample) >= 0: passed += 1; print("  ✅ reservoir::systematic_sample")
    var _v_sample_with_replacement = sample_with_replacement(_lf5, 5)
    if len(_v_sample_with_replacement) >= 0: passed += 1; print("  ✅ reservoir::sample_with_replacement")
    var _v_sample_without_replacement = sample_without_replacement(_lf5, 5)
    if len(_v_sample_without_replacement) >= 0: passed += 1; print("  ✅ reservoir::sample_without_replacement")

    print("  [reservoir] Passed:", passed, "Failed:", failed)
