"""bench_mycology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from mycology import spore_dispersal_distance, mycelial_growth_rate, fungal_biomass, sporulation_index, infection_efficiency, latent_period, epidemic_progress_rate, spore_germination_prob, colony_diameter, competitive_exclusion_index
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

    var _acc_spore_dispersal_distance: Float64 = 0.0
    var _t0_spore_dispersal_distance = perf_counter_ns()
    for _ in range(N):
        _acc_spore_dispersal_distance += spore_dispersal_distance(0.5, 0.5, 0.5)
    var _t1_spore_dispersal_distance = perf_counter_ns()
    var _ns_spore_dispersal_distance = Float64(_t1_spore_dispersal_distance - _t0_spore_dispersal_distance) / Float64(N)
    print("MOJO_TIMING mycology::spore_dispersal_distance", _ns_spore_dispersal_distance, _acc_spore_dispersal_distance)
    var _acc_mycelial_growth_rate: Float64 = 0.0
    var _t0_mycelial_growth_rate = perf_counter_ns()
    for _ in range(N):
        _acc_mycelial_growth_rate += mycelial_growth_rate(0.5, 0.5, 0.5)
    var _t1_mycelial_growth_rate = perf_counter_ns()
    var _ns_mycelial_growth_rate = Float64(_t1_mycelial_growth_rate - _t0_mycelial_growth_rate) / Float64(N)
    print("MOJO_TIMING mycology::mycelial_growth_rate", _ns_mycelial_growth_rate, _acc_mycelial_growth_rate)
    var _acc_fungal_biomass: Float64 = 0.0
    var _t0_fungal_biomass = perf_counter_ns()
    for _ in range(N):
        _acc_fungal_biomass += fungal_biomass(0.5, 0.5)
    var _t1_fungal_biomass = perf_counter_ns()
    var _ns_fungal_biomass = Float64(_t1_fungal_biomass - _t0_fungal_biomass) / Float64(N)
    print("MOJO_TIMING mycology::fungal_biomass", _ns_fungal_biomass, _acc_fungal_biomass)
    var _acc_sporulation_index: Float64 = 0.0
    var _t0_sporulation_index = perf_counter_ns()
    for _ in range(N):
        _acc_sporulation_index += sporulation_index(0.5, 0.5)
    var _t1_sporulation_index = perf_counter_ns()
    var _ns_sporulation_index = Float64(_t1_sporulation_index - _t0_sporulation_index) / Float64(N)
    print("MOJO_TIMING mycology::sporulation_index", _ns_sporulation_index, _acc_sporulation_index)
    var _acc_infection_efficiency: Float64 = 0.0
    var _t0_infection_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_infection_efficiency += infection_efficiency(0.5, 0.5)
    var _t1_infection_efficiency = perf_counter_ns()
    var _ns_infection_efficiency = Float64(_t1_infection_efficiency - _t0_infection_efficiency) / Float64(N)
    print("MOJO_TIMING mycology::infection_efficiency", _ns_infection_efficiency, _acc_infection_efficiency)
    var _acc_latent_period: Float64 = 0.0
    var _t0_latent_period = perf_counter_ns()
    for _ in range(N):
        _acc_latent_period += latent_period(0.5, 0.5, 0.5)
    var _t1_latent_period = perf_counter_ns()
    var _ns_latent_period = Float64(_t1_latent_period - _t0_latent_period) / Float64(N)
    print("MOJO_TIMING mycology::latent_period", _ns_latent_period, _acc_latent_period)
    var _acc_epidemic_progress_rate: Float64 = 0.0
    var _t0_epidemic_progress_rate = perf_counter_ns()
    for _ in range(N):
        _acc_epidemic_progress_rate += epidemic_progress_rate(0.5, 0.5, 0.5, 0.5)
    var _t1_epidemic_progress_rate = perf_counter_ns()
    var _ns_epidemic_progress_rate = Float64(_t1_epidemic_progress_rate - _t0_epidemic_progress_rate) / Float64(N)
    print("MOJO_TIMING mycology::epidemic_progress_rate", _ns_epidemic_progress_rate, _acc_epidemic_progress_rate)
    var _acc_spore_germination_prob: Float64 = 0.0
    var _t0_spore_germination_prob = perf_counter_ns()
    for _ in range(N):
        _acc_spore_germination_prob += spore_germination_prob(0.5, 0.5, 0.5)
    var _t1_spore_germination_prob = perf_counter_ns()
    var _ns_spore_germination_prob = Float64(_t1_spore_germination_prob - _t0_spore_germination_prob) / Float64(N)
    print("MOJO_TIMING mycology::spore_germination_prob", _ns_spore_germination_prob, _acc_spore_germination_prob)
    var _acc_colony_diameter: Float64 = 0.0
    var _t0_colony_diameter = perf_counter_ns()
    for _ in range(N):
        _acc_colony_diameter += colony_diameter(0.5, 0.5)
    var _t1_colony_diameter = perf_counter_ns()
    var _ns_colony_diameter = Float64(_t1_colony_diameter - _t0_colony_diameter) / Float64(N)
    print("MOJO_TIMING mycology::colony_diameter", _ns_colony_diameter, _acc_colony_diameter)
    var _acc_competitive_exclusion_index: Float64 = 0.0
    var _t0_competitive_exclusion_index = perf_counter_ns()
    for _ in range(N):
        _acc_competitive_exclusion_index += competitive_exclusion_index(0.5, 0.5)
    var _t1_competitive_exclusion_index = perf_counter_ns()
    var _ns_competitive_exclusion_index = Float64(_t1_competitive_exclusion_index - _t0_competitive_exclusion_index) / Float64(N)
    print("MOJO_TIMING mycology::competitive_exclusion_index", _ns_competitive_exclusion_index, _acc_competitive_exclusion_index)
