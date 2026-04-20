"""bench_correlation.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from correlation import cholesky_lower, sample_correlated_normal, probit, icdf
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

    var _acc_cholesky_lower: Float64 = 0.0
    var _t0_cholesky_lower = perf_counter_ns()
    for _ in range(N):
        var _r_cholesky_lower = cholesky_lower([[1.0,0.0,0.0],[0.0,1.0,0.0],[0.0,0.0,1.0]], 3)
        _acc_cholesky_lower += Float64(len(_r_cholesky_lower))
    var _t1_cholesky_lower = perf_counter_ns()
    var _ns_cholesky_lower = Float64(_t1_cholesky_lower - _t0_cholesky_lower) / Float64(N)
    print("MOJO_TIMING correlation::cholesky_lower", _ns_cholesky_lower, _acc_cholesky_lower)
    var _acc_sample_correlated_normal: Float64 = 0.0
    var _t0_sample_correlated_normal = perf_counter_ns()
    for _ in range(N):
        var _r_sample_correlated_normal = sample_correlated_normal([[1.0,0.0,0.0],[0.0,1.0,0.0],[0.0,0.0,1.0]], 3)
        _acc_sample_correlated_normal += Float64(len(_r_sample_correlated_normal))
    var _t1_sample_correlated_normal = perf_counter_ns()
    var _ns_sample_correlated_normal = Float64(_t1_sample_correlated_normal - _t0_sample_correlated_normal) / Float64(N)
    print("MOJO_TIMING correlation::sample_correlated_normal", _ns_sample_correlated_normal, _acc_sample_correlated_normal)
    var _acc_probit: Float64 = 0.0
    var _t0_probit = perf_counter_ns()
    for _ in range(N):
        _acc_probit += probit(0.5)
    var _t1_probit = perf_counter_ns()
    var _ns_probit = Float64(_t1_probit - _t0_probit) / Float64(N)
    print("MOJO_TIMING correlation::probit", _ns_probit, _acc_probit)
    var _acc_icdf: Float64 = 0.0
    var _t0_icdf = perf_counter_ns()
    for _ in range(N):
        _acc_icdf += icdf(0.5, 5, 0.5, 0.5, 0.5)
    var _t1_icdf = perf_counter_ns()
    var _ns_icdf = Float64(_t1_icdf - _t0_icdf) / Float64(N)
    print("MOJO_TIMING correlation::icdf", _ns_icdf, _acc_icdf)
