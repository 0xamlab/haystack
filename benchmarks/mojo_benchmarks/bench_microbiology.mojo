"""bench_microbiology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from microbiology import exponential_growth, doubling_time, monod_growth_rate, bacterial_generation_time, colony_forming_units, minimum_inhibitory_conc, biofilm_formation_index, inactivation_first_order, d_value, z_value
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

    var _acc_exponential_growth: Float64 = 0.0
    var _t0_exponential_growth = perf_counter_ns()
    for _ in range(N):
        _acc_exponential_growth += exponential_growth(0.5, 0.5, 0.5)
    var _t1_exponential_growth = perf_counter_ns()
    var _ns_exponential_growth = Float64(_t1_exponential_growth - _t0_exponential_growth) / Float64(N)
    print("MOJO_TIMING microbiology::exponential_growth", _ns_exponential_growth, _acc_exponential_growth)
    var _acc_doubling_time: Float64 = 0.0
    var _t0_doubling_time = perf_counter_ns()
    for _ in range(N):
        _acc_doubling_time += doubling_time(0.5)
    var _t1_doubling_time = perf_counter_ns()
    var _ns_doubling_time = Float64(_t1_doubling_time - _t0_doubling_time) / Float64(N)
    print("MOJO_TIMING microbiology::doubling_time", _ns_doubling_time, _acc_doubling_time)
    var _acc_monod_growth_rate: Float64 = 0.0
    var _t0_monod_growth_rate = perf_counter_ns()
    for _ in range(N):
        _acc_monod_growth_rate += monod_growth_rate(0.5, 0.5, 0.5)
    var _t1_monod_growth_rate = perf_counter_ns()
    var _ns_monod_growth_rate = Float64(_t1_monod_growth_rate - _t0_monod_growth_rate) / Float64(N)
    print("MOJO_TIMING microbiology::monod_growth_rate", _ns_monod_growth_rate, _acc_monod_growth_rate)
    var _acc_bacterial_generation_time: Float64 = 0.0
    var _t0_bacterial_generation_time = perf_counter_ns()
    for _ in range(N):
        _acc_bacterial_generation_time += bacterial_generation_time(0.5, 0.5, 0.5)
    var _t1_bacterial_generation_time = perf_counter_ns()
    var _ns_bacterial_generation_time = Float64(_t1_bacterial_generation_time - _t0_bacterial_generation_time) / Float64(N)
    print("MOJO_TIMING microbiology::bacterial_generation_time", _ns_bacterial_generation_time, _acc_bacterial_generation_time)
    var _acc_colony_forming_units: Float64 = 0.0
    var _t0_colony_forming_units = perf_counter_ns()
    for _ in range(N):
        _acc_colony_forming_units += colony_forming_units(0.5, 0.5, 0.5)
    var _t1_colony_forming_units = perf_counter_ns()
    var _ns_colony_forming_units = Float64(_t1_colony_forming_units - _t0_colony_forming_units) / Float64(N)
    print("MOJO_TIMING microbiology::colony_forming_units", _ns_colony_forming_units, _acc_colony_forming_units)
    var _acc_minimum_inhibitory_conc: Float64 = 0.0
    var _t0_minimum_inhibitory_conc = perf_counter_ns()
    for _ in range(N):
        _acc_minimum_inhibitory_conc += minimum_inhibitory_conc(0.5, 0.5)
    var _t1_minimum_inhibitory_conc = perf_counter_ns()
    var _ns_minimum_inhibitory_conc = Float64(_t1_minimum_inhibitory_conc - _t0_minimum_inhibitory_conc) / Float64(N)
    print("MOJO_TIMING microbiology::minimum_inhibitory_conc", _ns_minimum_inhibitory_conc, _acc_minimum_inhibitory_conc)
    var _acc_biofilm_formation_index: Float64 = 0.0
    var _t0_biofilm_formation_index = perf_counter_ns()
    for _ in range(N):
        _acc_biofilm_formation_index += biofilm_formation_index(0.5, 0.5)
    var _t1_biofilm_formation_index = perf_counter_ns()
    var _ns_biofilm_formation_index = Float64(_t1_biofilm_formation_index - _t0_biofilm_formation_index) / Float64(N)
    print("MOJO_TIMING microbiology::biofilm_formation_index", _ns_biofilm_formation_index, _acc_biofilm_formation_index)
    var _acc_inactivation_first_order: Float64 = 0.0
    var _t0_inactivation_first_order = perf_counter_ns()
    for _ in range(N):
        _acc_inactivation_first_order += inactivation_first_order(0.5, 0.5, 0.5)
    var _t1_inactivation_first_order = perf_counter_ns()
    var _ns_inactivation_first_order = Float64(_t1_inactivation_first_order - _t0_inactivation_first_order) / Float64(N)
    print("MOJO_TIMING microbiology::inactivation_first_order", _ns_inactivation_first_order, _acc_inactivation_first_order)
    var _acc_d_value: Float64 = 0.0
    var _t0_d_value = perf_counter_ns()
    for _ in range(N):
        _acc_d_value += d_value(0.5)
    var _t1_d_value = perf_counter_ns()
    var _ns_d_value = Float64(_t1_d_value - _t0_d_value) / Float64(N)
    print("MOJO_TIMING microbiology::d_value", _ns_d_value, _acc_d_value)
    var _acc_z_value: Float64 = 0.0
    var _t0_z_value = perf_counter_ns()
    for _ in range(N):
        _acc_z_value += z_value(0.5, 0.5, 0.5, 0.5)
    var _t1_z_value = perf_counter_ns()
    var _ns_z_value = Float64(_t1_z_value - _t0_z_value) / Float64(N)
    print("MOJO_TIMING microbiology::z_value", _ns_z_value, _acc_z_value)
