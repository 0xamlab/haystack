"""bench_pharmacology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from pharmacology import hill_equation, therapeutic_index, drug_bioavailability, receptor_occupancy, drug_protein_binding, volume_of_distribution, clearance_from_halflife, steady_state_concentration, loading_dose, drug_interaction_index
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

    var _acc_hill_equation: Float64 = 0.0
    var _t0_hill_equation = perf_counter_ns()
    for _ in range(N):
        _acc_hill_equation += hill_equation(0.5, 0.5, 0.5, 0.5)
    var _t1_hill_equation = perf_counter_ns()
    var _ns_hill_equation = Float64(_t1_hill_equation - _t0_hill_equation) / Float64(N)
    print("MOJO_TIMING pharmacology::hill_equation", _ns_hill_equation, _acc_hill_equation)
    var _result_hill_equation = hill_equation(0.5, 0.5, 0.5, 0.5)
    var _summary_hill_equation = _summary_float64(_result_hill_equation)
    print("MOJO_RESULT pharmacology::hill_equation", _summary_hill_equation)
    var _acc_therapeutic_index: Float64 = 0.0
    var _t0_therapeutic_index = perf_counter_ns()
    for _ in range(N):
        _acc_therapeutic_index += therapeutic_index(0.5, 0.5)
    var _t1_therapeutic_index = perf_counter_ns()
    var _ns_therapeutic_index = Float64(_t1_therapeutic_index - _t0_therapeutic_index) / Float64(N)
    print("MOJO_TIMING pharmacology::therapeutic_index", _ns_therapeutic_index, _acc_therapeutic_index)
    var _result_therapeutic_index = therapeutic_index(0.5, 0.5)
    var _summary_therapeutic_index = _summary_float64(_result_therapeutic_index)
    print("MOJO_RESULT pharmacology::therapeutic_index", _summary_therapeutic_index)
    var _acc_drug_bioavailability: Float64 = 0.0
    var _t0_drug_bioavailability = perf_counter_ns()
    for _ in range(N):
        _acc_drug_bioavailability += drug_bioavailability(0.5, 0.5, 0.5, 0.5)
    var _t1_drug_bioavailability = perf_counter_ns()
    var _ns_drug_bioavailability = Float64(_t1_drug_bioavailability - _t0_drug_bioavailability) / Float64(N)
    print("MOJO_TIMING pharmacology::drug_bioavailability", _ns_drug_bioavailability, _acc_drug_bioavailability)
    var _result_drug_bioavailability = drug_bioavailability(0.5, 0.5, 0.5, 0.5)
    var _summary_drug_bioavailability = _summary_float64(_result_drug_bioavailability)
    print("MOJO_RESULT pharmacology::drug_bioavailability", _summary_drug_bioavailability)
    var _acc_receptor_occupancy: Float64 = 0.0
    var _t0_receptor_occupancy = perf_counter_ns()
    for _ in range(N):
        _acc_receptor_occupancy += receptor_occupancy(0.5, 0.5)
    var _t1_receptor_occupancy = perf_counter_ns()
    var _ns_receptor_occupancy = Float64(_t1_receptor_occupancy - _t0_receptor_occupancy) / Float64(N)
    print("MOJO_TIMING pharmacology::receptor_occupancy", _ns_receptor_occupancy, _acc_receptor_occupancy)
    var _result_receptor_occupancy = receptor_occupancy(0.5, 0.5)
    var _summary_receptor_occupancy = _summary_float64(_result_receptor_occupancy)
    print("MOJO_RESULT pharmacology::receptor_occupancy", _summary_receptor_occupancy)
    var _acc_drug_protein_binding: Float64 = 0.0
    var _t0_drug_protein_binding = perf_counter_ns()
    for _ in range(N):
        _acc_drug_protein_binding += drug_protein_binding(0.5)
    var _t1_drug_protein_binding = perf_counter_ns()
    var _ns_drug_protein_binding = Float64(_t1_drug_protein_binding - _t0_drug_protein_binding) / Float64(N)
    print("MOJO_TIMING pharmacology::drug_protein_binding", _ns_drug_protein_binding, _acc_drug_protein_binding)
    var _result_drug_protein_binding = drug_protein_binding(0.5)
    var _summary_drug_protein_binding = _summary_float64(_result_drug_protein_binding)
    print("MOJO_RESULT pharmacology::drug_protein_binding", _summary_drug_protein_binding)
    var _acc_volume_of_distribution: Float64 = 0.0
    var _t0_volume_of_distribution = perf_counter_ns()
    for _ in range(N):
        _acc_volume_of_distribution += volume_of_distribution(0.5, 0.5)
    var _t1_volume_of_distribution = perf_counter_ns()
    var _ns_volume_of_distribution = Float64(_t1_volume_of_distribution - _t0_volume_of_distribution) / Float64(N)
    print("MOJO_TIMING pharmacology::volume_of_distribution", _ns_volume_of_distribution, _acc_volume_of_distribution)
    var _result_volume_of_distribution = volume_of_distribution(0.5, 0.5)
    var _summary_volume_of_distribution = _summary_float64(_result_volume_of_distribution)
    print("MOJO_RESULT pharmacology::volume_of_distribution", _summary_volume_of_distribution)
    var _acc_clearance_from_halflife: Float64 = 0.0
    var _t0_clearance_from_halflife = perf_counter_ns()
    for _ in range(N):
        _acc_clearance_from_halflife += clearance_from_halflife(0.5, 0.5)
    var _t1_clearance_from_halflife = perf_counter_ns()
    var _ns_clearance_from_halflife = Float64(_t1_clearance_from_halflife - _t0_clearance_from_halflife) / Float64(N)
    print("MOJO_TIMING pharmacology::clearance_from_halflife", _ns_clearance_from_halflife, _acc_clearance_from_halflife)
    var _result_clearance_from_halflife = clearance_from_halflife(0.5, 0.5)
    var _summary_clearance_from_halflife = _summary_float64(_result_clearance_from_halflife)
    print("MOJO_RESULT pharmacology::clearance_from_halflife", _summary_clearance_from_halflife)
    var _acc_steady_state_concentration: Float64 = 0.0
    var _t0_steady_state_concentration = perf_counter_ns()
    for _ in range(N):
        _acc_steady_state_concentration += steady_state_concentration(0.5, 0.5, 0.5, 0.5)
    var _t1_steady_state_concentration = perf_counter_ns()
    var _ns_steady_state_concentration = Float64(_t1_steady_state_concentration - _t0_steady_state_concentration) / Float64(N)
    print("MOJO_TIMING pharmacology::steady_state_concentration", _ns_steady_state_concentration, _acc_steady_state_concentration)
    var _result_steady_state_concentration = steady_state_concentration(0.5, 0.5, 0.5, 0.5)
    var _summary_steady_state_concentration = _summary_float64(_result_steady_state_concentration)
    print("MOJO_RESULT pharmacology::steady_state_concentration", _summary_steady_state_concentration)
    var _acc_loading_dose: Float64 = 0.0
    var _t0_loading_dose = perf_counter_ns()
    for _ in range(N):
        _acc_loading_dose += loading_dose(0.5, 0.5)
    var _t1_loading_dose = perf_counter_ns()
    var _ns_loading_dose = Float64(_t1_loading_dose - _t0_loading_dose) / Float64(N)
    print("MOJO_TIMING pharmacology::loading_dose", _ns_loading_dose, _acc_loading_dose)
    var _result_loading_dose = loading_dose(0.5, 0.5)
    var _summary_loading_dose = _summary_float64(_result_loading_dose)
    print("MOJO_RESULT pharmacology::loading_dose", _summary_loading_dose)
    var _acc_drug_interaction_index: Float64 = 0.0
    var _t0_drug_interaction_index = perf_counter_ns()
    for _ in range(N):
        _acc_drug_interaction_index += drug_interaction_index(0.5, 0.5, 0.5, 0.5)
    var _t1_drug_interaction_index = perf_counter_ns()
    var _ns_drug_interaction_index = Float64(_t1_drug_interaction_index - _t0_drug_interaction_index) / Float64(N)
    print("MOJO_TIMING pharmacology::drug_interaction_index", _ns_drug_interaction_index, _acc_drug_interaction_index)
    var _result_drug_interaction_index = drug_interaction_index(0.5, 0.5, 0.5, 0.5)
    var _summary_drug_interaction_index = _summary_float64(_result_drug_interaction_index)
    print("MOJO_RESULT pharmacology::drug_interaction_index", _summary_drug_interaction_index)
