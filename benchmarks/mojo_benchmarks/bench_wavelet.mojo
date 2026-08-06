"""bench_wavelet.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from wavelet import haar_forward, haar_inverse, haar_multilevel, haar_multilevel_inverse, threshold_hard, threshold_soft, denoise_haar, energy_ratio, detail_coefficients, approx_coefficients
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

    var _acc_haar_forward: Float64 = 0.0
    var _t0_haar_forward = perf_counter_ns()
    for _ in range(N):
        var _r_haar_forward = haar_forward(_lf5)
        _acc_haar_forward += Float64(len(_r_haar_forward))
    var _t1_haar_forward = perf_counter_ns()
    var _ns_haar_forward = Float64(_t1_haar_forward - _t0_haar_forward) / Float64(N)
    print("MOJO_TIMING wavelet::haar_forward", _ns_haar_forward, _acc_haar_forward)
    var _result_haar_forward = haar_forward(_lf5)
    var _summary_haar_forward = _summary_list_float64(_result_haar_forward)
    print("MOJO_RESULT wavelet::haar_forward", _summary_haar_forward)
    var _acc_haar_inverse: Float64 = 0.0
    var _t0_haar_inverse = perf_counter_ns()
    for _ in range(N):
        var _r_haar_inverse = haar_inverse(_lf5)
        _acc_haar_inverse += Float64(len(_r_haar_inverse))
    var _t1_haar_inverse = perf_counter_ns()
    var _ns_haar_inverse = Float64(_t1_haar_inverse - _t0_haar_inverse) / Float64(N)
    print("MOJO_TIMING wavelet::haar_inverse", _ns_haar_inverse, _acc_haar_inverse)
    var _result_haar_inverse = haar_inverse(_lf5)
    var _summary_haar_inverse = _summary_list_float64(_result_haar_inverse)
    print("MOJO_RESULT wavelet::haar_inverse", _summary_haar_inverse)
    var _acc_haar_multilevel: Float64 = 0.0
    var _t0_haar_multilevel = perf_counter_ns()
    for _ in range(N):
        var _r_haar_multilevel = haar_multilevel(_lf5, 5)
        _acc_haar_multilevel += Float64(len(_r_haar_multilevel))
    var _t1_haar_multilevel = perf_counter_ns()
    var _ns_haar_multilevel = Float64(_t1_haar_multilevel - _t0_haar_multilevel) / Float64(N)
    print("MOJO_TIMING wavelet::haar_multilevel", _ns_haar_multilevel, _acc_haar_multilevel)
    var _result_haar_multilevel = haar_multilevel(_lf5, 5)
    var _summary_haar_multilevel = _summary_list_float64(_result_haar_multilevel)
    print("MOJO_RESULT wavelet::haar_multilevel", _summary_haar_multilevel)
    var _acc_haar_multilevel_inverse: Float64 = 0.0
    var _t0_haar_multilevel_inverse = perf_counter_ns()
    for _ in range(N):
        var _r_haar_multilevel_inverse = haar_multilevel_inverse(_lf5, 5)
        _acc_haar_multilevel_inverse += Float64(len(_r_haar_multilevel_inverse))
    var _t1_haar_multilevel_inverse = perf_counter_ns()
    var _ns_haar_multilevel_inverse = Float64(_t1_haar_multilevel_inverse - _t0_haar_multilevel_inverse) / Float64(N)
    print("MOJO_TIMING wavelet::haar_multilevel_inverse", _ns_haar_multilevel_inverse, _acc_haar_multilevel_inverse)
    var _result_haar_multilevel_inverse = haar_multilevel_inverse(_lf5, 5)
    var _summary_haar_multilevel_inverse = _summary_list_float64(_result_haar_multilevel_inverse)
    print("MOJO_RESULT wavelet::haar_multilevel_inverse", _summary_haar_multilevel_inverse)
    var _acc_threshold_hard: Float64 = 0.0
    var _t0_threshold_hard = perf_counter_ns()
    for _ in range(N):
        var _r_threshold_hard = threshold_hard(_lf5, 0.5)
        _acc_threshold_hard += Float64(len(_r_threshold_hard))
    var _t1_threshold_hard = perf_counter_ns()
    var _ns_threshold_hard = Float64(_t1_threshold_hard - _t0_threshold_hard) / Float64(N)
    print("MOJO_TIMING wavelet::threshold_hard", _ns_threshold_hard, _acc_threshold_hard)
    var _result_threshold_hard = threshold_hard(_lf5, 0.5)
    var _summary_threshold_hard = _summary_list_float64(_result_threshold_hard)
    print("MOJO_RESULT wavelet::threshold_hard", _summary_threshold_hard)
    var _acc_threshold_soft: Float64 = 0.0
    var _t0_threshold_soft = perf_counter_ns()
    for _ in range(N):
        var _r_threshold_soft = threshold_soft(_lf5, 0.5)
        _acc_threshold_soft += Float64(len(_r_threshold_soft))
    var _t1_threshold_soft = perf_counter_ns()
    var _ns_threshold_soft = Float64(_t1_threshold_soft - _t0_threshold_soft) / Float64(N)
    print("MOJO_TIMING wavelet::threshold_soft", _ns_threshold_soft, _acc_threshold_soft)
    var _result_threshold_soft = threshold_soft(_lf5, 0.5)
    var _summary_threshold_soft = _summary_list_float64(_result_threshold_soft)
    print("MOJO_RESULT wavelet::threshold_soft", _summary_threshold_soft)
    var _acc_denoise_haar: Float64 = 0.0
    var _t0_denoise_haar = perf_counter_ns()
    for _ in range(N):
        var _r_denoise_haar = denoise_haar(_lf5, 0.5, 5)
        _acc_denoise_haar += Float64(len(_r_denoise_haar))
    var _t1_denoise_haar = perf_counter_ns()
    var _ns_denoise_haar = Float64(_t1_denoise_haar - _t0_denoise_haar) / Float64(N)
    print("MOJO_TIMING wavelet::denoise_haar", _ns_denoise_haar, _acc_denoise_haar)
    var _result_denoise_haar = denoise_haar(_lf5, 0.5, 5)
    var _summary_denoise_haar = _summary_list_float64(_result_denoise_haar)
    print("MOJO_RESULT wavelet::denoise_haar", _summary_denoise_haar)
    var _acc_energy_ratio: Float64 = 0.0
    var _t0_energy_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_energy_ratio += energy_ratio(_lf5)
    var _t1_energy_ratio = perf_counter_ns()
    var _ns_energy_ratio = Float64(_t1_energy_ratio - _t0_energy_ratio) / Float64(N)
    print("MOJO_TIMING wavelet::energy_ratio", _ns_energy_ratio, _acc_energy_ratio)
    var _result_energy_ratio = energy_ratio(_lf5)
    var _summary_energy_ratio = _summary_float64(_result_energy_ratio)
    print("MOJO_RESULT wavelet::energy_ratio", _summary_energy_ratio)
    var _acc_detail_coefficients: Float64 = 0.0
    var _t0_detail_coefficients = perf_counter_ns()
    for _ in range(N):
        var _r_detail_coefficients = detail_coefficients(_lf5)
        _acc_detail_coefficients += Float64(len(_r_detail_coefficients))
    var _t1_detail_coefficients = perf_counter_ns()
    var _ns_detail_coefficients = Float64(_t1_detail_coefficients - _t0_detail_coefficients) / Float64(N)
    print("MOJO_TIMING wavelet::detail_coefficients", _ns_detail_coefficients, _acc_detail_coefficients)
    var _result_detail_coefficients = detail_coefficients(_lf5)
    var _summary_detail_coefficients = _summary_list_float64(_result_detail_coefficients)
    print("MOJO_RESULT wavelet::detail_coefficients", _summary_detail_coefficients)
    var _acc_approx_coefficients: Float64 = 0.0
    var _t0_approx_coefficients = perf_counter_ns()
    for _ in range(N):
        var _r_approx_coefficients = approx_coefficients(_lf5)
        _acc_approx_coefficients += Float64(len(_r_approx_coefficients))
    var _t1_approx_coefficients = perf_counter_ns()
    var _ns_approx_coefficients = Float64(_t1_approx_coefficients - _t0_approx_coefficients) / Float64(N)
    print("MOJO_TIMING wavelet::approx_coefficients", _ns_approx_coefficients, _acc_approx_coefficients)
    var _result_approx_coefficients = approx_coefficients(_lf5)
    var _summary_approx_coefficients = _summary_list_float64(_result_approx_coefficients)
    print("MOJO_RESULT wavelet::approx_coefficients", _summary_approx_coefficients)
