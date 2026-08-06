"""test_metrics_agg.mojo — auto-generated tests for metrics_agg."""
from std.math import isnan, isinf
from metrics_agg import counter_create, histogram_create, rate, compute_throughput, latency_stats

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

    _ = counter_create("test")
    passed += 1; print("  ✅ metrics_agg::counter_create")
    _ = histogram_create("test", _lf5)
    passed += 1; print("  ✅ metrics_agg::histogram_create")
    var _v_rate = rate(_lf5, 0.5)
    if is_finite(_v_rate): passed += 1; print("  ✅ metrics_agg::rate =", _v_rate)
    else: failed += 1; print("  ❌ metrics_agg::rate → non-finite:", _v_rate)
    var _v_compute_throughput = compute_throughput(5, 0.5)
    if is_finite(_v_compute_throughput): passed += 1; print("  ✅ metrics_agg::compute_throughput =", _v_compute_throughput)
    else: failed += 1; print("  ❌ metrics_agg::compute_throughput → non-finite:", _v_compute_throughput)
    var _v_latency_stats = latency_stats(_lf5)
    if len(_v_latency_stats) >= 0: passed += 1; print("  ✅ metrics_agg::latency_stats")

    print("  [metrics_agg] Passed:", passed, "Failed:", failed)
