"""bench_endocrinology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from endocrinology import hormone_clearance_rate, receptor_binding_bmax, feedback_gain, hormone_pulsatility, cortisol_circadian, insulin_sensitivity_index, thyroid_free_fraction, growth_rate_igf, testosterone_free, negative_feedback_strength
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

    var _acc_hormone_clearance_rate: Float64 = 0.0
    var _t0_hormone_clearance_rate = perf_counter_ns()
    for _ in range(N):
        _acc_hormone_clearance_rate += hormone_clearance_rate(0.5, 0.5)
    var _t1_hormone_clearance_rate = perf_counter_ns()
    var _ns_hormone_clearance_rate = Float64(_t1_hormone_clearance_rate - _t0_hormone_clearance_rate) / Float64(N)
    print("MOJO_TIMING endocrinology::hormone_clearance_rate", _ns_hormone_clearance_rate, _acc_hormone_clearance_rate)
    var _acc_receptor_binding_bmax: Float64 = 0.0
    var _t0_receptor_binding_bmax = perf_counter_ns()
    for _ in range(N):
        _acc_receptor_binding_bmax += receptor_binding_bmax(0.5, 0.5, 0.5)
    var _t1_receptor_binding_bmax = perf_counter_ns()
    var _ns_receptor_binding_bmax = Float64(_t1_receptor_binding_bmax - _t0_receptor_binding_bmax) / Float64(N)
    print("MOJO_TIMING endocrinology::receptor_binding_bmax", _ns_receptor_binding_bmax, _acc_receptor_binding_bmax)
    var _acc_feedback_gain: Float64 = 0.0
    var _t0_feedback_gain = perf_counter_ns()
    for _ in range(N):
        _acc_feedback_gain += feedback_gain(0.5, 0.5)
    var _t1_feedback_gain = perf_counter_ns()
    var _ns_feedback_gain = Float64(_t1_feedback_gain - _t0_feedback_gain) / Float64(N)
    print("MOJO_TIMING endocrinology::feedback_gain", _ns_feedback_gain, _acc_feedback_gain)
    var _acc_hormone_pulsatility: Float64 = 0.0
    var _t0_hormone_pulsatility = perf_counter_ns()
    for _ in range(N):
        _acc_hormone_pulsatility += hormone_pulsatility(0.5, 0.5)
    var _t1_hormone_pulsatility = perf_counter_ns()
    var _ns_hormone_pulsatility = Float64(_t1_hormone_pulsatility - _t0_hormone_pulsatility) / Float64(N)
    print("MOJO_TIMING endocrinology::hormone_pulsatility", _ns_hormone_pulsatility, _acc_hormone_pulsatility)
    var _acc_cortisol_circadian: Float64 = 0.0
    var _t0_cortisol_circadian = perf_counter_ns()
    for _ in range(N):
        _acc_cortisol_circadian += cortisol_circadian(0.5, 0.5, 0.5)
    var _t1_cortisol_circadian = perf_counter_ns()
    var _ns_cortisol_circadian = Float64(_t1_cortisol_circadian - _t0_cortisol_circadian) / Float64(N)
    print("MOJO_TIMING endocrinology::cortisol_circadian", _ns_cortisol_circadian, _acc_cortisol_circadian)
    var _acc_insulin_sensitivity_index: Float64 = 0.0
    var _t0_insulin_sensitivity_index = perf_counter_ns()
    for _ in range(N):
        _acc_insulin_sensitivity_index += insulin_sensitivity_index(0.5, 0.5)
    var _t1_insulin_sensitivity_index = perf_counter_ns()
    var _ns_insulin_sensitivity_index = Float64(_t1_insulin_sensitivity_index - _t0_insulin_sensitivity_index) / Float64(N)
    print("MOJO_TIMING endocrinology::insulin_sensitivity_index", _ns_insulin_sensitivity_index, _acc_insulin_sensitivity_index)
    var _acc_thyroid_free_fraction: Float64 = 0.0
    var _t0_thyroid_free_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_thyroid_free_fraction += thyroid_free_fraction(0.5, 0.5, 0.5)
    var _t1_thyroid_free_fraction = perf_counter_ns()
    var _ns_thyroid_free_fraction = Float64(_t1_thyroid_free_fraction - _t0_thyroid_free_fraction) / Float64(N)
    print("MOJO_TIMING endocrinology::thyroid_free_fraction", _ns_thyroid_free_fraction, _acc_thyroid_free_fraction)
    var _acc_growth_rate_igf: Float64 = 0.0
    var _t0_growth_rate_igf = perf_counter_ns()
    for _ in range(N):
        _acc_growth_rate_igf += growth_rate_igf(0.5, 0.5, 0.5)
    var _t1_growth_rate_igf = perf_counter_ns()
    var _ns_growth_rate_igf = Float64(_t1_growth_rate_igf - _t0_growth_rate_igf) / Float64(N)
    print("MOJO_TIMING endocrinology::growth_rate_igf", _ns_growth_rate_igf, _acc_growth_rate_igf)
    var _acc_testosterone_free: Float64 = 0.0
    var _t0_testosterone_free = perf_counter_ns()
    for _ in range(N):
        _acc_testosterone_free += testosterone_free(0.5, 0.5, 0.5)
    var _t1_testosterone_free = perf_counter_ns()
    var _ns_testosterone_free = Float64(_t1_testosterone_free - _t0_testosterone_free) / Float64(N)
    print("MOJO_TIMING endocrinology::testosterone_free", _ns_testosterone_free, _acc_testosterone_free)
    var _acc_negative_feedback_strength: Float64 = 0.0
    var _t0_negative_feedback_strength = perf_counter_ns()
    for _ in range(N):
        _acc_negative_feedback_strength += negative_feedback_strength(0.5, 0.5)
    var _t1_negative_feedback_strength = perf_counter_ns()
    var _ns_negative_feedback_strength = Float64(_t1_negative_feedback_strength - _t0_negative_feedback_strength) / Float64(N)
    print("MOJO_TIMING endocrinology::negative_feedback_strength", _ns_negative_feedback_strength, _acc_negative_feedback_strength)
