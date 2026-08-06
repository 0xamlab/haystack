"""bench_signal_dsp.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from signal.dsp import moving_average, exponential_moving_average, diff, cumsum, convolve, autocorrelation, detrend_linear, normalize_signal, zero_crossings, peak_detect
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

    var _acc_moving_average: Float64 = 0.0
    var _t0_moving_average = perf_counter_ns()
    for _ in range(N):
        var _r_moving_average = moving_average(_lf5, 5)
        _acc_moving_average += Float64(len(_r_moving_average))
    var _t1_moving_average = perf_counter_ns()
    var _ns_moving_average = Float64(_t1_moving_average - _t0_moving_average) / Float64(N)
    print("MOJO_TIMING signal_dsp::moving_average", _ns_moving_average, _acc_moving_average)
    var _result_moving_average = moving_average(_lf5, 5)
    var _summary_moving_average = _summary_list_float64(_result_moving_average)
    print("MOJO_RESULT signal_dsp::moving_average", _summary_moving_average)
    var _acc_exponential_moving_average: Float64 = 0.0
    var _t0_exponential_moving_average = perf_counter_ns()
    for _ in range(N):
        var _r_exponential_moving_average = exponential_moving_average(_lf5, 0.5)
        _acc_exponential_moving_average += Float64(len(_r_exponential_moving_average))
    var _t1_exponential_moving_average = perf_counter_ns()
    var _ns_exponential_moving_average = Float64(_t1_exponential_moving_average - _t0_exponential_moving_average) / Float64(N)
    print("MOJO_TIMING signal_dsp::exponential_moving_average", _ns_exponential_moving_average, _acc_exponential_moving_average)
    var _result_exponential_moving_average = exponential_moving_average(_lf5, 0.5)
    var _summary_exponential_moving_average = _summary_list_float64(_result_exponential_moving_average)
    print("MOJO_RESULT signal_dsp::exponential_moving_average", _summary_exponential_moving_average)
    var _acc_diff: Float64 = 0.0
    var _t0_diff = perf_counter_ns()
    for _ in range(N):
        var _r_diff = diff(_lf5)
        _acc_diff += Float64(len(_r_diff))
    var _t1_diff = perf_counter_ns()
    var _ns_diff = Float64(_t1_diff - _t0_diff) / Float64(N)
    print("MOJO_TIMING signal_dsp::diff", _ns_diff, _acc_diff)
    var _result_diff = diff(_lf5)
    var _summary_diff = _summary_list_float64(_result_diff)
    print("MOJO_RESULT signal_dsp::diff", _summary_diff)
    var _acc_cumsum: Float64 = 0.0
    var _t0_cumsum = perf_counter_ns()
    for _ in range(N):
        var _r_cumsum = cumsum(_lf5)
        _acc_cumsum += Float64(len(_r_cumsum))
    var _t1_cumsum = perf_counter_ns()
    var _ns_cumsum = Float64(_t1_cumsum - _t0_cumsum) / Float64(N)
    print("MOJO_TIMING signal_dsp::cumsum", _ns_cumsum, _acc_cumsum)
    var _result_cumsum = cumsum(_lf5)
    var _summary_cumsum = _summary_list_float64(_result_cumsum)
    print("MOJO_RESULT signal_dsp::cumsum", _summary_cumsum)
    var _acc_convolve: Float64 = 0.0
    var _t0_convolve = perf_counter_ns()
    for _ in range(N):
        var _r_convolve = convolve(_lf5, _lf5)
        _acc_convolve += Float64(len(_r_convolve))
    var _t1_convolve = perf_counter_ns()
    var _ns_convolve = Float64(_t1_convolve - _t0_convolve) / Float64(N)
    print("MOJO_TIMING signal_dsp::convolve", _ns_convolve, _acc_convolve)
    var _result_convolve = convolve(_lf5, _lf5)
    var _summary_convolve = _summary_list_float64(_result_convolve)
    print("MOJO_RESULT signal_dsp::convolve", _summary_convolve)
    var _acc_autocorrelation: Float64 = 0.0
    var _t0_autocorrelation = perf_counter_ns()
    for _ in range(N):
        var _r_autocorrelation = autocorrelation(_lf5, 5)
        _acc_autocorrelation += Float64(len(_r_autocorrelation))
    var _t1_autocorrelation = perf_counter_ns()
    var _ns_autocorrelation = Float64(_t1_autocorrelation - _t0_autocorrelation) / Float64(N)
    print("MOJO_TIMING signal_dsp::autocorrelation", _ns_autocorrelation, _acc_autocorrelation)
    var _result_autocorrelation = autocorrelation(_lf5, 5)
    var _summary_autocorrelation = _summary_list_float64(_result_autocorrelation)
    print("MOJO_RESULT signal_dsp::autocorrelation", _summary_autocorrelation)
    var _acc_detrend_linear: Float64 = 0.0
    var _t0_detrend_linear = perf_counter_ns()
    for _ in range(N):
        var _r_detrend_linear = detrend_linear(_lf5)
        _acc_detrend_linear += Float64(len(_r_detrend_linear))
    var _t1_detrend_linear = perf_counter_ns()
    var _ns_detrend_linear = Float64(_t1_detrend_linear - _t0_detrend_linear) / Float64(N)
    print("MOJO_TIMING signal_dsp::detrend_linear", _ns_detrend_linear, _acc_detrend_linear)
    var _result_detrend_linear = detrend_linear(_lf5)
    var _summary_detrend_linear = _summary_list_float64(_result_detrend_linear)
    print("MOJO_RESULT signal_dsp::detrend_linear", _summary_detrend_linear)
    var _acc_normalize_signal: Float64 = 0.0
    var _t0_normalize_signal = perf_counter_ns()
    for _ in range(N):
        var _r_normalize_signal = normalize_signal(_lf5)
        _acc_normalize_signal += Float64(len(_r_normalize_signal))
    var _t1_normalize_signal = perf_counter_ns()
    var _ns_normalize_signal = Float64(_t1_normalize_signal - _t0_normalize_signal) / Float64(N)
    print("MOJO_TIMING signal_dsp::normalize_signal", _ns_normalize_signal, _acc_normalize_signal)
    var _result_normalize_signal = normalize_signal(_lf5)
    var _summary_normalize_signal = _summary_list_float64(_result_normalize_signal)
    print("MOJO_RESULT signal_dsp::normalize_signal", _summary_normalize_signal)
    var _acc_zero_crossings: Float64 = 0.0
    var _t0_zero_crossings = perf_counter_ns()
    for _ in range(N):
        _acc_zero_crossings += Float64(zero_crossings(_lf5))
    var _t1_zero_crossings = perf_counter_ns()
    var _ns_zero_crossings = Float64(_t1_zero_crossings - _t0_zero_crossings) / Float64(N)
    print("MOJO_TIMING signal_dsp::zero_crossings", _ns_zero_crossings, _acc_zero_crossings)
    var _result_zero_crossings = zero_crossings(_lf5)
    var _summary_zero_crossings = _summary_int(_result_zero_crossings)
    print("MOJO_RESULT signal_dsp::zero_crossings", _summary_zero_crossings)
    var _acc_peak_detect: Float64 = 0.0
    var _t0_peak_detect = perf_counter_ns()
    for _ in range(N):
        var _r_peak_detect = peak_detect(_lf5, 0.5)
        _acc_peak_detect += Float64(len(_r_peak_detect))
    var _t1_peak_detect = perf_counter_ns()
    var _ns_peak_detect = Float64(_t1_peak_detect - _t0_peak_detect) / Float64(N)
    print("MOJO_TIMING signal_dsp::peak_detect", _ns_peak_detect, _acc_peak_detect)
    var _result_peak_detect = peak_detect(_lf5, 0.5)
    var _summary_peak_detect = _summary_list_int(_result_peak_detect)
    print("MOJO_RESULT signal_dsp::peak_detect", _summary_peak_detect)
