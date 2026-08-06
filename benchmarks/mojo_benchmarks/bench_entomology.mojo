"""bench_entomology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from entomology import degree_days, accumulated_degree_days, population_growth_intrinsic, net_reproductive_rate, generation_time, doubling_time_population, species_diversity_simpson, trap_catch_index, infestation_rate, biocontrol_efficacy, larval_mortality_rate, metabolic_rate_insect
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

    var _acc_degree_days: Float64 = 0.0
    var _t0_degree_days = perf_counter_ns()
    for _ in range(N):
        _acc_degree_days += degree_days(0.5, 0.5, 0.5)
    var _t1_degree_days = perf_counter_ns()
    var _ns_degree_days = Float64(_t1_degree_days - _t0_degree_days) / Float64(N)
    print("MOJO_TIMING entomology::degree_days", _ns_degree_days, _acc_degree_days)
    var _result_degree_days = degree_days(0.5, 0.5, 0.5)
    var _summary_degree_days = _summary_float64(_result_degree_days)
    print("MOJO_RESULT entomology::degree_days", _summary_degree_days)
    var _acc_accumulated_degree_days: Float64 = 0.0
    var _t0_accumulated_degree_days = perf_counter_ns()
    for _ in range(N):
        _acc_accumulated_degree_days += accumulated_degree_days(0.5, 0.5)
    var _t1_accumulated_degree_days = perf_counter_ns()
    var _ns_accumulated_degree_days = Float64(_t1_accumulated_degree_days - _t0_accumulated_degree_days) / Float64(N)
    print("MOJO_TIMING entomology::accumulated_degree_days", _ns_accumulated_degree_days, _acc_accumulated_degree_days)
    var _result_accumulated_degree_days = accumulated_degree_days(0.5, 0.5)
    var _summary_accumulated_degree_days = _summary_float64(_result_accumulated_degree_days)
    print("MOJO_RESULT entomology::accumulated_degree_days", _summary_accumulated_degree_days)
    var _acc_population_growth_intrinsic: Float64 = 0.0
    var _t0_population_growth_intrinsic = perf_counter_ns()
    for _ in range(N):
        _acc_population_growth_intrinsic += population_growth_intrinsic(0.5, 0.5, 0.5)
    var _t1_population_growth_intrinsic = perf_counter_ns()
    var _ns_population_growth_intrinsic = Float64(_t1_population_growth_intrinsic - _t0_population_growth_intrinsic) / Float64(N)
    print("MOJO_TIMING entomology::population_growth_intrinsic", _ns_population_growth_intrinsic, _acc_population_growth_intrinsic)
    var _result_population_growth_intrinsic = population_growth_intrinsic(0.5, 0.5, 0.5)
    var _summary_population_growth_intrinsic = _summary_float64(_result_population_growth_intrinsic)
    print("MOJO_RESULT entomology::population_growth_intrinsic", _summary_population_growth_intrinsic)
    var _acc_net_reproductive_rate: Float64 = 0.0
    var _t0_net_reproductive_rate = perf_counter_ns()
    for _ in range(N):
        _acc_net_reproductive_rate += net_reproductive_rate(0.5, 0.5)
    var _t1_net_reproductive_rate = perf_counter_ns()
    var _ns_net_reproductive_rate = Float64(_t1_net_reproductive_rate - _t0_net_reproductive_rate) / Float64(N)
    print("MOJO_TIMING entomology::net_reproductive_rate", _ns_net_reproductive_rate, _acc_net_reproductive_rate)
    var _result_net_reproductive_rate = net_reproductive_rate(0.5, 0.5)
    var _summary_net_reproductive_rate = _summary_float64(_result_net_reproductive_rate)
    print("MOJO_RESULT entomology::net_reproductive_rate", _summary_net_reproductive_rate)
    var _acc_generation_time: Float64 = 0.0
    var _t0_generation_time = perf_counter_ns()
    for _ in range(N):
        _acc_generation_time += generation_time(0.5, 0.5)
    var _t1_generation_time = perf_counter_ns()
    var _ns_generation_time = Float64(_t1_generation_time - _t0_generation_time) / Float64(N)
    print("MOJO_TIMING entomology::generation_time", _ns_generation_time, _acc_generation_time)
    var _result_generation_time = generation_time(0.5, 0.5)
    var _summary_generation_time = _summary_float64(_result_generation_time)
    print("MOJO_RESULT entomology::generation_time", _summary_generation_time)
    var _acc_doubling_time_population: Float64 = 0.0
    var _t0_doubling_time_population = perf_counter_ns()
    for _ in range(N):
        _acc_doubling_time_population += doubling_time_population(0.5)
    var _t1_doubling_time_population = perf_counter_ns()
    var _ns_doubling_time_population = Float64(_t1_doubling_time_population - _t0_doubling_time_population) / Float64(N)
    print("MOJO_TIMING entomology::doubling_time_population", _ns_doubling_time_population, _acc_doubling_time_population)
    var _result_doubling_time_population = doubling_time_population(0.5)
    var _summary_doubling_time_population = _summary_float64(_result_doubling_time_population)
    print("MOJO_RESULT entomology::doubling_time_population", _summary_doubling_time_population)
    var _acc_species_diversity_simpson: Float64 = 0.0
    var _t0_species_diversity_simpson = perf_counter_ns()
    for _ in range(N):
        _acc_species_diversity_simpson += species_diversity_simpson(0.5)
    var _t1_species_diversity_simpson = perf_counter_ns()
    var _ns_species_diversity_simpson = Float64(_t1_species_diversity_simpson - _t0_species_diversity_simpson) / Float64(N)
    print("MOJO_TIMING entomology::species_diversity_simpson", _ns_species_diversity_simpson, _acc_species_diversity_simpson)
    var _result_species_diversity_simpson = species_diversity_simpson(0.5)
    var _summary_species_diversity_simpson = _summary_float64(_result_species_diversity_simpson)
    print("MOJO_RESULT entomology::species_diversity_simpson", _summary_species_diversity_simpson)
    var _acc_trap_catch_index: Float64 = 0.0
    var _t0_trap_catch_index = perf_counter_ns()
    for _ in range(N):
        _acc_trap_catch_index += trap_catch_index(0.5, 0.5, 0.5)
    var _t1_trap_catch_index = perf_counter_ns()
    var _ns_trap_catch_index = Float64(_t1_trap_catch_index - _t0_trap_catch_index) / Float64(N)
    print("MOJO_TIMING entomology::trap_catch_index", _ns_trap_catch_index, _acc_trap_catch_index)
    var _result_trap_catch_index = trap_catch_index(0.5, 0.5, 0.5)
    var _summary_trap_catch_index = _summary_float64(_result_trap_catch_index)
    print("MOJO_RESULT entomology::trap_catch_index", _summary_trap_catch_index)
    var _acc_infestation_rate: Float64 = 0.0
    var _t0_infestation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_infestation_rate += infestation_rate(0.5, 0.5)
    var _t1_infestation_rate = perf_counter_ns()
    var _ns_infestation_rate = Float64(_t1_infestation_rate - _t0_infestation_rate) / Float64(N)
    print("MOJO_TIMING entomology::infestation_rate", _ns_infestation_rate, _acc_infestation_rate)
    var _result_infestation_rate = infestation_rate(0.5, 0.5)
    var _summary_infestation_rate = _summary_float64(_result_infestation_rate)
    print("MOJO_RESULT entomology::infestation_rate", _summary_infestation_rate)
    var _acc_biocontrol_efficacy: Float64 = 0.0
    var _t0_biocontrol_efficacy = perf_counter_ns()
    for _ in range(N):
        _acc_biocontrol_efficacy += biocontrol_efficacy(0.5, 0.5)
    var _t1_biocontrol_efficacy = perf_counter_ns()
    var _ns_biocontrol_efficacy = Float64(_t1_biocontrol_efficacy - _t0_biocontrol_efficacy) / Float64(N)
    print("MOJO_TIMING entomology::biocontrol_efficacy", _ns_biocontrol_efficacy, _acc_biocontrol_efficacy)
    var _result_biocontrol_efficacy = biocontrol_efficacy(0.5, 0.5)
    var _summary_biocontrol_efficacy = _summary_float64(_result_biocontrol_efficacy)
    print("MOJO_RESULT entomology::biocontrol_efficacy", _summary_biocontrol_efficacy)
    var _acc_larval_mortality_rate: Float64 = 0.0
    var _t0_larval_mortality_rate = perf_counter_ns()
    for _ in range(N):
        _acc_larval_mortality_rate += larval_mortality_rate(0.5, 0.5)
    var _t1_larval_mortality_rate = perf_counter_ns()
    var _ns_larval_mortality_rate = Float64(_t1_larval_mortality_rate - _t0_larval_mortality_rate) / Float64(N)
    print("MOJO_TIMING entomology::larval_mortality_rate", _ns_larval_mortality_rate, _acc_larval_mortality_rate)
    var _result_larval_mortality_rate = larval_mortality_rate(0.5, 0.5)
    var _summary_larval_mortality_rate = _summary_float64(_result_larval_mortality_rate)
    print("MOJO_RESULT entomology::larval_mortality_rate", _summary_larval_mortality_rate)
    var _acc_metabolic_rate_insect: Float64 = 0.0
    var _t0_metabolic_rate_insect = perf_counter_ns()
    for _ in range(N):
        _acc_metabolic_rate_insect += metabolic_rate_insect(0.5, 0.5)
    var _t1_metabolic_rate_insect = perf_counter_ns()
    var _ns_metabolic_rate_insect = Float64(_t1_metabolic_rate_insect - _t0_metabolic_rate_insect) / Float64(N)
    print("MOJO_TIMING entomology::metabolic_rate_insect", _ns_metabolic_rate_insect, _acc_metabolic_rate_insect)
    var _result_metabolic_rate_insect = metabolic_rate_insect(0.5, 0.5)
    var _summary_metabolic_rate_insect = _summary_float64(_result_metabolic_rate_insect)
    print("MOJO_RESULT entomology::metabolic_rate_insect", _summary_metabolic_rate_insect)
