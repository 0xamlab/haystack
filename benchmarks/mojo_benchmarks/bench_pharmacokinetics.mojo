"""bench_pharmacokinetics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from pharmacokinetics import one_compartment_oral, one_compartment_iv, half_life, elimination_rate, clearance, bioavailability, loading_dose, maintenance_dose, steady_state_concentration, time_to_peak, accumulation_factor, drug_auc_trapezoidal
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

    var _acc_one_compartment_oral: Float64 = 0.0
    var _t0_one_compartment_oral = perf_counter_ns()
    for _ in range(N):
        _acc_one_compartment_oral += one_compartment_oral(100.0, 0.8, 0.2, 10.0, 2.0)
    var _t1_one_compartment_oral = perf_counter_ns()
    var _ns_one_compartment_oral = Float64(_t1_one_compartment_oral - _t0_one_compartment_oral) / Float64(N)
    print("MOJO_TIMING pharmacokinetics::one_compartment_oral", _ns_one_compartment_oral, _acc_one_compartment_oral)
    var _result_one_compartment_oral = one_compartment_oral(100.0, 0.8, 0.2, 10.0, 2.0)
    var _summary_one_compartment_oral = _summary_float64(_result_one_compartment_oral)
    print("MOJO_RESULT pharmacokinetics::one_compartment_oral", _summary_one_compartment_oral)
    var _acc_one_compartment_iv: Float64 = 0.0
    var _t0_one_compartment_iv = perf_counter_ns()
    for _ in range(N):
        _acc_one_compartment_iv += one_compartment_iv(0.5, 0.5, 0.5, 0.5)
    var _t1_one_compartment_iv = perf_counter_ns()
    var _ns_one_compartment_iv = Float64(_t1_one_compartment_iv - _t0_one_compartment_iv) / Float64(N)
    print("MOJO_TIMING pharmacokinetics::one_compartment_iv", _ns_one_compartment_iv, _acc_one_compartment_iv)
    var _result_one_compartment_iv = one_compartment_iv(0.5, 0.5, 0.5, 0.5)
    var _summary_one_compartment_iv = _summary_float64(_result_one_compartment_iv)
    print("MOJO_RESULT pharmacokinetics::one_compartment_iv", _summary_one_compartment_iv)
    var _acc_half_life: Float64 = 0.0
    var _t0_half_life = perf_counter_ns()
    for _ in range(N):
        _acc_half_life += half_life(0.5)
    var _t1_half_life = perf_counter_ns()
    var _ns_half_life = Float64(_t1_half_life - _t0_half_life) / Float64(N)
    print("MOJO_TIMING pharmacokinetics::half_life", _ns_half_life, _acc_half_life)
    var _result_half_life = half_life(0.5)
    var _summary_half_life = _summary_float64(_result_half_life)
    print("MOJO_RESULT pharmacokinetics::half_life", _summary_half_life)
    var _acc_elimination_rate: Float64 = 0.0
    var _t0_elimination_rate = perf_counter_ns()
    for _ in range(N):
        _acc_elimination_rate += elimination_rate(0.5)
    var _t1_elimination_rate = perf_counter_ns()
    var _ns_elimination_rate = Float64(_t1_elimination_rate - _t0_elimination_rate) / Float64(N)
    print("MOJO_TIMING pharmacokinetics::elimination_rate", _ns_elimination_rate, _acc_elimination_rate)
    var _result_elimination_rate = elimination_rate(0.5)
    var _summary_elimination_rate = _summary_float64(_result_elimination_rate)
    print("MOJO_RESULT pharmacokinetics::elimination_rate", _summary_elimination_rate)
    var _acc_clearance: Float64 = 0.0
    var _t0_clearance = perf_counter_ns()
    for _ in range(N):
        _acc_clearance += clearance(0.5, 0.5)
    var _t1_clearance = perf_counter_ns()
    var _ns_clearance = Float64(_t1_clearance - _t0_clearance) / Float64(N)
    print("MOJO_TIMING pharmacokinetics::clearance", _ns_clearance, _acc_clearance)
    var _result_clearance = clearance(0.5, 0.5)
    var _summary_clearance = _summary_float64(_result_clearance)
    print("MOJO_RESULT pharmacokinetics::clearance", _summary_clearance)
    var _acc_bioavailability: Float64 = 0.0
    var _t0_bioavailability = perf_counter_ns()
    for _ in range(N):
        _acc_bioavailability += bioavailability(0.5, 0.5)
    var _t1_bioavailability = perf_counter_ns()
    var _ns_bioavailability = Float64(_t1_bioavailability - _t0_bioavailability) / Float64(N)
    print("MOJO_TIMING pharmacokinetics::bioavailability", _ns_bioavailability, _acc_bioavailability)
    var _result_bioavailability = bioavailability(0.5, 0.5)
    var _summary_bioavailability = _summary_float64(_result_bioavailability)
    print("MOJO_RESULT pharmacokinetics::bioavailability", _summary_bioavailability)
    var _acc_loading_dose: Float64 = 0.0
    var _t0_loading_dose = perf_counter_ns()
    for _ in range(N):
        _acc_loading_dose += loading_dose(0.5, 0.5)
    var _t1_loading_dose = perf_counter_ns()
    var _ns_loading_dose = Float64(_t1_loading_dose - _t0_loading_dose) / Float64(N)
    print("MOJO_TIMING pharmacokinetics::loading_dose", _ns_loading_dose, _acc_loading_dose)
    var _result_loading_dose = loading_dose(0.5, 0.5)
    var _summary_loading_dose = _summary_float64(_result_loading_dose)
    print("MOJO_RESULT pharmacokinetics::loading_dose", _summary_loading_dose)
    var _acc_maintenance_dose: Float64 = 0.0
    var _t0_maintenance_dose = perf_counter_ns()
    for _ in range(N):
        _acc_maintenance_dose += maintenance_dose(0.5, 0.5, 0.5)
    var _t1_maintenance_dose = perf_counter_ns()
    var _ns_maintenance_dose = Float64(_t1_maintenance_dose - _t0_maintenance_dose) / Float64(N)
    print("MOJO_TIMING pharmacokinetics::maintenance_dose", _ns_maintenance_dose, _acc_maintenance_dose)
    var _result_maintenance_dose = maintenance_dose(0.5, 0.5, 0.5)
    var _summary_maintenance_dose = _summary_float64(_result_maintenance_dose)
    print("MOJO_RESULT pharmacokinetics::maintenance_dose", _summary_maintenance_dose)
    var _acc_steady_state_concentration: Float64 = 0.0
    var _t0_steady_state_concentration = perf_counter_ns()
    for _ in range(N):
        _acc_steady_state_concentration += steady_state_concentration(0.5, 0.5, 0.5)
    var _t1_steady_state_concentration = perf_counter_ns()
    var _ns_steady_state_concentration = Float64(_t1_steady_state_concentration - _t0_steady_state_concentration) / Float64(N)
    print("MOJO_TIMING pharmacokinetics::steady_state_concentration", _ns_steady_state_concentration, _acc_steady_state_concentration)
    var _result_steady_state_concentration = steady_state_concentration(0.5, 0.5, 0.5)
    var _summary_steady_state_concentration = _summary_float64(_result_steady_state_concentration)
    print("MOJO_RESULT pharmacokinetics::steady_state_concentration", _summary_steady_state_concentration)
    var _acc_time_to_peak: Float64 = 0.0
    var _t0_time_to_peak = perf_counter_ns()
    for _ in range(N):
        _acc_time_to_peak += time_to_peak(0.8, 0.2)
    var _t1_time_to_peak = perf_counter_ns()
    var _ns_time_to_peak = Float64(_t1_time_to_peak - _t0_time_to_peak) / Float64(N)
    print("MOJO_TIMING pharmacokinetics::time_to_peak", _ns_time_to_peak, _acc_time_to_peak)
    var _result_time_to_peak = time_to_peak(0.8, 0.2)
    var _summary_time_to_peak = _summary_float64(_result_time_to_peak)
    print("MOJO_RESULT pharmacokinetics::time_to_peak", _summary_time_to_peak)
    var _acc_accumulation_factor: Float64 = 0.0
    var _t0_accumulation_factor = perf_counter_ns()
    for _ in range(N):
        _acc_accumulation_factor += accumulation_factor(0.5, 0.5)
    var _t1_accumulation_factor = perf_counter_ns()
    var _ns_accumulation_factor = Float64(_t1_accumulation_factor - _t0_accumulation_factor) / Float64(N)
    print("MOJO_TIMING pharmacokinetics::accumulation_factor", _ns_accumulation_factor, _acc_accumulation_factor)
    var _result_accumulation_factor = accumulation_factor(0.5, 0.5)
    var _summary_accumulation_factor = _summary_float64(_result_accumulation_factor)
    print("MOJO_RESULT pharmacokinetics::accumulation_factor", _summary_accumulation_factor)
    var _acc_drug_auc_trapezoidal: Float64 = 0.0
    var _t0_drug_auc_trapezoidal = perf_counter_ns()
    for _ in range(N):
        _acc_drug_auc_trapezoidal += drug_auc_trapezoidal(0.5, 0.5, 0.5, 0.5)
    var _t1_drug_auc_trapezoidal = perf_counter_ns()
    var _ns_drug_auc_trapezoidal = Float64(_t1_drug_auc_trapezoidal - _t0_drug_auc_trapezoidal) / Float64(N)
    print("MOJO_TIMING pharmacokinetics::drug_auc_trapezoidal", _ns_drug_auc_trapezoidal, _acc_drug_auc_trapezoidal)
    var _result_drug_auc_trapezoidal = drug_auc_trapezoidal(0.5, 0.5, 0.5, 0.5)
    var _summary_drug_auc_trapezoidal = _summary_float64(_result_drug_auc_trapezoidal)
    print("MOJO_RESULT pharmacokinetics::drug_auc_trapezoidal", _summary_drug_auc_trapezoidal)
