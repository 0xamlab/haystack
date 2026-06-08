"""bench_paleontology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from paleontology import radiocarbon_age, potassium_argon_age, uranium_lead_age, stratigraphic_completeness, sedimentation_rate, fossil_diversity_index, extinction_rate, origination_rate, turnover_rate, body_mass_estimate_mammal, phylogenetic_distance, completeness_metric
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

    var _acc_radiocarbon_age: Float64 = 0.0
    var _t0_radiocarbon_age = perf_counter_ns()
    for _ in range(N):
        _acc_radiocarbon_age += radiocarbon_age(0.5, 0.5)
    var _t1_radiocarbon_age = perf_counter_ns()
    var _ns_radiocarbon_age = Float64(_t1_radiocarbon_age - _t0_radiocarbon_age) / Float64(N)
    print("MOJO_TIMING paleontology::radiocarbon_age", _ns_radiocarbon_age, _acc_radiocarbon_age)
    var _result_radiocarbon_age = radiocarbon_age(0.5, 0.5)
    var _summary_radiocarbon_age = _summary_float64(_result_radiocarbon_age)
    print("MOJO_RESULT paleontology::radiocarbon_age", _summary_radiocarbon_age)
    var _acc_potassium_argon_age: Float64 = 0.0
    var _t0_potassium_argon_age = perf_counter_ns()
    for _ in range(N):
        _acc_potassium_argon_age += potassium_argon_age(0.5, 0.5)
    var _t1_potassium_argon_age = perf_counter_ns()
    var _ns_potassium_argon_age = Float64(_t1_potassium_argon_age - _t0_potassium_argon_age) / Float64(N)
    print("MOJO_TIMING paleontology::potassium_argon_age", _ns_potassium_argon_age, _acc_potassium_argon_age)
    var _result_potassium_argon_age = potassium_argon_age(0.5, 0.5)
    var _summary_potassium_argon_age = _summary_float64(_result_potassium_argon_age)
    print("MOJO_RESULT paleontology::potassium_argon_age", _summary_potassium_argon_age)
    var _acc_uranium_lead_age: Float64 = 0.0
    var _t0_uranium_lead_age = perf_counter_ns()
    for _ in range(N):
        _acc_uranium_lead_age += uranium_lead_age(0.5, 0.5)
    var _t1_uranium_lead_age = perf_counter_ns()
    var _ns_uranium_lead_age = Float64(_t1_uranium_lead_age - _t0_uranium_lead_age) / Float64(N)
    print("MOJO_TIMING paleontology::uranium_lead_age", _ns_uranium_lead_age, _acc_uranium_lead_age)
    var _result_uranium_lead_age = uranium_lead_age(0.5, 0.5)
    var _summary_uranium_lead_age = _summary_float64(_result_uranium_lead_age)
    print("MOJO_RESULT paleontology::uranium_lead_age", _summary_uranium_lead_age)
    var _acc_stratigraphic_completeness: Float64 = 0.0
    var _t0_stratigraphic_completeness = perf_counter_ns()
    for _ in range(N):
        _acc_stratigraphic_completeness += stratigraphic_completeness(0.5, 0.5)
    var _t1_stratigraphic_completeness = perf_counter_ns()
    var _ns_stratigraphic_completeness = Float64(_t1_stratigraphic_completeness - _t0_stratigraphic_completeness) / Float64(N)
    print("MOJO_TIMING paleontology::stratigraphic_completeness", _ns_stratigraphic_completeness, _acc_stratigraphic_completeness)
    var _result_stratigraphic_completeness = stratigraphic_completeness(0.5, 0.5)
    var _summary_stratigraphic_completeness = _summary_float64(_result_stratigraphic_completeness)
    print("MOJO_RESULT paleontology::stratigraphic_completeness", _summary_stratigraphic_completeness)
    var _acc_sedimentation_rate: Float64 = 0.0
    var _t0_sedimentation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_sedimentation_rate += sedimentation_rate(0.5, 0.5)
    var _t1_sedimentation_rate = perf_counter_ns()
    var _ns_sedimentation_rate = Float64(_t1_sedimentation_rate - _t0_sedimentation_rate) / Float64(N)
    print("MOJO_TIMING paleontology::sedimentation_rate", _ns_sedimentation_rate, _acc_sedimentation_rate)
    var _result_sedimentation_rate = sedimentation_rate(0.5, 0.5)
    var _summary_sedimentation_rate = _summary_float64(_result_sedimentation_rate)
    print("MOJO_RESULT paleontology::sedimentation_rate", _summary_sedimentation_rate)
    var _acc_fossil_diversity_index: Float64 = 0.0
    var _t0_fossil_diversity_index = perf_counter_ns()
    for _ in range(N):
        _acc_fossil_diversity_index += fossil_diversity_index(0.5, 0.5)
    var _t1_fossil_diversity_index = perf_counter_ns()
    var _ns_fossil_diversity_index = Float64(_t1_fossil_diversity_index - _t0_fossil_diversity_index) / Float64(N)
    print("MOJO_TIMING paleontology::fossil_diversity_index", _ns_fossil_diversity_index, _acc_fossil_diversity_index)
    var _result_fossil_diversity_index = fossil_diversity_index(0.5, 0.5)
    var _summary_fossil_diversity_index = _summary_float64(_result_fossil_diversity_index)
    print("MOJO_RESULT paleontology::fossil_diversity_index", _summary_fossil_diversity_index)
    var _acc_extinction_rate: Float64 = 0.0
    var _t0_extinction_rate = perf_counter_ns()
    for _ in range(N):
        _acc_extinction_rate += extinction_rate(0.5, 0.5, 0.5)
    var _t1_extinction_rate = perf_counter_ns()
    var _ns_extinction_rate = Float64(_t1_extinction_rate - _t0_extinction_rate) / Float64(N)
    print("MOJO_TIMING paleontology::extinction_rate", _ns_extinction_rate, _acc_extinction_rate)
    var _result_extinction_rate = extinction_rate(0.5, 0.5, 0.5)
    var _summary_extinction_rate = _summary_float64(_result_extinction_rate)
    print("MOJO_RESULT paleontology::extinction_rate", _summary_extinction_rate)
    var _acc_origination_rate: Float64 = 0.0
    var _t0_origination_rate = perf_counter_ns()
    for _ in range(N):
        _acc_origination_rate += origination_rate(0.5, 0.5, 0.5)
    var _t1_origination_rate = perf_counter_ns()
    var _ns_origination_rate = Float64(_t1_origination_rate - _t0_origination_rate) / Float64(N)
    print("MOJO_TIMING paleontology::origination_rate", _ns_origination_rate, _acc_origination_rate)
    var _result_origination_rate = origination_rate(0.5, 0.5, 0.5)
    var _summary_origination_rate = _summary_float64(_result_origination_rate)
    print("MOJO_RESULT paleontology::origination_rate", _summary_origination_rate)
    var _acc_turnover_rate: Float64 = 0.0
    var _t0_turnover_rate = perf_counter_ns()
    for _ in range(N):
        _acc_turnover_rate += turnover_rate(0.5, 0.5)
    var _t1_turnover_rate = perf_counter_ns()
    var _ns_turnover_rate = Float64(_t1_turnover_rate - _t0_turnover_rate) / Float64(N)
    print("MOJO_TIMING paleontology::turnover_rate", _ns_turnover_rate, _acc_turnover_rate)
    var _result_turnover_rate = turnover_rate(0.5, 0.5)
    var _summary_turnover_rate = _summary_float64(_result_turnover_rate)
    print("MOJO_RESULT paleontology::turnover_rate", _summary_turnover_rate)
    var _acc_body_mass_estimate_mammal: Float64 = 0.0
    var _t0_body_mass_estimate_mammal = perf_counter_ns()
    for _ in range(N):
        _acc_body_mass_estimate_mammal += body_mass_estimate_mammal(0.5)
    var _t1_body_mass_estimate_mammal = perf_counter_ns()
    var _ns_body_mass_estimate_mammal = Float64(_t1_body_mass_estimate_mammal - _t0_body_mass_estimate_mammal) / Float64(N)
    print("MOJO_TIMING paleontology::body_mass_estimate_mammal", _ns_body_mass_estimate_mammal, _acc_body_mass_estimate_mammal)
    var _result_body_mass_estimate_mammal = body_mass_estimate_mammal(0.5)
    var _summary_body_mass_estimate_mammal = _summary_float64(_result_body_mass_estimate_mammal)
    print("MOJO_RESULT paleontology::body_mass_estimate_mammal", _summary_body_mass_estimate_mammal)
    var _acc_phylogenetic_distance: Float64 = 0.0
    var _t0_phylogenetic_distance = perf_counter_ns()
    for _ in range(N):
        _acc_phylogenetic_distance += phylogenetic_distance(0.5, 0.5)
    var _t1_phylogenetic_distance = perf_counter_ns()
    var _ns_phylogenetic_distance = Float64(_t1_phylogenetic_distance - _t0_phylogenetic_distance) / Float64(N)
    print("MOJO_TIMING paleontology::phylogenetic_distance", _ns_phylogenetic_distance, _acc_phylogenetic_distance)
    var _result_phylogenetic_distance = phylogenetic_distance(0.5, 0.5)
    var _summary_phylogenetic_distance = _summary_float64(_result_phylogenetic_distance)
    print("MOJO_RESULT paleontology::phylogenetic_distance", _summary_phylogenetic_distance)
    var _acc_completeness_metric: Float64 = 0.0
    var _t0_completeness_metric = perf_counter_ns()
    for _ in range(N):
        _acc_completeness_metric += completeness_metric(0.5, 0.5)
    var _t1_completeness_metric = perf_counter_ns()
    var _ns_completeness_metric = Float64(_t1_completeness_metric - _t0_completeness_metric) / Float64(N)
    print("MOJO_TIMING paleontology::completeness_metric", _ns_completeness_metric, _acc_completeness_metric)
    var _result_completeness_metric = completeness_metric(0.5, 0.5)
    var _summary_completeness_metric = _summary_float64(_result_completeness_metric)
    print("MOJO_RESULT paleontology::completeness_metric", _summary_completeness_metric)
