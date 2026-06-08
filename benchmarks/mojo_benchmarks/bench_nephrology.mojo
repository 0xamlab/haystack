"""bench_nephrology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from nephrology import gfr_ckd_epi, creatinine_clearance_cockroft, fractional_excretion_sodium, urine_anion_gap, transtubular_potassium_gradient, renal_plasma_flow, filtration_fraction, osmolar_clearance, free_water_clearance, protein_creatinine_ratio
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

    var _acc_gfr_ckd_epi: Float64 = 0.0
    var _t0_gfr_ckd_epi = perf_counter_ns()
    for _ in range(N):
        _acc_gfr_ckd_epi += gfr_ckd_epi(0.5, 0.5, 0.5)
    var _t1_gfr_ckd_epi = perf_counter_ns()
    var _ns_gfr_ckd_epi = Float64(_t1_gfr_ckd_epi - _t0_gfr_ckd_epi) / Float64(N)
    print("MOJO_TIMING nephrology::gfr_ckd_epi", _ns_gfr_ckd_epi, _acc_gfr_ckd_epi)
    var _result_gfr_ckd_epi = gfr_ckd_epi(0.5, 0.5, 0.5)
    var _summary_gfr_ckd_epi = _summary_float64(_result_gfr_ckd_epi)
    print("MOJO_RESULT nephrology::gfr_ckd_epi", _summary_gfr_ckd_epi)
    var _acc_creatinine_clearance_cockroft: Float64 = 0.0
    var _t0_creatinine_clearance_cockroft = perf_counter_ns()
    for _ in range(N):
        _acc_creatinine_clearance_cockroft += creatinine_clearance_cockroft(0.5, 0.5, 0.5, 0.5)
    var _t1_creatinine_clearance_cockroft = perf_counter_ns()
    var _ns_creatinine_clearance_cockroft = Float64(_t1_creatinine_clearance_cockroft - _t0_creatinine_clearance_cockroft) / Float64(N)
    print("MOJO_TIMING nephrology::creatinine_clearance_cockroft", _ns_creatinine_clearance_cockroft, _acc_creatinine_clearance_cockroft)
    var _result_creatinine_clearance_cockroft = creatinine_clearance_cockroft(0.5, 0.5, 0.5, 0.5)
    var _summary_creatinine_clearance_cockroft = _summary_float64(_result_creatinine_clearance_cockroft)
    print("MOJO_RESULT nephrology::creatinine_clearance_cockroft", _summary_creatinine_clearance_cockroft)
    var _acc_fractional_excretion_sodium: Float64 = 0.0
    var _t0_fractional_excretion_sodium = perf_counter_ns()
    for _ in range(N):
        _acc_fractional_excretion_sodium += fractional_excretion_sodium(0.5, 0.5, 0.5, 0.5)
    var _t1_fractional_excretion_sodium = perf_counter_ns()
    var _ns_fractional_excretion_sodium = Float64(_t1_fractional_excretion_sodium - _t0_fractional_excretion_sodium) / Float64(N)
    print("MOJO_TIMING nephrology::fractional_excretion_sodium", _ns_fractional_excretion_sodium, _acc_fractional_excretion_sodium)
    var _result_fractional_excretion_sodium = fractional_excretion_sodium(0.5, 0.5, 0.5, 0.5)
    var _summary_fractional_excretion_sodium = _summary_float64(_result_fractional_excretion_sodium)
    print("MOJO_RESULT nephrology::fractional_excretion_sodium", _summary_fractional_excretion_sodium)
    var _acc_urine_anion_gap: Float64 = 0.0
    var _t0_urine_anion_gap = perf_counter_ns()
    for _ in range(N):
        _acc_urine_anion_gap += urine_anion_gap(0.5, 0.5, 0.5)
    var _t1_urine_anion_gap = perf_counter_ns()
    var _ns_urine_anion_gap = Float64(_t1_urine_anion_gap - _t0_urine_anion_gap) / Float64(N)
    print("MOJO_TIMING nephrology::urine_anion_gap", _ns_urine_anion_gap, _acc_urine_anion_gap)
    var _result_urine_anion_gap = urine_anion_gap(0.5, 0.5, 0.5)
    var _summary_urine_anion_gap = _summary_float64(_result_urine_anion_gap)
    print("MOJO_RESULT nephrology::urine_anion_gap", _summary_urine_anion_gap)
    var _acc_transtubular_potassium_gradient: Float64 = 0.0
    var _t0_transtubular_potassium_gradient = perf_counter_ns()
    for _ in range(N):
        _acc_transtubular_potassium_gradient += transtubular_potassium_gradient(0.5, 0.5, 0.5, 0.5)
    var _t1_transtubular_potassium_gradient = perf_counter_ns()
    var _ns_transtubular_potassium_gradient = Float64(_t1_transtubular_potassium_gradient - _t0_transtubular_potassium_gradient) / Float64(N)
    print("MOJO_TIMING nephrology::transtubular_potassium_gradient", _ns_transtubular_potassium_gradient, _acc_transtubular_potassium_gradient)
    var _result_transtubular_potassium_gradient = transtubular_potassium_gradient(0.5, 0.5, 0.5, 0.5)
    var _summary_transtubular_potassium_gradient = _summary_float64(_result_transtubular_potassium_gradient)
    print("MOJO_RESULT nephrology::transtubular_potassium_gradient", _summary_transtubular_potassium_gradient)
    var _acc_renal_plasma_flow: Float64 = 0.0
    var _t0_renal_plasma_flow = perf_counter_ns()
    for _ in range(N):
        _acc_renal_plasma_flow += renal_plasma_flow(0.5, 0.5, 0.5)
    var _t1_renal_plasma_flow = perf_counter_ns()
    var _ns_renal_plasma_flow = Float64(_t1_renal_plasma_flow - _t0_renal_plasma_flow) / Float64(N)
    print("MOJO_TIMING nephrology::renal_plasma_flow", _ns_renal_plasma_flow, _acc_renal_plasma_flow)
    var _result_renal_plasma_flow = renal_plasma_flow(0.5, 0.5, 0.5)
    var _summary_renal_plasma_flow = _summary_float64(_result_renal_plasma_flow)
    print("MOJO_RESULT nephrology::renal_plasma_flow", _summary_renal_plasma_flow)
    var _acc_filtration_fraction: Float64 = 0.0
    var _t0_filtration_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_filtration_fraction += filtration_fraction(0.5, 0.5)
    var _t1_filtration_fraction = perf_counter_ns()
    var _ns_filtration_fraction = Float64(_t1_filtration_fraction - _t0_filtration_fraction) / Float64(N)
    print("MOJO_TIMING nephrology::filtration_fraction", _ns_filtration_fraction, _acc_filtration_fraction)
    var _result_filtration_fraction = filtration_fraction(0.5, 0.5)
    var _summary_filtration_fraction = _summary_float64(_result_filtration_fraction)
    print("MOJO_RESULT nephrology::filtration_fraction", _summary_filtration_fraction)
    var _acc_osmolar_clearance: Float64 = 0.0
    var _t0_osmolar_clearance = perf_counter_ns()
    for _ in range(N):
        _acc_osmolar_clearance += osmolar_clearance(0.5, 0.5, 0.5)
    var _t1_osmolar_clearance = perf_counter_ns()
    var _ns_osmolar_clearance = Float64(_t1_osmolar_clearance - _t0_osmolar_clearance) / Float64(N)
    print("MOJO_TIMING nephrology::osmolar_clearance", _ns_osmolar_clearance, _acc_osmolar_clearance)
    var _result_osmolar_clearance = osmolar_clearance(0.5, 0.5, 0.5)
    var _summary_osmolar_clearance = _summary_float64(_result_osmolar_clearance)
    print("MOJO_RESULT nephrology::osmolar_clearance", _summary_osmolar_clearance)
    var _acc_free_water_clearance: Float64 = 0.0
    var _t0_free_water_clearance = perf_counter_ns()
    for _ in range(N):
        _acc_free_water_clearance += free_water_clearance(0.5, 0.5)
    var _t1_free_water_clearance = perf_counter_ns()
    var _ns_free_water_clearance = Float64(_t1_free_water_clearance - _t0_free_water_clearance) / Float64(N)
    print("MOJO_TIMING nephrology::free_water_clearance", _ns_free_water_clearance, _acc_free_water_clearance)
    var _result_free_water_clearance = free_water_clearance(0.5, 0.5)
    var _summary_free_water_clearance = _summary_float64(_result_free_water_clearance)
    print("MOJO_RESULT nephrology::free_water_clearance", _summary_free_water_clearance)
    var _acc_protein_creatinine_ratio: Float64 = 0.0
    var _t0_protein_creatinine_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_protein_creatinine_ratio += protein_creatinine_ratio(0.5, 0.5)
    var _t1_protein_creatinine_ratio = perf_counter_ns()
    var _ns_protein_creatinine_ratio = Float64(_t1_protein_creatinine_ratio - _t0_protein_creatinine_ratio) / Float64(N)
    print("MOJO_TIMING nephrology::protein_creatinine_ratio", _ns_protein_creatinine_ratio, _acc_protein_creatinine_ratio)
    var _result_protein_creatinine_ratio = protein_creatinine_ratio(0.5, 0.5)
    var _summary_protein_creatinine_ratio = _summary_float64(_result_protein_creatinine_ratio)
    print("MOJO_RESULT nephrology::protein_creatinine_ratio", _summary_protein_creatinine_ratio)
