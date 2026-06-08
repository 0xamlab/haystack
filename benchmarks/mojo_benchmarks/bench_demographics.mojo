"""bench_demographics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from demographics import crude_birth_rate, crude_death_rate, natural_increase_rate, total_fertility_rate, infant_mortality_rate, life_expectancy_approx, dependency_ratio, sex_ratio, population_growth_rate, doubling_time, urbanization_rate, median_age_estimate
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

    var _acc_crude_birth_rate: Float64 = 0.0
    var _t0_crude_birth_rate = perf_counter_ns()
    for _ in range(N):
        _acc_crude_birth_rate += crude_birth_rate(0.5, 0.5)
    var _t1_crude_birth_rate = perf_counter_ns()
    var _ns_crude_birth_rate = Float64(_t1_crude_birth_rate - _t0_crude_birth_rate) / Float64(N)
    print("MOJO_TIMING demographics::crude_birth_rate", _ns_crude_birth_rate, _acc_crude_birth_rate)
    var _result_crude_birth_rate = crude_birth_rate(0.5, 0.5)
    var _summary_crude_birth_rate = _summary_float64(_result_crude_birth_rate)
    print("MOJO_RESULT demographics::crude_birth_rate", _summary_crude_birth_rate)
    var _acc_crude_death_rate: Float64 = 0.0
    var _t0_crude_death_rate = perf_counter_ns()
    for _ in range(N):
        _acc_crude_death_rate += crude_death_rate(0.5, 0.5)
    var _t1_crude_death_rate = perf_counter_ns()
    var _ns_crude_death_rate = Float64(_t1_crude_death_rate - _t0_crude_death_rate) / Float64(N)
    print("MOJO_TIMING demographics::crude_death_rate", _ns_crude_death_rate, _acc_crude_death_rate)
    var _result_crude_death_rate = crude_death_rate(0.5, 0.5)
    var _summary_crude_death_rate = _summary_float64(_result_crude_death_rate)
    print("MOJO_RESULT demographics::crude_death_rate", _summary_crude_death_rate)
    var _acc_natural_increase_rate: Float64 = 0.0
    var _t0_natural_increase_rate = perf_counter_ns()
    for _ in range(N):
        _acc_natural_increase_rate += natural_increase_rate(0.5, 0.5)
    var _t1_natural_increase_rate = perf_counter_ns()
    var _ns_natural_increase_rate = Float64(_t1_natural_increase_rate - _t0_natural_increase_rate) / Float64(N)
    print("MOJO_TIMING demographics::natural_increase_rate", _ns_natural_increase_rate, _acc_natural_increase_rate)
    var _result_natural_increase_rate = natural_increase_rate(0.5, 0.5)
    var _summary_natural_increase_rate = _summary_float64(_result_natural_increase_rate)
    print("MOJO_RESULT demographics::natural_increase_rate", _summary_natural_increase_rate)
    var _acc_total_fertility_rate: Float64 = 0.0
    var _t0_total_fertility_rate = perf_counter_ns()
    for _ in range(N):
        _acc_total_fertility_rate += total_fertility_rate(0.5, 0.5)
    var _t1_total_fertility_rate = perf_counter_ns()
    var _ns_total_fertility_rate = Float64(_t1_total_fertility_rate - _t0_total_fertility_rate) / Float64(N)
    print("MOJO_TIMING demographics::total_fertility_rate", _ns_total_fertility_rate, _acc_total_fertility_rate)
    var _result_total_fertility_rate = total_fertility_rate(0.5, 0.5)
    var _summary_total_fertility_rate = _summary_float64(_result_total_fertility_rate)
    print("MOJO_RESULT demographics::total_fertility_rate", _summary_total_fertility_rate)
    var _acc_infant_mortality_rate: Float64 = 0.0
    var _t0_infant_mortality_rate = perf_counter_ns()
    for _ in range(N):
        _acc_infant_mortality_rate += infant_mortality_rate(0.5, 0.5)
    var _t1_infant_mortality_rate = perf_counter_ns()
    var _ns_infant_mortality_rate = Float64(_t1_infant_mortality_rate - _t0_infant_mortality_rate) / Float64(N)
    print("MOJO_TIMING demographics::infant_mortality_rate", _ns_infant_mortality_rate, _acc_infant_mortality_rate)
    var _result_infant_mortality_rate = infant_mortality_rate(0.5, 0.5)
    var _summary_infant_mortality_rate = _summary_float64(_result_infant_mortality_rate)
    print("MOJO_RESULT demographics::infant_mortality_rate", _summary_infant_mortality_rate)
    var _acc_life_expectancy_approx: Float64 = 0.0
    var _t0_life_expectancy_approx = perf_counter_ns()
    for _ in range(N):
        _acc_life_expectancy_approx += life_expectancy_approx(0.5, 0.5)
    var _t1_life_expectancy_approx = perf_counter_ns()
    var _ns_life_expectancy_approx = Float64(_t1_life_expectancy_approx - _t0_life_expectancy_approx) / Float64(N)
    print("MOJO_TIMING demographics::life_expectancy_approx", _ns_life_expectancy_approx, _acc_life_expectancy_approx)
    var _result_life_expectancy_approx = life_expectancy_approx(0.5, 0.5)
    var _summary_life_expectancy_approx = _summary_float64(_result_life_expectancy_approx)
    print("MOJO_RESULT demographics::life_expectancy_approx", _summary_life_expectancy_approx)
    var _acc_dependency_ratio: Float64 = 0.0
    var _t0_dependency_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_dependency_ratio += dependency_ratio(0.5, 0.5, 0.5)
    var _t1_dependency_ratio = perf_counter_ns()
    var _ns_dependency_ratio = Float64(_t1_dependency_ratio - _t0_dependency_ratio) / Float64(N)
    print("MOJO_TIMING demographics::dependency_ratio", _ns_dependency_ratio, _acc_dependency_ratio)
    var _result_dependency_ratio = dependency_ratio(0.5, 0.5, 0.5)
    var _summary_dependency_ratio = _summary_float64(_result_dependency_ratio)
    print("MOJO_RESULT demographics::dependency_ratio", _summary_dependency_ratio)
    var _acc_sex_ratio: Float64 = 0.0
    var _t0_sex_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_sex_ratio += sex_ratio(0.5, 0.5)
    var _t1_sex_ratio = perf_counter_ns()
    var _ns_sex_ratio = Float64(_t1_sex_ratio - _t0_sex_ratio) / Float64(N)
    print("MOJO_TIMING demographics::sex_ratio", _ns_sex_ratio, _acc_sex_ratio)
    var _result_sex_ratio = sex_ratio(0.5, 0.5)
    var _summary_sex_ratio = _summary_float64(_result_sex_ratio)
    print("MOJO_RESULT demographics::sex_ratio", _summary_sex_ratio)
    var _acc_population_growth_rate: Float64 = 0.0
    var _t0_population_growth_rate = perf_counter_ns()
    for _ in range(N):
        _acc_population_growth_rate += population_growth_rate(0.5, 0.5, 0.5, 0.5)
    var _t1_population_growth_rate = perf_counter_ns()
    var _ns_population_growth_rate = Float64(_t1_population_growth_rate - _t0_population_growth_rate) / Float64(N)
    print("MOJO_TIMING demographics::population_growth_rate", _ns_population_growth_rate, _acc_population_growth_rate)
    var _result_population_growth_rate = population_growth_rate(0.5, 0.5, 0.5, 0.5)
    var _summary_population_growth_rate = _summary_float64(_result_population_growth_rate)
    print("MOJO_RESULT demographics::population_growth_rate", _summary_population_growth_rate)
    var _acc_doubling_time: Float64 = 0.0
    var _t0_doubling_time = perf_counter_ns()
    for _ in range(N):
        _acc_doubling_time += doubling_time(0.5)
    var _t1_doubling_time = perf_counter_ns()
    var _ns_doubling_time = Float64(_t1_doubling_time - _t0_doubling_time) / Float64(N)
    print("MOJO_TIMING demographics::doubling_time", _ns_doubling_time, _acc_doubling_time)
    var _result_doubling_time = doubling_time(0.5)
    var _summary_doubling_time = _summary_float64(_result_doubling_time)
    print("MOJO_RESULT demographics::doubling_time", _summary_doubling_time)
    var _acc_urbanization_rate: Float64 = 0.0
    var _t0_urbanization_rate = perf_counter_ns()
    for _ in range(N):
        _acc_urbanization_rate += urbanization_rate(0.5, 0.5)
    var _t1_urbanization_rate = perf_counter_ns()
    var _ns_urbanization_rate = Float64(_t1_urbanization_rate - _t0_urbanization_rate) / Float64(N)
    print("MOJO_TIMING demographics::urbanization_rate", _ns_urbanization_rate, _acc_urbanization_rate)
    var _result_urbanization_rate = urbanization_rate(0.5, 0.5)
    var _summary_urbanization_rate = _summary_float64(_result_urbanization_rate)
    print("MOJO_RESULT demographics::urbanization_rate", _summary_urbanization_rate)
    var _acc_median_age_estimate: Float64 = 0.0
    var _t0_median_age_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_median_age_estimate += median_age_estimate(0.5, 0.5)
    var _t1_median_age_estimate = perf_counter_ns()
    var _ns_median_age_estimate = Float64(_t1_median_age_estimate - _t0_median_age_estimate) / Float64(N)
    print("MOJO_TIMING demographics::median_age_estimate", _ns_median_age_estimate, _acc_median_age_estimate)
    var _result_median_age_estimate = median_age_estimate(0.5, 0.5)
    var _summary_median_age_estimate = _summary_float64(_result_median_age_estimate)
    print("MOJO_RESULT demographics::median_age_estimate", _summary_median_age_estimate)
