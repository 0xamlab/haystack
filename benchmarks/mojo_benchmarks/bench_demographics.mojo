"""bench_demographics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from demographics import crude_birth_rate, crude_death_rate, natural_increase_rate, total_fertility_rate, infant_mortality_rate, life_expectancy_approx, dependency_ratio, sex_ratio, population_growth_rate, doubling_time, urbanization_rate, median_age_estimate
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

    var _acc_crude_birth_rate: Float64 = 0.0
    var _t0_crude_birth_rate = perf_counter_ns()
    for _ in range(N):
        _acc_crude_birth_rate += crude_birth_rate(0.5, 0.5)
    var _t1_crude_birth_rate = perf_counter_ns()
    var _ns_crude_birth_rate = Float64(_t1_crude_birth_rate - _t0_crude_birth_rate) / Float64(N)
    print("MOJO_TIMING demographics::crude_birth_rate", _ns_crude_birth_rate, _acc_crude_birth_rate)
    var _acc_crude_death_rate: Float64 = 0.0
    var _t0_crude_death_rate = perf_counter_ns()
    for _ in range(N):
        _acc_crude_death_rate += crude_death_rate(0.5, 0.5)
    var _t1_crude_death_rate = perf_counter_ns()
    var _ns_crude_death_rate = Float64(_t1_crude_death_rate - _t0_crude_death_rate) / Float64(N)
    print("MOJO_TIMING demographics::crude_death_rate", _ns_crude_death_rate, _acc_crude_death_rate)
    var _acc_natural_increase_rate: Float64 = 0.0
    var _t0_natural_increase_rate = perf_counter_ns()
    for _ in range(N):
        _acc_natural_increase_rate += natural_increase_rate(0.5, 0.5)
    var _t1_natural_increase_rate = perf_counter_ns()
    var _ns_natural_increase_rate = Float64(_t1_natural_increase_rate - _t0_natural_increase_rate) / Float64(N)
    print("MOJO_TIMING demographics::natural_increase_rate", _ns_natural_increase_rate, _acc_natural_increase_rate)
    var _acc_total_fertility_rate: Float64 = 0.0
    var _t0_total_fertility_rate = perf_counter_ns()
    for _ in range(N):
        _acc_total_fertility_rate += total_fertility_rate(0.5, 0.5)
    var _t1_total_fertility_rate = perf_counter_ns()
    var _ns_total_fertility_rate = Float64(_t1_total_fertility_rate - _t0_total_fertility_rate) / Float64(N)
    print("MOJO_TIMING demographics::total_fertility_rate", _ns_total_fertility_rate, _acc_total_fertility_rate)
    var _acc_infant_mortality_rate: Float64 = 0.0
    var _t0_infant_mortality_rate = perf_counter_ns()
    for _ in range(N):
        _acc_infant_mortality_rate += infant_mortality_rate(0.5, 0.5)
    var _t1_infant_mortality_rate = perf_counter_ns()
    var _ns_infant_mortality_rate = Float64(_t1_infant_mortality_rate - _t0_infant_mortality_rate) / Float64(N)
    print("MOJO_TIMING demographics::infant_mortality_rate", _ns_infant_mortality_rate, _acc_infant_mortality_rate)
    var _acc_life_expectancy_approx: Float64 = 0.0
    var _t0_life_expectancy_approx = perf_counter_ns()
    for _ in range(N):
        _acc_life_expectancy_approx += life_expectancy_approx(0.5, 0.5)
    var _t1_life_expectancy_approx = perf_counter_ns()
    var _ns_life_expectancy_approx = Float64(_t1_life_expectancy_approx - _t0_life_expectancy_approx) / Float64(N)
    print("MOJO_TIMING demographics::life_expectancy_approx", _ns_life_expectancy_approx, _acc_life_expectancy_approx)
    var _acc_dependency_ratio: Float64 = 0.0
    var _t0_dependency_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_dependency_ratio += dependency_ratio(0.5, 0.5, 0.5)
    var _t1_dependency_ratio = perf_counter_ns()
    var _ns_dependency_ratio = Float64(_t1_dependency_ratio - _t0_dependency_ratio) / Float64(N)
    print("MOJO_TIMING demographics::dependency_ratio", _ns_dependency_ratio, _acc_dependency_ratio)
    var _acc_sex_ratio: Float64 = 0.0
    var _t0_sex_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_sex_ratio += sex_ratio(0.5, 0.5)
    var _t1_sex_ratio = perf_counter_ns()
    var _ns_sex_ratio = Float64(_t1_sex_ratio - _t0_sex_ratio) / Float64(N)
    print("MOJO_TIMING demographics::sex_ratio", _ns_sex_ratio, _acc_sex_ratio)
    var _acc_population_growth_rate: Float64 = 0.0
    var _t0_population_growth_rate = perf_counter_ns()
    for _ in range(N):
        _acc_population_growth_rate += population_growth_rate(0.5, 0.5, 0.5, 0.5)
    var _t1_population_growth_rate = perf_counter_ns()
    var _ns_population_growth_rate = Float64(_t1_population_growth_rate - _t0_population_growth_rate) / Float64(N)
    print("MOJO_TIMING demographics::population_growth_rate", _ns_population_growth_rate, _acc_population_growth_rate)
    var _acc_doubling_time: Float64 = 0.0
    var _t0_doubling_time = perf_counter_ns()
    for _ in range(N):
        _acc_doubling_time += doubling_time(0.5)
    var _t1_doubling_time = perf_counter_ns()
    var _ns_doubling_time = Float64(_t1_doubling_time - _t0_doubling_time) / Float64(N)
    print("MOJO_TIMING demographics::doubling_time", _ns_doubling_time, _acc_doubling_time)
    var _acc_urbanization_rate: Float64 = 0.0
    var _t0_urbanization_rate = perf_counter_ns()
    for _ in range(N):
        _acc_urbanization_rate += urbanization_rate(0.5, 0.5)
    var _t1_urbanization_rate = perf_counter_ns()
    var _ns_urbanization_rate = Float64(_t1_urbanization_rate - _t0_urbanization_rate) / Float64(N)
    print("MOJO_TIMING demographics::urbanization_rate", _ns_urbanization_rate, _acc_urbanization_rate)
    var _acc_median_age_estimate: Float64 = 0.0
    var _t0_median_age_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_median_age_estimate += median_age_estimate(0.5, 0.5)
    var _t1_median_age_estimate = perf_counter_ns()
    var _ns_median_age_estimate = Float64(_t1_median_age_estimate - _t0_median_age_estimate) / Float64(N)
    print("MOJO_TIMING demographics::median_age_estimate", _ns_median_age_estimate, _acc_median_age_estimate)
