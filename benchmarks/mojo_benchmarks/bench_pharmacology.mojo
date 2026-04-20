"""bench_pharmacology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from pharmacology import hill_equation, therapeutic_index, drug_bioavailability, receptor_occupancy, drug_protein_binding, volume_of_distribution, clearance_from_halflife, steady_state_concentration, loading_dose, drug_interaction_index
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

    var _acc_hill_equation: Float64 = 0.0
    var _t0_hill_equation = perf_counter_ns()
    for _ in range(N):
        _acc_hill_equation += hill_equation(0.5, 0.5, 0.5, 0.5)
    var _t1_hill_equation = perf_counter_ns()
    var _ns_hill_equation = Float64(_t1_hill_equation - _t0_hill_equation) / Float64(N)
    print("MOJO_TIMING pharmacology::hill_equation", _ns_hill_equation, _acc_hill_equation)
    var _acc_therapeutic_index: Float64 = 0.0
    var _t0_therapeutic_index = perf_counter_ns()
    for _ in range(N):
        _acc_therapeutic_index += therapeutic_index(0.5, 0.5)
    var _t1_therapeutic_index = perf_counter_ns()
    var _ns_therapeutic_index = Float64(_t1_therapeutic_index - _t0_therapeutic_index) / Float64(N)
    print("MOJO_TIMING pharmacology::therapeutic_index", _ns_therapeutic_index, _acc_therapeutic_index)
    var _acc_drug_bioavailability: Float64 = 0.0
    var _t0_drug_bioavailability = perf_counter_ns()
    for _ in range(N):
        _acc_drug_bioavailability += drug_bioavailability(0.5, 0.5, 0.5, 0.5)
    var _t1_drug_bioavailability = perf_counter_ns()
    var _ns_drug_bioavailability = Float64(_t1_drug_bioavailability - _t0_drug_bioavailability) / Float64(N)
    print("MOJO_TIMING pharmacology::drug_bioavailability", _ns_drug_bioavailability, _acc_drug_bioavailability)
    var _acc_receptor_occupancy: Float64 = 0.0
    var _t0_receptor_occupancy = perf_counter_ns()
    for _ in range(N):
        _acc_receptor_occupancy += receptor_occupancy(0.5, 0.5)
    var _t1_receptor_occupancy = perf_counter_ns()
    var _ns_receptor_occupancy = Float64(_t1_receptor_occupancy - _t0_receptor_occupancy) / Float64(N)
    print("MOJO_TIMING pharmacology::receptor_occupancy", _ns_receptor_occupancy, _acc_receptor_occupancy)
    var _acc_drug_protein_binding: Float64 = 0.0
    var _t0_drug_protein_binding = perf_counter_ns()
    for _ in range(N):
        _acc_drug_protein_binding += drug_protein_binding(0.5)
    var _t1_drug_protein_binding = perf_counter_ns()
    var _ns_drug_protein_binding = Float64(_t1_drug_protein_binding - _t0_drug_protein_binding) / Float64(N)
    print("MOJO_TIMING pharmacology::drug_protein_binding", _ns_drug_protein_binding, _acc_drug_protein_binding)
    var _acc_volume_of_distribution: Float64 = 0.0
    var _t0_volume_of_distribution = perf_counter_ns()
    for _ in range(N):
        _acc_volume_of_distribution += volume_of_distribution(0.5, 0.5)
    var _t1_volume_of_distribution = perf_counter_ns()
    var _ns_volume_of_distribution = Float64(_t1_volume_of_distribution - _t0_volume_of_distribution) / Float64(N)
    print("MOJO_TIMING pharmacology::volume_of_distribution", _ns_volume_of_distribution, _acc_volume_of_distribution)
    var _acc_clearance_from_halflife: Float64 = 0.0
    var _t0_clearance_from_halflife = perf_counter_ns()
    for _ in range(N):
        _acc_clearance_from_halflife += clearance_from_halflife(0.5, 0.5)
    var _t1_clearance_from_halflife = perf_counter_ns()
    var _ns_clearance_from_halflife = Float64(_t1_clearance_from_halflife - _t0_clearance_from_halflife) / Float64(N)
    print("MOJO_TIMING pharmacology::clearance_from_halflife", _ns_clearance_from_halflife, _acc_clearance_from_halflife)
    var _acc_steady_state_concentration: Float64 = 0.0
    var _t0_steady_state_concentration = perf_counter_ns()
    for _ in range(N):
        _acc_steady_state_concentration += steady_state_concentration(0.5, 0.5, 0.5, 0.5)
    var _t1_steady_state_concentration = perf_counter_ns()
    var _ns_steady_state_concentration = Float64(_t1_steady_state_concentration - _t0_steady_state_concentration) / Float64(N)
    print("MOJO_TIMING pharmacology::steady_state_concentration", _ns_steady_state_concentration, _acc_steady_state_concentration)
    var _acc_loading_dose: Float64 = 0.0
    var _t0_loading_dose = perf_counter_ns()
    for _ in range(N):
        _acc_loading_dose += loading_dose(0.5, 0.5)
    var _t1_loading_dose = perf_counter_ns()
    var _ns_loading_dose = Float64(_t1_loading_dose - _t0_loading_dose) / Float64(N)
    print("MOJO_TIMING pharmacology::loading_dose", _ns_loading_dose, _acc_loading_dose)
    var _acc_drug_interaction_index: Float64 = 0.0
    var _t0_drug_interaction_index = perf_counter_ns()
    for _ in range(N):
        _acc_drug_interaction_index += drug_interaction_index(0.5, 0.5, 0.5, 0.5)
    var _t1_drug_interaction_index = perf_counter_ns()
    var _ns_drug_interaction_index = Float64(_t1_drug_interaction_index - _t0_drug_interaction_index) / Float64(N)
    print("MOJO_TIMING pharmacology::drug_interaction_index", _ns_drug_interaction_index, _acc_drug_interaction_index)
