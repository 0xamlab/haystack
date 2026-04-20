"""bench_ecology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from ecology import logistic_growth, exponential_growth, carrying_capacity_estimate, lotka_volterra_prey, lotka_volterra_predator, species_richness_margalef, shannon_diversity, simpson_index, simpson_diversity, jaccard_similarity, sorensen_similarity, species_area_relationship
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

    var _acc_logistic_growth: Float64 = 0.0
    var _t0_logistic_growth = perf_counter_ns()
    for _ in range(N):
        _acc_logistic_growth += logistic_growth(0.5, 0.5, 0.5)
    var _t1_logistic_growth = perf_counter_ns()
    var _ns_logistic_growth = Float64(_t1_logistic_growth - _t0_logistic_growth) / Float64(N)
    print("MOJO_TIMING ecology::logistic_growth", _ns_logistic_growth, _acc_logistic_growth)
    var _acc_exponential_growth: Float64 = 0.0
    var _t0_exponential_growth = perf_counter_ns()
    for _ in range(N):
        _acc_exponential_growth += exponential_growth(0.5, 0.5, 0.5)
    var _t1_exponential_growth = perf_counter_ns()
    var _ns_exponential_growth = Float64(_t1_exponential_growth - _t0_exponential_growth) / Float64(N)
    print("MOJO_TIMING ecology::exponential_growth", _ns_exponential_growth, _acc_exponential_growth)
    var _acc_carrying_capacity_estimate: Float64 = 0.0
    var _t0_carrying_capacity_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_carrying_capacity_estimate += carrying_capacity_estimate(0.5, 0.5, 0.5, 0.5)
    var _t1_carrying_capacity_estimate = perf_counter_ns()
    var _ns_carrying_capacity_estimate = Float64(_t1_carrying_capacity_estimate - _t0_carrying_capacity_estimate) / Float64(N)
    print("MOJO_TIMING ecology::carrying_capacity_estimate", _ns_carrying_capacity_estimate, _acc_carrying_capacity_estimate)
    var _acc_lotka_volterra_prey: Float64 = 0.0
    var _t0_lotka_volterra_prey = perf_counter_ns()
    for _ in range(N):
        _acc_lotka_volterra_prey += lotka_volterra_prey(0.5, 0.5, 0.5, 0.5)
    var _t1_lotka_volterra_prey = perf_counter_ns()
    var _ns_lotka_volterra_prey = Float64(_t1_lotka_volterra_prey - _t0_lotka_volterra_prey) / Float64(N)
    print("MOJO_TIMING ecology::lotka_volterra_prey", _ns_lotka_volterra_prey, _acc_lotka_volterra_prey)
    var _acc_lotka_volterra_predator: Float64 = 0.0
    var _t0_lotka_volterra_predator = perf_counter_ns()
    for _ in range(N):
        _acc_lotka_volterra_predator += lotka_volterra_predator(0.5, 0.5, 0.5, 0.5)
    var _t1_lotka_volterra_predator = perf_counter_ns()
    var _ns_lotka_volterra_predator = Float64(_t1_lotka_volterra_predator - _t0_lotka_volterra_predator) / Float64(N)
    print("MOJO_TIMING ecology::lotka_volterra_predator", _ns_lotka_volterra_predator, _acc_lotka_volterra_predator)
    var _acc_species_richness_margalef: Float64 = 0.0
    var _t0_species_richness_margalef = perf_counter_ns()
    for _ in range(N):
        _acc_species_richness_margalef += species_richness_margalef(0.5, 0.5)
    var _t1_species_richness_margalef = perf_counter_ns()
    var _ns_species_richness_margalef = Float64(_t1_species_richness_margalef - _t0_species_richness_margalef) / Float64(N)
    print("MOJO_TIMING ecology::species_richness_margalef", _ns_species_richness_margalef, _acc_species_richness_margalef)
    var _acc_shannon_diversity: Float64 = 0.0
    var _t0_shannon_diversity = perf_counter_ns()
    for _ in range(N):
        _acc_shannon_diversity += shannon_diversity(0.5)
    var _t1_shannon_diversity = perf_counter_ns()
    var _ns_shannon_diversity = Float64(_t1_shannon_diversity - _t0_shannon_diversity) / Float64(N)
    print("MOJO_TIMING ecology::shannon_diversity", _ns_shannon_diversity, _acc_shannon_diversity)
    var _acc_simpson_index: Float64 = 0.0
    var _t0_simpson_index = perf_counter_ns()
    for _ in range(N):
        _acc_simpson_index += simpson_index(0.5)
    var _t1_simpson_index = perf_counter_ns()
    var _ns_simpson_index = Float64(_t1_simpson_index - _t0_simpson_index) / Float64(N)
    print("MOJO_TIMING ecology::simpson_index", _ns_simpson_index, _acc_simpson_index)
    var _acc_simpson_diversity: Float64 = 0.0
    var _t0_simpson_diversity = perf_counter_ns()
    for _ in range(N):
        _acc_simpson_diversity += simpson_diversity(0.5)
    var _t1_simpson_diversity = perf_counter_ns()
    var _ns_simpson_diversity = Float64(_t1_simpson_diversity - _t0_simpson_diversity) / Float64(N)
    print("MOJO_TIMING ecology::simpson_diversity", _ns_simpson_diversity, _acc_simpson_diversity)
    var _acc_jaccard_similarity: Float64 = 0.0
    var _t0_jaccard_similarity = perf_counter_ns()
    for _ in range(N):
        _acc_jaccard_similarity += jaccard_similarity(0.5, 0.5, 0.5)
    var _t1_jaccard_similarity = perf_counter_ns()
    var _ns_jaccard_similarity = Float64(_t1_jaccard_similarity - _t0_jaccard_similarity) / Float64(N)
    print("MOJO_TIMING ecology::jaccard_similarity", _ns_jaccard_similarity, _acc_jaccard_similarity)
    var _acc_sorensen_similarity: Float64 = 0.0
    var _t0_sorensen_similarity = perf_counter_ns()
    for _ in range(N):
        _acc_sorensen_similarity += sorensen_similarity(0.5, 0.5, 0.5)
    var _t1_sorensen_similarity = perf_counter_ns()
    var _ns_sorensen_similarity = Float64(_t1_sorensen_similarity - _t0_sorensen_similarity) / Float64(N)
    print("MOJO_TIMING ecology::sorensen_similarity", _ns_sorensen_similarity, _acc_sorensen_similarity)
    var _acc_species_area_relationship: Float64 = 0.0
    var _t0_species_area_relationship = perf_counter_ns()
    for _ in range(N):
        _acc_species_area_relationship += species_area_relationship(0.5, 0.5, 0.5)
    var _t1_species_area_relationship = perf_counter_ns()
    var _ns_species_area_relationship = Float64(_t1_species_area_relationship - _t0_species_area_relationship) / Float64(N)
    print("MOJO_TIMING ecology::species_area_relationship", _ns_species_area_relationship, _acc_species_area_relationship)
