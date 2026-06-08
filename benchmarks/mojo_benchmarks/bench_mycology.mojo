"""bench_mycology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from mycology import spore_dispersal_distance, mycelial_growth_rate, fungal_biomass, sporulation_index, infection_efficiency, latent_period, epidemic_progress_rate, spore_germination_prob, colony_diameter, competitive_exclusion_index
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_spore_dispersal_distance: Float64 = 0.0
    var _t0_spore_dispersal_distance = perf_counter_ns()
    for _ in range(N):
        _acc_spore_dispersal_distance += spore_dispersal_distance(0.5, 0.5, 0.5)
    var _t1_spore_dispersal_distance = perf_counter_ns()
    var _ns_spore_dispersal_distance = Float64(_t1_spore_dispersal_distance - _t0_spore_dispersal_distance) / Float64(N)
    print("MOJO_TIMING mycology::spore_dispersal_distance", _ns_spore_dispersal_distance, _acc_spore_dispersal_distance)
    var _result_spore_dispersal_distance = spore_dispersal_distance(0.5, 0.5, 0.5)
    var _summary_spore_dispersal_distance = _summary_float64(_result_spore_dispersal_distance)
    print("MOJO_RESULT mycology::spore_dispersal_distance", _summary_spore_dispersal_distance)
    var _acc_mycelial_growth_rate: Float64 = 0.0
    var _t0_mycelial_growth_rate = perf_counter_ns()
    for _ in range(N):
        _acc_mycelial_growth_rate += mycelial_growth_rate(0.5, 0.5, 0.5)
    var _t1_mycelial_growth_rate = perf_counter_ns()
    var _ns_mycelial_growth_rate = Float64(_t1_mycelial_growth_rate - _t0_mycelial_growth_rate) / Float64(N)
    print("MOJO_TIMING mycology::mycelial_growth_rate", _ns_mycelial_growth_rate, _acc_mycelial_growth_rate)
    var _result_mycelial_growth_rate = mycelial_growth_rate(0.5, 0.5, 0.5)
    var _summary_mycelial_growth_rate = _summary_float64(_result_mycelial_growth_rate)
    print("MOJO_RESULT mycology::mycelial_growth_rate", _summary_mycelial_growth_rate)
    var _acc_fungal_biomass: Float64 = 0.0
    var _t0_fungal_biomass = perf_counter_ns()
    for _ in range(N):
        _acc_fungal_biomass += fungal_biomass(0.5, 0.5)
    var _t1_fungal_biomass = perf_counter_ns()
    var _ns_fungal_biomass = Float64(_t1_fungal_biomass - _t0_fungal_biomass) / Float64(N)
    print("MOJO_TIMING mycology::fungal_biomass", _ns_fungal_biomass, _acc_fungal_biomass)
    var _result_fungal_biomass = fungal_biomass(0.5, 0.5)
    var _summary_fungal_biomass = _summary_float64(_result_fungal_biomass)
    print("MOJO_RESULT mycology::fungal_biomass", _summary_fungal_biomass)
    var _acc_sporulation_index: Float64 = 0.0
    var _t0_sporulation_index = perf_counter_ns()
    for _ in range(N):
        _acc_sporulation_index += sporulation_index(0.5, 0.5)
    var _t1_sporulation_index = perf_counter_ns()
    var _ns_sporulation_index = Float64(_t1_sporulation_index - _t0_sporulation_index) / Float64(N)
    print("MOJO_TIMING mycology::sporulation_index", _ns_sporulation_index, _acc_sporulation_index)
    var _result_sporulation_index = sporulation_index(0.5, 0.5)
    var _summary_sporulation_index = _summary_float64(_result_sporulation_index)
    print("MOJO_RESULT mycology::sporulation_index", _summary_sporulation_index)
    var _acc_infection_efficiency: Float64 = 0.0
    var _t0_infection_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_infection_efficiency += infection_efficiency(0.5, 0.5)
    var _t1_infection_efficiency = perf_counter_ns()
    var _ns_infection_efficiency = Float64(_t1_infection_efficiency - _t0_infection_efficiency) / Float64(N)
    print("MOJO_TIMING mycology::infection_efficiency", _ns_infection_efficiency, _acc_infection_efficiency)
    var _result_infection_efficiency = infection_efficiency(0.5, 0.5)
    var _summary_infection_efficiency = _summary_float64(_result_infection_efficiency)
    print("MOJO_RESULT mycology::infection_efficiency", _summary_infection_efficiency)
    var _acc_latent_period: Float64 = 0.0
    var _t0_latent_period = perf_counter_ns()
    for _ in range(N):
        _acc_latent_period += latent_period(0.5, 0.5, 0.5)
    var _t1_latent_period = perf_counter_ns()
    var _ns_latent_period = Float64(_t1_latent_period - _t0_latent_period) / Float64(N)
    print("MOJO_TIMING mycology::latent_period", _ns_latent_period, _acc_latent_period)
    var _result_latent_period = latent_period(0.5, 0.5, 0.5)
    var _summary_latent_period = _summary_float64(_result_latent_period)
    print("MOJO_RESULT mycology::latent_period", _summary_latent_period)
    var _acc_epidemic_progress_rate: Float64 = 0.0
    var _t0_epidemic_progress_rate = perf_counter_ns()
    for _ in range(N):
        _acc_epidemic_progress_rate += epidemic_progress_rate(0.5, 0.5, 0.5, 0.5)
    var _t1_epidemic_progress_rate = perf_counter_ns()
    var _ns_epidemic_progress_rate = Float64(_t1_epidemic_progress_rate - _t0_epidemic_progress_rate) / Float64(N)
    print("MOJO_TIMING mycology::epidemic_progress_rate", _ns_epidemic_progress_rate, _acc_epidemic_progress_rate)
    var _result_epidemic_progress_rate = epidemic_progress_rate(0.5, 0.5, 0.5, 0.5)
    var _summary_epidemic_progress_rate = _summary_float64(_result_epidemic_progress_rate)
    print("MOJO_RESULT mycology::epidemic_progress_rate", _summary_epidemic_progress_rate)
    var _acc_spore_germination_prob: Float64 = 0.0
    var _t0_spore_germination_prob = perf_counter_ns()
    for _ in range(N):
        _acc_spore_germination_prob += spore_germination_prob(0.5, 0.5, 0.5)
    var _t1_spore_germination_prob = perf_counter_ns()
    var _ns_spore_germination_prob = Float64(_t1_spore_germination_prob - _t0_spore_germination_prob) / Float64(N)
    print("MOJO_TIMING mycology::spore_germination_prob", _ns_spore_germination_prob, _acc_spore_germination_prob)
    var _result_spore_germination_prob = spore_germination_prob(0.5, 0.5, 0.5)
    var _summary_spore_germination_prob = _summary_float64(_result_spore_germination_prob)
    print("MOJO_RESULT mycology::spore_germination_prob", _summary_spore_germination_prob)
    var _acc_colony_diameter: Float64 = 0.0
    var _t0_colony_diameter = perf_counter_ns()
    for _ in range(N):
        _acc_colony_diameter += colony_diameter(0.5, 0.5)
    var _t1_colony_diameter = perf_counter_ns()
    var _ns_colony_diameter = Float64(_t1_colony_diameter - _t0_colony_diameter) / Float64(N)
    print("MOJO_TIMING mycology::colony_diameter", _ns_colony_diameter, _acc_colony_diameter)
    var _result_colony_diameter = colony_diameter(0.5, 0.5)
    var _summary_colony_diameter = _summary_float64(_result_colony_diameter)
    print("MOJO_RESULT mycology::colony_diameter", _summary_colony_diameter)
    var _acc_competitive_exclusion_index: Float64 = 0.0
    var _t0_competitive_exclusion_index = perf_counter_ns()
    for _ in range(N):
        _acc_competitive_exclusion_index += competitive_exclusion_index(0.5, 0.5)
    var _t1_competitive_exclusion_index = perf_counter_ns()
    var _ns_competitive_exclusion_index = Float64(_t1_competitive_exclusion_index - _t0_competitive_exclusion_index) / Float64(N)
    print("MOJO_TIMING mycology::competitive_exclusion_index", _ns_competitive_exclusion_index, _acc_competitive_exclusion_index)
    var _result_competitive_exclusion_index = competitive_exclusion_index(0.5, 0.5)
    var _summary_competitive_exclusion_index = _summary_float64(_result_competitive_exclusion_index)
    print("MOJO_RESULT mycology::competitive_exclusion_index", _summary_competitive_exclusion_index)
