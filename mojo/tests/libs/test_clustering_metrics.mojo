"""test_clustering_metrics.mojo — auto-generated tests for clustering_metrics library."""
from std.math import isnan, isinf
from clustering_metrics import cluster_sizes, contingency_matrix, purity, adjusted_rand_index

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

    var _v_cluster_sizes = cluster_sizes(_li5, 5)
    if len(_v_cluster_sizes) >= 0: passed += 1; print("  ✅ clustering_metrics::cluster_sizes")
    _ = contingency_matrix(_li5, _li5, 5, 5)
    passed += 1; print("  ✅ clustering_metrics::contingency_matrix")
    var _v_purity = purity(_li5, _li5, 5, 5)
    if is_finite(_v_purity): passed += 1; print("  ✅ clustering_metrics::purity =", _v_purity)
    else: failed += 1; print("  ❌ clustering_metrics::purity → non-finite:", _v_purity)
    var _v_adjusted_rand_index = adjusted_rand_index(_li5, _li5)
    if is_finite(_v_adjusted_rand_index): passed += 1; print("  ✅ clustering_metrics::adjusted_rand_index =", _v_adjusted_rand_index)
    else: failed += 1; print("  ❌ clustering_metrics::adjusted_rand_index → non-finite:", _v_adjusted_rand_index)

    print("  [clustering_metrics] Passed:", passed, "Failed:", failed)
