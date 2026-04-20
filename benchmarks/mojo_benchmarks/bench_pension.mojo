"""bench_pension.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from pension import replacement_ratio, defined_benefit_pension, defined_contribution_value, annuity_factor, pension_lump_sum_from_annuity, funding_ratio, contribution_rate_required, inflation_adjusted_pension, pension_gap, social_security_bend_points, years_to_full_vesting, withdrawal_rate
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

    var _acc_replacement_ratio: Float64 = 0.0
    var _t0_replacement_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_replacement_ratio += replacement_ratio(0.5, 0.5)
    var _t1_replacement_ratio = perf_counter_ns()
    var _ns_replacement_ratio = Float64(_t1_replacement_ratio - _t0_replacement_ratio) / Float64(N)
    print("MOJO_TIMING pension::replacement_ratio", _ns_replacement_ratio, _acc_replacement_ratio)
    var _acc_defined_benefit_pension: Float64 = 0.0
    var _t0_defined_benefit_pension = perf_counter_ns()
    for _ in range(N):
        _acc_defined_benefit_pension += defined_benefit_pension(0.5, 0.5, 0.5)
    var _t1_defined_benefit_pension = perf_counter_ns()
    var _ns_defined_benefit_pension = Float64(_t1_defined_benefit_pension - _t0_defined_benefit_pension) / Float64(N)
    print("MOJO_TIMING pension::defined_benefit_pension", _ns_defined_benefit_pension, _acc_defined_benefit_pension)
    var _acc_defined_contribution_value: Float64 = 0.0
    var _t0_defined_contribution_value = perf_counter_ns()
    for _ in range(N):
        _acc_defined_contribution_value += defined_contribution_value(0.5, 0.5, 5)
    var _t1_defined_contribution_value = perf_counter_ns()
    var _ns_defined_contribution_value = Float64(_t1_defined_contribution_value - _t0_defined_contribution_value) / Float64(N)
    print("MOJO_TIMING pension::defined_contribution_value", _ns_defined_contribution_value, _acc_defined_contribution_value)
    var _acc_annuity_factor: Float64 = 0.0
    var _t0_annuity_factor = perf_counter_ns()
    for _ in range(N):
        _acc_annuity_factor += annuity_factor(0.5, 5)
    var _t1_annuity_factor = perf_counter_ns()
    var _ns_annuity_factor = Float64(_t1_annuity_factor - _t0_annuity_factor) / Float64(N)
    print("MOJO_TIMING pension::annuity_factor", _ns_annuity_factor, _acc_annuity_factor)
    var _acc_pension_lump_sum_from_annuity: Float64 = 0.0
    var _t0_pension_lump_sum_from_annuity = perf_counter_ns()
    for _ in range(N):
        _acc_pension_lump_sum_from_annuity += pension_lump_sum_from_annuity(0.5, 0.5)
    var _t1_pension_lump_sum_from_annuity = perf_counter_ns()
    var _ns_pension_lump_sum_from_annuity = Float64(_t1_pension_lump_sum_from_annuity - _t0_pension_lump_sum_from_annuity) / Float64(N)
    print("MOJO_TIMING pension::pension_lump_sum_from_annuity", _ns_pension_lump_sum_from_annuity, _acc_pension_lump_sum_from_annuity)
    var _acc_funding_ratio: Float64 = 0.0
    var _t0_funding_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_funding_ratio += funding_ratio(0.5, 0.5)
    var _t1_funding_ratio = perf_counter_ns()
    var _ns_funding_ratio = Float64(_t1_funding_ratio - _t0_funding_ratio) / Float64(N)
    print("MOJO_TIMING pension::funding_ratio", _ns_funding_ratio, _acc_funding_ratio)
    var _acc_contribution_rate_required: Float64 = 0.0
    var _t0_contribution_rate_required = perf_counter_ns()
    for _ in range(N):
        _acc_contribution_rate_required += contribution_rate_required(0.5, 5, 0.5, 0.5)
    var _t1_contribution_rate_required = perf_counter_ns()
    var _ns_contribution_rate_required = Float64(_t1_contribution_rate_required - _t0_contribution_rate_required) / Float64(N)
    print("MOJO_TIMING pension::contribution_rate_required", _ns_contribution_rate_required, _acc_contribution_rate_required)
    var _acc_inflation_adjusted_pension: Float64 = 0.0
    var _t0_inflation_adjusted_pension = perf_counter_ns()
    for _ in range(N):
        _acc_inflation_adjusted_pension += inflation_adjusted_pension(0.5, 0.5, 5)
    var _t1_inflation_adjusted_pension = perf_counter_ns()
    var _ns_inflation_adjusted_pension = Float64(_t1_inflation_adjusted_pension - _t0_inflation_adjusted_pension) / Float64(N)
    print("MOJO_TIMING pension::inflation_adjusted_pension", _ns_inflation_adjusted_pension, _acc_inflation_adjusted_pension)
    var _acc_pension_gap: Float64 = 0.0
    var _t0_pension_gap = perf_counter_ns()
    for _ in range(N):
        _acc_pension_gap += pension_gap(0.5, 0.5)
    var _t1_pension_gap = perf_counter_ns()
    var _ns_pension_gap = Float64(_t1_pension_gap - _t0_pension_gap) / Float64(N)
    print("MOJO_TIMING pension::pension_gap", _ns_pension_gap, _acc_pension_gap)
    var _acc_social_security_bend_points: Float64 = 0.0
    var _t0_social_security_bend_points = perf_counter_ns()
    for _ in range(N):
        _acc_social_security_bend_points += social_security_bend_points(0.5, 0.5, 0.5)
    var _t1_social_security_bend_points = perf_counter_ns()
    var _ns_social_security_bend_points = Float64(_t1_social_security_bend_points - _t0_social_security_bend_points) / Float64(N)
    print("MOJO_TIMING pension::social_security_bend_points", _ns_social_security_bend_points, _acc_social_security_bend_points)
    var _acc_years_to_full_vesting: Float64 = 0.0
    var _t0_years_to_full_vesting = perf_counter_ns()
    for _ in range(N):
        _acc_years_to_full_vesting += years_to_full_vesting(0.5, 0.5)
    var _t1_years_to_full_vesting = perf_counter_ns()
    var _ns_years_to_full_vesting = Float64(_t1_years_to_full_vesting - _t0_years_to_full_vesting) / Float64(N)
    print("MOJO_TIMING pension::years_to_full_vesting", _ns_years_to_full_vesting, _acc_years_to_full_vesting)
    var _acc_withdrawal_rate: Float64 = 0.0
    var _t0_withdrawal_rate = perf_counter_ns()
    for _ in range(N):
        _acc_withdrawal_rate += withdrawal_rate(0.5, 0.5)
    var _t1_withdrawal_rate = perf_counter_ns()
    var _ns_withdrawal_rate = Float64(_t1_withdrawal_rate - _t0_withdrawal_rate) / Float64(N)
    print("MOJO_TIMING pension::withdrawal_rate", _ns_withdrawal_rate, _acc_withdrawal_rate)
