"""bench_metrics_agg.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from metrics_agg import counter_create, histogram_create, rate, compute_throughput, latency_stats, Histogram, MetricsCounter
from std.time import perf_counter_ns

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var _lub5 = List[UInt8]()
    _lub5.append(1); _lub5.append(2); _lub5.append(3)
    _lub5.append(4); _lub5.append(5)
    var _llf3 = List[List[Float64]]()
    _llf3.append(List[Float64]()); _llf3.append(List[Float64]()); _llf3.append(List[Float64]())
    _llf3[0].append(4.0); _llf3[0].append(0.0); _llf3[0].append(5.0)
    _llf3[1].append(0.0); _llf3[1].append(3.0); _llf3[1].append(4.0)
    _llf3[2].append(3.0); _llf3[2].append(4.0); _llf3[2].append(0.0)
    var N: Int = 10000

    var _keeper_counter_create = List[MetricsCounter]()
    _keeper_counter_create.append(counter_create("test"))
    var _acc_counter_create: Float64 = 0.0
    var _t0_counter_create = perf_counter_ns()
    for _ in range(N):
        _keeper_counter_create[0] = counter_create("test")
        _acc_counter_create += Float64(len(_keeper_counter_create))
    var _t1_counter_create = perf_counter_ns()
    var _ns_counter_create = Float64(_t1_counter_create - _t0_counter_create) / Float64(N)
    print("MOJO_TIMING metrics_agg::counter_create", _ns_counter_create, _acc_counter_create)
    var _keeper_histogram_create = List[Histogram]()
    _keeper_histogram_create.append(histogram_create("test", _lf5))
    var _acc_histogram_create: Float64 = 0.0
    var _t0_histogram_create = perf_counter_ns()
    for _ in range(N):
        _keeper_histogram_create[0] = histogram_create("test", _lf5)
        _acc_histogram_create += Float64(len(_keeper_histogram_create))
    var _t1_histogram_create = perf_counter_ns()
    var _ns_histogram_create = Float64(_t1_histogram_create - _t0_histogram_create) / Float64(N)
    print("MOJO_TIMING metrics_agg::histogram_create", _ns_histogram_create, _acc_histogram_create)
    var _acc_rate: Float64 = 0.0
    var _t0_rate = perf_counter_ns()
    for _ in range(N):
        _acc_rate += rate(_lf5, 0.5)
    var _t1_rate = perf_counter_ns()
    var _ns_rate = Float64(_t1_rate - _t0_rate) / Float64(N)
    print("MOJO_TIMING metrics_agg::rate", _ns_rate, _acc_rate)
    var _acc_compute_throughput: Float64 = 0.0
    var _t0_compute_throughput = perf_counter_ns()
    for _ in range(N):
        _acc_compute_throughput += compute_throughput(5, 0.5)
    var _t1_compute_throughput = perf_counter_ns()
    var _ns_compute_throughput = Float64(_t1_compute_throughput - _t0_compute_throughput) / Float64(N)
    print("MOJO_TIMING metrics_agg::compute_throughput", _ns_compute_throughput, _acc_compute_throughput)
    var _acc_latency_stats: Float64 = 0.0
    var _t0_latency_stats = perf_counter_ns()
    for _ in range(N):
        var _r_latency_stats = latency_stats(_lf5)
        _acc_latency_stats += Float64(len(_r_latency_stats))
    var _t1_latency_stats = perf_counter_ns()
    var _ns_latency_stats = Float64(_t1_latency_stats - _t0_latency_stats) / Float64(N)
    print("MOJO_TIMING metrics_agg::latency_stats", _ns_latency_stats, _acc_latency_stats)
