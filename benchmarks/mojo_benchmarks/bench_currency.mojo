"""bench_currency.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from currency import round_currency, compound_interest, continuous_compound, amortization_payment, amortization_schedule, present_value, present_value_annuity, future_value_annuity, effective_annual_rate, discount_factor, rule_of_72, loan_balance_after
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

    var _acc_round_currency: Float64 = 0.0
    var _t0_round_currency = perf_counter_ns()
    for _ in range(N):
        _acc_round_currency += round_currency(0.5, 5)
    var _t1_round_currency = perf_counter_ns()
    var _ns_round_currency = Float64(_t1_round_currency - _t0_round_currency) / Float64(N)
    print("MOJO_TIMING currency::round_currency", _ns_round_currency, _acc_round_currency)
    var _acc_compound_interest: Float64 = 0.0
    var _t0_compound_interest = perf_counter_ns()
    for _ in range(N):
        _acc_compound_interest += compound_interest(0.5, 0.5, 5)
    var _t1_compound_interest = perf_counter_ns()
    var _ns_compound_interest = Float64(_t1_compound_interest - _t0_compound_interest) / Float64(N)
    print("MOJO_TIMING currency::compound_interest", _ns_compound_interest, _acc_compound_interest)
    var _acc_continuous_compound: Float64 = 0.0
    var _t0_continuous_compound = perf_counter_ns()
    for _ in range(N):
        _acc_continuous_compound += continuous_compound(0.5, 0.5, 0.5)
    var _t1_continuous_compound = perf_counter_ns()
    var _ns_continuous_compound = Float64(_t1_continuous_compound - _t0_continuous_compound) / Float64(N)
    print("MOJO_TIMING currency::continuous_compound", _ns_continuous_compound, _acc_continuous_compound)
    var _acc_amortization_payment: Float64 = 0.0
    var _t0_amortization_payment = perf_counter_ns()
    for _ in range(N):
        _acc_amortization_payment += amortization_payment(0.5, 0.5, 5)
    var _t1_amortization_payment = perf_counter_ns()
    var _ns_amortization_payment = Float64(_t1_amortization_payment - _t0_amortization_payment) / Float64(N)
    print("MOJO_TIMING currency::amortization_payment", _ns_amortization_payment, _acc_amortization_payment)
    var _acc_amortization_schedule: Float64 = 0.0
    var _t0_amortization_schedule = perf_counter_ns()
    for _ in range(N):
        var _r_amortization_schedule = amortization_schedule(0.5, 0.5, 5)
        _acc_amortization_schedule += Float64(len(_r_amortization_schedule))
    var _t1_amortization_schedule = perf_counter_ns()
    var _ns_amortization_schedule = Float64(_t1_amortization_schedule - _t0_amortization_schedule) / Float64(N)
    print("MOJO_TIMING currency::amortization_schedule", _ns_amortization_schedule, _acc_amortization_schedule)
    var _acc_present_value: Float64 = 0.0
    var _t0_present_value = perf_counter_ns()
    for _ in range(N):
        _acc_present_value += present_value(0.5, 0.5, 5)
    var _t1_present_value = perf_counter_ns()
    var _ns_present_value = Float64(_t1_present_value - _t0_present_value) / Float64(N)
    print("MOJO_TIMING currency::present_value", _ns_present_value, _acc_present_value)
    var _acc_present_value_annuity: Float64 = 0.0
    var _t0_present_value_annuity = perf_counter_ns()
    for _ in range(N):
        _acc_present_value_annuity += present_value_annuity(0.5, 0.5, 5)
    var _t1_present_value_annuity = perf_counter_ns()
    var _ns_present_value_annuity = Float64(_t1_present_value_annuity - _t0_present_value_annuity) / Float64(N)
    print("MOJO_TIMING currency::present_value_annuity", _ns_present_value_annuity, _acc_present_value_annuity)
    var _acc_future_value_annuity: Float64 = 0.0
    var _t0_future_value_annuity = perf_counter_ns()
    for _ in range(N):
        _acc_future_value_annuity += future_value_annuity(0.5, 0.5, 5)
    var _t1_future_value_annuity = perf_counter_ns()
    var _ns_future_value_annuity = Float64(_t1_future_value_annuity - _t0_future_value_annuity) / Float64(N)
    print("MOJO_TIMING currency::future_value_annuity", _ns_future_value_annuity, _acc_future_value_annuity)
    var _acc_effective_annual_rate: Float64 = 0.0
    var _t0_effective_annual_rate = perf_counter_ns()
    for _ in range(N):
        _acc_effective_annual_rate += effective_annual_rate(0.5, 5)
    var _t1_effective_annual_rate = perf_counter_ns()
    var _ns_effective_annual_rate = Float64(_t1_effective_annual_rate - _t0_effective_annual_rate) / Float64(N)
    print("MOJO_TIMING currency::effective_annual_rate", _ns_effective_annual_rate, _acc_effective_annual_rate)
    var _acc_discount_factor: Float64 = 0.0
    var _t0_discount_factor = perf_counter_ns()
    for _ in range(N):
        _acc_discount_factor += discount_factor(0.5, 5)
    var _t1_discount_factor = perf_counter_ns()
    var _ns_discount_factor = Float64(_t1_discount_factor - _t0_discount_factor) / Float64(N)
    print("MOJO_TIMING currency::discount_factor", _ns_discount_factor, _acc_discount_factor)
    var _acc_rule_of_72: Float64 = 0.0
    var _t0_rule_of_72 = perf_counter_ns()
    for _ in range(N):
        _acc_rule_of_72 += rule_of_72(0.5)
    var _t1_rule_of_72 = perf_counter_ns()
    var _ns_rule_of_72 = Float64(_t1_rule_of_72 - _t0_rule_of_72) / Float64(N)
    print("MOJO_TIMING currency::rule_of_72", _ns_rule_of_72, _acc_rule_of_72)
    var _acc_loan_balance_after: Float64 = 0.0
    var _t0_loan_balance_after = perf_counter_ns()
    for _ in range(N):
        _acc_loan_balance_after += loan_balance_after(0.5, 0.5, 5, 5)
    var _t1_loan_balance_after = perf_counter_ns()
    var _ns_loan_balance_after = Float64(_t1_loan_balance_after - _t0_loan_balance_after) / Float64(N)
    print("MOJO_TIMING currency::loan_balance_after", _ns_loan_balance_after, _acc_loan_balance_after)
