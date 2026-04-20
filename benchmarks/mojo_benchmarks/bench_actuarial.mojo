"""bench_actuarial.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from actuarial import present_value, future_value, annuity_present_value, annuity_future_value, life_expectancy_curtate, mortality_rate, survival_probability, force_of_mortality, net_single_premium, loss_ratio, combined_ratio, reserve_prospective
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

    var _acc_present_value: Float64 = 0.0
    var _t0_present_value = perf_counter_ns()
    for _ in range(N):
        _acc_present_value += present_value(0.5, 0.5, 0.5)
    var _t1_present_value = perf_counter_ns()
    var _ns_present_value = Float64(_t1_present_value - _t0_present_value) / Float64(N)
    print("MOJO_TIMING actuarial::present_value", _ns_present_value, _acc_present_value)
    var _acc_future_value: Float64 = 0.0
    var _t0_future_value = perf_counter_ns()
    for _ in range(N):
        _acc_future_value += future_value(0.5, 0.5, 0.5)
    var _t1_future_value = perf_counter_ns()
    var _ns_future_value = Float64(_t1_future_value - _t0_future_value) / Float64(N)
    print("MOJO_TIMING actuarial::future_value", _ns_future_value, _acc_future_value)
    var _acc_annuity_present_value: Float64 = 0.0
    var _t0_annuity_present_value = perf_counter_ns()
    for _ in range(N):
        _acc_annuity_present_value += annuity_present_value(0.5, 0.5, 0.5)
    var _t1_annuity_present_value = perf_counter_ns()
    var _ns_annuity_present_value = Float64(_t1_annuity_present_value - _t0_annuity_present_value) / Float64(N)
    print("MOJO_TIMING actuarial::annuity_present_value", _ns_annuity_present_value, _acc_annuity_present_value)
    var _acc_annuity_future_value: Float64 = 0.0
    var _t0_annuity_future_value = perf_counter_ns()
    for _ in range(N):
        _acc_annuity_future_value += annuity_future_value(0.5, 0.5, 0.5)
    var _t1_annuity_future_value = perf_counter_ns()
    var _ns_annuity_future_value = Float64(_t1_annuity_future_value - _t0_annuity_future_value) / Float64(N)
    print("MOJO_TIMING actuarial::annuity_future_value", _ns_annuity_future_value, _acc_annuity_future_value)
    var _acc_life_expectancy_curtate: Float64 = 0.0
    var _t0_life_expectancy_curtate = perf_counter_ns()
    for _ in range(N):
        _acc_life_expectancy_curtate += life_expectancy_curtate(0.5, 5, 5)
    var _t1_life_expectancy_curtate = perf_counter_ns()
    var _ns_life_expectancy_curtate = Float64(_t1_life_expectancy_curtate - _t0_life_expectancy_curtate) / Float64(N)
    print("MOJO_TIMING actuarial::life_expectancy_curtate", _ns_life_expectancy_curtate, _acc_life_expectancy_curtate)
    var _acc_mortality_rate: Float64 = 0.0
    var _t0_mortality_rate = perf_counter_ns()
    for _ in range(N):
        _acc_mortality_rate += mortality_rate(0.5, 0.5)
    var _t1_mortality_rate = perf_counter_ns()
    var _ns_mortality_rate = Float64(_t1_mortality_rate - _t0_mortality_rate) / Float64(N)
    print("MOJO_TIMING actuarial::mortality_rate", _ns_mortality_rate, _acc_mortality_rate)
    var _acc_survival_probability: Float64 = 0.0
    var _t0_survival_probability = perf_counter_ns()
    for _ in range(N):
        _acc_survival_probability += survival_probability(0.5)
    var _t1_survival_probability = perf_counter_ns()
    var _ns_survival_probability = Float64(_t1_survival_probability - _t0_survival_probability) / Float64(N)
    print("MOJO_TIMING actuarial::survival_probability", _ns_survival_probability, _acc_survival_probability)
    var _acc_force_of_mortality: Float64 = 0.0
    var _t0_force_of_mortality = perf_counter_ns()
    for _ in range(N):
        _acc_force_of_mortality += force_of_mortality(0.5)
    var _t1_force_of_mortality = perf_counter_ns()
    var _ns_force_of_mortality = Float64(_t1_force_of_mortality - _t0_force_of_mortality) / Float64(N)
    print("MOJO_TIMING actuarial::force_of_mortality", _ns_force_of_mortality, _acc_force_of_mortality)
    var _acc_net_single_premium: Float64 = 0.0
    var _t0_net_single_premium = perf_counter_ns()
    for _ in range(N):
        _acc_net_single_premium += net_single_premium(0.5, 0.5, 0.5)
    var _t1_net_single_premium = perf_counter_ns()
    var _ns_net_single_premium = Float64(_t1_net_single_premium - _t0_net_single_premium) / Float64(N)
    print("MOJO_TIMING actuarial::net_single_premium", _ns_net_single_premium, _acc_net_single_premium)
    var _acc_loss_ratio: Float64 = 0.0
    var _t0_loss_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_loss_ratio += loss_ratio(0.5, 0.5)
    var _t1_loss_ratio = perf_counter_ns()
    var _ns_loss_ratio = Float64(_t1_loss_ratio - _t0_loss_ratio) / Float64(N)
    print("MOJO_TIMING actuarial::loss_ratio", _ns_loss_ratio, _acc_loss_ratio)
    var _acc_combined_ratio: Float64 = 0.0
    var _t0_combined_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_combined_ratio += combined_ratio(0.5, 0.5)
    var _t1_combined_ratio = perf_counter_ns()
    var _ns_combined_ratio = Float64(_t1_combined_ratio - _t0_combined_ratio) / Float64(N)
    print("MOJO_TIMING actuarial::combined_ratio", _ns_combined_ratio, _acc_combined_ratio)
    var _acc_reserve_prospective: Float64 = 0.0
    var _t0_reserve_prospective = perf_counter_ns()
    for _ in range(N):
        _acc_reserve_prospective += reserve_prospective(0.5, 0.5)
    var _t1_reserve_prospective = perf_counter_ns()
    var _ns_reserve_prospective = Float64(_t1_reserve_prospective - _t0_reserve_prospective) / Float64(N)
    print("MOJO_TIMING actuarial::reserve_prospective", _ns_reserve_prospective, _acc_reserve_prospective)
