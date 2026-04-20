"""bench_aquaculture.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from aquaculture import stocking_density, feed_conversion_ratio, specific_growth_rate, dissolved_oxygen_consumption, water_exchange_rate, ammonia_production, carrying_capacity, harvest_weight, survival_rate, production_per_cycle, biofilter_capacity, cost_per_kg_produced
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

    var _acc_stocking_density: Float64 = 0.0
    var _t0_stocking_density = perf_counter_ns()
    for _ in range(N):
        _acc_stocking_density += stocking_density(0.5, 0.5)
    var _t1_stocking_density = perf_counter_ns()
    var _ns_stocking_density = Float64(_t1_stocking_density - _t0_stocking_density) / Float64(N)
    print("MOJO_TIMING aquaculture::stocking_density", _ns_stocking_density, _acc_stocking_density)
    var _acc_feed_conversion_ratio: Float64 = 0.0
    var _t0_feed_conversion_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_feed_conversion_ratio += feed_conversion_ratio(0.5, 0.5)
    var _t1_feed_conversion_ratio = perf_counter_ns()
    var _ns_feed_conversion_ratio = Float64(_t1_feed_conversion_ratio - _t0_feed_conversion_ratio) / Float64(N)
    print("MOJO_TIMING aquaculture::feed_conversion_ratio", _ns_feed_conversion_ratio, _acc_feed_conversion_ratio)
    var _acc_specific_growth_rate: Float64 = 0.0
    var _t0_specific_growth_rate = perf_counter_ns()
    for _ in range(N):
        _acc_specific_growth_rate += specific_growth_rate(0.5, 0.5, 0.5)
    var _t1_specific_growth_rate = perf_counter_ns()
    var _ns_specific_growth_rate = Float64(_t1_specific_growth_rate - _t0_specific_growth_rate) / Float64(N)
    print("MOJO_TIMING aquaculture::specific_growth_rate", _ns_specific_growth_rate, _acc_specific_growth_rate)
    var _acc_dissolved_oxygen_consumption: Float64 = 0.0
    var _t0_dissolved_oxygen_consumption = perf_counter_ns()
    for _ in range(N):
        _acc_dissolved_oxygen_consumption += dissolved_oxygen_consumption(0.5, 0.5)
    var _t1_dissolved_oxygen_consumption = perf_counter_ns()
    var _ns_dissolved_oxygen_consumption = Float64(_t1_dissolved_oxygen_consumption - _t0_dissolved_oxygen_consumption) / Float64(N)
    print("MOJO_TIMING aquaculture::dissolved_oxygen_consumption", _ns_dissolved_oxygen_consumption, _acc_dissolved_oxygen_consumption)
    var _acc_water_exchange_rate: Float64 = 0.0
    var _t0_water_exchange_rate = perf_counter_ns()
    for _ in range(N):
        _acc_water_exchange_rate += water_exchange_rate(0.5, 0.5)
    var _t1_water_exchange_rate = perf_counter_ns()
    var _ns_water_exchange_rate = Float64(_t1_water_exchange_rate - _t0_water_exchange_rate) / Float64(N)
    print("MOJO_TIMING aquaculture::water_exchange_rate", _ns_water_exchange_rate, _acc_water_exchange_rate)
    var _acc_ammonia_production: Float64 = 0.0
    var _t0_ammonia_production = perf_counter_ns()
    for _ in range(N):
        _acc_ammonia_production += ammonia_production(0.5, 0.5)
    var _t1_ammonia_production = perf_counter_ns()
    var _ns_ammonia_production = Float64(_t1_ammonia_production - _t0_ammonia_production) / Float64(N)
    print("MOJO_TIMING aquaculture::ammonia_production", _ns_ammonia_production, _acc_ammonia_production)
    var _acc_carrying_capacity: Float64 = 0.0
    var _t0_carrying_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_carrying_capacity += carrying_capacity(0.5, 0.5)
    var _t1_carrying_capacity = perf_counter_ns()
    var _ns_carrying_capacity = Float64(_t1_carrying_capacity - _t0_carrying_capacity) / Float64(N)
    print("MOJO_TIMING aquaculture::carrying_capacity", _ns_carrying_capacity, _acc_carrying_capacity)
    var _acc_harvest_weight: Float64 = 0.0
    var _t0_harvest_weight = perf_counter_ns()
    for _ in range(N):
        _acc_harvest_weight += harvest_weight(0.5, 0.5, 0.5)
    var _t1_harvest_weight = perf_counter_ns()
    var _ns_harvest_weight = Float64(_t1_harvest_weight - _t0_harvest_weight) / Float64(N)
    print("MOJO_TIMING aquaculture::harvest_weight", _ns_harvest_weight, _acc_harvest_weight)
    var _acc_survival_rate: Float64 = 0.0
    var _t0_survival_rate = perf_counter_ns()
    for _ in range(N):
        _acc_survival_rate += survival_rate(0.5, 0.5)
    var _t1_survival_rate = perf_counter_ns()
    var _ns_survival_rate = Float64(_t1_survival_rate - _t0_survival_rate) / Float64(N)
    print("MOJO_TIMING aquaculture::survival_rate", _ns_survival_rate, _acc_survival_rate)
    var _acc_production_per_cycle: Float64 = 0.0
    var _t0_production_per_cycle = perf_counter_ns()
    for _ in range(N):
        _acc_production_per_cycle += production_per_cycle(0.5, 0.5, 0.5)
    var _t1_production_per_cycle = perf_counter_ns()
    var _ns_production_per_cycle = Float64(_t1_production_per_cycle - _t0_production_per_cycle) / Float64(N)
    print("MOJO_TIMING aquaculture::production_per_cycle", _ns_production_per_cycle, _acc_production_per_cycle)
    var _acc_biofilter_capacity: Float64 = 0.0
    var _t0_biofilter_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_biofilter_capacity += biofilter_capacity(0.5, 0.5)
    var _t1_biofilter_capacity = perf_counter_ns()
    var _ns_biofilter_capacity = Float64(_t1_biofilter_capacity - _t0_biofilter_capacity) / Float64(N)
    print("MOJO_TIMING aquaculture::biofilter_capacity", _ns_biofilter_capacity, _acc_biofilter_capacity)
    var _acc_cost_per_kg_produced: Float64 = 0.0
    var _t0_cost_per_kg_produced = perf_counter_ns()
    for _ in range(N):
        _acc_cost_per_kg_produced += cost_per_kg_produced(0.5, 0.5)
    var _t1_cost_per_kg_produced = perf_counter_ns()
    var _ns_cost_per_kg_produced = Float64(_t1_cost_per_kg_produced - _t0_cost_per_kg_produced) / Float64(N)
    print("MOJO_TIMING aquaculture::cost_per_kg_produced", _ns_cost_per_kg_produced, _acc_cost_per_kg_produced)
