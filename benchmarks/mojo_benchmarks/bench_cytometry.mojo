"""bench_cytometry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from cytometry import percent_positive_gate, median_fluorescence_intensity, staining_index, coefficient_of_variation_peak, cell_cycle_g1_fraction, apoptosis_annexin_pi, lymphocyte_subset_ratio, absolute_count, compensation_spillover, sensitivity_lod_cytometry
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

    var _acc_percent_positive_gate: Float64 = 0.0
    var _t0_percent_positive_gate = perf_counter_ns()
    for _ in range(N):
        _acc_percent_positive_gate += percent_positive_gate(0.5, 0.5)
    var _t1_percent_positive_gate = perf_counter_ns()
    var _ns_percent_positive_gate = Float64(_t1_percent_positive_gate - _t0_percent_positive_gate) / Float64(N)
    print("MOJO_TIMING cytometry::percent_positive_gate", _ns_percent_positive_gate, _acc_percent_positive_gate)
    var _result_percent_positive_gate = percent_positive_gate(0.5, 0.5)
    var _summary_percent_positive_gate = _summary_float64(_result_percent_positive_gate)
    print("MOJO_RESULT cytometry::percent_positive_gate", _summary_percent_positive_gate)
    var _acc_median_fluorescence_intensity: Float64 = 0.0
    var _t0_median_fluorescence_intensity = perf_counter_ns()
    for _ in range(N):
        _acc_median_fluorescence_intensity += median_fluorescence_intensity(0.5, 0.5)
    var _t1_median_fluorescence_intensity = perf_counter_ns()
    var _ns_median_fluorescence_intensity = Float64(_t1_median_fluorescence_intensity - _t0_median_fluorescence_intensity) / Float64(N)
    print("MOJO_TIMING cytometry::median_fluorescence_intensity", _ns_median_fluorescence_intensity, _acc_median_fluorescence_intensity)
    var _result_median_fluorescence_intensity = median_fluorescence_intensity(0.5, 0.5)
    var _summary_median_fluorescence_intensity = _summary_float64(_result_median_fluorescence_intensity)
    print("MOJO_RESULT cytometry::median_fluorescence_intensity", _summary_median_fluorescence_intensity)
    var _acc_staining_index: Float64 = 0.0
    var _t0_staining_index = perf_counter_ns()
    for _ in range(N):
        _acc_staining_index += staining_index(0.5, 0.5, 0.5)
    var _t1_staining_index = perf_counter_ns()
    var _ns_staining_index = Float64(_t1_staining_index - _t0_staining_index) / Float64(N)
    print("MOJO_TIMING cytometry::staining_index", _ns_staining_index, _acc_staining_index)
    var _result_staining_index = staining_index(0.5, 0.5, 0.5)
    var _summary_staining_index = _summary_float64(_result_staining_index)
    print("MOJO_RESULT cytometry::staining_index", _summary_staining_index)
    var _acc_coefficient_of_variation_peak: Float64 = 0.0
    var _t0_coefficient_of_variation_peak = perf_counter_ns()
    for _ in range(N):
        _acc_coefficient_of_variation_peak += coefficient_of_variation_peak(0.5, 0.5)
    var _t1_coefficient_of_variation_peak = perf_counter_ns()
    var _ns_coefficient_of_variation_peak = Float64(_t1_coefficient_of_variation_peak - _t0_coefficient_of_variation_peak) / Float64(N)
    print("MOJO_TIMING cytometry::coefficient_of_variation_peak", _ns_coefficient_of_variation_peak, _acc_coefficient_of_variation_peak)
    var _result_coefficient_of_variation_peak = coefficient_of_variation_peak(0.5, 0.5)
    var _summary_coefficient_of_variation_peak = _summary_float64(_result_coefficient_of_variation_peak)
    print("MOJO_RESULT cytometry::coefficient_of_variation_peak", _summary_coefficient_of_variation_peak)
    var _acc_cell_cycle_g1_fraction: Float64 = 0.0
    var _t0_cell_cycle_g1_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_cell_cycle_g1_fraction += cell_cycle_g1_fraction(0.5, 0.5, 0.5)
    var _t1_cell_cycle_g1_fraction = perf_counter_ns()
    var _ns_cell_cycle_g1_fraction = Float64(_t1_cell_cycle_g1_fraction - _t0_cell_cycle_g1_fraction) / Float64(N)
    print("MOJO_TIMING cytometry::cell_cycle_g1_fraction", _ns_cell_cycle_g1_fraction, _acc_cell_cycle_g1_fraction)
    var _result_cell_cycle_g1_fraction = cell_cycle_g1_fraction(0.5, 0.5, 0.5)
    var _summary_cell_cycle_g1_fraction = _summary_float64(_result_cell_cycle_g1_fraction)
    print("MOJO_RESULT cytometry::cell_cycle_g1_fraction", _summary_cell_cycle_g1_fraction)
    var _acc_apoptosis_annexin_pi: Float64 = 0.0
    var _t0_apoptosis_annexin_pi = perf_counter_ns()
    for _ in range(N):
        _acc_apoptosis_annexin_pi += apoptosis_annexin_pi(0.5, 0.5, 0.5)
    var _t1_apoptosis_annexin_pi = perf_counter_ns()
    var _ns_apoptosis_annexin_pi = Float64(_t1_apoptosis_annexin_pi - _t0_apoptosis_annexin_pi) / Float64(N)
    print("MOJO_TIMING cytometry::apoptosis_annexin_pi", _ns_apoptosis_annexin_pi, _acc_apoptosis_annexin_pi)
    var _result_apoptosis_annexin_pi = apoptosis_annexin_pi(0.5, 0.5, 0.5)
    var _summary_apoptosis_annexin_pi = _summary_float64(_result_apoptosis_annexin_pi)
    print("MOJO_RESULT cytometry::apoptosis_annexin_pi", _summary_apoptosis_annexin_pi)
    var _acc_lymphocyte_subset_ratio: Float64 = 0.0
    var _t0_lymphocyte_subset_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_lymphocyte_subset_ratio += lymphocyte_subset_ratio(0.5, 0.5)
    var _t1_lymphocyte_subset_ratio = perf_counter_ns()
    var _ns_lymphocyte_subset_ratio = Float64(_t1_lymphocyte_subset_ratio - _t0_lymphocyte_subset_ratio) / Float64(N)
    print("MOJO_TIMING cytometry::lymphocyte_subset_ratio", _ns_lymphocyte_subset_ratio, _acc_lymphocyte_subset_ratio)
    var _result_lymphocyte_subset_ratio = lymphocyte_subset_ratio(0.5, 0.5)
    var _summary_lymphocyte_subset_ratio = _summary_float64(_result_lymphocyte_subset_ratio)
    print("MOJO_RESULT cytometry::lymphocyte_subset_ratio", _summary_lymphocyte_subset_ratio)
    var _acc_absolute_count: Float64 = 0.0
    var _t0_absolute_count = perf_counter_ns()
    for _ in range(N):
        _acc_absolute_count += absolute_count(0.5, 0.5)
    var _t1_absolute_count = perf_counter_ns()
    var _ns_absolute_count = Float64(_t1_absolute_count - _t0_absolute_count) / Float64(N)
    print("MOJO_TIMING cytometry::absolute_count", _ns_absolute_count, _acc_absolute_count)
    var _result_absolute_count = absolute_count(0.5, 0.5)
    var _summary_absolute_count = _summary_float64(_result_absolute_count)
    print("MOJO_RESULT cytometry::absolute_count", _summary_absolute_count)
    var _acc_compensation_spillover: Float64 = 0.0
    var _t0_compensation_spillover = perf_counter_ns()
    for _ in range(N):
        _acc_compensation_spillover += compensation_spillover(0.5, 0.5, 0.5)
    var _t1_compensation_spillover = perf_counter_ns()
    var _ns_compensation_spillover = Float64(_t1_compensation_spillover - _t0_compensation_spillover) / Float64(N)
    print("MOJO_TIMING cytometry::compensation_spillover", _ns_compensation_spillover, _acc_compensation_spillover)
    var _result_compensation_spillover = compensation_spillover(0.5, 0.5, 0.5)
    var _summary_compensation_spillover = _summary_float64(_result_compensation_spillover)
    print("MOJO_RESULT cytometry::compensation_spillover", _summary_compensation_spillover)
    var _acc_sensitivity_lod_cytometry: Float64 = 0.0
    var _t0_sensitivity_lod_cytometry = perf_counter_ns()
    for _ in range(N):
        _acc_sensitivity_lod_cytometry += sensitivity_lod_cytometry(0.5, 0.5, 0.5)
    var _t1_sensitivity_lod_cytometry = perf_counter_ns()
    var _ns_sensitivity_lod_cytometry = Float64(_t1_sensitivity_lod_cytometry - _t0_sensitivity_lod_cytometry) / Float64(N)
    print("MOJO_TIMING cytometry::sensitivity_lod_cytometry", _ns_sensitivity_lod_cytometry, _acc_sensitivity_lod_cytometry)
    var _result_sensitivity_lod_cytometry = sensitivity_lod_cytometry(0.5, 0.5, 0.5)
    var _summary_sensitivity_lod_cytometry = _summary_float64(_result_sensitivity_lod_cytometry)
    print("MOJO_RESULT cytometry::sensitivity_lod_cytometry", _summary_sensitivity_lod_cytometry)
