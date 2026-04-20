"""bench_signal_filter.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from signal.filter import lowpass_ema, highpass_ema, bandpass, median_filter, savitzky_golay_3, moving_average_filter, iir_filter_1st, diff_filter, integrate_filter, snr, rms
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

    var _acc_lowpass_ema: Float64 = 0.0
    var _t0_lowpass_ema = perf_counter_ns()
    for _ in range(N):
        var _r_lowpass_ema = lowpass_ema(_lf5, 0.5)
        _acc_lowpass_ema += Float64(len(_r_lowpass_ema))
    var _t1_lowpass_ema = perf_counter_ns()
    var _ns_lowpass_ema = Float64(_t1_lowpass_ema - _t0_lowpass_ema) / Float64(N)
    print("MOJO_TIMING signal_filter::lowpass_ema", _ns_lowpass_ema, _acc_lowpass_ema)
    var _acc_highpass_ema: Float64 = 0.0
    var _t0_highpass_ema = perf_counter_ns()
    for _ in range(N):
        var _r_highpass_ema = highpass_ema(_lf5, 0.5)
        _acc_highpass_ema += Float64(len(_r_highpass_ema))
    var _t1_highpass_ema = perf_counter_ns()
    var _ns_highpass_ema = Float64(_t1_highpass_ema - _t0_highpass_ema) / Float64(N)
    print("MOJO_TIMING signal_filter::highpass_ema", _ns_highpass_ema, _acc_highpass_ema)
    var _acc_bandpass: Float64 = 0.0
    var _t0_bandpass = perf_counter_ns()
    for _ in range(N):
        var _r_bandpass = bandpass(_lf5, 0.5, 0.5)
        _acc_bandpass += Float64(len(_r_bandpass))
    var _t1_bandpass = perf_counter_ns()
    var _ns_bandpass = Float64(_t1_bandpass - _t0_bandpass) / Float64(N)
    print("MOJO_TIMING signal_filter::bandpass", _ns_bandpass, _acc_bandpass)
    var _acc_median_filter: Float64 = 0.0
    var _t0_median_filter = perf_counter_ns()
    for _ in range(N):
        var _r_median_filter = median_filter(_lf5, 5)
        _acc_median_filter += Float64(len(_r_median_filter))
    var _t1_median_filter = perf_counter_ns()
    var _ns_median_filter = Float64(_t1_median_filter - _t0_median_filter) / Float64(N)
    print("MOJO_TIMING signal_filter::median_filter", _ns_median_filter, _acc_median_filter)
    var _acc_savitzky_golay_3: Float64 = 0.0
    var _t0_savitzky_golay_3 = perf_counter_ns()
    for _ in range(N):
        var _r_savitzky_golay_3 = savitzky_golay_3(_lf5)
        _acc_savitzky_golay_3 += Float64(len(_r_savitzky_golay_3))
    var _t1_savitzky_golay_3 = perf_counter_ns()
    var _ns_savitzky_golay_3 = Float64(_t1_savitzky_golay_3 - _t0_savitzky_golay_3) / Float64(N)
    print("MOJO_TIMING signal_filter::savitzky_golay_3", _ns_savitzky_golay_3, _acc_savitzky_golay_3)
    var _acc_moving_average_filter: Float64 = 0.0
    var _t0_moving_average_filter = perf_counter_ns()
    for _ in range(N):
        var _r_moving_average_filter = moving_average_filter(_lf5, 5)
        _acc_moving_average_filter += Float64(len(_r_moving_average_filter))
    var _t1_moving_average_filter = perf_counter_ns()
    var _ns_moving_average_filter = Float64(_t1_moving_average_filter - _t0_moving_average_filter) / Float64(N)
    print("MOJO_TIMING signal_filter::moving_average_filter", _ns_moving_average_filter, _acc_moving_average_filter)
    var _acc_iir_filter_1st: Float64 = 0.0
    var _t0_iir_filter_1st = perf_counter_ns()
    for _ in range(N):
        var _r_iir_filter_1st = iir_filter_1st(_lf5, 0.5, 0.5)
        _acc_iir_filter_1st += Float64(len(_r_iir_filter_1st))
    var _t1_iir_filter_1st = perf_counter_ns()
    var _ns_iir_filter_1st = Float64(_t1_iir_filter_1st - _t0_iir_filter_1st) / Float64(N)
    print("MOJO_TIMING signal_filter::iir_filter_1st", _ns_iir_filter_1st, _acc_iir_filter_1st)
    var _acc_diff_filter: Float64 = 0.0
    var _t0_diff_filter = perf_counter_ns()
    for _ in range(N):
        var _r_diff_filter = diff_filter(_lf5)
        _acc_diff_filter += Float64(len(_r_diff_filter))
    var _t1_diff_filter = perf_counter_ns()
    var _ns_diff_filter = Float64(_t1_diff_filter - _t0_diff_filter) / Float64(N)
    print("MOJO_TIMING signal_filter::diff_filter", _ns_diff_filter, _acc_diff_filter)
    var _acc_integrate_filter: Float64 = 0.0
    var _t0_integrate_filter = perf_counter_ns()
    for _ in range(N):
        var _r_integrate_filter = integrate_filter(_lf5, 0.5)
        _acc_integrate_filter += Float64(len(_r_integrate_filter))
    var _t1_integrate_filter = perf_counter_ns()
    var _ns_integrate_filter = Float64(_t1_integrate_filter - _t0_integrate_filter) / Float64(N)
    print("MOJO_TIMING signal_filter::integrate_filter", _ns_integrate_filter, _acc_integrate_filter)
    var _acc_snr: Float64 = 0.0
    var _t0_snr = perf_counter_ns()
    for _ in range(N):
        _acc_snr += snr(_lf5, _lf5)
    var _t1_snr = perf_counter_ns()
    var _ns_snr = Float64(_t1_snr - _t0_snr) / Float64(N)
    print("MOJO_TIMING signal_filter::snr", _ns_snr, _acc_snr)
    var _acc_rms: Float64 = 0.0
    var _t0_rms = perf_counter_ns()
    for _ in range(N):
        _acc_rms += rms(_lf5)
    var _t1_rms = perf_counter_ns()
    var _ns_rms = Float64(_t1_rms - _t0_rms) / Float64(N)
    print("MOJO_TIMING signal_filter::rms", _ns_rms, _acc_rms)
