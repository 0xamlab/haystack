"""bench_taphonomy.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from taphonomy import organic_decay_rate, bone_density_loss, fossil_completeness, permineralisation_rate, trampling_abrasion_index, hydraulic_sorting_index, time_averaged_assemblage, preservation_potential, diagenetic_alteration_index, carbon_nitrogen_ratio_bone
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

    var _acc_organic_decay_rate: Float64 = 0.0
    var _t0_organic_decay_rate = perf_counter_ns()
    for _ in range(N):
        _acc_organic_decay_rate += organic_decay_rate(0.5, 0.5, 0.5)
    var _t1_organic_decay_rate = perf_counter_ns()
    var _ns_organic_decay_rate = Float64(_t1_organic_decay_rate - _t0_organic_decay_rate) / Float64(N)
    print("MOJO_TIMING taphonomy::organic_decay_rate", _ns_organic_decay_rate, _acc_organic_decay_rate)
    var _result_organic_decay_rate = organic_decay_rate(0.5, 0.5, 0.5)
    var _summary_organic_decay_rate = _summary_float64(_result_organic_decay_rate)
    print("MOJO_RESULT taphonomy::organic_decay_rate", _summary_organic_decay_rate)
    var _acc_bone_density_loss: Float64 = 0.0
    var _t0_bone_density_loss = perf_counter_ns()
    for _ in range(N):
        _acc_bone_density_loss += bone_density_loss(0.5, 0.5, 0.5)
    var _t1_bone_density_loss = perf_counter_ns()
    var _ns_bone_density_loss = Float64(_t1_bone_density_loss - _t0_bone_density_loss) / Float64(N)
    print("MOJO_TIMING taphonomy::bone_density_loss", _ns_bone_density_loss, _acc_bone_density_loss)
    var _result_bone_density_loss = bone_density_loss(0.5, 0.5, 0.5)
    var _summary_bone_density_loss = _summary_float64(_result_bone_density_loss)
    print("MOJO_RESULT taphonomy::bone_density_loss", _summary_bone_density_loss)
    var _acc_fossil_completeness: Float64 = 0.0
    var _t0_fossil_completeness = perf_counter_ns()
    for _ in range(N):
        _acc_fossil_completeness += fossil_completeness(0.5, 0.5)
    var _t1_fossil_completeness = perf_counter_ns()
    var _ns_fossil_completeness = Float64(_t1_fossil_completeness - _t0_fossil_completeness) / Float64(N)
    print("MOJO_TIMING taphonomy::fossil_completeness", _ns_fossil_completeness, _acc_fossil_completeness)
    var _result_fossil_completeness = fossil_completeness(0.5, 0.5)
    var _summary_fossil_completeness = _summary_float64(_result_fossil_completeness)
    print("MOJO_RESULT taphonomy::fossil_completeness", _summary_fossil_completeness)
    var _acc_permineralisation_rate: Float64 = 0.0
    var _t0_permineralisation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_permineralisation_rate += permineralisation_rate(0.5, 0.5, 0.5)
    var _t1_permineralisation_rate = perf_counter_ns()
    var _ns_permineralisation_rate = Float64(_t1_permineralisation_rate - _t0_permineralisation_rate) / Float64(N)
    print("MOJO_TIMING taphonomy::permineralisation_rate", _ns_permineralisation_rate, _acc_permineralisation_rate)
    var _result_permineralisation_rate = permineralisation_rate(0.5, 0.5, 0.5)
    var _summary_permineralisation_rate = _summary_float64(_result_permineralisation_rate)
    print("MOJO_RESULT taphonomy::permineralisation_rate", _summary_permineralisation_rate)
    var _acc_trampling_abrasion_index: Float64 = 0.0
    var _t0_trampling_abrasion_index = perf_counter_ns()
    for _ in range(N):
        _acc_trampling_abrasion_index += trampling_abrasion_index(0.5, 0.5, 0.5)
    var _t1_trampling_abrasion_index = perf_counter_ns()
    var _ns_trampling_abrasion_index = Float64(_t1_trampling_abrasion_index - _t0_trampling_abrasion_index) / Float64(N)
    print("MOJO_TIMING taphonomy::trampling_abrasion_index", _ns_trampling_abrasion_index, _acc_trampling_abrasion_index)
    var _result_trampling_abrasion_index = trampling_abrasion_index(0.5, 0.5, 0.5)
    var _summary_trampling_abrasion_index = _summary_float64(_result_trampling_abrasion_index)
    print("MOJO_RESULT taphonomy::trampling_abrasion_index", _summary_trampling_abrasion_index)
    var _acc_hydraulic_sorting_index: Float64 = 0.0
    var _t0_hydraulic_sorting_index = perf_counter_ns()
    for _ in range(N):
        _acc_hydraulic_sorting_index += hydraulic_sorting_index(0.5, 0.5, 0.5)
    var _t1_hydraulic_sorting_index = perf_counter_ns()
    var _ns_hydraulic_sorting_index = Float64(_t1_hydraulic_sorting_index - _t0_hydraulic_sorting_index) / Float64(N)
    print("MOJO_TIMING taphonomy::hydraulic_sorting_index", _ns_hydraulic_sorting_index, _acc_hydraulic_sorting_index)
    var _result_hydraulic_sorting_index = hydraulic_sorting_index(0.5, 0.5, 0.5)
    var _summary_hydraulic_sorting_index = _summary_float64(_result_hydraulic_sorting_index)
    print("MOJO_RESULT taphonomy::hydraulic_sorting_index", _summary_hydraulic_sorting_index)
    var _acc_time_averaged_assemblage: Float64 = 0.0
    var _t0_time_averaged_assemblage = perf_counter_ns()
    for _ in range(N):
        _acc_time_averaged_assemblage += time_averaged_assemblage(0.5, 0.5)
    var _t1_time_averaged_assemblage = perf_counter_ns()
    var _ns_time_averaged_assemblage = Float64(_t1_time_averaged_assemblage - _t0_time_averaged_assemblage) / Float64(N)
    print("MOJO_TIMING taphonomy::time_averaged_assemblage", _ns_time_averaged_assemblage, _acc_time_averaged_assemblage)
    var _result_time_averaged_assemblage = time_averaged_assemblage(0.5, 0.5)
    var _summary_time_averaged_assemblage = _summary_float64(_result_time_averaged_assemblage)
    print("MOJO_RESULT taphonomy::time_averaged_assemblage", _summary_time_averaged_assemblage)
    var _acc_preservation_potential: Float64 = 0.0
    var _t0_preservation_potential = perf_counter_ns()
    for _ in range(N):
        _acc_preservation_potential += preservation_potential(0.5, 0.5, 0.5)
    var _t1_preservation_potential = perf_counter_ns()
    var _ns_preservation_potential = Float64(_t1_preservation_potential - _t0_preservation_potential) / Float64(N)
    print("MOJO_TIMING taphonomy::preservation_potential", _ns_preservation_potential, _acc_preservation_potential)
    var _result_preservation_potential = preservation_potential(0.5, 0.5, 0.5)
    var _summary_preservation_potential = _summary_float64(_result_preservation_potential)
    print("MOJO_RESULT taphonomy::preservation_potential", _summary_preservation_potential)
    var _acc_diagenetic_alteration_index: Float64 = 0.0
    var _t0_diagenetic_alteration_index = perf_counter_ns()
    for _ in range(N):
        _acc_diagenetic_alteration_index += diagenetic_alteration_index(0.5, 0.5)
    var _t1_diagenetic_alteration_index = perf_counter_ns()
    var _ns_diagenetic_alteration_index = Float64(_t1_diagenetic_alteration_index - _t0_diagenetic_alteration_index) / Float64(N)
    print("MOJO_TIMING taphonomy::diagenetic_alteration_index", _ns_diagenetic_alteration_index, _acc_diagenetic_alteration_index)
    var _result_diagenetic_alteration_index = diagenetic_alteration_index(0.5, 0.5)
    var _summary_diagenetic_alteration_index = _summary_float64(_result_diagenetic_alteration_index)
    print("MOJO_RESULT taphonomy::diagenetic_alteration_index", _summary_diagenetic_alteration_index)
    var _acc_carbon_nitrogen_ratio_bone: Float64 = 0.0
    var _t0_carbon_nitrogen_ratio_bone = perf_counter_ns()
    for _ in range(N):
        _acc_carbon_nitrogen_ratio_bone += carbon_nitrogen_ratio_bone(0.5, 0.5)
    var _t1_carbon_nitrogen_ratio_bone = perf_counter_ns()
    var _ns_carbon_nitrogen_ratio_bone = Float64(_t1_carbon_nitrogen_ratio_bone - _t0_carbon_nitrogen_ratio_bone) / Float64(N)
    print("MOJO_TIMING taphonomy::carbon_nitrogen_ratio_bone", _ns_carbon_nitrogen_ratio_bone, _acc_carbon_nitrogen_ratio_bone)
    var _result_carbon_nitrogen_ratio_bone = carbon_nitrogen_ratio_bone(0.5, 0.5)
    var _summary_carbon_nitrogen_ratio_bone = _summary_float64(_result_carbon_nitrogen_ratio_bone)
    print("MOJO_RESULT taphonomy::carbon_nitrogen_ratio_bone", _summary_carbon_nitrogen_ratio_bone)
