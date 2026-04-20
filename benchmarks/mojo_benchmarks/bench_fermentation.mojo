"""bench_fermentation.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from fermentation import ethanol_yield, alcohol_by_volume, carbon_dioxide_produced, yeast_growth_rate, substrate_consumption, volumetric_productivity, fermentation_efficiency, dissolved_oxygen_kla, ph_buffer_capacity, heat_generation_rate
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

    var _acc_ethanol_yield: Float64 = 0.0
    var _t0_ethanol_yield = perf_counter_ns()
    for _ in range(N):
        _acc_ethanol_yield += ethanol_yield(0.5)
    var _t1_ethanol_yield = perf_counter_ns()
    var _ns_ethanol_yield = Float64(_t1_ethanol_yield - _t0_ethanol_yield) / Float64(N)
    print("MOJO_TIMING fermentation::ethanol_yield", _ns_ethanol_yield, _acc_ethanol_yield)
    var _acc_alcohol_by_volume: Float64 = 0.0
    var _t0_alcohol_by_volume = perf_counter_ns()
    for _ in range(N):
        _acc_alcohol_by_volume += alcohol_by_volume(0.5, 0.5)
    var _t1_alcohol_by_volume = perf_counter_ns()
    var _ns_alcohol_by_volume = Float64(_t1_alcohol_by_volume - _t0_alcohol_by_volume) / Float64(N)
    print("MOJO_TIMING fermentation::alcohol_by_volume", _ns_alcohol_by_volume, _acc_alcohol_by_volume)
    var _acc_carbon_dioxide_produced: Float64 = 0.0
    var _t0_carbon_dioxide_produced = perf_counter_ns()
    for _ in range(N):
        _acc_carbon_dioxide_produced += carbon_dioxide_produced(0.5)
    var _t1_carbon_dioxide_produced = perf_counter_ns()
    var _ns_carbon_dioxide_produced = Float64(_t1_carbon_dioxide_produced - _t0_carbon_dioxide_produced) / Float64(N)
    print("MOJO_TIMING fermentation::carbon_dioxide_produced", _ns_carbon_dioxide_produced, _acc_carbon_dioxide_produced)
    var _acc_yeast_growth_rate: Float64 = 0.0
    var _t0_yeast_growth_rate = perf_counter_ns()
    for _ in range(N):
        _acc_yeast_growth_rate += yeast_growth_rate(0.5, 0.5, 0.5, 0.5)
    var _t1_yeast_growth_rate = perf_counter_ns()
    var _ns_yeast_growth_rate = Float64(_t1_yeast_growth_rate - _t0_yeast_growth_rate) / Float64(N)
    print("MOJO_TIMING fermentation::yeast_growth_rate", _ns_yeast_growth_rate, _acc_yeast_growth_rate)
    var _acc_substrate_consumption: Float64 = 0.0
    var _t0_substrate_consumption = perf_counter_ns()
    for _ in range(N):
        _acc_substrate_consumption += substrate_consumption(0.5, 0.5, 0.5)
    var _t1_substrate_consumption = perf_counter_ns()
    var _ns_substrate_consumption = Float64(_t1_substrate_consumption - _t0_substrate_consumption) / Float64(N)
    print("MOJO_TIMING fermentation::substrate_consumption", _ns_substrate_consumption, _acc_substrate_consumption)
    var _acc_volumetric_productivity: Float64 = 0.0
    var _t0_volumetric_productivity = perf_counter_ns()
    for _ in range(N):
        _acc_volumetric_productivity += volumetric_productivity(0.5, 0.5)
    var _t1_volumetric_productivity = perf_counter_ns()
    var _ns_volumetric_productivity = Float64(_t1_volumetric_productivity - _t0_volumetric_productivity) / Float64(N)
    print("MOJO_TIMING fermentation::volumetric_productivity", _ns_volumetric_productivity, _acc_volumetric_productivity)
    var _acc_fermentation_efficiency: Float64 = 0.0
    var _t0_fermentation_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_fermentation_efficiency += fermentation_efficiency(0.5, 0.5)
    var _t1_fermentation_efficiency = perf_counter_ns()
    var _ns_fermentation_efficiency = Float64(_t1_fermentation_efficiency - _t0_fermentation_efficiency) / Float64(N)
    print("MOJO_TIMING fermentation::fermentation_efficiency", _ns_fermentation_efficiency, _acc_fermentation_efficiency)
    var _acc_dissolved_oxygen_kla: Float64 = 0.0
    var _t0_dissolved_oxygen_kla = perf_counter_ns()
    for _ in range(N):
        _acc_dissolved_oxygen_kla += dissolved_oxygen_kla(0.5, 0.5, 0.5)
    var _t1_dissolved_oxygen_kla = perf_counter_ns()
    var _ns_dissolved_oxygen_kla = Float64(_t1_dissolved_oxygen_kla - _t0_dissolved_oxygen_kla) / Float64(N)
    print("MOJO_TIMING fermentation::dissolved_oxygen_kla", _ns_dissolved_oxygen_kla, _acc_dissolved_oxygen_kla)
    var _acc_ph_buffer_capacity: Float64 = 0.0
    var _t0_ph_buffer_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_ph_buffer_capacity += ph_buffer_capacity(0.5, 0.5, 0.5)
    var _t1_ph_buffer_capacity = perf_counter_ns()
    var _ns_ph_buffer_capacity = Float64(_t1_ph_buffer_capacity - _t0_ph_buffer_capacity) / Float64(N)
    print("MOJO_TIMING fermentation::ph_buffer_capacity", _ns_ph_buffer_capacity, _acc_ph_buffer_capacity)
    var _acc_heat_generation_rate: Float64 = 0.0
    var _t0_heat_generation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_heat_generation_rate += heat_generation_rate(0.5, 0.5)
    var _t1_heat_generation_rate = perf_counter_ns()
    var _ns_heat_generation_rate = Float64(_t1_heat_generation_rate - _t0_heat_generation_rate) / Float64(N)
    print("MOJO_TIMING fermentation::heat_generation_rate", _ns_heat_generation_rate, _acc_heat_generation_rate)
