"""bench_currency.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from currency import round_currency, compound_interest, continuous_compound, amortization_payment, amortization_schedule, present_value, present_value_annuity, future_value_annuity, effective_annual_rate, discount_factor, rule_of_72, loan_balance_after
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

    var _acc_round_currency: Float64 = 0.0
    var _t0_round_currency = perf_counter_ns()
    for _ in range(N):
        _acc_round_currency += round_currency(0.5, 5)
    var _t1_round_currency = perf_counter_ns()
    var _ns_round_currency = Float64(_t1_round_currency - _t0_round_currency) / Float64(N)
    print("MOJO_TIMING currency::round_currency", _ns_round_currency, _acc_round_currency)
    var _result_round_currency = round_currency(0.5, 5)
    var _summary_round_currency = _summary_float64(_result_round_currency)
    print("MOJO_RESULT currency::round_currency", _summary_round_currency)
    var _acc_compound_interest: Float64 = 0.0
    var _t0_compound_interest = perf_counter_ns()
    for _ in range(N):
        _acc_compound_interest += compound_interest(0.5, 0.5, 5)
    var _t1_compound_interest = perf_counter_ns()
    var _ns_compound_interest = Float64(_t1_compound_interest - _t0_compound_interest) / Float64(N)
    print("MOJO_TIMING currency::compound_interest", _ns_compound_interest, _acc_compound_interest)
    var _result_compound_interest = compound_interest(0.5, 0.5, 5)
    var _summary_compound_interest = _summary_float64(_result_compound_interest)
    print("MOJO_RESULT currency::compound_interest", _summary_compound_interest)
    var _acc_continuous_compound: Float64 = 0.0
    var _t0_continuous_compound = perf_counter_ns()
    for _ in range(N):
        _acc_continuous_compound += continuous_compound(0.5, 0.5, 0.5)
    var _t1_continuous_compound = perf_counter_ns()
    var _ns_continuous_compound = Float64(_t1_continuous_compound - _t0_continuous_compound) / Float64(N)
    print("MOJO_TIMING currency::continuous_compound", _ns_continuous_compound, _acc_continuous_compound)
    var _result_continuous_compound = continuous_compound(0.5, 0.5, 0.5)
    var _summary_continuous_compound = _summary_float64(_result_continuous_compound)
    print("MOJO_RESULT currency::continuous_compound", _summary_continuous_compound)
    var _acc_amortization_payment: Float64 = 0.0
    var _t0_amortization_payment = perf_counter_ns()
    for _ in range(N):
        _acc_amortization_payment += amortization_payment(0.5, 0.5, 5)
    var _t1_amortization_payment = perf_counter_ns()
    var _ns_amortization_payment = Float64(_t1_amortization_payment - _t0_amortization_payment) / Float64(N)
    print("MOJO_TIMING currency::amortization_payment", _ns_amortization_payment, _acc_amortization_payment)
    var _result_amortization_payment = amortization_payment(0.5, 0.5, 5)
    var _summary_amortization_payment = _summary_float64(_result_amortization_payment)
    print("MOJO_RESULT currency::amortization_payment", _summary_amortization_payment)
    var _acc_amortization_schedule: Float64 = 0.0
    var _t0_amortization_schedule = perf_counter_ns()
    for _ in range(N):
        var _r_amortization_schedule = amortization_schedule(0.5, 0.5, 5)
        _acc_amortization_schedule += Float64(len(_r_amortization_schedule))
    var _t1_amortization_schedule = perf_counter_ns()
    var _ns_amortization_schedule = Float64(_t1_amortization_schedule - _t0_amortization_schedule) / Float64(N)
    print("MOJO_TIMING currency::amortization_schedule", _ns_amortization_schedule, _acc_amortization_schedule)
    var _result_amortization_schedule = amortization_schedule(0.5, 0.5, 5)
    var _summary_amortization_schedule = _summary_list_list_float64(_result_amortization_schedule)
    print("MOJO_RESULT currency::amortization_schedule", _summary_amortization_schedule)
    var _acc_present_value: Float64 = 0.0
    var _t0_present_value = perf_counter_ns()
    for _ in range(N):
        _acc_present_value += present_value(0.5, 0.5, 5)
    var _t1_present_value = perf_counter_ns()
    var _ns_present_value = Float64(_t1_present_value - _t0_present_value) / Float64(N)
    print("MOJO_TIMING currency::present_value", _ns_present_value, _acc_present_value)
    var _result_present_value = present_value(0.5, 0.5, 5)
    var _summary_present_value = _summary_float64(_result_present_value)
    print("MOJO_RESULT currency::present_value", _summary_present_value)
    var _acc_present_value_annuity: Float64 = 0.0
    var _t0_present_value_annuity = perf_counter_ns()
    for _ in range(N):
        _acc_present_value_annuity += present_value_annuity(0.5, 0.5, 5)
    var _t1_present_value_annuity = perf_counter_ns()
    var _ns_present_value_annuity = Float64(_t1_present_value_annuity - _t0_present_value_annuity) / Float64(N)
    print("MOJO_TIMING currency::present_value_annuity", _ns_present_value_annuity, _acc_present_value_annuity)
    var _result_present_value_annuity = present_value_annuity(0.5, 0.5, 5)
    var _summary_present_value_annuity = _summary_float64(_result_present_value_annuity)
    print("MOJO_RESULT currency::present_value_annuity", _summary_present_value_annuity)
    var _acc_future_value_annuity: Float64 = 0.0
    var _t0_future_value_annuity = perf_counter_ns()
    for _ in range(N):
        _acc_future_value_annuity += future_value_annuity(0.5, 0.5, 5)
    var _t1_future_value_annuity = perf_counter_ns()
    var _ns_future_value_annuity = Float64(_t1_future_value_annuity - _t0_future_value_annuity) / Float64(N)
    print("MOJO_TIMING currency::future_value_annuity", _ns_future_value_annuity, _acc_future_value_annuity)
    var _result_future_value_annuity = future_value_annuity(0.5, 0.5, 5)
    var _summary_future_value_annuity = _summary_float64(_result_future_value_annuity)
    print("MOJO_RESULT currency::future_value_annuity", _summary_future_value_annuity)
    var _acc_effective_annual_rate: Float64 = 0.0
    var _t0_effective_annual_rate = perf_counter_ns()
    for _ in range(N):
        _acc_effective_annual_rate += effective_annual_rate(0.5, 5)
    var _t1_effective_annual_rate = perf_counter_ns()
    var _ns_effective_annual_rate = Float64(_t1_effective_annual_rate - _t0_effective_annual_rate) / Float64(N)
    print("MOJO_TIMING currency::effective_annual_rate", _ns_effective_annual_rate, _acc_effective_annual_rate)
    var _result_effective_annual_rate = effective_annual_rate(0.5, 5)
    var _summary_effective_annual_rate = _summary_float64(_result_effective_annual_rate)
    print("MOJO_RESULT currency::effective_annual_rate", _summary_effective_annual_rate)
    var _acc_discount_factor: Float64 = 0.0
    var _t0_discount_factor = perf_counter_ns()
    for _ in range(N):
        _acc_discount_factor += discount_factor(0.5, 5)
    var _t1_discount_factor = perf_counter_ns()
    var _ns_discount_factor = Float64(_t1_discount_factor - _t0_discount_factor) / Float64(N)
    print("MOJO_TIMING currency::discount_factor", _ns_discount_factor, _acc_discount_factor)
    var _result_discount_factor = discount_factor(0.5, 5)
    var _summary_discount_factor = _summary_float64(_result_discount_factor)
    print("MOJO_RESULT currency::discount_factor", _summary_discount_factor)
    var _acc_rule_of_72: Float64 = 0.0
    var _t0_rule_of_72 = perf_counter_ns()
    for _ in range(N):
        _acc_rule_of_72 += rule_of_72(0.5)
    var _t1_rule_of_72 = perf_counter_ns()
    var _ns_rule_of_72 = Float64(_t1_rule_of_72 - _t0_rule_of_72) / Float64(N)
    print("MOJO_TIMING currency::rule_of_72", _ns_rule_of_72, _acc_rule_of_72)
    var _result_rule_of_72 = rule_of_72(0.5)
    var _summary_rule_of_72 = _summary_float64(_result_rule_of_72)
    print("MOJO_RESULT currency::rule_of_72", _summary_rule_of_72)
    var _acc_loan_balance_after: Float64 = 0.0
    var _t0_loan_balance_after = perf_counter_ns()
    for _ in range(N):
        _acc_loan_balance_after += loan_balance_after(0.5, 0.5, 5, 5)
    var _t1_loan_balance_after = perf_counter_ns()
    var _ns_loan_balance_after = Float64(_t1_loan_balance_after - _t0_loan_balance_after) / Float64(N)
    print("MOJO_TIMING currency::loan_balance_after", _ns_loan_balance_after, _acc_loan_balance_after)
    var _result_loan_balance_after = loan_balance_after(0.5, 0.5, 5, 5)
    var _summary_loan_balance_after = _summary_float64(_result_loan_balance_after)
    print("MOJO_RESULT currency::loan_balance_after", _summary_loan_balance_after)
