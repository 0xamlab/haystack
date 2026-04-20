"""bench_wastewater.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from wastewater import bod_removal_efficiency, hydraulic_retention_time, solids_retention_time, food_to_microorganism_ratio, sludge_volume_index, oxygen_demand, chlorine_demand, ct_value, alkalinity_consumption, sludge_production, trickling_filter_efficiency, detention_time_settling
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

    var _acc_bod_removal_efficiency: Float64 = 0.0
    var _t0_bod_removal_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_bod_removal_efficiency += bod_removal_efficiency(0.5, 0.5)
    var _t1_bod_removal_efficiency = perf_counter_ns()
    var _ns_bod_removal_efficiency = Float64(_t1_bod_removal_efficiency - _t0_bod_removal_efficiency) / Float64(N)
    print("MOJO_TIMING wastewater::bod_removal_efficiency", _ns_bod_removal_efficiency, _acc_bod_removal_efficiency)
    var _acc_hydraulic_retention_time: Float64 = 0.0
    var _t0_hydraulic_retention_time = perf_counter_ns()
    for _ in range(N):
        _acc_hydraulic_retention_time += hydraulic_retention_time(0.5, 0.5)
    var _t1_hydraulic_retention_time = perf_counter_ns()
    var _ns_hydraulic_retention_time = Float64(_t1_hydraulic_retention_time - _t0_hydraulic_retention_time) / Float64(N)
    print("MOJO_TIMING wastewater::hydraulic_retention_time", _ns_hydraulic_retention_time, _acc_hydraulic_retention_time)
    var _acc_solids_retention_time: Float64 = 0.0
    var _t0_solids_retention_time = perf_counter_ns()
    for _ in range(N):
        _acc_solids_retention_time += solids_retention_time(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_solids_retention_time = perf_counter_ns()
    var _ns_solids_retention_time = Float64(_t1_solids_retention_time - _t0_solids_retention_time) / Float64(N)
    print("MOJO_TIMING wastewater::solids_retention_time", _ns_solids_retention_time, _acc_solids_retention_time)
    var _acc_food_to_microorganism_ratio: Float64 = 0.0
    var _t0_food_to_microorganism_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_food_to_microorganism_ratio += food_to_microorganism_ratio(0.5, 0.5, 0.5, 0.5)
    var _t1_food_to_microorganism_ratio = perf_counter_ns()
    var _ns_food_to_microorganism_ratio = Float64(_t1_food_to_microorganism_ratio - _t0_food_to_microorganism_ratio) / Float64(N)
    print("MOJO_TIMING wastewater::food_to_microorganism_ratio", _ns_food_to_microorganism_ratio, _acc_food_to_microorganism_ratio)
    var _acc_sludge_volume_index: Float64 = 0.0
    var _t0_sludge_volume_index = perf_counter_ns()
    for _ in range(N):
        _acc_sludge_volume_index += sludge_volume_index(0.5, 0.5)
    var _t1_sludge_volume_index = perf_counter_ns()
    var _ns_sludge_volume_index = Float64(_t1_sludge_volume_index - _t0_sludge_volume_index) / Float64(N)
    print("MOJO_TIMING wastewater::sludge_volume_index", _ns_sludge_volume_index, _acc_sludge_volume_index)
    var _acc_oxygen_demand: Float64 = 0.0
    var _t0_oxygen_demand = perf_counter_ns()
    for _ in range(N):
        _acc_oxygen_demand += oxygen_demand(0.5, 0.5, 0.5, 0.5)
    var _t1_oxygen_demand = perf_counter_ns()
    var _ns_oxygen_demand = Float64(_t1_oxygen_demand - _t0_oxygen_demand) / Float64(N)
    print("MOJO_TIMING wastewater::oxygen_demand", _ns_oxygen_demand, _acc_oxygen_demand)
    var _acc_chlorine_demand: Float64 = 0.0
    var _t0_chlorine_demand = perf_counter_ns()
    for _ in range(N):
        _acc_chlorine_demand += chlorine_demand(0.5, 0.5)
    var _t1_chlorine_demand = perf_counter_ns()
    var _ns_chlorine_demand = Float64(_t1_chlorine_demand - _t0_chlorine_demand) / Float64(N)
    print("MOJO_TIMING wastewater::chlorine_demand", _ns_chlorine_demand, _acc_chlorine_demand)
    var _acc_ct_value: Float64 = 0.0
    var _t0_ct_value = perf_counter_ns()
    for _ in range(N):
        _acc_ct_value += ct_value(0.5, 0.5)
    var _t1_ct_value = perf_counter_ns()
    var _ns_ct_value = Float64(_t1_ct_value - _t0_ct_value) / Float64(N)
    print("MOJO_TIMING wastewater::ct_value", _ns_ct_value, _acc_ct_value)
    var _acc_alkalinity_consumption: Float64 = 0.0
    var _t0_alkalinity_consumption = perf_counter_ns()
    for _ in range(N):
        _acc_alkalinity_consumption += alkalinity_consumption(0.5)
    var _t1_alkalinity_consumption = perf_counter_ns()
    var _ns_alkalinity_consumption = Float64(_t1_alkalinity_consumption - _t0_alkalinity_consumption) / Float64(N)
    print("MOJO_TIMING wastewater::alkalinity_consumption", _ns_alkalinity_consumption, _acc_alkalinity_consumption)
    var _acc_sludge_production: Float64 = 0.0
    var _t0_sludge_production = perf_counter_ns()
    for _ in range(N):
        _acc_sludge_production += sludge_production(0.5, 0.5, 0.5, 0.5)
    var _t1_sludge_production = perf_counter_ns()
    var _ns_sludge_production = Float64(_t1_sludge_production - _t0_sludge_production) / Float64(N)
    print("MOJO_TIMING wastewater::sludge_production", _ns_sludge_production, _acc_sludge_production)
    var _acc_trickling_filter_efficiency: Float64 = 0.0
    var _t0_trickling_filter_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_trickling_filter_efficiency += trickling_filter_efficiency(0.5, 0.5)
    var _t1_trickling_filter_efficiency = perf_counter_ns()
    var _ns_trickling_filter_efficiency = Float64(_t1_trickling_filter_efficiency - _t0_trickling_filter_efficiency) / Float64(N)
    print("MOJO_TIMING wastewater::trickling_filter_efficiency", _ns_trickling_filter_efficiency, _acc_trickling_filter_efficiency)
    var _acc_detention_time_settling: Float64 = 0.0
    var _t0_detention_time_settling = perf_counter_ns()
    for _ in range(N):
        _acc_detention_time_settling += detention_time_settling(0.5, 0.5)
    var _t1_detention_time_settling = perf_counter_ns()
    var _ns_detention_time_settling = Float64(_t1_detention_time_settling - _t0_detention_time_settling) / Float64(N)
    print("MOJO_TIMING wastewater::detention_time_settling", _ns_detention_time_settling, _acc_detention_time_settling)
