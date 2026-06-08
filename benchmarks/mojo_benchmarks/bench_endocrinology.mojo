"""bench_endocrinology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from endocrinology import hormone_clearance_rate, receptor_binding_bmax, feedback_gain, hormone_pulsatility, cortisol_circadian, insulin_sensitivity_index, thyroid_free_fraction, growth_rate_igf, testosterone_free, negative_feedback_strength
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

    var _acc_hormone_clearance_rate: Float64 = 0.0
    var _t0_hormone_clearance_rate = perf_counter_ns()
    for _ in range(N):
        _acc_hormone_clearance_rate += hormone_clearance_rate(0.5, 0.5)
    var _t1_hormone_clearance_rate = perf_counter_ns()
    var _ns_hormone_clearance_rate = Float64(_t1_hormone_clearance_rate - _t0_hormone_clearance_rate) / Float64(N)
    print("MOJO_TIMING endocrinology::hormone_clearance_rate", _ns_hormone_clearance_rate, _acc_hormone_clearance_rate)
    var _result_hormone_clearance_rate = hormone_clearance_rate(0.5, 0.5)
    var _summary_hormone_clearance_rate = _summary_float64(_result_hormone_clearance_rate)
    print("MOJO_RESULT endocrinology::hormone_clearance_rate", _summary_hormone_clearance_rate)
    var _acc_receptor_binding_bmax: Float64 = 0.0
    var _t0_receptor_binding_bmax = perf_counter_ns()
    for _ in range(N):
        _acc_receptor_binding_bmax += receptor_binding_bmax(0.5, 0.5, 0.5)
    var _t1_receptor_binding_bmax = perf_counter_ns()
    var _ns_receptor_binding_bmax = Float64(_t1_receptor_binding_bmax - _t0_receptor_binding_bmax) / Float64(N)
    print("MOJO_TIMING endocrinology::receptor_binding_bmax", _ns_receptor_binding_bmax, _acc_receptor_binding_bmax)
    var _result_receptor_binding_bmax = receptor_binding_bmax(0.5, 0.5, 0.5)
    var _summary_receptor_binding_bmax = _summary_float64(_result_receptor_binding_bmax)
    print("MOJO_RESULT endocrinology::receptor_binding_bmax", _summary_receptor_binding_bmax)
    var _acc_feedback_gain: Float64 = 0.0
    var _t0_feedback_gain = perf_counter_ns()
    for _ in range(N):
        _acc_feedback_gain += feedback_gain(0.5, 0.5)
    var _t1_feedback_gain = perf_counter_ns()
    var _ns_feedback_gain = Float64(_t1_feedback_gain - _t0_feedback_gain) / Float64(N)
    print("MOJO_TIMING endocrinology::feedback_gain", _ns_feedback_gain, _acc_feedback_gain)
    var _result_feedback_gain = feedback_gain(0.5, 0.5)
    var _summary_feedback_gain = _summary_float64(_result_feedback_gain)
    print("MOJO_RESULT endocrinology::feedback_gain", _summary_feedback_gain)
    var _acc_hormone_pulsatility: Float64 = 0.0
    var _t0_hormone_pulsatility = perf_counter_ns()
    for _ in range(N):
        _acc_hormone_pulsatility += hormone_pulsatility(0.5, 0.5)
    var _t1_hormone_pulsatility = perf_counter_ns()
    var _ns_hormone_pulsatility = Float64(_t1_hormone_pulsatility - _t0_hormone_pulsatility) / Float64(N)
    print("MOJO_TIMING endocrinology::hormone_pulsatility", _ns_hormone_pulsatility, _acc_hormone_pulsatility)
    var _result_hormone_pulsatility = hormone_pulsatility(0.5, 0.5)
    var _summary_hormone_pulsatility = _summary_float64(_result_hormone_pulsatility)
    print("MOJO_RESULT endocrinology::hormone_pulsatility", _summary_hormone_pulsatility)
    var _acc_cortisol_circadian: Float64 = 0.0
    var _t0_cortisol_circadian = perf_counter_ns()
    for _ in range(N):
        _acc_cortisol_circadian += cortisol_circadian(0.5, 0.5, 0.5)
    var _t1_cortisol_circadian = perf_counter_ns()
    var _ns_cortisol_circadian = Float64(_t1_cortisol_circadian - _t0_cortisol_circadian) / Float64(N)
    print("MOJO_TIMING endocrinology::cortisol_circadian", _ns_cortisol_circadian, _acc_cortisol_circadian)
    var _result_cortisol_circadian = cortisol_circadian(0.5, 0.5, 0.5)
    var _summary_cortisol_circadian = _summary_float64(_result_cortisol_circadian)
    print("MOJO_RESULT endocrinology::cortisol_circadian", _summary_cortisol_circadian)
    var _acc_insulin_sensitivity_index: Float64 = 0.0
    var _t0_insulin_sensitivity_index = perf_counter_ns()
    for _ in range(N):
        _acc_insulin_sensitivity_index += insulin_sensitivity_index(0.5, 0.5)
    var _t1_insulin_sensitivity_index = perf_counter_ns()
    var _ns_insulin_sensitivity_index = Float64(_t1_insulin_sensitivity_index - _t0_insulin_sensitivity_index) / Float64(N)
    print("MOJO_TIMING endocrinology::insulin_sensitivity_index", _ns_insulin_sensitivity_index, _acc_insulin_sensitivity_index)
    var _result_insulin_sensitivity_index = insulin_sensitivity_index(0.5, 0.5)
    var _summary_insulin_sensitivity_index = _summary_float64(_result_insulin_sensitivity_index)
    print("MOJO_RESULT endocrinology::insulin_sensitivity_index", _summary_insulin_sensitivity_index)
    var _acc_thyroid_free_fraction: Float64 = 0.0
    var _t0_thyroid_free_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_thyroid_free_fraction += thyroid_free_fraction(0.5, 0.5, 0.5)
    var _t1_thyroid_free_fraction = perf_counter_ns()
    var _ns_thyroid_free_fraction = Float64(_t1_thyroid_free_fraction - _t0_thyroid_free_fraction) / Float64(N)
    print("MOJO_TIMING endocrinology::thyroid_free_fraction", _ns_thyroid_free_fraction, _acc_thyroid_free_fraction)
    var _result_thyroid_free_fraction = thyroid_free_fraction(0.5, 0.5, 0.5)
    var _summary_thyroid_free_fraction = _summary_float64(_result_thyroid_free_fraction)
    print("MOJO_RESULT endocrinology::thyroid_free_fraction", _summary_thyroid_free_fraction)
    var _acc_growth_rate_igf: Float64 = 0.0
    var _t0_growth_rate_igf = perf_counter_ns()
    for _ in range(N):
        _acc_growth_rate_igf += growth_rate_igf(0.5, 0.5, 0.5)
    var _t1_growth_rate_igf = perf_counter_ns()
    var _ns_growth_rate_igf = Float64(_t1_growth_rate_igf - _t0_growth_rate_igf) / Float64(N)
    print("MOJO_TIMING endocrinology::growth_rate_igf", _ns_growth_rate_igf, _acc_growth_rate_igf)
    var _result_growth_rate_igf = growth_rate_igf(0.5, 0.5, 0.5)
    var _summary_growth_rate_igf = _summary_float64(_result_growth_rate_igf)
    print("MOJO_RESULT endocrinology::growth_rate_igf", _summary_growth_rate_igf)
    var _acc_testosterone_free: Float64 = 0.0
    var _t0_testosterone_free = perf_counter_ns()
    for _ in range(N):
        _acc_testosterone_free += testosterone_free(0.5, 0.5, 0.5)
    var _t1_testosterone_free = perf_counter_ns()
    var _ns_testosterone_free = Float64(_t1_testosterone_free - _t0_testosterone_free) / Float64(N)
    print("MOJO_TIMING endocrinology::testosterone_free", _ns_testosterone_free, _acc_testosterone_free)
    var _result_testosterone_free = testosterone_free(0.5, 0.5, 0.5)
    var _summary_testosterone_free = _summary_float64(_result_testosterone_free)
    print("MOJO_RESULT endocrinology::testosterone_free", _summary_testosterone_free)
    var _acc_negative_feedback_strength: Float64 = 0.0
    var _t0_negative_feedback_strength = perf_counter_ns()
    for _ in range(N):
        _acc_negative_feedback_strength += negative_feedback_strength(0.5, 0.5)
    var _t1_negative_feedback_strength = perf_counter_ns()
    var _ns_negative_feedback_strength = Float64(_t1_negative_feedback_strength - _t0_negative_feedback_strength) / Float64(N)
    print("MOJO_TIMING endocrinology::negative_feedback_strength", _ns_negative_feedback_strength, _acc_negative_feedback_strength)
    var _result_negative_feedback_strength = negative_feedback_strength(0.5, 0.5)
    var _summary_negative_feedback_strength = _summary_float64(_result_negative_feedback_strength)
    print("MOJO_RESULT endocrinology::negative_feedback_strength", _summary_negative_feedback_strength)
