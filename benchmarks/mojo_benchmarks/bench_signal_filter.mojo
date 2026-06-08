"""bench_signal_filter.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from signal.filter import lowpass_ema, highpass_ema, bandpass, median_filter, savitzky_golay_3, moving_average_filter, iir_filter_1st, diff_filter, integrate_filter, snr, rms
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_lowpass_ema: Float64 = 0.0
    var _t0_lowpass_ema = perf_counter_ns()
    for _ in range(N):
        var _r_lowpass_ema = lowpass_ema(_lf5, 0.5)
        _acc_lowpass_ema += Float64(len(_r_lowpass_ema))
    var _t1_lowpass_ema = perf_counter_ns()
    var _ns_lowpass_ema = Float64(_t1_lowpass_ema - _t0_lowpass_ema) / Float64(N)
    print("MOJO_TIMING signal_filter::lowpass_ema", _ns_lowpass_ema, _acc_lowpass_ema)
    var _result_lowpass_ema = lowpass_ema(_lf5, 0.5)
    var _summary_lowpass_ema = _summary_list_float64(_result_lowpass_ema)
    print("MOJO_RESULT signal_filter::lowpass_ema", _summary_lowpass_ema)
    var _acc_highpass_ema: Float64 = 0.0
    var _t0_highpass_ema = perf_counter_ns()
    for _ in range(N):
        var _r_highpass_ema = highpass_ema(_lf5, 0.5)
        _acc_highpass_ema += Float64(len(_r_highpass_ema))
    var _t1_highpass_ema = perf_counter_ns()
    var _ns_highpass_ema = Float64(_t1_highpass_ema - _t0_highpass_ema) / Float64(N)
    print("MOJO_TIMING signal_filter::highpass_ema", _ns_highpass_ema, _acc_highpass_ema)
    var _result_highpass_ema = highpass_ema(_lf5, 0.5)
    var _summary_highpass_ema = _summary_list_float64(_result_highpass_ema)
    print("MOJO_RESULT signal_filter::highpass_ema", _summary_highpass_ema)
    var _acc_bandpass: Float64 = 0.0
    var _t0_bandpass = perf_counter_ns()
    for _ in range(N):
        var _r_bandpass = bandpass(_lf5, 0.5, 0.5)
        _acc_bandpass += Float64(len(_r_bandpass))
    var _t1_bandpass = perf_counter_ns()
    var _ns_bandpass = Float64(_t1_bandpass - _t0_bandpass) / Float64(N)
    print("MOJO_TIMING signal_filter::bandpass", _ns_bandpass, _acc_bandpass)
    var _result_bandpass = bandpass(_lf5, 0.5, 0.5)
    var _summary_bandpass = _summary_list_float64(_result_bandpass)
    print("MOJO_RESULT signal_filter::bandpass", _summary_bandpass)
    var _acc_median_filter: Float64 = 0.0
    var _t0_median_filter = perf_counter_ns()
    for _ in range(N):
        var _r_median_filter = median_filter(_lf5, 5)
        _acc_median_filter += Float64(len(_r_median_filter))
    var _t1_median_filter = perf_counter_ns()
    var _ns_median_filter = Float64(_t1_median_filter - _t0_median_filter) / Float64(N)
    print("MOJO_TIMING signal_filter::median_filter", _ns_median_filter, _acc_median_filter)
    var _result_median_filter = median_filter(_lf5, 5)
    var _summary_median_filter = _summary_list_float64(_result_median_filter)
    print("MOJO_RESULT signal_filter::median_filter", _summary_median_filter)
    var _acc_savitzky_golay_3: Float64 = 0.0
    var _t0_savitzky_golay_3 = perf_counter_ns()
    for _ in range(N):
        var _r_savitzky_golay_3 = savitzky_golay_3(_lf5)
        _acc_savitzky_golay_3 += Float64(len(_r_savitzky_golay_3))
    var _t1_savitzky_golay_3 = perf_counter_ns()
    var _ns_savitzky_golay_3 = Float64(_t1_savitzky_golay_3 - _t0_savitzky_golay_3) / Float64(N)
    print("MOJO_TIMING signal_filter::savitzky_golay_3", _ns_savitzky_golay_3, _acc_savitzky_golay_3)
    var _result_savitzky_golay_3 = savitzky_golay_3(_lf5)
    var _summary_savitzky_golay_3 = _summary_list_float64(_result_savitzky_golay_3)
    print("MOJO_RESULT signal_filter::savitzky_golay_3", _summary_savitzky_golay_3)
    var _acc_moving_average_filter: Float64 = 0.0
    var _t0_moving_average_filter = perf_counter_ns()
    for _ in range(N):
        var _r_moving_average_filter = moving_average_filter(_lf5, 5)
        _acc_moving_average_filter += Float64(len(_r_moving_average_filter))
    var _t1_moving_average_filter = perf_counter_ns()
    var _ns_moving_average_filter = Float64(_t1_moving_average_filter - _t0_moving_average_filter) / Float64(N)
    print("MOJO_TIMING signal_filter::moving_average_filter", _ns_moving_average_filter, _acc_moving_average_filter)
    var _result_moving_average_filter = moving_average_filter(_lf5, 5)
    var _summary_moving_average_filter = _summary_list_float64(_result_moving_average_filter)
    print("MOJO_RESULT signal_filter::moving_average_filter", _summary_moving_average_filter)
    var _acc_iir_filter_1st: Float64 = 0.0
    var _t0_iir_filter_1st = perf_counter_ns()
    for _ in range(N):
        var _r_iir_filter_1st = iir_filter_1st(_lf5, 0.5, 0.5)
        _acc_iir_filter_1st += Float64(len(_r_iir_filter_1st))
    var _t1_iir_filter_1st = perf_counter_ns()
    var _ns_iir_filter_1st = Float64(_t1_iir_filter_1st - _t0_iir_filter_1st) / Float64(N)
    print("MOJO_TIMING signal_filter::iir_filter_1st", _ns_iir_filter_1st, _acc_iir_filter_1st)
    var _result_iir_filter_1st = iir_filter_1st(_lf5, 0.5, 0.5)
    var _summary_iir_filter_1st = _summary_list_float64(_result_iir_filter_1st)
    print("MOJO_RESULT signal_filter::iir_filter_1st", _summary_iir_filter_1st)
    var _acc_diff_filter: Float64 = 0.0
    var _t0_diff_filter = perf_counter_ns()
    for _ in range(N):
        var _r_diff_filter = diff_filter(_lf5)
        _acc_diff_filter += Float64(len(_r_diff_filter))
    var _t1_diff_filter = perf_counter_ns()
    var _ns_diff_filter = Float64(_t1_diff_filter - _t0_diff_filter) / Float64(N)
    print("MOJO_TIMING signal_filter::diff_filter", _ns_diff_filter, _acc_diff_filter)
    var _result_diff_filter = diff_filter(_lf5)
    var _summary_diff_filter = _summary_list_float64(_result_diff_filter)
    print("MOJO_RESULT signal_filter::diff_filter", _summary_diff_filter)
    var _acc_integrate_filter: Float64 = 0.0
    var _t0_integrate_filter = perf_counter_ns()
    for _ in range(N):
        var _r_integrate_filter = integrate_filter(_lf5, 0.5)
        _acc_integrate_filter += Float64(len(_r_integrate_filter))
    var _t1_integrate_filter = perf_counter_ns()
    var _ns_integrate_filter = Float64(_t1_integrate_filter - _t0_integrate_filter) / Float64(N)
    print("MOJO_TIMING signal_filter::integrate_filter", _ns_integrate_filter, _acc_integrate_filter)
    var _result_integrate_filter = integrate_filter(_lf5, 0.5)
    var _summary_integrate_filter = _summary_list_float64(_result_integrate_filter)
    print("MOJO_RESULT signal_filter::integrate_filter", _summary_integrate_filter)
    var _acc_snr: Float64 = 0.0
    var _t0_snr = perf_counter_ns()
    for _ in range(N):
        _acc_snr += snr(_lf5, _lf5)
    var _t1_snr = perf_counter_ns()
    var _ns_snr = Float64(_t1_snr - _t0_snr) / Float64(N)
    print("MOJO_TIMING signal_filter::snr", _ns_snr, _acc_snr)
    var _result_snr = snr(_lf5, _lf5)
    var _summary_snr = _summary_float64(_result_snr)
    print("MOJO_RESULT signal_filter::snr", _summary_snr)
    var _acc_rms: Float64 = 0.0
    var _t0_rms = perf_counter_ns()
    for _ in range(N):
        _acc_rms += rms(_lf5)
    var _t1_rms = perf_counter_ns()
    var _ns_rms = Float64(_t1_rms - _t0_rms) / Float64(N)
    print("MOJO_TIMING signal_filter::rms", _ns_rms, _acc_rms)
    var _result_rms = rms(_lf5)
    var _summary_rms = _summary_float64(_result_rms)
    print("MOJO_RESULT signal_filter::rms", _summary_rms)
