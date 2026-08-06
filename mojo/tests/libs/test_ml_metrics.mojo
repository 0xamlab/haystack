"""test_ml_metrics.mojo — auto-generated tests for ml.metrics."""
from std.math import isnan, isinf
from ml.metrics import accuracy, mse, rmse, mae, r2_score, confusion_matrix, precision_recall_f1

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

    var _v_accuracy = accuracy(_lf5, _lf5)
    if is_finite(_v_accuracy): passed += 1; print("  ✅ ml.metrics::accuracy =", _v_accuracy)
    else: failed += 1; print("  ❌ ml.metrics::accuracy → non-finite:", _v_accuracy)
    var _v_mse = mse(_lf5, _lf5)
    if is_finite(_v_mse): passed += 1; print("  ✅ ml.metrics::mse =", _v_mse)
    else: failed += 1; print("  ❌ ml.metrics::mse → non-finite:", _v_mse)
    var _v_rmse = rmse(_lf5, _lf5)
    if is_finite(_v_rmse): passed += 1; print("  ✅ ml.metrics::rmse =", _v_rmse)
    else: failed += 1; print("  ❌ ml.metrics::rmse → non-finite:", _v_rmse)
    var _v_mae = mae(_lf5, _lf5)
    if is_finite(_v_mae): passed += 1; print("  ✅ ml.metrics::mae =", _v_mae)
    else: failed += 1; print("  ❌ ml.metrics::mae → non-finite:", _v_mae)
    var _v_r2_score = r2_score(_lf5, _lf5)
    if is_finite(_v_r2_score): passed += 1; print("  ✅ ml.metrics::r2_score =", _v_r2_score)
    else: failed += 1; print("  ❌ ml.metrics::r2_score → non-finite:", _v_r2_score)
    _ = confusion_matrix(_li5, _li5, 5)
    passed += 1; print("  ✅ ml.metrics::confusion_matrix")
    _ = precision_recall_f1(_li5, _li5)
    passed += 1; print("  ✅ ml.metrics::precision_recall_f1")

    print("  [ml.metrics] Passed:", passed, "Failed:", failed)
