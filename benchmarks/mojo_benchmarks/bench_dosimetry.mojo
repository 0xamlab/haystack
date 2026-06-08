"""bench_dosimetry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from dosimetry import absorbed_dose, equivalent_dose, effective_dose, dose_rate, activity_decay, specific_activity, tenth_value_layer, buildup_factor, kerma, radiation_weighting
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

    var _acc_absorbed_dose: Float64 = 0.0
    var _t0_absorbed_dose = perf_counter_ns()
    for _ in range(N):
        _acc_absorbed_dose += absorbed_dose(0.5, 0.5)
    var _t1_absorbed_dose = perf_counter_ns()
    var _ns_absorbed_dose = Float64(_t1_absorbed_dose - _t0_absorbed_dose) / Float64(N)
    print("MOJO_TIMING dosimetry::absorbed_dose", _ns_absorbed_dose, _acc_absorbed_dose)
    var _result_absorbed_dose = absorbed_dose(0.5, 0.5)
    var _summary_absorbed_dose = _summary_float64(_result_absorbed_dose)
    print("MOJO_RESULT dosimetry::absorbed_dose", _summary_absorbed_dose)
    var _acc_equivalent_dose: Float64 = 0.0
    var _t0_equivalent_dose = perf_counter_ns()
    for _ in range(N):
        _acc_equivalent_dose += equivalent_dose(0.5, 0.5)
    var _t1_equivalent_dose = perf_counter_ns()
    var _ns_equivalent_dose = Float64(_t1_equivalent_dose - _t0_equivalent_dose) / Float64(N)
    print("MOJO_TIMING dosimetry::equivalent_dose", _ns_equivalent_dose, _acc_equivalent_dose)
    var _result_equivalent_dose = equivalent_dose(0.5, 0.5)
    var _summary_equivalent_dose = _summary_float64(_result_equivalent_dose)
    print("MOJO_RESULT dosimetry::equivalent_dose", _summary_equivalent_dose)
    var _acc_effective_dose: Float64 = 0.0
    var _t0_effective_dose = perf_counter_ns()
    for _ in range(N):
        _acc_effective_dose += effective_dose(0.5, 0.5)
    var _t1_effective_dose = perf_counter_ns()
    var _ns_effective_dose = Float64(_t1_effective_dose - _t0_effective_dose) / Float64(N)
    print("MOJO_TIMING dosimetry::effective_dose", _ns_effective_dose, _acc_effective_dose)
    var _result_effective_dose = effective_dose(0.5, 0.5)
    var _summary_effective_dose = _summary_float64(_result_effective_dose)
    print("MOJO_RESULT dosimetry::effective_dose", _summary_effective_dose)
    var _acc_dose_rate: Float64 = 0.0
    var _t0_dose_rate = perf_counter_ns()
    for _ in range(N):
        _acc_dose_rate += dose_rate(0.5, 0.5, 0.5)
    var _t1_dose_rate = perf_counter_ns()
    var _ns_dose_rate = Float64(_t1_dose_rate - _t0_dose_rate) / Float64(N)
    print("MOJO_TIMING dosimetry::dose_rate", _ns_dose_rate, _acc_dose_rate)
    var _result_dose_rate = dose_rate(0.5, 0.5, 0.5)
    var _summary_dose_rate = _summary_float64(_result_dose_rate)
    print("MOJO_RESULT dosimetry::dose_rate", _summary_dose_rate)
    var _acc_activity_decay: Float64 = 0.0
    var _t0_activity_decay = perf_counter_ns()
    for _ in range(N):
        _acc_activity_decay += activity_decay(0.5, 0.5, 0.5)
    var _t1_activity_decay = perf_counter_ns()
    var _ns_activity_decay = Float64(_t1_activity_decay - _t0_activity_decay) / Float64(N)
    print("MOJO_TIMING dosimetry::activity_decay", _ns_activity_decay, _acc_activity_decay)
    var _result_activity_decay = activity_decay(0.5, 0.5, 0.5)
    var _summary_activity_decay = _summary_float64(_result_activity_decay)
    print("MOJO_RESULT dosimetry::activity_decay", _summary_activity_decay)
    var _acc_specific_activity: Float64 = 0.0
    var _t0_specific_activity = perf_counter_ns()
    for _ in range(N):
        _acc_specific_activity += specific_activity(0.5, 0.5)
    var _t1_specific_activity = perf_counter_ns()
    var _ns_specific_activity = Float64(_t1_specific_activity - _t0_specific_activity) / Float64(N)
    print("MOJO_TIMING dosimetry::specific_activity", _ns_specific_activity, _acc_specific_activity)
    var _result_specific_activity = specific_activity(0.5, 0.5)
    var _summary_specific_activity = _summary_float64(_result_specific_activity)
    print("MOJO_RESULT dosimetry::specific_activity", _summary_specific_activity)
    var _acc_tenth_value_layer: Float64 = 0.0
    var _t0_tenth_value_layer = perf_counter_ns()
    for _ in range(N):
        _acc_tenth_value_layer += tenth_value_layer(0.5)
    var _t1_tenth_value_layer = perf_counter_ns()
    var _ns_tenth_value_layer = Float64(_t1_tenth_value_layer - _t0_tenth_value_layer) / Float64(N)
    print("MOJO_TIMING dosimetry::tenth_value_layer", _ns_tenth_value_layer, _acc_tenth_value_layer)
    var _result_tenth_value_layer = tenth_value_layer(0.5)
    var _summary_tenth_value_layer = _summary_float64(_result_tenth_value_layer)
    print("MOJO_RESULT dosimetry::tenth_value_layer", _summary_tenth_value_layer)
    var _acc_buildup_factor: Float64 = 0.0
    var _t0_buildup_factor = perf_counter_ns()
    for _ in range(N):
        _acc_buildup_factor += buildup_factor(0.5, 0.5, 0.5)
    var _t1_buildup_factor = perf_counter_ns()
    var _ns_buildup_factor = Float64(_t1_buildup_factor - _t0_buildup_factor) / Float64(N)
    print("MOJO_TIMING dosimetry::buildup_factor", _ns_buildup_factor, _acc_buildup_factor)
    var _result_buildup_factor = buildup_factor(0.5, 0.5, 0.5)
    var _summary_buildup_factor = _summary_float64(_result_buildup_factor)
    print("MOJO_RESULT dosimetry::buildup_factor", _summary_buildup_factor)
    var _acc_kerma: Float64 = 0.0
    var _t0_kerma = perf_counter_ns()
    for _ in range(N):
        _acc_kerma += kerma(0.5, 0.5)
    var _t1_kerma = perf_counter_ns()
    var _ns_kerma = Float64(_t1_kerma - _t0_kerma) / Float64(N)
    print("MOJO_TIMING dosimetry::kerma", _ns_kerma, _acc_kerma)
    var _result_kerma = kerma(0.5, 0.5)
    var _summary_kerma = _summary_float64(_result_kerma)
    print("MOJO_RESULT dosimetry::kerma", _summary_kerma)
    var _acc_radiation_weighting: Float64 = 0.0
    var _t0_radiation_weighting = perf_counter_ns()
    for _ in range(N):
        _acc_radiation_weighting += radiation_weighting(0.5)
    var _t1_radiation_weighting = perf_counter_ns()
    var _ns_radiation_weighting = Float64(_t1_radiation_weighting - _t0_radiation_weighting) / Float64(N)
    print("MOJO_TIMING dosimetry::radiation_weighting", _ns_radiation_weighting, _acc_radiation_weighting)
    var _result_radiation_weighting = radiation_weighting(0.5)
    var _summary_radiation_weighting = _summary_float64(_result_radiation_weighting)
    print("MOJO_RESULT dosimetry::radiation_weighting", _summary_radiation_weighting)
