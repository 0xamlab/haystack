"""bench_hypothesis.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from hypothesis import rank_data, mann_whitney_u, wilcoxon_signed_rank, kruskal_wallis, fisher_exact_2x2, sign_test
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

    var _acc_rank_data: Float64 = 0.0
    var _t0_rank_data = perf_counter_ns()
    for _ in range(N):
        var _r_rank_data = rank_data(_lf5)
        _acc_rank_data += Float64(len(_r_rank_data))
    var _t1_rank_data = perf_counter_ns()
    var _ns_rank_data = Float64(_t1_rank_data - _t0_rank_data) / Float64(N)
    print("MOJO_TIMING hypothesis::rank_data", _ns_rank_data, _acc_rank_data)
    var _acc_mann_whitney_u: Float64 = 0.0
    var _t0_mann_whitney_u = perf_counter_ns()
    for _ in range(N):
        var _r_mann_whitney_u = mann_whitney_u(_lf5, _lf5)
        _acc_mann_whitney_u += Float64(len(_r_mann_whitney_u))
    var _t1_mann_whitney_u = perf_counter_ns()
    var _ns_mann_whitney_u = Float64(_t1_mann_whitney_u - _t0_mann_whitney_u) / Float64(N)
    print("MOJO_TIMING hypothesis::mann_whitney_u", _ns_mann_whitney_u, _acc_mann_whitney_u)
    var _acc_wilcoxon_signed_rank: Float64 = 0.0
    var _t0_wilcoxon_signed_rank = perf_counter_ns()
    for _ in range(N):
        var _r_wilcoxon_signed_rank = wilcoxon_signed_rank(_lf5, _lf5)
        _acc_wilcoxon_signed_rank += Float64(len(_r_wilcoxon_signed_rank))
    var _t1_wilcoxon_signed_rank = perf_counter_ns()
    var _ns_wilcoxon_signed_rank = Float64(_t1_wilcoxon_signed_rank - _t0_wilcoxon_signed_rank) / Float64(N)
    print("MOJO_TIMING hypothesis::wilcoxon_signed_rank", _ns_wilcoxon_signed_rank, _acc_wilcoxon_signed_rank)
    var _acc_kruskal_wallis: Float64 = 0.0
    var _t0_kruskal_wallis = perf_counter_ns()
    for _ in range(N):
        var _r_kruskal_wallis = kruskal_wallis([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_kruskal_wallis += Float64(len(_r_kruskal_wallis))
    var _t1_kruskal_wallis = perf_counter_ns()
    var _ns_kruskal_wallis = Float64(_t1_kruskal_wallis - _t0_kruskal_wallis) / Float64(N)
    print("MOJO_TIMING hypothesis::kruskal_wallis", _ns_kruskal_wallis, _acc_kruskal_wallis)
    var _acc_fisher_exact_2x2: Float64 = 0.0
    var _t0_fisher_exact_2x2 = perf_counter_ns()
    for _ in range(N):
        _acc_fisher_exact_2x2 += fisher_exact_2x2(5, 5, 5, 5)
    var _t1_fisher_exact_2x2 = perf_counter_ns()
    var _ns_fisher_exact_2x2 = Float64(_t1_fisher_exact_2x2 - _t0_fisher_exact_2x2) / Float64(N)
    print("MOJO_TIMING hypothesis::fisher_exact_2x2", _ns_fisher_exact_2x2, _acc_fisher_exact_2x2)
    var _acc_sign_test: Float64 = 0.0
    var _t0_sign_test = perf_counter_ns()
    for _ in range(N):
        var _r_sign_test = sign_test(_lf5, 0.5)
        _acc_sign_test += Float64(len(_r_sign_test))
    var _t1_sign_test = perf_counter_ns()
    var _ns_sign_test = Float64(_t1_sign_test - _t0_sign_test) / Float64(N)
    print("MOJO_TIMING hypothesis::sign_test", _ns_sign_test, _acc_sign_test)
