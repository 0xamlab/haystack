"""bench_water_chemistry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from water_chemistry import ph_from_hydrogen_ion, hydrogen_ion_from_ph, water_hardness, alkalinity_as_caco3, langelier_saturation_index, turbidity_ntu_to_sdd, chlorine_demand, dissolved_oxygen_deficit, conductivity_tds, bod_removal
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

    var _acc_ph_from_hydrogen_ion: Float64 = 0.0
    var _t0_ph_from_hydrogen_ion = perf_counter_ns()
    for _ in range(N):
        _acc_ph_from_hydrogen_ion += ph_from_hydrogen_ion(0.5)
    var _t1_ph_from_hydrogen_ion = perf_counter_ns()
    var _ns_ph_from_hydrogen_ion = Float64(_t1_ph_from_hydrogen_ion - _t0_ph_from_hydrogen_ion) / Float64(N)
    print("MOJO_TIMING water_chemistry::ph_from_hydrogen_ion", _ns_ph_from_hydrogen_ion, _acc_ph_from_hydrogen_ion)
    var _acc_hydrogen_ion_from_ph: Float64 = 0.0
    var _t0_hydrogen_ion_from_ph = perf_counter_ns()
    for _ in range(N):
        _acc_hydrogen_ion_from_ph += hydrogen_ion_from_ph(0.5)
    var _t1_hydrogen_ion_from_ph = perf_counter_ns()
    var _ns_hydrogen_ion_from_ph = Float64(_t1_hydrogen_ion_from_ph - _t0_hydrogen_ion_from_ph) / Float64(N)
    print("MOJO_TIMING water_chemistry::hydrogen_ion_from_ph", _ns_hydrogen_ion_from_ph, _acc_hydrogen_ion_from_ph)
    var _acc_water_hardness: Float64 = 0.0
    var _t0_water_hardness = perf_counter_ns()
    for _ in range(N):
        _acc_water_hardness += water_hardness(0.5, 0.5)
    var _t1_water_hardness = perf_counter_ns()
    var _ns_water_hardness = Float64(_t1_water_hardness - _t0_water_hardness) / Float64(N)
    print("MOJO_TIMING water_chemistry::water_hardness", _ns_water_hardness, _acc_water_hardness)
    var _acc_alkalinity_as_caco3: Float64 = 0.0
    var _t0_alkalinity_as_caco3 = perf_counter_ns()
    for _ in range(N):
        _acc_alkalinity_as_caco3 += alkalinity_as_caco3(0.5, 0.5, 0.5)
    var _t1_alkalinity_as_caco3 = perf_counter_ns()
    var _ns_alkalinity_as_caco3 = Float64(_t1_alkalinity_as_caco3 - _t0_alkalinity_as_caco3) / Float64(N)
    print("MOJO_TIMING water_chemistry::alkalinity_as_caco3", _ns_alkalinity_as_caco3, _acc_alkalinity_as_caco3)
    var _acc_langelier_saturation_index: Float64 = 0.0
    var _t0_langelier_saturation_index = perf_counter_ns()
    for _ in range(N):
        _acc_langelier_saturation_index += langelier_saturation_index(0.5, 0.5)
    var _t1_langelier_saturation_index = perf_counter_ns()
    var _ns_langelier_saturation_index = Float64(_t1_langelier_saturation_index - _t0_langelier_saturation_index) / Float64(N)
    print("MOJO_TIMING water_chemistry::langelier_saturation_index", _ns_langelier_saturation_index, _acc_langelier_saturation_index)
    var _acc_turbidity_ntu_to_sdd: Float64 = 0.0
    var _t0_turbidity_ntu_to_sdd = perf_counter_ns()
    for _ in range(N):
        _acc_turbidity_ntu_to_sdd += turbidity_ntu_to_sdd(0.5)
    var _t1_turbidity_ntu_to_sdd = perf_counter_ns()
    var _ns_turbidity_ntu_to_sdd = Float64(_t1_turbidity_ntu_to_sdd - _t0_turbidity_ntu_to_sdd) / Float64(N)
    print("MOJO_TIMING water_chemistry::turbidity_ntu_to_sdd", _ns_turbidity_ntu_to_sdd, _acc_turbidity_ntu_to_sdd)
    var _acc_chlorine_demand: Float64 = 0.0
    var _t0_chlorine_demand = perf_counter_ns()
    for _ in range(N):
        _acc_chlorine_demand += chlorine_demand(0.5, 0.5)
    var _t1_chlorine_demand = perf_counter_ns()
    var _ns_chlorine_demand = Float64(_t1_chlorine_demand - _t0_chlorine_demand) / Float64(N)
    print("MOJO_TIMING water_chemistry::chlorine_demand", _ns_chlorine_demand, _acc_chlorine_demand)
    var _acc_dissolved_oxygen_deficit: Float64 = 0.0
    var _t0_dissolved_oxygen_deficit = perf_counter_ns()
    for _ in range(N):
        _acc_dissolved_oxygen_deficit += dissolved_oxygen_deficit(0.5, 0.5)
    var _t1_dissolved_oxygen_deficit = perf_counter_ns()
    var _ns_dissolved_oxygen_deficit = Float64(_t1_dissolved_oxygen_deficit - _t0_dissolved_oxygen_deficit) / Float64(N)
    print("MOJO_TIMING water_chemistry::dissolved_oxygen_deficit", _ns_dissolved_oxygen_deficit, _acc_dissolved_oxygen_deficit)
    var _acc_conductivity_tds: Float64 = 0.0
    var _t0_conductivity_tds = perf_counter_ns()
    for _ in range(N):
        _acc_conductivity_tds += conductivity_tds(0.5, 0.5)
    var _t1_conductivity_tds = perf_counter_ns()
    var _ns_conductivity_tds = Float64(_t1_conductivity_tds - _t0_conductivity_tds) / Float64(N)
    print("MOJO_TIMING water_chemistry::conductivity_tds", _ns_conductivity_tds, _acc_conductivity_tds)
    var _acc_bod_removal: Float64 = 0.0
    var _t0_bod_removal = perf_counter_ns()
    for _ in range(N):
        _acc_bod_removal += bod_removal(0.5, 0.5)
    var _t1_bod_removal = perf_counter_ns()
    var _ns_bod_removal = Float64(_t1_bod_removal - _t0_bod_removal) / Float64(N)
    print("MOJO_TIMING water_chemistry::bod_removal", _ns_bod_removal, _acc_bod_removal)
