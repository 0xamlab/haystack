"""bench_ab_testing.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from ab_testing import sample_size_proportion, z_test_proportions, confidence_interval_proportion, relative_uplift, is_significant, power_analysis, mde, sequential_test, epsilon_greedy_select, ucb1_select
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

    var _acc_sample_size_proportion: Float64 = 0.0
    var _t0_sample_size_proportion = perf_counter_ns()
    for _ in range(N):
        _acc_sample_size_proportion += Float64(sample_size_proportion(0.5, 0.5, 0.5, 0.5))
    var _t1_sample_size_proportion = perf_counter_ns()
    var _ns_sample_size_proportion = Float64(_t1_sample_size_proportion - _t0_sample_size_proportion) / Float64(N)
    print("MOJO_TIMING ab_testing::sample_size_proportion", _ns_sample_size_proportion, _acc_sample_size_proportion)
    var _result_sample_size_proportion = sample_size_proportion(0.5, 0.5, 0.5, 0.5)
    var _summary_sample_size_proportion = _summary_int(_result_sample_size_proportion)
    print("MOJO_RESULT ab_testing::sample_size_proportion", _summary_sample_size_proportion)
    var _acc_z_test_proportions: Float64 = 0.0
    var _t0_z_test_proportions = perf_counter_ns()
    for _ in range(N):
        var _r_z_test_proportions = z_test_proportions(5, 5, 5, 5)
        _acc_z_test_proportions += Float64(len(_r_z_test_proportions))
    var _t1_z_test_proportions = perf_counter_ns()
    var _ns_z_test_proportions = Float64(_t1_z_test_proportions - _t0_z_test_proportions) / Float64(N)
    print("MOJO_TIMING ab_testing::z_test_proportions", _ns_z_test_proportions, _acc_z_test_proportions)
    var _result_z_test_proportions = z_test_proportions(5, 5, 5, 5)
    var _summary_z_test_proportions = _summary_list_float64(_result_z_test_proportions)
    print("MOJO_RESULT ab_testing::z_test_proportions", _summary_z_test_proportions)
    var _acc_confidence_interval_proportion: Float64 = 0.0
    var _t0_confidence_interval_proportion = perf_counter_ns()
    for _ in range(N):
        var _r_confidence_interval_proportion = confidence_interval_proportion(5, 5, 0.5)
        _acc_confidence_interval_proportion += Float64(len(_r_confidence_interval_proportion))
    var _t1_confidence_interval_proportion = perf_counter_ns()
    var _ns_confidence_interval_proportion = Float64(_t1_confidence_interval_proportion - _t0_confidence_interval_proportion) / Float64(N)
    print("MOJO_TIMING ab_testing::confidence_interval_proportion", _ns_confidence_interval_proportion, _acc_confidence_interval_proportion)
    var _result_confidence_interval_proportion = confidence_interval_proportion(5, 5, 0.5)
    var _summary_confidence_interval_proportion = _summary_list_float64(_result_confidence_interval_proportion)
    print("MOJO_RESULT ab_testing::confidence_interval_proportion", _summary_confidence_interval_proportion)
    var _acc_relative_uplift: Float64 = 0.0
    var _t0_relative_uplift = perf_counter_ns()
    for _ in range(N):
        _acc_relative_uplift += relative_uplift(0.5, 0.5)
    var _t1_relative_uplift = perf_counter_ns()
    var _ns_relative_uplift = Float64(_t1_relative_uplift - _t0_relative_uplift) / Float64(N)
    print("MOJO_TIMING ab_testing::relative_uplift", _ns_relative_uplift, _acc_relative_uplift)
    var _result_relative_uplift = relative_uplift(0.5, 0.5)
    var _summary_relative_uplift = _summary_float64(_result_relative_uplift)
    print("MOJO_RESULT ab_testing::relative_uplift", _summary_relative_uplift)
    var _acc_is_significant: Float64 = 0.0
    var _t0_is_significant = perf_counter_ns()
    for _ in range(N):
        _acc_is_significant += Float64(is_significant(0.5, 0.5))
    var _t1_is_significant = perf_counter_ns()
    var _ns_is_significant = Float64(_t1_is_significant - _t0_is_significant) / Float64(N)
    print("MOJO_TIMING ab_testing::is_significant", _ns_is_significant, _acc_is_significant)
    var _result_is_significant = is_significant(0.5, 0.5)
    var _summary_is_significant = _summary_bool(_result_is_significant)
    print("MOJO_RESULT ab_testing::is_significant", _summary_is_significant)
    var _acc_power_analysis: Float64 = 0.0
    var _t0_power_analysis = perf_counter_ns()
    for _ in range(N):
        _acc_power_analysis += power_analysis(0.5, 5, 0.5)
    var _t1_power_analysis = perf_counter_ns()
    var _ns_power_analysis = Float64(_t1_power_analysis - _t0_power_analysis) / Float64(N)
    print("MOJO_TIMING ab_testing::power_analysis", _ns_power_analysis, _acc_power_analysis)
    var _result_power_analysis = power_analysis(0.5, 5, 0.5)
    var _summary_power_analysis = _summary_float64(_result_power_analysis)
    print("MOJO_RESULT ab_testing::power_analysis", _summary_power_analysis)
    var _acc_mde: Float64 = 0.0
    var _t0_mde = perf_counter_ns()
    for _ in range(N):
        _acc_mde += mde(5, 0.5, 0.5, 0.5)
    var _t1_mde = perf_counter_ns()
    var _ns_mde = Float64(_t1_mde - _t0_mde) / Float64(N)
    print("MOJO_TIMING ab_testing::mde", _ns_mde, _acc_mde)
    var _result_mde = mde(5, 0.5, 0.5, 0.5)
    var _summary_mde = _summary_float64(_result_mde)
    print("MOJO_RESULT ab_testing::mde", _summary_mde)
    var _acc_sequential_test: Float64 = 0.0
    var _t0_sequential_test = perf_counter_ns()
    for _ in range(N):
        _acc_sequential_test += Float64(sequential_test(5, 5, 5, 5, 0.5))
    var _t1_sequential_test = perf_counter_ns()
    var _ns_sequential_test = Float64(_t1_sequential_test - _t0_sequential_test) / Float64(N)
    print("MOJO_TIMING ab_testing::sequential_test", _ns_sequential_test, _acc_sequential_test)
    var _result_sequential_test = sequential_test(5, 5, 5, 5, 0.5)
    var _summary_sequential_test = _summary_int(_result_sequential_test)
    print("MOJO_RESULT ab_testing::sequential_test", _summary_sequential_test)
    var _acc_epsilon_greedy_select: Float64 = 0.0
    var _t0_epsilon_greedy_select = perf_counter_ns()
    for _ in range(N):
        _acc_epsilon_greedy_select += Float64(epsilon_greedy_select(_lf5, _li5, 0.5))
    var _t1_epsilon_greedy_select = perf_counter_ns()
    var _ns_epsilon_greedy_select = Float64(_t1_epsilon_greedy_select - _t0_epsilon_greedy_select) / Float64(N)
    print("MOJO_TIMING ab_testing::epsilon_greedy_select", _ns_epsilon_greedy_select, _acc_epsilon_greedy_select)
    var _result_epsilon_greedy_select = epsilon_greedy_select(_lf5, _li5, 0.5)
    var _summary_epsilon_greedy_select = _summary_int(_result_epsilon_greedy_select)
    print("MOJO_RESULT ab_testing::epsilon_greedy_select", _summary_epsilon_greedy_select)
    var _acc_ucb1_select: Float64 = 0.0
    var _t0_ucb1_select = perf_counter_ns()
    for _ in range(N):
        _acc_ucb1_select += Float64(ucb1_select(_lf5, _li5, 5))
    var _t1_ucb1_select = perf_counter_ns()
    var _ns_ucb1_select = Float64(_t1_ucb1_select - _t0_ucb1_select) / Float64(N)
    print("MOJO_TIMING ab_testing::ucb1_select", _ns_ucb1_select, _acc_ucb1_select)
    var _result_ucb1_select = ucb1_select(_lf5, _li5, 5)
    var _summary_ucb1_select = _summary_int(_result_ucb1_select)
    print("MOJO_RESULT ab_testing::ucb1_select", _summary_ucb1_select)
