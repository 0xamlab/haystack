"""bench_aquaculture.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from aquaculture import stocking_density, feed_conversion_ratio, specific_growth_rate, dissolved_oxygen_consumption, water_exchange_rate, ammonia_production, carrying_capacity, harvest_weight, survival_rate, production_per_cycle, biofilter_capacity, cost_per_kg_produced
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))


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
    var _result_stocking_density = stocking_density(0.5, 0.5)
    var _summary_stocking_density = _summary_float64(_result_stocking_density)
    print("MOJO_RESULT aquaculture::stocking_density", _summary_stocking_density)
    var _acc_feed_conversion_ratio: Float64 = 0.0
    var _t0_feed_conversion_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_feed_conversion_ratio += feed_conversion_ratio(0.5, 0.5)
    var _t1_feed_conversion_ratio = perf_counter_ns()
    var _ns_feed_conversion_ratio = Float64(_t1_feed_conversion_ratio - _t0_feed_conversion_ratio) / Float64(N)
    print("MOJO_TIMING aquaculture::feed_conversion_ratio", _ns_feed_conversion_ratio, _acc_feed_conversion_ratio)
    var _result_feed_conversion_ratio = feed_conversion_ratio(0.5, 0.5)
    var _summary_feed_conversion_ratio = _summary_float64(_result_feed_conversion_ratio)
    print("MOJO_RESULT aquaculture::feed_conversion_ratio", _summary_feed_conversion_ratio)
    var _acc_specific_growth_rate: Float64 = 0.0
    var _t0_specific_growth_rate = perf_counter_ns()
    for _ in range(N):
        _acc_specific_growth_rate += specific_growth_rate(0.5, 0.5, 0.5)
    var _t1_specific_growth_rate = perf_counter_ns()
    var _ns_specific_growth_rate = Float64(_t1_specific_growth_rate - _t0_specific_growth_rate) / Float64(N)
    print("MOJO_TIMING aquaculture::specific_growth_rate", _ns_specific_growth_rate, _acc_specific_growth_rate)
    var _result_specific_growth_rate = specific_growth_rate(0.5, 0.5, 0.5)
    var _summary_specific_growth_rate = _summary_float64(_result_specific_growth_rate)
    print("MOJO_RESULT aquaculture::specific_growth_rate", _summary_specific_growth_rate)
    var _acc_dissolved_oxygen_consumption: Float64 = 0.0
    var _t0_dissolved_oxygen_consumption = perf_counter_ns()
    for _ in range(N):
        _acc_dissolved_oxygen_consumption += dissolved_oxygen_consumption(0.5, 0.5)
    var _t1_dissolved_oxygen_consumption = perf_counter_ns()
    var _ns_dissolved_oxygen_consumption = Float64(_t1_dissolved_oxygen_consumption - _t0_dissolved_oxygen_consumption) / Float64(N)
    print("MOJO_TIMING aquaculture::dissolved_oxygen_consumption", _ns_dissolved_oxygen_consumption, _acc_dissolved_oxygen_consumption)
    var _result_dissolved_oxygen_consumption = dissolved_oxygen_consumption(0.5, 0.5)
    var _summary_dissolved_oxygen_consumption = _summary_float64(_result_dissolved_oxygen_consumption)
    print("MOJO_RESULT aquaculture::dissolved_oxygen_consumption", _summary_dissolved_oxygen_consumption)
    var _acc_water_exchange_rate: Float64 = 0.0
    var _t0_water_exchange_rate = perf_counter_ns()
    for _ in range(N):
        _acc_water_exchange_rate += water_exchange_rate(0.5, 0.5)
    var _t1_water_exchange_rate = perf_counter_ns()
    var _ns_water_exchange_rate = Float64(_t1_water_exchange_rate - _t0_water_exchange_rate) / Float64(N)
    print("MOJO_TIMING aquaculture::water_exchange_rate", _ns_water_exchange_rate, _acc_water_exchange_rate)
    var _result_water_exchange_rate = water_exchange_rate(0.5, 0.5)
    var _summary_water_exchange_rate = _summary_float64(_result_water_exchange_rate)
    print("MOJO_RESULT aquaculture::water_exchange_rate", _summary_water_exchange_rate)
    var _acc_ammonia_production: Float64 = 0.0
    var _t0_ammonia_production = perf_counter_ns()
    for _ in range(N):
        _acc_ammonia_production += ammonia_production(0.5, 0.5)
    var _t1_ammonia_production = perf_counter_ns()
    var _ns_ammonia_production = Float64(_t1_ammonia_production - _t0_ammonia_production) / Float64(N)
    print("MOJO_TIMING aquaculture::ammonia_production", _ns_ammonia_production, _acc_ammonia_production)
    var _result_ammonia_production = ammonia_production(0.5, 0.5)
    var _summary_ammonia_production = _summary_float64(_result_ammonia_production)
    print("MOJO_RESULT aquaculture::ammonia_production", _summary_ammonia_production)
    var _acc_carrying_capacity: Float64 = 0.0
    var _t0_carrying_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_carrying_capacity += carrying_capacity(0.5, 0.5)
    var _t1_carrying_capacity = perf_counter_ns()
    var _ns_carrying_capacity = Float64(_t1_carrying_capacity - _t0_carrying_capacity) / Float64(N)
    print("MOJO_TIMING aquaculture::carrying_capacity", _ns_carrying_capacity, _acc_carrying_capacity)
    var _result_carrying_capacity = carrying_capacity(0.5, 0.5)
    var _summary_carrying_capacity = _summary_float64(_result_carrying_capacity)
    print("MOJO_RESULT aquaculture::carrying_capacity", _summary_carrying_capacity)
    var _acc_harvest_weight: Float64 = 0.0
    var _t0_harvest_weight = perf_counter_ns()
    for _ in range(N):
        _acc_harvest_weight += harvest_weight(0.5, 0.5, 0.5)
    var _t1_harvest_weight = perf_counter_ns()
    var _ns_harvest_weight = Float64(_t1_harvest_weight - _t0_harvest_weight) / Float64(N)
    print("MOJO_TIMING aquaculture::harvest_weight", _ns_harvest_weight, _acc_harvest_weight)
    var _result_harvest_weight = harvest_weight(0.5, 0.5, 0.5)
    var _summary_harvest_weight = _summary_float64(_result_harvest_weight)
    print("MOJO_RESULT aquaculture::harvest_weight", _summary_harvest_weight)
    var _acc_survival_rate: Float64 = 0.0
    var _t0_survival_rate = perf_counter_ns()
    for _ in range(N):
        _acc_survival_rate += survival_rate(0.5, 0.5)
    var _t1_survival_rate = perf_counter_ns()
    var _ns_survival_rate = Float64(_t1_survival_rate - _t0_survival_rate) / Float64(N)
    print("MOJO_TIMING aquaculture::survival_rate", _ns_survival_rate, _acc_survival_rate)
    var _result_survival_rate = survival_rate(0.5, 0.5)
    var _summary_survival_rate = _summary_float64(_result_survival_rate)
    print("MOJO_RESULT aquaculture::survival_rate", _summary_survival_rate)
    var _acc_production_per_cycle: Float64 = 0.0
    var _t0_production_per_cycle = perf_counter_ns()
    for _ in range(N):
        _acc_production_per_cycle += production_per_cycle(0.5, 0.5, 0.5)
    var _t1_production_per_cycle = perf_counter_ns()
    var _ns_production_per_cycle = Float64(_t1_production_per_cycle - _t0_production_per_cycle) / Float64(N)
    print("MOJO_TIMING aquaculture::production_per_cycle", _ns_production_per_cycle, _acc_production_per_cycle)
    var _result_production_per_cycle = production_per_cycle(0.5, 0.5, 0.5)
    var _summary_production_per_cycle = _summary_float64(_result_production_per_cycle)
    print("MOJO_RESULT aquaculture::production_per_cycle", _summary_production_per_cycle)
    var _acc_biofilter_capacity: Float64 = 0.0
    var _t0_biofilter_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_biofilter_capacity += biofilter_capacity(0.5, 0.5)
    var _t1_biofilter_capacity = perf_counter_ns()
    var _ns_biofilter_capacity = Float64(_t1_biofilter_capacity - _t0_biofilter_capacity) / Float64(N)
    print("MOJO_TIMING aquaculture::biofilter_capacity", _ns_biofilter_capacity, _acc_biofilter_capacity)
    var _result_biofilter_capacity = biofilter_capacity(0.5, 0.5)
    var _summary_biofilter_capacity = _summary_float64(_result_biofilter_capacity)
    print("MOJO_RESULT aquaculture::biofilter_capacity", _summary_biofilter_capacity)
    var _acc_cost_per_kg_produced: Float64 = 0.0
    var _t0_cost_per_kg_produced = perf_counter_ns()
    for _ in range(N):
        _acc_cost_per_kg_produced += cost_per_kg_produced(0.5, 0.5)
    var _t1_cost_per_kg_produced = perf_counter_ns()
    var _ns_cost_per_kg_produced = Float64(_t1_cost_per_kg_produced - _t0_cost_per_kg_produced) / Float64(N)
    print("MOJO_TIMING aquaculture::cost_per_kg_produced", _ns_cost_per_kg_produced, _acc_cost_per_kg_produced)
    var _result_cost_per_kg_produced = cost_per_kg_produced(0.5, 0.5)
    var _summary_cost_per_kg_produced = _summary_float64(_result_cost_per_kg_produced)
    print("MOJO_RESULT aquaculture::cost_per_kg_produced", _summary_cost_per_kg_produced)
