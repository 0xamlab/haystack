"""bench_stat_tests.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from stat_tests import ks_test_2sample, ks_test_normal, t_test_1sample, t_test_2sample, chi_squared_test, anderson_darling_normal, shapiro_wilk_approx, pearson_r, spearman_r, CorrResult, TestResult
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

    var _keeper_ks_test_2sample = List[TestResult]()
    _keeper_ks_test_2sample.append(ks_test_2sample(_lf5, _lf5))
    var _acc_ks_test_2sample: Float64 = 0.0
    var _t0_ks_test_2sample = perf_counter_ns()
    for _ in range(N):
        _keeper_ks_test_2sample[0] = ks_test_2sample(_lf5, _lf5)
        _acc_ks_test_2sample += Float64(len(_keeper_ks_test_2sample))
    var _t1_ks_test_2sample = perf_counter_ns()
    var _ns_ks_test_2sample = Float64(_t1_ks_test_2sample - _t0_ks_test_2sample) / Float64(N)
    print("MOJO_TIMING stat_tests::ks_test_2sample", _ns_ks_test_2sample, _acc_ks_test_2sample)
    var _keeper_ks_test_normal = List[TestResult]()
    _keeper_ks_test_normal.append(ks_test_normal(_lf5))
    var _acc_ks_test_normal: Float64 = 0.0
    var _t0_ks_test_normal = perf_counter_ns()
    for _ in range(N):
        _keeper_ks_test_normal[0] = ks_test_normal(_lf5)
        _acc_ks_test_normal += Float64(len(_keeper_ks_test_normal))
    var _t1_ks_test_normal = perf_counter_ns()
    var _ns_ks_test_normal = Float64(_t1_ks_test_normal - _t0_ks_test_normal) / Float64(N)
    print("MOJO_TIMING stat_tests::ks_test_normal", _ns_ks_test_normal, _acc_ks_test_normal)
    var _keeper_t_test_1sample = List[TestResult]()
    _keeper_t_test_1sample.append(t_test_1sample(_lf5, 0.5))
    var _acc_t_test_1sample: Float64 = 0.0
    var _t0_t_test_1sample = perf_counter_ns()
    for _ in range(N):
        _keeper_t_test_1sample[0] = t_test_1sample(_lf5, 0.5)
        _acc_t_test_1sample += Float64(len(_keeper_t_test_1sample))
    var _t1_t_test_1sample = perf_counter_ns()
    var _ns_t_test_1sample = Float64(_t1_t_test_1sample - _t0_t_test_1sample) / Float64(N)
    print("MOJO_TIMING stat_tests::t_test_1sample", _ns_t_test_1sample, _acc_t_test_1sample)
    var _keeper_t_test_2sample = List[TestResult]()
    _keeper_t_test_2sample.append(t_test_2sample(_lf5, _lf5))
    var _acc_t_test_2sample: Float64 = 0.0
    var _t0_t_test_2sample = perf_counter_ns()
    for _ in range(N):
        _keeper_t_test_2sample[0] = t_test_2sample(_lf5, _lf5)
        _acc_t_test_2sample += Float64(len(_keeper_t_test_2sample))
    var _t1_t_test_2sample = perf_counter_ns()
    var _ns_t_test_2sample = Float64(_t1_t_test_2sample - _t0_t_test_2sample) / Float64(N)
    print("MOJO_TIMING stat_tests::t_test_2sample", _ns_t_test_2sample, _acc_t_test_2sample)
    var _keeper_chi_squared_test = List[TestResult]()
    _keeper_chi_squared_test.append(chi_squared_test(_lf5, _lf5))
    var _acc_chi_squared_test: Float64 = 0.0
    var _t0_chi_squared_test = perf_counter_ns()
    for _ in range(N):
        _keeper_chi_squared_test[0] = chi_squared_test(_lf5, _lf5)
        _acc_chi_squared_test += Float64(len(_keeper_chi_squared_test))
    var _t1_chi_squared_test = perf_counter_ns()
    var _ns_chi_squared_test = Float64(_t1_chi_squared_test - _t0_chi_squared_test) / Float64(N)
    print("MOJO_TIMING stat_tests::chi_squared_test", _ns_chi_squared_test, _acc_chi_squared_test)
    var _keeper_anderson_darling_normal = List[TestResult]()
    _keeper_anderson_darling_normal.append(anderson_darling_normal(_lf5))
    var _acc_anderson_darling_normal: Float64 = 0.0
    var _t0_anderson_darling_normal = perf_counter_ns()
    for _ in range(N):
        _keeper_anderson_darling_normal[0] = anderson_darling_normal(_lf5)
        _acc_anderson_darling_normal += Float64(len(_keeper_anderson_darling_normal))
    var _t1_anderson_darling_normal = perf_counter_ns()
    var _ns_anderson_darling_normal = Float64(_t1_anderson_darling_normal - _t0_anderson_darling_normal) / Float64(N)
    print("MOJO_TIMING stat_tests::anderson_darling_normal", _ns_anderson_darling_normal, _acc_anderson_darling_normal)
    var _keeper_shapiro_wilk_approx = List[TestResult]()
    _keeper_shapiro_wilk_approx.append(shapiro_wilk_approx(_lf5))
    var _acc_shapiro_wilk_approx: Float64 = 0.0
    var _t0_shapiro_wilk_approx = perf_counter_ns()
    for _ in range(N):
        _keeper_shapiro_wilk_approx[0] = shapiro_wilk_approx(_lf5)
        _acc_shapiro_wilk_approx += Float64(len(_keeper_shapiro_wilk_approx))
    var _t1_shapiro_wilk_approx = perf_counter_ns()
    var _ns_shapiro_wilk_approx = Float64(_t1_shapiro_wilk_approx - _t0_shapiro_wilk_approx) / Float64(N)
    print("MOJO_TIMING stat_tests::shapiro_wilk_approx", _ns_shapiro_wilk_approx, _acc_shapiro_wilk_approx)
    var _keeper_pearson_r = List[CorrResult]()
    _keeper_pearson_r.append(pearson_r(_lf5, _lf5))
    var _acc_pearson_r: Float64 = 0.0
    var _t0_pearson_r = perf_counter_ns()
    for _ in range(N):
        _keeper_pearson_r[0] = pearson_r(_lf5, _lf5)
        _acc_pearson_r += Float64(len(_keeper_pearson_r))
    var _t1_pearson_r = perf_counter_ns()
    var _ns_pearson_r = Float64(_t1_pearson_r - _t0_pearson_r) / Float64(N)
    print("MOJO_TIMING stat_tests::pearson_r", _ns_pearson_r, _acc_pearson_r)
    var _keeper_spearman_r = List[CorrResult]()
    _keeper_spearman_r.append(spearman_r(_lf5, _lf5))
    var _acc_spearman_r: Float64 = 0.0
    var _t0_spearman_r = perf_counter_ns()
    for _ in range(N):
        _keeper_spearman_r[0] = spearman_r(_lf5, _lf5)
        _acc_spearman_r += Float64(len(_keeper_spearman_r))
    var _t1_spearman_r = perf_counter_ns()
    var _ns_spearman_r = Float64(_t1_spearman_r - _t0_spearman_r) / Float64(N)
    print("MOJO_TIMING stat_tests::spearman_r", _ns_spearman_r, _acc_spearman_r)
