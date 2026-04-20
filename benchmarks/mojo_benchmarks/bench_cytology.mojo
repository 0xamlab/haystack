"""bench_cytology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from cytology import cell_volume_sphere, nuclear_cytoplasmic_ratio, membrane_permeability, cell_doubling_time, mitotic_index, cell_viability, apoptosis_rate, phagocytic_index, cell_adhesion_strength, osmotic_fragility
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

    var _acc_cell_volume_sphere: Float64 = 0.0
    var _t0_cell_volume_sphere = perf_counter_ns()
    for _ in range(N):
        _acc_cell_volume_sphere += cell_volume_sphere(0.5)
    var _t1_cell_volume_sphere = perf_counter_ns()
    var _ns_cell_volume_sphere = Float64(_t1_cell_volume_sphere - _t0_cell_volume_sphere) / Float64(N)
    print("MOJO_TIMING cytology::cell_volume_sphere", _ns_cell_volume_sphere, _acc_cell_volume_sphere)
    var _acc_nuclear_cytoplasmic_ratio: Float64 = 0.0
    var _t0_nuclear_cytoplasmic_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_nuclear_cytoplasmic_ratio += nuclear_cytoplasmic_ratio(0.5, 0.5)
    var _t1_nuclear_cytoplasmic_ratio = perf_counter_ns()
    var _ns_nuclear_cytoplasmic_ratio = Float64(_t1_nuclear_cytoplasmic_ratio - _t0_nuclear_cytoplasmic_ratio) / Float64(N)
    print("MOJO_TIMING cytology::nuclear_cytoplasmic_ratio", _ns_nuclear_cytoplasmic_ratio, _acc_nuclear_cytoplasmic_ratio)
    var _acc_membrane_permeability: Float64 = 0.0
    var _t0_membrane_permeability = perf_counter_ns()
    for _ in range(N):
        _acc_membrane_permeability += membrane_permeability(0.5, 0.5, 0.5)
    var _t1_membrane_permeability = perf_counter_ns()
    var _ns_membrane_permeability = Float64(_t1_membrane_permeability - _t0_membrane_permeability) / Float64(N)
    print("MOJO_TIMING cytology::membrane_permeability", _ns_membrane_permeability, _acc_membrane_permeability)
    var _acc_cell_doubling_time: Float64 = 0.0
    var _t0_cell_doubling_time = perf_counter_ns()
    for _ in range(N):
        _acc_cell_doubling_time += cell_doubling_time(0.5)
    var _t1_cell_doubling_time = perf_counter_ns()
    var _ns_cell_doubling_time = Float64(_t1_cell_doubling_time - _t0_cell_doubling_time) / Float64(N)
    print("MOJO_TIMING cytology::cell_doubling_time", _ns_cell_doubling_time, _acc_cell_doubling_time)
    var _acc_mitotic_index: Float64 = 0.0
    var _t0_mitotic_index = perf_counter_ns()
    for _ in range(N):
        _acc_mitotic_index += mitotic_index(0.5, 0.5)
    var _t1_mitotic_index = perf_counter_ns()
    var _ns_mitotic_index = Float64(_t1_mitotic_index - _t0_mitotic_index) / Float64(N)
    print("MOJO_TIMING cytology::mitotic_index", _ns_mitotic_index, _acc_mitotic_index)
    var _acc_cell_viability: Float64 = 0.0
    var _t0_cell_viability = perf_counter_ns()
    for _ in range(N):
        _acc_cell_viability += cell_viability(0.5, 0.5)
    var _t1_cell_viability = perf_counter_ns()
    var _ns_cell_viability = Float64(_t1_cell_viability - _t0_cell_viability) / Float64(N)
    print("MOJO_TIMING cytology::cell_viability", _ns_cell_viability, _acc_cell_viability)
    var _acc_apoptosis_rate: Float64 = 0.0
    var _t0_apoptosis_rate = perf_counter_ns()
    for _ in range(N):
        _acc_apoptosis_rate += apoptosis_rate(0.5, 0.5, 0.5)
    var _t1_apoptosis_rate = perf_counter_ns()
    var _ns_apoptosis_rate = Float64(_t1_apoptosis_rate - _t0_apoptosis_rate) / Float64(N)
    print("MOJO_TIMING cytology::apoptosis_rate", _ns_apoptosis_rate, _acc_apoptosis_rate)
    var _acc_phagocytic_index: Float64 = 0.0
    var _t0_phagocytic_index = perf_counter_ns()
    for _ in range(N):
        _acc_phagocytic_index += phagocytic_index(0.5, 0.5)
    var _t1_phagocytic_index = perf_counter_ns()
    var _ns_phagocytic_index = Float64(_t1_phagocytic_index - _t0_phagocytic_index) / Float64(N)
    print("MOJO_TIMING cytology::phagocytic_index", _ns_phagocytic_index, _acc_phagocytic_index)
    var _acc_cell_adhesion_strength: Float64 = 0.0
    var _t0_cell_adhesion_strength = perf_counter_ns()
    for _ in range(N):
        _acc_cell_adhesion_strength += cell_adhesion_strength(0.5, 0.5)
    var _t1_cell_adhesion_strength = perf_counter_ns()
    var _ns_cell_adhesion_strength = Float64(_t1_cell_adhesion_strength - _t0_cell_adhesion_strength) / Float64(N)
    print("MOJO_TIMING cytology::cell_adhesion_strength", _ns_cell_adhesion_strength, _acc_cell_adhesion_strength)
    var _acc_osmotic_fragility: Float64 = 0.0
    var _t0_osmotic_fragility = perf_counter_ns()
    for _ in range(N):
        _acc_osmotic_fragility += osmotic_fragility(0.5, 0.5)
    var _t1_osmotic_fragility = perf_counter_ns()
    var _ns_osmotic_fragility = Float64(_t1_osmotic_fragility - _t0_osmotic_fragility) / Float64(N)
    print("MOJO_TIMING cytology::osmotic_fragility", _ns_osmotic_fragility, _acc_osmotic_fragility)
