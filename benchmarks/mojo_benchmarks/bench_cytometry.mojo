"""bench_cytometry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from cytometry import percent_positive_gate, median_fluorescence_intensity, staining_index, coefficient_of_variation_peak, cell_cycle_g1_fraction, apoptosis_annexin_pi, lymphocyte_subset_ratio, absolute_count, compensation_spillover, sensitivity_lod_cytometry
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

    var _acc_percent_positive_gate: Float64 = 0.0
    var _t0_percent_positive_gate = perf_counter_ns()
    for _ in range(N):
        _acc_percent_positive_gate += percent_positive_gate(0.5, 0.5)
    var _t1_percent_positive_gate = perf_counter_ns()
    var _ns_percent_positive_gate = Float64(_t1_percent_positive_gate - _t0_percent_positive_gate) / Float64(N)
    print("MOJO_TIMING cytometry::percent_positive_gate", _ns_percent_positive_gate, _acc_percent_positive_gate)
    var _acc_median_fluorescence_intensity: Float64 = 0.0
    var _t0_median_fluorescence_intensity = perf_counter_ns()
    for _ in range(N):
        _acc_median_fluorescence_intensity += median_fluorescence_intensity(0.5, 0.5)
    var _t1_median_fluorescence_intensity = perf_counter_ns()
    var _ns_median_fluorescence_intensity = Float64(_t1_median_fluorescence_intensity - _t0_median_fluorescence_intensity) / Float64(N)
    print("MOJO_TIMING cytometry::median_fluorescence_intensity", _ns_median_fluorescence_intensity, _acc_median_fluorescence_intensity)
    var _acc_staining_index: Float64 = 0.0
    var _t0_staining_index = perf_counter_ns()
    for _ in range(N):
        _acc_staining_index += staining_index(0.5, 0.5, 0.5)
    var _t1_staining_index = perf_counter_ns()
    var _ns_staining_index = Float64(_t1_staining_index - _t0_staining_index) / Float64(N)
    print("MOJO_TIMING cytometry::staining_index", _ns_staining_index, _acc_staining_index)
    var _acc_coefficient_of_variation_peak: Float64 = 0.0
    var _t0_coefficient_of_variation_peak = perf_counter_ns()
    for _ in range(N):
        _acc_coefficient_of_variation_peak += coefficient_of_variation_peak(0.5, 0.5)
    var _t1_coefficient_of_variation_peak = perf_counter_ns()
    var _ns_coefficient_of_variation_peak = Float64(_t1_coefficient_of_variation_peak - _t0_coefficient_of_variation_peak) / Float64(N)
    print("MOJO_TIMING cytometry::coefficient_of_variation_peak", _ns_coefficient_of_variation_peak, _acc_coefficient_of_variation_peak)
    var _acc_cell_cycle_g1_fraction: Float64 = 0.0
    var _t0_cell_cycle_g1_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_cell_cycle_g1_fraction += cell_cycle_g1_fraction(0.5, 0.5, 0.5)
    var _t1_cell_cycle_g1_fraction = perf_counter_ns()
    var _ns_cell_cycle_g1_fraction = Float64(_t1_cell_cycle_g1_fraction - _t0_cell_cycle_g1_fraction) / Float64(N)
    print("MOJO_TIMING cytometry::cell_cycle_g1_fraction", _ns_cell_cycle_g1_fraction, _acc_cell_cycle_g1_fraction)
    var _acc_apoptosis_annexin_pi: Float64 = 0.0
    var _t0_apoptosis_annexin_pi = perf_counter_ns()
    for _ in range(N):
        _acc_apoptosis_annexin_pi += apoptosis_annexin_pi(0.5, 0.5, 0.5)
    var _t1_apoptosis_annexin_pi = perf_counter_ns()
    var _ns_apoptosis_annexin_pi = Float64(_t1_apoptosis_annexin_pi - _t0_apoptosis_annexin_pi) / Float64(N)
    print("MOJO_TIMING cytometry::apoptosis_annexin_pi", _ns_apoptosis_annexin_pi, _acc_apoptosis_annexin_pi)
    var _acc_lymphocyte_subset_ratio: Float64 = 0.0
    var _t0_lymphocyte_subset_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_lymphocyte_subset_ratio += lymphocyte_subset_ratio(0.5, 0.5)
    var _t1_lymphocyte_subset_ratio = perf_counter_ns()
    var _ns_lymphocyte_subset_ratio = Float64(_t1_lymphocyte_subset_ratio - _t0_lymphocyte_subset_ratio) / Float64(N)
    print("MOJO_TIMING cytometry::lymphocyte_subset_ratio", _ns_lymphocyte_subset_ratio, _acc_lymphocyte_subset_ratio)
    var _acc_absolute_count: Float64 = 0.0
    var _t0_absolute_count = perf_counter_ns()
    for _ in range(N):
        _acc_absolute_count += absolute_count(0.5, 0.5)
    var _t1_absolute_count = perf_counter_ns()
    var _ns_absolute_count = Float64(_t1_absolute_count - _t0_absolute_count) / Float64(N)
    print("MOJO_TIMING cytometry::absolute_count", _ns_absolute_count, _acc_absolute_count)
    var _acc_compensation_spillover: Float64 = 0.0
    var _t0_compensation_spillover = perf_counter_ns()
    for _ in range(N):
        _acc_compensation_spillover += compensation_spillover(0.5, 0.5, 0.5)
    var _t1_compensation_spillover = perf_counter_ns()
    var _ns_compensation_spillover = Float64(_t1_compensation_spillover - _t0_compensation_spillover) / Float64(N)
    print("MOJO_TIMING cytometry::compensation_spillover", _ns_compensation_spillover, _acc_compensation_spillover)
    var _acc_sensitivity_lod_cytometry: Float64 = 0.0
    var _t0_sensitivity_lod_cytometry = perf_counter_ns()
    for _ in range(N):
        _acc_sensitivity_lod_cytometry += sensitivity_lod_cytometry(0.5, 0.5, 0.5)
    var _t1_sensitivity_lod_cytometry = perf_counter_ns()
    var _ns_sensitivity_lod_cytometry = Float64(_t1_sensitivity_lod_cytometry - _t0_sensitivity_lod_cytometry) / Float64(N)
    print("MOJO_TIMING cytometry::sensitivity_lod_cytometry", _ns_sensitivity_lod_cytometry, _acc_sensitivity_lod_cytometry)
