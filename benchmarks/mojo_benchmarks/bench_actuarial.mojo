"""bench_actuarial.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from actuarial import present_value, future_value, annuity_present_value, annuity_future_value, life_expectancy_curtate, mortality_rate, survival_probability, force_of_mortality, net_single_premium, loss_ratio, combined_ratio, reserve_prospective
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

    var _acc_present_value: Float64 = 0.0
    var _t0_present_value = perf_counter_ns()
    for _ in range(N):
        _acc_present_value += present_value(0.5, 0.5, 0.5)
    var _t1_present_value = perf_counter_ns()
    var _ns_present_value = Float64(_t1_present_value - _t0_present_value) / Float64(N)
    print("MOJO_TIMING actuarial::present_value", _ns_present_value, _acc_present_value)
    var _result_present_value = present_value(0.5, 0.5, 0.5)
    var _summary_present_value = _summary_float64(_result_present_value)
    print("MOJO_RESULT actuarial::present_value", _summary_present_value)
    var _acc_future_value: Float64 = 0.0
    var _t0_future_value = perf_counter_ns()
    for _ in range(N):
        _acc_future_value += future_value(0.5, 0.5, 0.5)
    var _t1_future_value = perf_counter_ns()
    var _ns_future_value = Float64(_t1_future_value - _t0_future_value) / Float64(N)
    print("MOJO_TIMING actuarial::future_value", _ns_future_value, _acc_future_value)
    var _result_future_value = future_value(0.5, 0.5, 0.5)
    var _summary_future_value = _summary_float64(_result_future_value)
    print("MOJO_RESULT actuarial::future_value", _summary_future_value)
    var _acc_annuity_present_value: Float64 = 0.0
    var _t0_annuity_present_value = perf_counter_ns()
    for _ in range(N):
        _acc_annuity_present_value += annuity_present_value(0.5, 0.5, 0.5)
    var _t1_annuity_present_value = perf_counter_ns()
    var _ns_annuity_present_value = Float64(_t1_annuity_present_value - _t0_annuity_present_value) / Float64(N)
    print("MOJO_TIMING actuarial::annuity_present_value", _ns_annuity_present_value, _acc_annuity_present_value)
    var _result_annuity_present_value = annuity_present_value(0.5, 0.5, 0.5)
    var _summary_annuity_present_value = _summary_float64(_result_annuity_present_value)
    print("MOJO_RESULT actuarial::annuity_present_value", _summary_annuity_present_value)
    var _acc_annuity_future_value: Float64 = 0.0
    var _t0_annuity_future_value = perf_counter_ns()
    for _ in range(N):
        _acc_annuity_future_value += annuity_future_value(0.5, 0.5, 0.5)
    var _t1_annuity_future_value = perf_counter_ns()
    var _ns_annuity_future_value = Float64(_t1_annuity_future_value - _t0_annuity_future_value) / Float64(N)
    print("MOJO_TIMING actuarial::annuity_future_value", _ns_annuity_future_value, _acc_annuity_future_value)
    var _result_annuity_future_value = annuity_future_value(0.5, 0.5, 0.5)
    var _summary_annuity_future_value = _summary_float64(_result_annuity_future_value)
    print("MOJO_RESULT actuarial::annuity_future_value", _summary_annuity_future_value)
    var _acc_life_expectancy_curtate: Float64 = 0.0
    var _t0_life_expectancy_curtate = perf_counter_ns()
    for _ in range(N):
        _acc_life_expectancy_curtate += life_expectancy_curtate(0.5, 5, 5)
    var _t1_life_expectancy_curtate = perf_counter_ns()
    var _ns_life_expectancy_curtate = Float64(_t1_life_expectancy_curtate - _t0_life_expectancy_curtate) / Float64(N)
    print("MOJO_TIMING actuarial::life_expectancy_curtate", _ns_life_expectancy_curtate, _acc_life_expectancy_curtate)
    var _result_life_expectancy_curtate = life_expectancy_curtate(0.5, 5, 5)
    var _summary_life_expectancy_curtate = _summary_float64(_result_life_expectancy_curtate)
    print("MOJO_RESULT actuarial::life_expectancy_curtate", _summary_life_expectancy_curtate)
    var _acc_mortality_rate: Float64 = 0.0
    var _t0_mortality_rate = perf_counter_ns()
    for _ in range(N):
        _acc_mortality_rate += mortality_rate(0.5, 0.5)
    var _t1_mortality_rate = perf_counter_ns()
    var _ns_mortality_rate = Float64(_t1_mortality_rate - _t0_mortality_rate) / Float64(N)
    print("MOJO_TIMING actuarial::mortality_rate", _ns_mortality_rate, _acc_mortality_rate)
    var _result_mortality_rate = mortality_rate(0.5, 0.5)
    var _summary_mortality_rate = _summary_float64(_result_mortality_rate)
    print("MOJO_RESULT actuarial::mortality_rate", _summary_mortality_rate)
    var _acc_survival_probability: Float64 = 0.0
    var _t0_survival_probability = perf_counter_ns()
    for _ in range(N):
        _acc_survival_probability += survival_probability(0.5)
    var _t1_survival_probability = perf_counter_ns()
    var _ns_survival_probability = Float64(_t1_survival_probability - _t0_survival_probability) / Float64(N)
    print("MOJO_TIMING actuarial::survival_probability", _ns_survival_probability, _acc_survival_probability)
    var _result_survival_probability = survival_probability(0.5)
    var _summary_survival_probability = _summary_float64(_result_survival_probability)
    print("MOJO_RESULT actuarial::survival_probability", _summary_survival_probability)
    var _acc_force_of_mortality: Float64 = 0.0
    var _t0_force_of_mortality = perf_counter_ns()
    for _ in range(N):
        _acc_force_of_mortality += force_of_mortality(0.5)
    var _t1_force_of_mortality = perf_counter_ns()
    var _ns_force_of_mortality = Float64(_t1_force_of_mortality - _t0_force_of_mortality) / Float64(N)
    print("MOJO_TIMING actuarial::force_of_mortality", _ns_force_of_mortality, _acc_force_of_mortality)
    var _result_force_of_mortality = force_of_mortality(0.5)
    var _summary_force_of_mortality = _summary_float64(_result_force_of_mortality)
    print("MOJO_RESULT actuarial::force_of_mortality", _summary_force_of_mortality)
    var _acc_net_single_premium: Float64 = 0.0
    var _t0_net_single_premium = perf_counter_ns()
    for _ in range(N):
        _acc_net_single_premium += net_single_premium(0.5, 0.5, 0.5)
    var _t1_net_single_premium = perf_counter_ns()
    var _ns_net_single_premium = Float64(_t1_net_single_premium - _t0_net_single_premium) / Float64(N)
    print("MOJO_TIMING actuarial::net_single_premium", _ns_net_single_premium, _acc_net_single_premium)
    var _result_net_single_premium = net_single_premium(0.5, 0.5, 0.5)
    var _summary_net_single_premium = _summary_float64(_result_net_single_premium)
    print("MOJO_RESULT actuarial::net_single_premium", _summary_net_single_premium)
    var _acc_loss_ratio: Float64 = 0.0
    var _t0_loss_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_loss_ratio += loss_ratio(0.5, 0.5)
    var _t1_loss_ratio = perf_counter_ns()
    var _ns_loss_ratio = Float64(_t1_loss_ratio - _t0_loss_ratio) / Float64(N)
    print("MOJO_TIMING actuarial::loss_ratio", _ns_loss_ratio, _acc_loss_ratio)
    var _result_loss_ratio = loss_ratio(0.5, 0.5)
    var _summary_loss_ratio = _summary_float64(_result_loss_ratio)
    print("MOJO_RESULT actuarial::loss_ratio", _summary_loss_ratio)
    var _acc_combined_ratio: Float64 = 0.0
    var _t0_combined_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_combined_ratio += combined_ratio(0.5, 0.5)
    var _t1_combined_ratio = perf_counter_ns()
    var _ns_combined_ratio = Float64(_t1_combined_ratio - _t0_combined_ratio) / Float64(N)
    print("MOJO_TIMING actuarial::combined_ratio", _ns_combined_ratio, _acc_combined_ratio)
    var _result_combined_ratio = combined_ratio(0.5, 0.5)
    var _summary_combined_ratio = _summary_float64(_result_combined_ratio)
    print("MOJO_RESULT actuarial::combined_ratio", _summary_combined_ratio)
    var _acc_reserve_prospective: Float64 = 0.0
    var _t0_reserve_prospective = perf_counter_ns()
    for _ in range(N):
        _acc_reserve_prospective += reserve_prospective(0.5, 0.5)
    var _t1_reserve_prospective = perf_counter_ns()
    var _ns_reserve_prospective = Float64(_t1_reserve_prospective - _t0_reserve_prospective) / Float64(N)
    print("MOJO_TIMING actuarial::reserve_prospective", _ns_reserve_prospective, _acc_reserve_prospective)
    var _result_reserve_prospective = reserve_prospective(0.5, 0.5)
    var _summary_reserve_prospective = _summary_float64(_result_reserve_prospective)
    print("MOJO_RESULT actuarial::reserve_prospective", _summary_reserve_prospective)
