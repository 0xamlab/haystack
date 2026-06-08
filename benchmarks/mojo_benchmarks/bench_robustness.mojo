"""bench_robustness.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from robustness import eval_test_func, perturbation_test, sensitivity_one_at_a_time, morris_screening, sobol_first_order_estimate, input_range_sweep, tornado_data, robustness_score
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

    var _acc_eval_test_func: Float64 = 0.0
    var _t0_eval_test_func = perf_counter_ns()
    for _ in range(N):
        _acc_eval_test_func += eval_test_func(_lf5, 5)
    var _t1_eval_test_func = perf_counter_ns()
    var _ns_eval_test_func = Float64(_t1_eval_test_func - _t0_eval_test_func) / Float64(N)
    print("MOJO_TIMING robustness::eval_test_func", _ns_eval_test_func, _acc_eval_test_func)
    var _result_eval_test_func = eval_test_func(_lf5, 5)
    var _summary_eval_test_func = _summary_float64(_result_eval_test_func)
    print("MOJO_RESULT robustness::eval_test_func", _summary_eval_test_func)
    var _acc_perturbation_test: Float64 = 0.0
    var _t0_perturbation_test = perf_counter_ns()
    for _ in range(N):
        var _r_perturbation_test = perturbation_test(_lf5, 0.5)
        _acc_perturbation_test += Float64(len(_r_perturbation_test))
    var _t1_perturbation_test = perf_counter_ns()
    var _ns_perturbation_test = Float64(_t1_perturbation_test - _t0_perturbation_test) / Float64(N)
    print("MOJO_TIMING robustness::perturbation_test", _ns_perturbation_test, _acc_perturbation_test)
    var _result_perturbation_test = perturbation_test(_lf5, 0.5)
    var _summary_perturbation_test = _summary_list_float64(_result_perturbation_test)
    print("MOJO_RESULT robustness::perturbation_test", _summary_perturbation_test)
    var _acc_sensitivity_one_at_a_time: Float64 = 0.0
    var _t0_sensitivity_one_at_a_time = perf_counter_ns()
    for _ in range(N):
        _acc_sensitivity_one_at_a_time += sensitivity_one_at_a_time(_lf5, 5, 0.5, 5)
    var _t1_sensitivity_one_at_a_time = perf_counter_ns()
    var _ns_sensitivity_one_at_a_time = Float64(_t1_sensitivity_one_at_a_time - _t0_sensitivity_one_at_a_time) / Float64(N)
    print("MOJO_TIMING robustness::sensitivity_one_at_a_time", _ns_sensitivity_one_at_a_time, _acc_sensitivity_one_at_a_time)
    var _result_sensitivity_one_at_a_time = sensitivity_one_at_a_time(_lf5, 5, 0.5, 5)
    var _summary_sensitivity_one_at_a_time = _summary_float64(_result_sensitivity_one_at_a_time)
    print("MOJO_RESULT robustness::sensitivity_one_at_a_time", _summary_sensitivity_one_at_a_time)
    var _acc_morris_screening: Float64 = 0.0
    var _t0_morris_screening = perf_counter_ns()
    for _ in range(N):
        var _r_morris_screening = morris_screening(5, 5, 5, 0.5)
        _acc_morris_screening += Float64(len(_r_morris_screening))
    var _t1_morris_screening = perf_counter_ns()
    var _ns_morris_screening = Float64(_t1_morris_screening - _t0_morris_screening) / Float64(N)
    print("MOJO_TIMING robustness::morris_screening", _ns_morris_screening, _acc_morris_screening)
    var _result_morris_screening = morris_screening(5, 5, 5, 0.5)
    var _summary_morris_screening = _summary_list_float64(_result_morris_screening)
    print("MOJO_RESULT robustness::morris_screening", _summary_morris_screening)
    var _acc_sobol_first_order_estimate: Float64 = 0.0
    var _t0_sobol_first_order_estimate = perf_counter_ns()
    for _ in range(N):
        var _r_sobol_first_order_estimate = sobol_first_order_estimate(5, 5, 5)
        _acc_sobol_first_order_estimate += Float64(len(_r_sobol_first_order_estimate))
    var _t1_sobol_first_order_estimate = perf_counter_ns()
    var _ns_sobol_first_order_estimate = Float64(_t1_sobol_first_order_estimate - _t0_sobol_first_order_estimate) / Float64(N)
    print("MOJO_TIMING robustness::sobol_first_order_estimate", _ns_sobol_first_order_estimate, _acc_sobol_first_order_estimate)
    var _result_sobol_first_order_estimate = sobol_first_order_estimate(5, 5, 5)
    var _summary_sobol_first_order_estimate = _summary_list_float64(_result_sobol_first_order_estimate)
    print("MOJO_RESULT robustness::sobol_first_order_estimate", _summary_sobol_first_order_estimate)
    var _acc_input_range_sweep: Float64 = 0.0
    var _t0_input_range_sweep = perf_counter_ns()
    for _ in range(N):
        var _r_input_range_sweep = input_range_sweep(_lf5, 5, 0.5, 0.5, 5, 5)
        _acc_input_range_sweep += Float64(len(_r_input_range_sweep))
    var _t1_input_range_sweep = perf_counter_ns()
    var _ns_input_range_sweep = Float64(_t1_input_range_sweep - _t0_input_range_sweep) / Float64(N)
    print("MOJO_TIMING robustness::input_range_sweep", _ns_input_range_sweep, _acc_input_range_sweep)
    var _result_input_range_sweep = input_range_sweep(_lf5, 5, 0.5, 0.5, 5, 5)
    var _summary_input_range_sweep = _summary_list_list_float64(_result_input_range_sweep)
    print("MOJO_RESULT robustness::input_range_sweep", _summary_input_range_sweep)
    var _acc_tornado_data: Float64 = 0.0
    var _t0_tornado_data = perf_counter_ns()
    for _ in range(N):
        var _r_tornado_data = tornado_data(_lf5, _lf5, 5)
        _acc_tornado_data += Float64(len(_r_tornado_data))
    var _t1_tornado_data = perf_counter_ns()
    var _ns_tornado_data = Float64(_t1_tornado_data - _t0_tornado_data) / Float64(N)
    print("MOJO_TIMING robustness::tornado_data", _ns_tornado_data, _acc_tornado_data)
    var _result_tornado_data = tornado_data(_lf5, _lf5, 5)
    var _summary_tornado_data = _summary_list_list_float64(_result_tornado_data)
    print("MOJO_RESULT robustness::tornado_data", _summary_tornado_data)
    var _acc_robustness_score: Float64 = 0.0
    var _t0_robustness_score = perf_counter_ns()
    for _ in range(N):
        _acc_robustness_score += robustness_score(_lf5)
    var _t1_robustness_score = perf_counter_ns()
    var _ns_robustness_score = Float64(_t1_robustness_score - _t0_robustness_score) / Float64(N)
    print("MOJO_TIMING robustness::robustness_score", _ns_robustness_score, _acc_robustness_score)
    var _result_robustness_score = robustness_score(_lf5)
    var _summary_robustness_score = _summary_float64(_result_robustness_score)
    print("MOJO_RESULT robustness::robustness_score", _summary_robustness_score)
