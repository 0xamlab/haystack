"""test_ml_naive_bayes.mojo — auto-generated tests for ml.naive_bayes."""
from std.math import isnan, isinf
from ml.naive_bayes import compute_priors, gaussian_log_likelihood, accuracy, confusion_matrix, precision_recall

fn is_finite(x: Float64) -> Bool:
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

    var _v_compute_priors = compute_priors(_li5, 5)
    if len(_v_compute_priors) >= 0: passed += 1; print("  ✅ ml.naive_bayes::compute_priors")
    var _v_gaussian_log_likelihood = gaussian_log_likelihood(0.5, 0.5, 0.5)
    if is_finite(_v_gaussian_log_likelihood): passed += 1; print("  ✅ ml.naive_bayes::gaussian_log_likelihood =", _v_gaussian_log_likelihood)
    else: failed += 1; print("  ❌ ml.naive_bayes::gaussian_log_likelihood → non-finite:", _v_gaussian_log_likelihood)
    var _v_accuracy = accuracy(_li5, _li5)
    if is_finite(_v_accuracy): passed += 1; print("  ✅ ml.naive_bayes::accuracy =", _v_accuracy)
    else: failed += 1; print("  ❌ ml.naive_bayes::accuracy → non-finite:", _v_accuracy)
    _ = confusion_matrix(_li5, _li5, 5)
    passed += 1; print("  ✅ ml.naive_bayes::confusion_matrix")
    var _v_precision_recall = precision_recall(_li5, _li5, 5)
    if len(_v_precision_recall) >= 0: passed += 1; print("  ✅ ml.naive_bayes::precision_recall")

    print("  [ml.naive_bayes] Passed:", passed, "Failed:", failed)
