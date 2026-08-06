"""bench_toxicokinetics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from toxicokinetics import internal_dose, peak_plasma_concentration, time_to_peak, plasma_auc, apparent_volume_distribution, elimination_half_life, systemic_clearance, bioconcentration_factor, toxic_equivalency_factor, margin_of_exposure
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

    var _acc_internal_dose: Float64 = 0.0
    var _t0_internal_dose = perf_counter_ns()
    for _ in range(N):
        _acc_internal_dose += internal_dose(0.5, 0.5)
    var _t1_internal_dose = perf_counter_ns()
    var _ns_internal_dose = Float64(_t1_internal_dose - _t0_internal_dose) / Float64(N)
    print("MOJO_TIMING toxicokinetics::internal_dose", _ns_internal_dose, _acc_internal_dose)
    var _result_internal_dose = internal_dose(0.5, 0.5)
    var _summary_internal_dose = _summary_float64(_result_internal_dose)
    print("MOJO_RESULT toxicokinetics::internal_dose", _summary_internal_dose)
    var _acc_peak_plasma_concentration: Float64 = 0.0
    var _t0_peak_plasma_concentration = perf_counter_ns()
    for _ in range(N):
        _acc_peak_plasma_concentration += peak_plasma_concentration(0.5, 0.5)
    var _t1_peak_plasma_concentration = perf_counter_ns()
    var _ns_peak_plasma_concentration = Float64(_t1_peak_plasma_concentration - _t0_peak_plasma_concentration) / Float64(N)
    print("MOJO_TIMING toxicokinetics::peak_plasma_concentration", _ns_peak_plasma_concentration, _acc_peak_plasma_concentration)
    var _result_peak_plasma_concentration = peak_plasma_concentration(0.5, 0.5)
    var _summary_peak_plasma_concentration = _summary_float64(_result_peak_plasma_concentration)
    print("MOJO_RESULT toxicokinetics::peak_plasma_concentration", _summary_peak_plasma_concentration)
    var _acc_time_to_peak: Float64 = 0.0
    var _t0_time_to_peak = perf_counter_ns()
    for _ in range(N):
        _acc_time_to_peak += time_to_peak(0.5, 0.5)
    var _t1_time_to_peak = perf_counter_ns()
    var _ns_time_to_peak = Float64(_t1_time_to_peak - _t0_time_to_peak) / Float64(N)
    print("MOJO_TIMING toxicokinetics::time_to_peak", _ns_time_to_peak, _acc_time_to_peak)
    var _result_time_to_peak = time_to_peak(0.5, 0.5)
    var _summary_time_to_peak = _summary_float64(_result_time_to_peak)
    print("MOJO_RESULT toxicokinetics::time_to_peak", _summary_time_to_peak)
    var _acc_plasma_auc: Float64 = 0.0
    var _t0_plasma_auc = perf_counter_ns()
    for _ in range(N):
        _acc_plasma_auc += plasma_auc(0.5, 0.5, 0.5, 0.5)
    var _t1_plasma_auc = perf_counter_ns()
    var _ns_plasma_auc = Float64(_t1_plasma_auc - _t0_plasma_auc) / Float64(N)
    print("MOJO_TIMING toxicokinetics::plasma_auc", _ns_plasma_auc, _acc_plasma_auc)
    var _result_plasma_auc = plasma_auc(0.5, 0.5, 0.5, 0.5)
    var _summary_plasma_auc = _summary_float64(_result_plasma_auc)
    print("MOJO_RESULT toxicokinetics::plasma_auc", _summary_plasma_auc)
    var _acc_apparent_volume_distribution: Float64 = 0.0
    var _t0_apparent_volume_distribution = perf_counter_ns()
    for _ in range(N):
        _acc_apparent_volume_distribution += apparent_volume_distribution(0.5, 0.5)
    var _t1_apparent_volume_distribution = perf_counter_ns()
    var _ns_apparent_volume_distribution = Float64(_t1_apparent_volume_distribution - _t0_apparent_volume_distribution) / Float64(N)
    print("MOJO_TIMING toxicokinetics::apparent_volume_distribution", _ns_apparent_volume_distribution, _acc_apparent_volume_distribution)
    var _result_apparent_volume_distribution = apparent_volume_distribution(0.5, 0.5)
    var _summary_apparent_volume_distribution = _summary_float64(_result_apparent_volume_distribution)
    print("MOJO_RESULT toxicokinetics::apparent_volume_distribution", _summary_apparent_volume_distribution)
    var _acc_elimination_half_life: Float64 = 0.0
    var _t0_elimination_half_life = perf_counter_ns()
    for _ in range(N):
        _acc_elimination_half_life += elimination_half_life(0.5)
    var _t1_elimination_half_life = perf_counter_ns()
    var _ns_elimination_half_life = Float64(_t1_elimination_half_life - _t0_elimination_half_life) / Float64(N)
    print("MOJO_TIMING toxicokinetics::elimination_half_life", _ns_elimination_half_life, _acc_elimination_half_life)
    var _result_elimination_half_life = elimination_half_life(0.5)
    var _summary_elimination_half_life = _summary_float64(_result_elimination_half_life)
    print("MOJO_RESULT toxicokinetics::elimination_half_life", _summary_elimination_half_life)
    var _acc_systemic_clearance: Float64 = 0.0
    var _t0_systemic_clearance = perf_counter_ns()
    for _ in range(N):
        _acc_systemic_clearance += systemic_clearance(0.5, 0.5)
    var _t1_systemic_clearance = perf_counter_ns()
    var _ns_systemic_clearance = Float64(_t1_systemic_clearance - _t0_systemic_clearance) / Float64(N)
    print("MOJO_TIMING toxicokinetics::systemic_clearance", _ns_systemic_clearance, _acc_systemic_clearance)
    var _result_systemic_clearance = systemic_clearance(0.5, 0.5)
    var _summary_systemic_clearance = _summary_float64(_result_systemic_clearance)
    print("MOJO_RESULT toxicokinetics::systemic_clearance", _summary_systemic_clearance)
    var _acc_bioconcentration_factor: Float64 = 0.0
    var _t0_bioconcentration_factor = perf_counter_ns()
    for _ in range(N):
        _acc_bioconcentration_factor += bioconcentration_factor(0.5, 0.5)
    var _t1_bioconcentration_factor = perf_counter_ns()
    var _ns_bioconcentration_factor = Float64(_t1_bioconcentration_factor - _t0_bioconcentration_factor) / Float64(N)
    print("MOJO_TIMING toxicokinetics::bioconcentration_factor", _ns_bioconcentration_factor, _acc_bioconcentration_factor)
    var _result_bioconcentration_factor = bioconcentration_factor(0.5, 0.5)
    var _summary_bioconcentration_factor = _summary_float64(_result_bioconcentration_factor)
    print("MOJO_RESULT toxicokinetics::bioconcentration_factor", _summary_bioconcentration_factor)
    var _acc_toxic_equivalency_factor: Float64 = 0.0
    var _t0_toxic_equivalency_factor = perf_counter_ns()
    for _ in range(N):
        _acc_toxic_equivalency_factor += toxic_equivalency_factor(0.5, 0.5)
    var _t1_toxic_equivalency_factor = perf_counter_ns()
    var _ns_toxic_equivalency_factor = Float64(_t1_toxic_equivalency_factor - _t0_toxic_equivalency_factor) / Float64(N)
    print("MOJO_TIMING toxicokinetics::toxic_equivalency_factor", _ns_toxic_equivalency_factor, _acc_toxic_equivalency_factor)
    var _result_toxic_equivalency_factor = toxic_equivalency_factor(0.5, 0.5)
    var _summary_toxic_equivalency_factor = _summary_float64(_result_toxic_equivalency_factor)
    print("MOJO_RESULT toxicokinetics::toxic_equivalency_factor", _summary_toxic_equivalency_factor)
    var _acc_margin_of_exposure: Float64 = 0.0
    var _t0_margin_of_exposure = perf_counter_ns()
    for _ in range(N):
        _acc_margin_of_exposure += margin_of_exposure(0.5, 0.5)
    var _t1_margin_of_exposure = perf_counter_ns()
    var _ns_margin_of_exposure = Float64(_t1_margin_of_exposure - _t0_margin_of_exposure) / Float64(N)
    print("MOJO_TIMING toxicokinetics::margin_of_exposure", _ns_margin_of_exposure, _acc_margin_of_exposure)
    var _result_margin_of_exposure = margin_of_exposure(0.5, 0.5)
    var _summary_margin_of_exposure = _summary_float64(_result_margin_of_exposure)
    print("MOJO_RESULT toxicokinetics::margin_of_exposure", _summary_margin_of_exposure)
