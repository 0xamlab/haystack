"""bench_rubber.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from rubber import shore_a_to_youngs_modulus, mooney_viscosity_index, tensile_set, compression_set, elongation_at_break, tear_strength, resilience_rebound, hardness_change_aging, swelling_percentage, crosslink_density_estimate, abrasion_loss_volume, heat_buildup
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

    var _acc_shore_a_to_youngs_modulus: Float64 = 0.0
    var _t0_shore_a_to_youngs_modulus = perf_counter_ns()
    for _ in range(N):
        _acc_shore_a_to_youngs_modulus += shore_a_to_youngs_modulus(0.5)
    var _t1_shore_a_to_youngs_modulus = perf_counter_ns()
    var _ns_shore_a_to_youngs_modulus = Float64(_t1_shore_a_to_youngs_modulus - _t0_shore_a_to_youngs_modulus) / Float64(N)
    print("MOJO_TIMING rubber::shore_a_to_youngs_modulus", _ns_shore_a_to_youngs_modulus, _acc_shore_a_to_youngs_modulus)
    var _acc_mooney_viscosity_index: Float64 = 0.0
    var _t0_mooney_viscosity_index = perf_counter_ns()
    for _ in range(N):
        _acc_mooney_viscosity_index += mooney_viscosity_index(0.5, 0.5)
    var _t1_mooney_viscosity_index = perf_counter_ns()
    var _ns_mooney_viscosity_index = Float64(_t1_mooney_viscosity_index - _t0_mooney_viscosity_index) / Float64(N)
    print("MOJO_TIMING rubber::mooney_viscosity_index", _ns_mooney_viscosity_index, _acc_mooney_viscosity_index)
    var _acc_tensile_set: Float64 = 0.0
    var _t0_tensile_set = perf_counter_ns()
    for _ in range(N):
        _acc_tensile_set += tensile_set(0.5, 0.5, 0.5)
    var _t1_tensile_set = perf_counter_ns()
    var _ns_tensile_set = Float64(_t1_tensile_set - _t0_tensile_set) / Float64(N)
    print("MOJO_TIMING rubber::tensile_set", _ns_tensile_set, _acc_tensile_set)
    var _acc_compression_set: Float64 = 0.0
    var _t0_compression_set = perf_counter_ns()
    for _ in range(N):
        _acc_compression_set += compression_set(0.5, 0.5, 0.5)
    var _t1_compression_set = perf_counter_ns()
    var _ns_compression_set = Float64(_t1_compression_set - _t0_compression_set) / Float64(N)
    print("MOJO_TIMING rubber::compression_set", _ns_compression_set, _acc_compression_set)
    var _acc_elongation_at_break: Float64 = 0.0
    var _t0_elongation_at_break = perf_counter_ns()
    for _ in range(N):
        _acc_elongation_at_break += elongation_at_break(0.5, 0.5)
    var _t1_elongation_at_break = perf_counter_ns()
    var _ns_elongation_at_break = Float64(_t1_elongation_at_break - _t0_elongation_at_break) / Float64(N)
    print("MOJO_TIMING rubber::elongation_at_break", _ns_elongation_at_break, _acc_elongation_at_break)
    var _acc_tear_strength: Float64 = 0.0
    var _t0_tear_strength = perf_counter_ns()
    for _ in range(N):
        _acc_tear_strength += tear_strength(0.5, 0.5)
    var _t1_tear_strength = perf_counter_ns()
    var _ns_tear_strength = Float64(_t1_tear_strength - _t0_tear_strength) / Float64(N)
    print("MOJO_TIMING rubber::tear_strength", _ns_tear_strength, _acc_tear_strength)
    var _acc_resilience_rebound: Float64 = 0.0
    var _t0_resilience_rebound = perf_counter_ns()
    for _ in range(N):
        _acc_resilience_rebound += resilience_rebound(0.5, 0.5)
    var _t1_resilience_rebound = perf_counter_ns()
    var _ns_resilience_rebound = Float64(_t1_resilience_rebound - _t0_resilience_rebound) / Float64(N)
    print("MOJO_TIMING rubber::resilience_rebound", _ns_resilience_rebound, _acc_resilience_rebound)
    var _acc_hardness_change_aging: Float64 = 0.0
    var _t0_hardness_change_aging = perf_counter_ns()
    for _ in range(N):
        _acc_hardness_change_aging += hardness_change_aging(0.5, 0.5)
    var _t1_hardness_change_aging = perf_counter_ns()
    var _ns_hardness_change_aging = Float64(_t1_hardness_change_aging - _t0_hardness_change_aging) / Float64(N)
    print("MOJO_TIMING rubber::hardness_change_aging", _ns_hardness_change_aging, _acc_hardness_change_aging)
    var _acc_swelling_percentage: Float64 = 0.0
    var _t0_swelling_percentage = perf_counter_ns()
    for _ in range(N):
        _acc_swelling_percentage += swelling_percentage(0.5, 0.5)
    var _t1_swelling_percentage = perf_counter_ns()
    var _ns_swelling_percentage = Float64(_t1_swelling_percentage - _t0_swelling_percentage) / Float64(N)
    print("MOJO_TIMING rubber::swelling_percentage", _ns_swelling_percentage, _acc_swelling_percentage)
    var _acc_crosslink_density_estimate: Float64 = 0.0
    var _t0_crosslink_density_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_crosslink_density_estimate += crosslink_density_estimate(0.5, 0.5, 0.5)
    var _t1_crosslink_density_estimate = perf_counter_ns()
    var _ns_crosslink_density_estimate = Float64(_t1_crosslink_density_estimate - _t0_crosslink_density_estimate) / Float64(N)
    print("MOJO_TIMING rubber::crosslink_density_estimate", _ns_crosslink_density_estimate, _acc_crosslink_density_estimate)
    var _acc_abrasion_loss_volume: Float64 = 0.0
    var _t0_abrasion_loss_volume = perf_counter_ns()
    for _ in range(N):
        _acc_abrasion_loss_volume += abrasion_loss_volume(0.5, 0.5)
    var _t1_abrasion_loss_volume = perf_counter_ns()
    var _ns_abrasion_loss_volume = Float64(_t1_abrasion_loss_volume - _t0_abrasion_loss_volume) / Float64(N)
    print("MOJO_TIMING rubber::abrasion_loss_volume", _ns_abrasion_loss_volume, _acc_abrasion_loss_volume)
    var _acc_heat_buildup: Float64 = 0.0
    var _t0_heat_buildup = perf_counter_ns()
    for _ in range(N):
        _acc_heat_buildup += heat_buildup(0.5, 0.5, 0.5)
    var _t1_heat_buildup = perf_counter_ns()
    var _ns_heat_buildup = Float64(_t1_heat_buildup - _t0_heat_buildup) / Float64(N)
    print("MOJO_TIMING rubber::heat_buildup", _ns_heat_buildup, _acc_heat_buildup)
