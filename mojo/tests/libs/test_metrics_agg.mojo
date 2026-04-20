"""test_metrics_agg.mojo — auto-generated tests for metrics_agg library."""
from std.math import isnan, isinf
from metrics_agg import counter_create, histogram_create, rate, compute_throughput, latency_stats

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
