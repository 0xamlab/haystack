"""bench_stat_tests.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from stat_tests import ks_test_2sample, ks_test_normal, t_test_1sample, t_test_2sample, chi_squared_test, anderson_darling_normal, shapiro_wilk_approx, pearson_r, spearman_r, CorrResult, TestResult
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))


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
