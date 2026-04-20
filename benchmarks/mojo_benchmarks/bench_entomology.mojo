"""bench_entomology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from entomology import degree_days, accumulated_degree_days, population_growth_intrinsic, net_reproductive_rate, generation_time, doubling_time_population, species_diversity_simpson, trap_catch_index, infestation_rate, biocontrol_efficacy, larval_mortality_rate, metabolic_rate_insect
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

    var _acc_degree_days: Float64 = 0.0
    var _t0_degree_days = perf_counter_ns()
    for _ in range(N):
        _acc_degree_days += degree_days(0.5, 0.5, 0.5)
    var _t1_degree_days = perf_counter_ns()
    var _ns_degree_days = Float64(_t1_degree_days - _t0_degree_days) / Float64(N)
    print("MOJO_TIMING entomology::degree_days", _ns_degree_days, _acc_degree_days)
    var _acc_accumulated_degree_days: Float64 = 0.0
    var _t0_accumulated_degree_days = perf_counter_ns()
    for _ in range(N):
        _acc_accumulated_degree_days += accumulated_degree_days(0.5, 0.5)
    var _t1_accumulated_degree_days = perf_counter_ns()
    var _ns_accumulated_degree_days = Float64(_t1_accumulated_degree_days - _t0_accumulated_degree_days) / Float64(N)
    print("MOJO_TIMING entomology::accumulated_degree_days", _ns_accumulated_degree_days, _acc_accumulated_degree_days)
    var _acc_population_growth_intrinsic: Float64 = 0.0
    var _t0_population_growth_intrinsic = perf_counter_ns()
    for _ in range(N):
        _acc_population_growth_intrinsic += population_growth_intrinsic(0.5, 0.5, 0.5)
    var _t1_population_growth_intrinsic = perf_counter_ns()
    var _ns_population_growth_intrinsic = Float64(_t1_population_growth_intrinsic - _t0_population_growth_intrinsic) / Float64(N)
    print("MOJO_TIMING entomology::population_growth_intrinsic", _ns_population_growth_intrinsic, _acc_population_growth_intrinsic)
    var _acc_net_reproductive_rate: Float64 = 0.0
    var _t0_net_reproductive_rate = perf_counter_ns()
    for _ in range(N):
        _acc_net_reproductive_rate += net_reproductive_rate(0.5, 0.5)
    var _t1_net_reproductive_rate = perf_counter_ns()
    var _ns_net_reproductive_rate = Float64(_t1_net_reproductive_rate - _t0_net_reproductive_rate) / Float64(N)
    print("MOJO_TIMING entomology::net_reproductive_rate", _ns_net_reproductive_rate, _acc_net_reproductive_rate)
    var _acc_generation_time: Float64 = 0.0
    var _t0_generation_time = perf_counter_ns()
    for _ in range(N):
        _acc_generation_time += generation_time(0.5, 0.5)
    var _t1_generation_time = perf_counter_ns()
    var _ns_generation_time = Float64(_t1_generation_time - _t0_generation_time) / Float64(N)
    print("MOJO_TIMING entomology::generation_time", _ns_generation_time, _acc_generation_time)
    var _acc_doubling_time_population: Float64 = 0.0
    var _t0_doubling_time_population = perf_counter_ns()
    for _ in range(N):
        _acc_doubling_time_population += doubling_time_population(0.5)
    var _t1_doubling_time_population = perf_counter_ns()
    var _ns_doubling_time_population = Float64(_t1_doubling_time_population - _t0_doubling_time_population) / Float64(N)
    print("MOJO_TIMING entomology::doubling_time_population", _ns_doubling_time_population, _acc_doubling_time_population)
    var _acc_species_diversity_simpson: Float64 = 0.0
    var _t0_species_diversity_simpson = perf_counter_ns()
    for _ in range(N):
        _acc_species_diversity_simpson += species_diversity_simpson(0.5)
    var _t1_species_diversity_simpson = perf_counter_ns()
    var _ns_species_diversity_simpson = Float64(_t1_species_diversity_simpson - _t0_species_diversity_simpson) / Float64(N)
    print("MOJO_TIMING entomology::species_diversity_simpson", _ns_species_diversity_simpson, _acc_species_diversity_simpson)
    var _acc_trap_catch_index: Float64 = 0.0
    var _t0_trap_catch_index = perf_counter_ns()
    for _ in range(N):
        _acc_trap_catch_index += trap_catch_index(0.5, 0.5, 0.5)
    var _t1_trap_catch_index = perf_counter_ns()
    var _ns_trap_catch_index = Float64(_t1_trap_catch_index - _t0_trap_catch_index) / Float64(N)
    print("MOJO_TIMING entomology::trap_catch_index", _ns_trap_catch_index, _acc_trap_catch_index)
    var _acc_infestation_rate: Float64 = 0.0
    var _t0_infestation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_infestation_rate += infestation_rate(0.5, 0.5)
    var _t1_infestation_rate = perf_counter_ns()
    var _ns_infestation_rate = Float64(_t1_infestation_rate - _t0_infestation_rate) / Float64(N)
    print("MOJO_TIMING entomology::infestation_rate", _ns_infestation_rate, _acc_infestation_rate)
    var _acc_biocontrol_efficacy: Float64 = 0.0
    var _t0_biocontrol_efficacy = perf_counter_ns()
    for _ in range(N):
        _acc_biocontrol_efficacy += biocontrol_efficacy(0.5, 0.5)
    var _t1_biocontrol_efficacy = perf_counter_ns()
    var _ns_biocontrol_efficacy = Float64(_t1_biocontrol_efficacy - _t0_biocontrol_efficacy) / Float64(N)
    print("MOJO_TIMING entomology::biocontrol_efficacy", _ns_biocontrol_efficacy, _acc_biocontrol_efficacy)
    var _acc_larval_mortality_rate: Float64 = 0.0
    var _t0_larval_mortality_rate = perf_counter_ns()
    for _ in range(N):
        _acc_larval_mortality_rate += larval_mortality_rate(0.5, 0.5)
    var _t1_larval_mortality_rate = perf_counter_ns()
    var _ns_larval_mortality_rate = Float64(_t1_larval_mortality_rate - _t0_larval_mortality_rate) / Float64(N)
    print("MOJO_TIMING entomology::larval_mortality_rate", _ns_larval_mortality_rate, _acc_larval_mortality_rate)
    var _acc_metabolic_rate_insect: Float64 = 0.0
    var _t0_metabolic_rate_insect = perf_counter_ns()
    for _ in range(N):
        _acc_metabolic_rate_insect += metabolic_rate_insect(0.5, 0.5)
    var _t1_metabolic_rate_insect = perf_counter_ns()
    var _ns_metabolic_rate_insect = Float64(_t1_metabolic_rate_insect - _t0_metabolic_rate_insect) / Float64(N)
    print("MOJO_TIMING entomology::metabolic_rate_insect", _ns_metabolic_rate_insect, _acc_metabolic_rate_insect)
