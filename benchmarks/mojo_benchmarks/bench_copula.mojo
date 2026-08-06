"""bench_copula.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from copula import norm_cdf_approx, norm_ppf_approx, gaussian_copula_sample, rank_correlation, kendall_tau
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

    var _acc_norm_cdf_approx: Float64 = 0.0
    var _t0_norm_cdf_approx = perf_counter_ns()
    for _ in range(N):
        _acc_norm_cdf_approx += norm_cdf_approx(0.5)
    var _t1_norm_cdf_approx = perf_counter_ns()
    var _ns_norm_cdf_approx = Float64(_t1_norm_cdf_approx - _t0_norm_cdf_approx) / Float64(N)
    print("MOJO_TIMING copula::norm_cdf_approx", _ns_norm_cdf_approx, _acc_norm_cdf_approx)
    var _result_norm_cdf_approx = norm_cdf_approx(0.5)
    var _summary_norm_cdf_approx = _summary_float64(_result_norm_cdf_approx)
    print("MOJO_RESULT copula::norm_cdf_approx", _summary_norm_cdf_approx)
    var _acc_norm_ppf_approx: Float64 = 0.0
    var _t0_norm_ppf_approx = perf_counter_ns()
    for _ in range(N):
        _acc_norm_ppf_approx += norm_ppf_approx(0.5)
    var _t1_norm_ppf_approx = perf_counter_ns()
    var _ns_norm_ppf_approx = Float64(_t1_norm_ppf_approx - _t0_norm_ppf_approx) / Float64(N)
    print("MOJO_TIMING copula::norm_ppf_approx", _ns_norm_ppf_approx, _acc_norm_ppf_approx)
    var _result_norm_ppf_approx = norm_ppf_approx(0.5)
    var _summary_norm_ppf_approx = _summary_float64(_result_norm_ppf_approx)
    print("MOJO_RESULT copula::norm_ppf_approx", _summary_norm_ppf_approx)
    var _acc_gaussian_copula_sample: Float64 = 0.0
    var _t0_gaussian_copula_sample = perf_counter_ns()
    for _ in range(N):
        var _r_gaussian_copula_sample = gaussian_copula_sample(5, 0.5)
        _acc_gaussian_copula_sample += Float64(len(_r_gaussian_copula_sample))
    var _t1_gaussian_copula_sample = perf_counter_ns()
    var _ns_gaussian_copula_sample = Float64(_t1_gaussian_copula_sample - _t0_gaussian_copula_sample) / Float64(N)
    print("MOJO_TIMING copula::gaussian_copula_sample", _ns_gaussian_copula_sample, _acc_gaussian_copula_sample)
    var _result_gaussian_copula_sample = gaussian_copula_sample(5, 0.5)
    var _summary_gaussian_copula_sample = _summary_list_list_float64(_result_gaussian_copula_sample)
    print("MOJO_RESULT copula::gaussian_copula_sample", _summary_gaussian_copula_sample)
    var _acc_rank_correlation: Float64 = 0.0
    var _t0_rank_correlation = perf_counter_ns()
    for _ in range(N):
        _acc_rank_correlation += rank_correlation(_lf5, _lf5)
    var _t1_rank_correlation = perf_counter_ns()
    var _ns_rank_correlation = Float64(_t1_rank_correlation - _t0_rank_correlation) / Float64(N)
    print("MOJO_TIMING copula::rank_correlation", _ns_rank_correlation, _acc_rank_correlation)
    var _result_rank_correlation = rank_correlation(_lf5, _lf5)
    var _summary_rank_correlation = _summary_float64(_result_rank_correlation)
    print("MOJO_RESULT copula::rank_correlation", _summary_rank_correlation)
    var _acc_kendall_tau: Float64 = 0.0
    var _t0_kendall_tau = perf_counter_ns()
    for _ in range(N):
        _acc_kendall_tau += kendall_tau(_lf5, _lf5)
    var _t1_kendall_tau = perf_counter_ns()
    var _ns_kendall_tau = Float64(_t1_kendall_tau - _t0_kendall_tau) / Float64(N)
    print("MOJO_TIMING copula::kendall_tau", _ns_kendall_tau, _acc_kendall_tau)
    var _result_kendall_tau = kendall_tau(_lf5, _lf5)
    var _summary_kendall_tau = _summary_float64(_result_kendall_tau)
    print("MOJO_RESULT copula::kendall_tau", _summary_kendall_tau)
