"""bench_hypothesis.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from hypothesis import rank_data, mann_whitney_u, wilcoxon_signed_rank, kruskal_wallis, fisher_exact_2x2, sign_test
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

    var _acc_rank_data: Float64 = 0.0
    var _t0_rank_data = perf_counter_ns()
    for _ in range(N):
        var _r_rank_data = rank_data(_lf5)
        _acc_rank_data += Float64(len(_r_rank_data))
    var _t1_rank_data = perf_counter_ns()
    var _ns_rank_data = Float64(_t1_rank_data - _t0_rank_data) / Float64(N)
    print("MOJO_TIMING hypothesis::rank_data", _ns_rank_data, _acc_rank_data)
    var _result_rank_data = rank_data(_lf5)
    var _summary_rank_data = _summary_list_float64(_result_rank_data)
    print("MOJO_RESULT hypothesis::rank_data", _summary_rank_data)
    var _acc_mann_whitney_u: Float64 = 0.0
    var _t0_mann_whitney_u = perf_counter_ns()
    for _ in range(N):
        var _r_mann_whitney_u = mann_whitney_u(_lf5, _lf5)
        _acc_mann_whitney_u += Float64(len(_r_mann_whitney_u))
    var _t1_mann_whitney_u = perf_counter_ns()
    var _ns_mann_whitney_u = Float64(_t1_mann_whitney_u - _t0_mann_whitney_u) / Float64(N)
    print("MOJO_TIMING hypothesis::mann_whitney_u", _ns_mann_whitney_u, _acc_mann_whitney_u)
    var _result_mann_whitney_u = mann_whitney_u(_lf5, _lf5)
    var _summary_mann_whitney_u = _summary_list_float64(_result_mann_whitney_u)
    print("MOJO_RESULT hypothesis::mann_whitney_u", _summary_mann_whitney_u)
    var _acc_wilcoxon_signed_rank: Float64 = 0.0
    var _t0_wilcoxon_signed_rank = perf_counter_ns()
    for _ in range(N):
        var _r_wilcoxon_signed_rank = wilcoxon_signed_rank(_lf5, _lf5)
        _acc_wilcoxon_signed_rank += Float64(len(_r_wilcoxon_signed_rank))
    var _t1_wilcoxon_signed_rank = perf_counter_ns()
    var _ns_wilcoxon_signed_rank = Float64(_t1_wilcoxon_signed_rank - _t0_wilcoxon_signed_rank) / Float64(N)
    print("MOJO_TIMING hypothesis::wilcoxon_signed_rank", _ns_wilcoxon_signed_rank, _acc_wilcoxon_signed_rank)
    var _result_wilcoxon_signed_rank = wilcoxon_signed_rank(_lf5, _lf5)
    var _summary_wilcoxon_signed_rank = _summary_list_float64(_result_wilcoxon_signed_rank)
    print("MOJO_RESULT hypothesis::wilcoxon_signed_rank", _summary_wilcoxon_signed_rank)
    var _acc_kruskal_wallis: Float64 = 0.0
    var _t0_kruskal_wallis = perf_counter_ns()
    for _ in range(N):
        var _r_kruskal_wallis = kruskal_wallis([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_kruskal_wallis += Float64(len(_r_kruskal_wallis))
    var _t1_kruskal_wallis = perf_counter_ns()
    var _ns_kruskal_wallis = Float64(_t1_kruskal_wallis - _t0_kruskal_wallis) / Float64(N)
    print("MOJO_TIMING hypothesis::kruskal_wallis", _ns_kruskal_wallis, _acc_kruskal_wallis)
    var _result_kruskal_wallis = kruskal_wallis([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_kruskal_wallis = _summary_list_float64(_result_kruskal_wallis)
    print("MOJO_RESULT hypothesis::kruskal_wallis", _summary_kruskal_wallis)
    var _acc_fisher_exact_2x2: Float64 = 0.0
    var _t0_fisher_exact_2x2 = perf_counter_ns()
    for _ in range(N):
        _acc_fisher_exact_2x2 += fisher_exact_2x2(5, 5, 5, 5)
    var _t1_fisher_exact_2x2 = perf_counter_ns()
    var _ns_fisher_exact_2x2 = Float64(_t1_fisher_exact_2x2 - _t0_fisher_exact_2x2) / Float64(N)
    print("MOJO_TIMING hypothesis::fisher_exact_2x2", _ns_fisher_exact_2x2, _acc_fisher_exact_2x2)
    var _result_fisher_exact_2x2 = fisher_exact_2x2(5, 5, 5, 5)
    var _summary_fisher_exact_2x2 = _summary_float64(_result_fisher_exact_2x2)
    print("MOJO_RESULT hypothesis::fisher_exact_2x2", _summary_fisher_exact_2x2)
    var _acc_sign_test: Float64 = 0.0
    var _t0_sign_test = perf_counter_ns()
    for _ in range(N):
        var _r_sign_test = sign_test(_lf5, 0.5)
        _acc_sign_test += Float64(len(_r_sign_test))
    var _t1_sign_test = perf_counter_ns()
    var _ns_sign_test = Float64(_t1_sign_test - _t0_sign_test) / Float64(N)
    print("MOJO_TIMING hypothesis::sign_test", _ns_sign_test, _acc_sign_test)
    var _result_sign_test = sign_test(_lf5, 0.5)
    var _summary_sign_test = _summary_list_float64(_result_sign_test)
    print("MOJO_RESULT hypothesis::sign_test", _summary_sign_test)
