"""bench_sketch.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from sketch import create_cms, cms_hash, create_hll, hll_hash, leading_zeros, CountMinSketch, HyperLogLog
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

    var _keeper_create_cms = List[CountMinSketch]()
    _keeper_create_cms.append(create_cms(5, 5))
    var _acc_create_cms: Float64 = 0.0
    var _t0_create_cms = perf_counter_ns()
    for _ in range(N):
        _keeper_create_cms[0] = create_cms(5, 5)
        _acc_create_cms += Float64(len(_keeper_create_cms))
    var _t1_create_cms = perf_counter_ns()
    var _ns_create_cms = Float64(_t1_create_cms - _t0_create_cms) / Float64(N)
    print("MOJO_TIMING sketch::create_cms", _ns_create_cms, _acc_create_cms)
    var _acc_cms_hash: Float64 = 0.0
    var _t0_cms_hash = perf_counter_ns()
    for _ in range(N):
        _acc_cms_hash += Float64(cms_hash(5, 5, 5))
    var _t1_cms_hash = perf_counter_ns()
    var _ns_cms_hash = Float64(_t1_cms_hash - _t0_cms_hash) / Float64(N)
    print("MOJO_TIMING sketch::cms_hash", _ns_cms_hash, _acc_cms_hash)
    var _keeper_create_hll = List[HyperLogLog]()
    _keeper_create_hll.append(create_hll(5))
    var _acc_create_hll: Float64 = 0.0
    var _t0_create_hll = perf_counter_ns()
    for _ in range(N):
        _keeper_create_hll[0] = create_hll(5)
        _acc_create_hll += Float64(len(_keeper_create_hll))
    var _t1_create_hll = perf_counter_ns()
    var _ns_create_hll = Float64(_t1_create_hll - _t0_create_hll) / Float64(N)
    print("MOJO_TIMING sketch::create_hll", _ns_create_hll, _acc_create_hll)
    var _acc_hll_hash: Float64 = 0.0
    var _t0_hll_hash = perf_counter_ns()
    for _ in range(N):
        _acc_hll_hash += Float64(hll_hash(5))
    var _t1_hll_hash = perf_counter_ns()
    var _ns_hll_hash = Float64(_t1_hll_hash - _t0_hll_hash) / Float64(N)
    print("MOJO_TIMING sketch::hll_hash", _ns_hll_hash, _acc_hll_hash)
    var _acc_leading_zeros: Float64 = 0.0
    var _t0_leading_zeros = perf_counter_ns()
    for _ in range(N):
        _acc_leading_zeros += Float64(leading_zeros(5, 5))
    var _t1_leading_zeros = perf_counter_ns()
    var _ns_leading_zeros = Float64(_t1_leading_zeros - _t0_leading_zeros) / Float64(N)
    print("MOJO_TIMING sketch::leading_zeros", _ns_leading_zeros, _acc_leading_zeros)
