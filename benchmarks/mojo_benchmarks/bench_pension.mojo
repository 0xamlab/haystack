"""bench_pension.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from pension import replacement_ratio, defined_benefit_pension, defined_contribution_value, annuity_factor, pension_lump_sum_from_annuity, funding_ratio, contribution_rate_required, inflation_adjusted_pension, pension_gap, social_security_bend_points, years_to_full_vesting, withdrawal_rate
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

    var _acc_replacement_ratio: Float64 = 0.0
    var _t0_replacement_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_replacement_ratio += replacement_ratio(0.5, 0.5)
    var _t1_replacement_ratio = perf_counter_ns()
    var _ns_replacement_ratio = Float64(_t1_replacement_ratio - _t0_replacement_ratio) / Float64(N)
    print("MOJO_TIMING pension::replacement_ratio", _ns_replacement_ratio, _acc_replacement_ratio)
    var _result_replacement_ratio = replacement_ratio(0.5, 0.5)
    var _summary_replacement_ratio = _summary_float64(_result_replacement_ratio)
    print("MOJO_RESULT pension::replacement_ratio", _summary_replacement_ratio)
    var _acc_defined_benefit_pension: Float64 = 0.0
    var _t0_defined_benefit_pension = perf_counter_ns()
    for _ in range(N):
        _acc_defined_benefit_pension += defined_benefit_pension(0.5, 0.5, 0.5)
    var _t1_defined_benefit_pension = perf_counter_ns()
    var _ns_defined_benefit_pension = Float64(_t1_defined_benefit_pension - _t0_defined_benefit_pension) / Float64(N)
    print("MOJO_TIMING pension::defined_benefit_pension", _ns_defined_benefit_pension, _acc_defined_benefit_pension)
    var _result_defined_benefit_pension = defined_benefit_pension(0.5, 0.5, 0.5)
    var _summary_defined_benefit_pension = _summary_float64(_result_defined_benefit_pension)
    print("MOJO_RESULT pension::defined_benefit_pension", _summary_defined_benefit_pension)
    var _acc_defined_contribution_value: Float64 = 0.0
    var _t0_defined_contribution_value = perf_counter_ns()
    for _ in range(N):
        _acc_defined_contribution_value += defined_contribution_value(0.5, 0.5, 5)
    var _t1_defined_contribution_value = perf_counter_ns()
    var _ns_defined_contribution_value = Float64(_t1_defined_contribution_value - _t0_defined_contribution_value) / Float64(N)
    print("MOJO_TIMING pension::defined_contribution_value", _ns_defined_contribution_value, _acc_defined_contribution_value)
    var _result_defined_contribution_value = defined_contribution_value(0.5, 0.5, 5)
    var _summary_defined_contribution_value = _summary_float64(_result_defined_contribution_value)
    print("MOJO_RESULT pension::defined_contribution_value", _summary_defined_contribution_value)
    var _acc_annuity_factor: Float64 = 0.0
    var _t0_annuity_factor = perf_counter_ns()
    for _ in range(N):
        _acc_annuity_factor += annuity_factor(0.5, 5)
    var _t1_annuity_factor = perf_counter_ns()
    var _ns_annuity_factor = Float64(_t1_annuity_factor - _t0_annuity_factor) / Float64(N)
    print("MOJO_TIMING pension::annuity_factor", _ns_annuity_factor, _acc_annuity_factor)
    var _result_annuity_factor = annuity_factor(0.5, 5)
    var _summary_annuity_factor = _summary_float64(_result_annuity_factor)
    print("MOJO_RESULT pension::annuity_factor", _summary_annuity_factor)
    var _acc_pension_lump_sum_from_annuity: Float64 = 0.0
    var _t0_pension_lump_sum_from_annuity = perf_counter_ns()
    for _ in range(N):
        _acc_pension_lump_sum_from_annuity += pension_lump_sum_from_annuity(0.5, 0.5)
    var _t1_pension_lump_sum_from_annuity = perf_counter_ns()
    var _ns_pension_lump_sum_from_annuity = Float64(_t1_pension_lump_sum_from_annuity - _t0_pension_lump_sum_from_annuity) / Float64(N)
    print("MOJO_TIMING pension::pension_lump_sum_from_annuity", _ns_pension_lump_sum_from_annuity, _acc_pension_lump_sum_from_annuity)
    var _result_pension_lump_sum_from_annuity = pension_lump_sum_from_annuity(0.5, 0.5)
    var _summary_pension_lump_sum_from_annuity = _summary_float64(_result_pension_lump_sum_from_annuity)
    print("MOJO_RESULT pension::pension_lump_sum_from_annuity", _summary_pension_lump_sum_from_annuity)
    var _acc_funding_ratio: Float64 = 0.0
    var _t0_funding_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_funding_ratio += funding_ratio(0.5, 0.5)
    var _t1_funding_ratio = perf_counter_ns()
    var _ns_funding_ratio = Float64(_t1_funding_ratio - _t0_funding_ratio) / Float64(N)
    print("MOJO_TIMING pension::funding_ratio", _ns_funding_ratio, _acc_funding_ratio)
    var _result_funding_ratio = funding_ratio(0.5, 0.5)
    var _summary_funding_ratio = _summary_float64(_result_funding_ratio)
    print("MOJO_RESULT pension::funding_ratio", _summary_funding_ratio)
    var _acc_contribution_rate_required: Float64 = 0.0
    var _t0_contribution_rate_required = perf_counter_ns()
    for _ in range(N):
        _acc_contribution_rate_required += contribution_rate_required(0.5, 5, 0.5, 0.5)
    var _t1_contribution_rate_required = perf_counter_ns()
    var _ns_contribution_rate_required = Float64(_t1_contribution_rate_required - _t0_contribution_rate_required) / Float64(N)
    print("MOJO_TIMING pension::contribution_rate_required", _ns_contribution_rate_required, _acc_contribution_rate_required)
    var _result_contribution_rate_required = contribution_rate_required(0.5, 5, 0.5, 0.5)
    var _summary_contribution_rate_required = _summary_float64(_result_contribution_rate_required)
    print("MOJO_RESULT pension::contribution_rate_required", _summary_contribution_rate_required)
    var _acc_inflation_adjusted_pension: Float64 = 0.0
    var _t0_inflation_adjusted_pension = perf_counter_ns()
    for _ in range(N):
        _acc_inflation_adjusted_pension += inflation_adjusted_pension(0.5, 0.5, 5)
    var _t1_inflation_adjusted_pension = perf_counter_ns()
    var _ns_inflation_adjusted_pension = Float64(_t1_inflation_adjusted_pension - _t0_inflation_adjusted_pension) / Float64(N)
    print("MOJO_TIMING pension::inflation_adjusted_pension", _ns_inflation_adjusted_pension, _acc_inflation_adjusted_pension)
    var _result_inflation_adjusted_pension = inflation_adjusted_pension(0.5, 0.5, 5)
    var _summary_inflation_adjusted_pension = _summary_float64(_result_inflation_adjusted_pension)
    print("MOJO_RESULT pension::inflation_adjusted_pension", _summary_inflation_adjusted_pension)
    var _acc_pension_gap: Float64 = 0.0
    var _t0_pension_gap = perf_counter_ns()
    for _ in range(N):
        _acc_pension_gap += pension_gap(0.5, 0.5)
    var _t1_pension_gap = perf_counter_ns()
    var _ns_pension_gap = Float64(_t1_pension_gap - _t0_pension_gap) / Float64(N)
    print("MOJO_TIMING pension::pension_gap", _ns_pension_gap, _acc_pension_gap)
    var _result_pension_gap = pension_gap(0.5, 0.5)
    var _summary_pension_gap = _summary_float64(_result_pension_gap)
    print("MOJO_RESULT pension::pension_gap", _summary_pension_gap)
    var _acc_social_security_bend_points: Float64 = 0.0
    var _t0_social_security_bend_points = perf_counter_ns()
    for _ in range(N):
        _acc_social_security_bend_points += social_security_bend_points(0.5, 0.5, 0.5)
    var _t1_social_security_bend_points = perf_counter_ns()
    var _ns_social_security_bend_points = Float64(_t1_social_security_bend_points - _t0_social_security_bend_points) / Float64(N)
    print("MOJO_TIMING pension::social_security_bend_points", _ns_social_security_bend_points, _acc_social_security_bend_points)
    var _result_social_security_bend_points = social_security_bend_points(0.5, 0.5, 0.5)
    var _summary_social_security_bend_points = _summary_float64(_result_social_security_bend_points)
    print("MOJO_RESULT pension::social_security_bend_points", _summary_social_security_bend_points)
    var _acc_years_to_full_vesting: Float64 = 0.0
    var _t0_years_to_full_vesting = perf_counter_ns()
    for _ in range(N):
        _acc_years_to_full_vesting += years_to_full_vesting(0.5, 0.5)
    var _t1_years_to_full_vesting = perf_counter_ns()
    var _ns_years_to_full_vesting = Float64(_t1_years_to_full_vesting - _t0_years_to_full_vesting) / Float64(N)
    print("MOJO_TIMING pension::years_to_full_vesting", _ns_years_to_full_vesting, _acc_years_to_full_vesting)
    var _result_years_to_full_vesting = years_to_full_vesting(0.5, 0.5)
    var _summary_years_to_full_vesting = _summary_float64(_result_years_to_full_vesting)
    print("MOJO_RESULT pension::years_to_full_vesting", _summary_years_to_full_vesting)
    var _acc_withdrawal_rate: Float64 = 0.0
    var _t0_withdrawal_rate = perf_counter_ns()
    for _ in range(N):
        _acc_withdrawal_rate += withdrawal_rate(0.5, 0.5)
    var _t1_withdrawal_rate = perf_counter_ns()
    var _ns_withdrawal_rate = Float64(_t1_withdrawal_rate - _t0_withdrawal_rate) / Float64(N)
    print("MOJO_TIMING pension::withdrawal_rate", _ns_withdrawal_rate, _acc_withdrawal_rate)
    var _result_withdrawal_rate = withdrawal_rate(0.5, 0.5)
    var _summary_withdrawal_rate = _summary_float64(_result_withdrawal_rate)
    print("MOJO_RESULT pension::withdrawal_rate", _summary_withdrawal_rate)
