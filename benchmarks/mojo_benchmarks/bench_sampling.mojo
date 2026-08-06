"""bench_sampling.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from sampling import halton_sequence, halton_2d, stratified_sample_1d, latin_hypercube_sample, sobol_like_2d, discrepancy_l2_star
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

    var _acc_halton_sequence: Float64 = 0.0
    var _t0_halton_sequence = perf_counter_ns()
    for _ in range(N):
        var _r_halton_sequence = halton_sequence(5, 5)
        _acc_halton_sequence += Float64(len(_r_halton_sequence))
    var _t1_halton_sequence = perf_counter_ns()
    var _ns_halton_sequence = Float64(_t1_halton_sequence - _t0_halton_sequence) / Float64(N)
    print("MOJO_TIMING sampling::halton_sequence", _ns_halton_sequence, _acc_halton_sequence)
    var _result_halton_sequence = halton_sequence(5, 5)
    var _summary_halton_sequence = _summary_list_float64(_result_halton_sequence)
    print("MOJO_RESULT sampling::halton_sequence", _summary_halton_sequence)
    var _acc_halton_2d: Float64 = 0.0
    var _t0_halton_2d = perf_counter_ns()
    for _ in range(N):
        var _r_halton_2d = halton_2d(5)
        _acc_halton_2d += Float64(len(_r_halton_2d))
    var _t1_halton_2d = perf_counter_ns()
    var _ns_halton_2d = Float64(_t1_halton_2d - _t0_halton_2d) / Float64(N)
    print("MOJO_TIMING sampling::halton_2d", _ns_halton_2d, _acc_halton_2d)
    var _result_halton_2d = halton_2d(5)
    var _summary_halton_2d = _summary_list_list_float64(_result_halton_2d)
    print("MOJO_RESULT sampling::halton_2d", _summary_halton_2d)
    var _acc_stratified_sample_1d: Float64 = 0.0
    var _t0_stratified_sample_1d = perf_counter_ns()
    for _ in range(N):
        var _r_stratified_sample_1d = stratified_sample_1d(5)
        _acc_stratified_sample_1d += Float64(len(_r_stratified_sample_1d))
    var _t1_stratified_sample_1d = perf_counter_ns()
    var _ns_stratified_sample_1d = Float64(_t1_stratified_sample_1d - _t0_stratified_sample_1d) / Float64(N)
    print("MOJO_TIMING sampling::stratified_sample_1d", _ns_stratified_sample_1d, _acc_stratified_sample_1d)
    var _result_stratified_sample_1d = stratified_sample_1d(5)
    var _summary_stratified_sample_1d = _summary_list_float64(_result_stratified_sample_1d)
    print("MOJO_RESULT sampling::stratified_sample_1d", _summary_stratified_sample_1d)
    var _acc_latin_hypercube_sample: Float64 = 0.0
    var _t0_latin_hypercube_sample = perf_counter_ns()
    for _ in range(N):
        var _r_latin_hypercube_sample = latin_hypercube_sample(5, 5)
        _acc_latin_hypercube_sample += Float64(len(_r_latin_hypercube_sample))
    var _t1_latin_hypercube_sample = perf_counter_ns()
    var _ns_latin_hypercube_sample = Float64(_t1_latin_hypercube_sample - _t0_latin_hypercube_sample) / Float64(N)
    print("MOJO_TIMING sampling::latin_hypercube_sample", _ns_latin_hypercube_sample, _acc_latin_hypercube_sample)
    var _result_latin_hypercube_sample = latin_hypercube_sample(5, 5)
    var _summary_latin_hypercube_sample = _summary_list_list_float64(_result_latin_hypercube_sample)
    print("MOJO_RESULT sampling::latin_hypercube_sample", _summary_latin_hypercube_sample)
    var _acc_sobol_like_2d: Float64 = 0.0
    var _t0_sobol_like_2d = perf_counter_ns()
    for _ in range(N):
        var _r_sobol_like_2d = sobol_like_2d(5)
        _acc_sobol_like_2d += Float64(len(_r_sobol_like_2d))
    var _t1_sobol_like_2d = perf_counter_ns()
    var _ns_sobol_like_2d = Float64(_t1_sobol_like_2d - _t0_sobol_like_2d) / Float64(N)
    print("MOJO_TIMING sampling::sobol_like_2d", _ns_sobol_like_2d, _acc_sobol_like_2d)
    var _result_sobol_like_2d = sobol_like_2d(5)
    var _summary_sobol_like_2d = _summary_list_list_float64(_result_sobol_like_2d)
    print("MOJO_RESULT sampling::sobol_like_2d", _summary_sobol_like_2d)
    var _acc_discrepancy_l2_star: Float64 = 0.0
    var _t0_discrepancy_l2_star = perf_counter_ns()
    for _ in range(N):
        _acc_discrepancy_l2_star += discrepancy_l2_star([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_discrepancy_l2_star = perf_counter_ns()
    var _ns_discrepancy_l2_star = Float64(_t1_discrepancy_l2_star - _t0_discrepancy_l2_star) / Float64(N)
    print("MOJO_TIMING sampling::discrepancy_l2_star", _ns_discrepancy_l2_star, _acc_discrepancy_l2_star)
    var _result_discrepancy_l2_star = discrepancy_l2_star([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_discrepancy_l2_star = _summary_float64(_result_discrepancy_l2_star)
    print("MOJO_RESULT sampling::discrepancy_l2_star", _summary_discrepancy_l2_star)
