"""bench_dendrochronology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from dendrochronology import ring_width_index, basal_area_increment, standardise_negative_exp, sensitivity_coefficient, first_order_autocorrelation, expressed_population_signal, signal_free_mean, pointer_year_threshold, crossdating_t_value, temperature_response
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

    var _acc_ring_width_index: Float64 = 0.0
    var _t0_ring_width_index = perf_counter_ns()
    for _ in range(N):
        _acc_ring_width_index += ring_width_index(0.5, 0.5)
    var _t1_ring_width_index = perf_counter_ns()
    var _ns_ring_width_index = Float64(_t1_ring_width_index - _t0_ring_width_index) / Float64(N)
    print("MOJO_TIMING dendrochronology::ring_width_index", _ns_ring_width_index, _acc_ring_width_index)
    var _acc_basal_area_increment: Float64 = 0.0
    var _t0_basal_area_increment = perf_counter_ns()
    for _ in range(N):
        _acc_basal_area_increment += basal_area_increment(0.5, 0.5)
    var _t1_basal_area_increment = perf_counter_ns()
    var _ns_basal_area_increment = Float64(_t1_basal_area_increment - _t0_basal_area_increment) / Float64(N)
    print("MOJO_TIMING dendrochronology::basal_area_increment", _ns_basal_area_increment, _acc_basal_area_increment)
    var _acc_standardise_negative_exp: Float64 = 0.0
    var _t0_standardise_negative_exp = perf_counter_ns()
    for _ in range(N):
        _acc_standardise_negative_exp += standardise_negative_exp(0.5, 0.5, 0.5, 0.5)
    var _t1_standardise_negative_exp = perf_counter_ns()
    var _ns_standardise_negative_exp = Float64(_t1_standardise_negative_exp - _t0_standardise_negative_exp) / Float64(N)
    print("MOJO_TIMING dendrochronology::standardise_negative_exp", _ns_standardise_negative_exp, _acc_standardise_negative_exp)
    var _acc_sensitivity_coefficient: Float64 = 0.0
    var _t0_sensitivity_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_sensitivity_coefficient += sensitivity_coefficient(0.5, 0.5)
    var _t1_sensitivity_coefficient = perf_counter_ns()
    var _ns_sensitivity_coefficient = Float64(_t1_sensitivity_coefficient - _t0_sensitivity_coefficient) / Float64(N)
    print("MOJO_TIMING dendrochronology::sensitivity_coefficient", _ns_sensitivity_coefficient, _acc_sensitivity_coefficient)
    var _acc_first_order_autocorrelation: Float64 = 0.0
    var _t0_first_order_autocorrelation = perf_counter_ns()
    for _ in range(N):
        _acc_first_order_autocorrelation += first_order_autocorrelation(0.5, 0.5, 0.5, 0.5)
    var _t1_first_order_autocorrelation = perf_counter_ns()
    var _ns_first_order_autocorrelation = Float64(_t1_first_order_autocorrelation - _t0_first_order_autocorrelation) / Float64(N)
    print("MOJO_TIMING dendrochronology::first_order_autocorrelation", _ns_first_order_autocorrelation, _acc_first_order_autocorrelation)
    var _acc_expressed_population_signal: Float64 = 0.0
    var _t0_expressed_population_signal = perf_counter_ns()
    for _ in range(N):
        _acc_expressed_population_signal += expressed_population_signal(0.5, 0.5)
    var _t1_expressed_population_signal = perf_counter_ns()
    var _ns_expressed_population_signal = Float64(_t1_expressed_population_signal - _t0_expressed_population_signal) / Float64(N)
    print("MOJO_TIMING dendrochronology::expressed_population_signal", _ns_expressed_population_signal, _acc_expressed_population_signal)
    var _acc_signal_free_mean: Float64 = 0.0
    var _t0_signal_free_mean = perf_counter_ns()
    for _ in range(N):
        _acc_signal_free_mean += signal_free_mean(0.5, 0.5)
    var _t1_signal_free_mean = perf_counter_ns()
    var _ns_signal_free_mean = Float64(_t1_signal_free_mean - _t0_signal_free_mean) / Float64(N)
    print("MOJO_TIMING dendrochronology::signal_free_mean", _ns_signal_free_mean, _acc_signal_free_mean)
    var _acc_pointer_year_threshold: Float64 = 0.0
    var _t0_pointer_year_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_pointer_year_threshold += pointer_year_threshold(0.5, 0.5, 0.5)
    var _t1_pointer_year_threshold = perf_counter_ns()
    var _ns_pointer_year_threshold = Float64(_t1_pointer_year_threshold - _t0_pointer_year_threshold) / Float64(N)
    print("MOJO_TIMING dendrochronology::pointer_year_threshold", _ns_pointer_year_threshold, _acc_pointer_year_threshold)
    var _acc_crossdating_t_value: Float64 = 0.0
    var _t0_crossdating_t_value = perf_counter_ns()
    for _ in range(N):
        _acc_crossdating_t_value += crossdating_t_value(0.5, 0.5)
    var _t1_crossdating_t_value = perf_counter_ns()
    var _ns_crossdating_t_value = Float64(_t1_crossdating_t_value - _t0_crossdating_t_value) / Float64(N)
    print("MOJO_TIMING dendrochronology::crossdating_t_value", _ns_crossdating_t_value, _acc_crossdating_t_value)
    var _acc_temperature_response: Float64 = 0.0
    var _t0_temperature_response = perf_counter_ns()
    for _ in range(N):
        _acc_temperature_response += temperature_response(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_temperature_response = perf_counter_ns()
    var _ns_temperature_response = Float64(_t1_temperature_response - _t0_temperature_response) / Float64(N)
    print("MOJO_TIMING dendrochronology::temperature_response", _ns_temperature_response, _acc_temperature_response)
