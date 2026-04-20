"""bench_polymer.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from polymer import degree_of_polymerization, number_average_mw, weight_average_mw, polydispersity_index, mark_houwink, glass_transition_fox, flory_huggins_free_energy, end_to_end_distance, radius_of_gyration, carothers_conversion, melt_flow_index_approx, tensile_modulus_rule_of_mixtures
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

    var _acc_degree_of_polymerization: Float64 = 0.0
    var _t0_degree_of_polymerization = perf_counter_ns()
    for _ in range(N):
        _acc_degree_of_polymerization += degree_of_polymerization(0.5, 0.5)
    var _t1_degree_of_polymerization = perf_counter_ns()
    var _ns_degree_of_polymerization = Float64(_t1_degree_of_polymerization - _t0_degree_of_polymerization) / Float64(N)
    print("MOJO_TIMING polymer::degree_of_polymerization", _ns_degree_of_polymerization, _acc_degree_of_polymerization)
    var _acc_number_average_mw: Float64 = 0.0
    var _t0_number_average_mw = perf_counter_ns()
    for _ in range(N):
        _acc_number_average_mw += number_average_mw(0.5, 0.5)
    var _t1_number_average_mw = perf_counter_ns()
    var _ns_number_average_mw = Float64(_t1_number_average_mw - _t0_number_average_mw) / Float64(N)
    print("MOJO_TIMING polymer::number_average_mw", _ns_number_average_mw, _acc_number_average_mw)
    var _acc_weight_average_mw: Float64 = 0.0
    var _t0_weight_average_mw = perf_counter_ns()
    for _ in range(N):
        _acc_weight_average_mw += weight_average_mw(0.5, 0.5)
    var _t1_weight_average_mw = perf_counter_ns()
    var _ns_weight_average_mw = Float64(_t1_weight_average_mw - _t0_weight_average_mw) / Float64(N)
    print("MOJO_TIMING polymer::weight_average_mw", _ns_weight_average_mw, _acc_weight_average_mw)
    var _acc_polydispersity_index: Float64 = 0.0
    var _t0_polydispersity_index = perf_counter_ns()
    for _ in range(N):
        _acc_polydispersity_index += polydispersity_index(0.5, 0.5)
    var _t1_polydispersity_index = perf_counter_ns()
    var _ns_polydispersity_index = Float64(_t1_polydispersity_index - _t0_polydispersity_index) / Float64(N)
    print("MOJO_TIMING polymer::polydispersity_index", _ns_polydispersity_index, _acc_polydispersity_index)
    var _acc_mark_houwink: Float64 = 0.0
    var _t0_mark_houwink = perf_counter_ns()
    for _ in range(N):
        _acc_mark_houwink += mark_houwink(0.5, 0.5, 0.5)
    var _t1_mark_houwink = perf_counter_ns()
    var _ns_mark_houwink = Float64(_t1_mark_houwink - _t0_mark_houwink) / Float64(N)
    print("MOJO_TIMING polymer::mark_houwink", _ns_mark_houwink, _acc_mark_houwink)
    var _acc_glass_transition_fox: Float64 = 0.0
    var _t0_glass_transition_fox = perf_counter_ns()
    for _ in range(N):
        _acc_glass_transition_fox += glass_transition_fox(0.5, 0.5, 0.5, 0.5)
    var _t1_glass_transition_fox = perf_counter_ns()
    var _ns_glass_transition_fox = Float64(_t1_glass_transition_fox - _t0_glass_transition_fox) / Float64(N)
    print("MOJO_TIMING polymer::glass_transition_fox", _ns_glass_transition_fox, _acc_glass_transition_fox)
    var _acc_flory_huggins_free_energy: Float64 = 0.0
    var _t0_flory_huggins_free_energy = perf_counter_ns()
    for _ in range(N):
        _acc_flory_huggins_free_energy += flory_huggins_free_energy(0.5, 0.5, 0.5)
    var _t1_flory_huggins_free_energy = perf_counter_ns()
    var _ns_flory_huggins_free_energy = Float64(_t1_flory_huggins_free_energy - _t0_flory_huggins_free_energy) / Float64(N)
    print("MOJO_TIMING polymer::flory_huggins_free_energy", _ns_flory_huggins_free_energy, _acc_flory_huggins_free_energy)
    var _acc_end_to_end_distance: Float64 = 0.0
    var _t0_end_to_end_distance = perf_counter_ns()
    for _ in range(N):
        _acc_end_to_end_distance += end_to_end_distance(0.5, 0.5)
    var _t1_end_to_end_distance = perf_counter_ns()
    var _ns_end_to_end_distance = Float64(_t1_end_to_end_distance - _t0_end_to_end_distance) / Float64(N)
    print("MOJO_TIMING polymer::end_to_end_distance", _ns_end_to_end_distance, _acc_end_to_end_distance)
    var _acc_radius_of_gyration: Float64 = 0.0
    var _t0_radius_of_gyration = perf_counter_ns()
    for _ in range(N):
        _acc_radius_of_gyration += radius_of_gyration(0.5)
    var _t1_radius_of_gyration = perf_counter_ns()
    var _ns_radius_of_gyration = Float64(_t1_radius_of_gyration - _t0_radius_of_gyration) / Float64(N)
    print("MOJO_TIMING polymer::radius_of_gyration", _ns_radius_of_gyration, _acc_radius_of_gyration)
    var _acc_carothers_conversion: Float64 = 0.0
    var _t0_carothers_conversion = perf_counter_ns()
    for _ in range(N):
        _acc_carothers_conversion += carothers_conversion(0.5)
    var _t1_carothers_conversion = perf_counter_ns()
    var _ns_carothers_conversion = Float64(_t1_carothers_conversion - _t0_carothers_conversion) / Float64(N)
    print("MOJO_TIMING polymer::carothers_conversion", _ns_carothers_conversion, _acc_carothers_conversion)
    var _acc_melt_flow_index_approx: Float64 = 0.0
    var _t0_melt_flow_index_approx = perf_counter_ns()
    for _ in range(N):
        _acc_melt_flow_index_approx += melt_flow_index_approx(0.5, 0.5)
    var _t1_melt_flow_index_approx = perf_counter_ns()
    var _ns_melt_flow_index_approx = Float64(_t1_melt_flow_index_approx - _t0_melt_flow_index_approx) / Float64(N)
    print("MOJO_TIMING polymer::melt_flow_index_approx", _ns_melt_flow_index_approx, _acc_melt_flow_index_approx)
    var _acc_tensile_modulus_rule_of_mixtures: Float64 = 0.0
    var _t0_tensile_modulus_rule_of_mixtures = perf_counter_ns()
    for _ in range(N):
        _acc_tensile_modulus_rule_of_mixtures += tensile_modulus_rule_of_mixtures(0.5, 0.5, 0.5)
    var _t1_tensile_modulus_rule_of_mixtures = perf_counter_ns()
    var _ns_tensile_modulus_rule_of_mixtures = Float64(_t1_tensile_modulus_rule_of_mixtures - _t0_tensile_modulus_rule_of_mixtures) / Float64(N)
    print("MOJO_TIMING polymer::tensile_modulus_rule_of_mixtures", _ns_tensile_modulus_rule_of_mixtures, _acc_tensile_modulus_rule_of_mixtures)
