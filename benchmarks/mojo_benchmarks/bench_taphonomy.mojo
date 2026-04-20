"""bench_taphonomy.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from taphonomy import organic_decay_rate, bone_density_loss, fossil_completeness, permineralisation_rate, trampling_abrasion_index, hydraulic_sorting_index, time_averaged_assemblage, preservation_potential, diagenetic_alteration_index, carbon_nitrogen_ratio_bone
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

    var _acc_organic_decay_rate: Float64 = 0.0
    var _t0_organic_decay_rate = perf_counter_ns()
    for _ in range(N):
        _acc_organic_decay_rate += organic_decay_rate(0.5, 0.5, 0.5)
    var _t1_organic_decay_rate = perf_counter_ns()
    var _ns_organic_decay_rate = Float64(_t1_organic_decay_rate - _t0_organic_decay_rate) / Float64(N)
    print("MOJO_TIMING taphonomy::organic_decay_rate", _ns_organic_decay_rate, _acc_organic_decay_rate)
    var _acc_bone_density_loss: Float64 = 0.0
    var _t0_bone_density_loss = perf_counter_ns()
    for _ in range(N):
        _acc_bone_density_loss += bone_density_loss(0.5, 0.5, 0.5)
    var _t1_bone_density_loss = perf_counter_ns()
    var _ns_bone_density_loss = Float64(_t1_bone_density_loss - _t0_bone_density_loss) / Float64(N)
    print("MOJO_TIMING taphonomy::bone_density_loss", _ns_bone_density_loss, _acc_bone_density_loss)
    var _acc_fossil_completeness: Float64 = 0.0
    var _t0_fossil_completeness = perf_counter_ns()
    for _ in range(N):
        _acc_fossil_completeness += fossil_completeness(0.5, 0.5)
    var _t1_fossil_completeness = perf_counter_ns()
    var _ns_fossil_completeness = Float64(_t1_fossil_completeness - _t0_fossil_completeness) / Float64(N)
    print("MOJO_TIMING taphonomy::fossil_completeness", _ns_fossil_completeness, _acc_fossil_completeness)
    var _acc_permineralisation_rate: Float64 = 0.0
    var _t0_permineralisation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_permineralisation_rate += permineralisation_rate(0.5, 0.5, 0.5)
    var _t1_permineralisation_rate = perf_counter_ns()
    var _ns_permineralisation_rate = Float64(_t1_permineralisation_rate - _t0_permineralisation_rate) / Float64(N)
    print("MOJO_TIMING taphonomy::permineralisation_rate", _ns_permineralisation_rate, _acc_permineralisation_rate)
    var _acc_trampling_abrasion_index: Float64 = 0.0
    var _t0_trampling_abrasion_index = perf_counter_ns()
    for _ in range(N):
        _acc_trampling_abrasion_index += trampling_abrasion_index(0.5, 0.5, 0.5)
    var _t1_trampling_abrasion_index = perf_counter_ns()
    var _ns_trampling_abrasion_index = Float64(_t1_trampling_abrasion_index - _t0_trampling_abrasion_index) / Float64(N)
    print("MOJO_TIMING taphonomy::trampling_abrasion_index", _ns_trampling_abrasion_index, _acc_trampling_abrasion_index)
    var _acc_hydraulic_sorting_index: Float64 = 0.0
    var _t0_hydraulic_sorting_index = perf_counter_ns()
    for _ in range(N):
        _acc_hydraulic_sorting_index += hydraulic_sorting_index(0.5, 0.5, 0.5)
    var _t1_hydraulic_sorting_index = perf_counter_ns()
    var _ns_hydraulic_sorting_index = Float64(_t1_hydraulic_sorting_index - _t0_hydraulic_sorting_index) / Float64(N)
    print("MOJO_TIMING taphonomy::hydraulic_sorting_index", _ns_hydraulic_sorting_index, _acc_hydraulic_sorting_index)
    var _acc_time_averaged_assemblage: Float64 = 0.0
    var _t0_time_averaged_assemblage = perf_counter_ns()
    for _ in range(N):
        _acc_time_averaged_assemblage += time_averaged_assemblage(0.5, 0.5)
    var _t1_time_averaged_assemblage = perf_counter_ns()
    var _ns_time_averaged_assemblage = Float64(_t1_time_averaged_assemblage - _t0_time_averaged_assemblage) / Float64(N)
    print("MOJO_TIMING taphonomy::time_averaged_assemblage", _ns_time_averaged_assemblage, _acc_time_averaged_assemblage)
    var _acc_preservation_potential: Float64 = 0.0
    var _t0_preservation_potential = perf_counter_ns()
    for _ in range(N):
        _acc_preservation_potential += preservation_potential(0.5, 0.5, 0.5)
    var _t1_preservation_potential = perf_counter_ns()
    var _ns_preservation_potential = Float64(_t1_preservation_potential - _t0_preservation_potential) / Float64(N)
    print("MOJO_TIMING taphonomy::preservation_potential", _ns_preservation_potential, _acc_preservation_potential)
    var _acc_diagenetic_alteration_index: Float64 = 0.0
    var _t0_diagenetic_alteration_index = perf_counter_ns()
    for _ in range(N):
        _acc_diagenetic_alteration_index += diagenetic_alteration_index(0.5, 0.5)
    var _t1_diagenetic_alteration_index = perf_counter_ns()
    var _ns_diagenetic_alteration_index = Float64(_t1_diagenetic_alteration_index - _t0_diagenetic_alteration_index) / Float64(N)
    print("MOJO_TIMING taphonomy::diagenetic_alteration_index", _ns_diagenetic_alteration_index, _acc_diagenetic_alteration_index)
    var _acc_carbon_nitrogen_ratio_bone: Float64 = 0.0
    var _t0_carbon_nitrogen_ratio_bone = perf_counter_ns()
    for _ in range(N):
        _acc_carbon_nitrogen_ratio_bone += carbon_nitrogen_ratio_bone(0.5, 0.5)
    var _t1_carbon_nitrogen_ratio_bone = perf_counter_ns()
    var _ns_carbon_nitrogen_ratio_bone = Float64(_t1_carbon_nitrogen_ratio_bone - _t0_carbon_nitrogen_ratio_bone) / Float64(N)
    print("MOJO_TIMING taphonomy::carbon_nitrogen_ratio_bone", _ns_carbon_nitrogen_ratio_bone, _acc_carbon_nitrogen_ratio_bone)
