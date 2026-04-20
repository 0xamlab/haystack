"""bench_real_estate.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from real_estate import cap_rate, gross_rent_multiplier, cash_on_cash_return, debt_service_coverage, loan_to_value, net_operating_income, mortgage_payment, price_per_sqft, break_even_ratio, internal_rate_of_return_approx, equity_buildup, appreciation_value
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

    var _acc_cap_rate: Float64 = 0.0
    var _t0_cap_rate = perf_counter_ns()
    for _ in range(N):
        _acc_cap_rate += cap_rate(0.5, 0.5)
    var _t1_cap_rate = perf_counter_ns()
    var _ns_cap_rate = Float64(_t1_cap_rate - _t0_cap_rate) / Float64(N)
    print("MOJO_TIMING real_estate::cap_rate", _ns_cap_rate, _acc_cap_rate)
    var _acc_gross_rent_multiplier: Float64 = 0.0
    var _t0_gross_rent_multiplier = perf_counter_ns()
    for _ in range(N):
        _acc_gross_rent_multiplier += gross_rent_multiplier(0.5, 0.5)
    var _t1_gross_rent_multiplier = perf_counter_ns()
    var _ns_gross_rent_multiplier = Float64(_t1_gross_rent_multiplier - _t0_gross_rent_multiplier) / Float64(N)
    print("MOJO_TIMING real_estate::gross_rent_multiplier", _ns_gross_rent_multiplier, _acc_gross_rent_multiplier)
    var _acc_cash_on_cash_return: Float64 = 0.0
    var _t0_cash_on_cash_return = perf_counter_ns()
    for _ in range(N):
        _acc_cash_on_cash_return += cash_on_cash_return(0.5, 0.5)
    var _t1_cash_on_cash_return = perf_counter_ns()
    var _ns_cash_on_cash_return = Float64(_t1_cash_on_cash_return - _t0_cash_on_cash_return) / Float64(N)
    print("MOJO_TIMING real_estate::cash_on_cash_return", _ns_cash_on_cash_return, _acc_cash_on_cash_return)
    var _acc_debt_service_coverage: Float64 = 0.0
    var _t0_debt_service_coverage = perf_counter_ns()
    for _ in range(N):
        _acc_debt_service_coverage += debt_service_coverage(0.5, 0.5)
    var _t1_debt_service_coverage = perf_counter_ns()
    var _ns_debt_service_coverage = Float64(_t1_debt_service_coverage - _t0_debt_service_coverage) / Float64(N)
    print("MOJO_TIMING real_estate::debt_service_coverage", _ns_debt_service_coverage, _acc_debt_service_coverage)
    var _acc_loan_to_value: Float64 = 0.0
    var _t0_loan_to_value = perf_counter_ns()
    for _ in range(N):
        _acc_loan_to_value += loan_to_value(0.5, 0.5)
    var _t1_loan_to_value = perf_counter_ns()
    var _ns_loan_to_value = Float64(_t1_loan_to_value - _t0_loan_to_value) / Float64(N)
    print("MOJO_TIMING real_estate::loan_to_value", _ns_loan_to_value, _acc_loan_to_value)
    var _acc_net_operating_income: Float64 = 0.0
    var _t0_net_operating_income = perf_counter_ns()
    for _ in range(N):
        _acc_net_operating_income += net_operating_income(0.5, 0.5, 0.5)
    var _t1_net_operating_income = perf_counter_ns()
    var _ns_net_operating_income = Float64(_t1_net_operating_income - _t0_net_operating_income) / Float64(N)
    print("MOJO_TIMING real_estate::net_operating_income", _ns_net_operating_income, _acc_net_operating_income)
    var _acc_mortgage_payment: Float64 = 0.0
    var _t0_mortgage_payment = perf_counter_ns()
    for _ in range(N):
        _acc_mortgage_payment += mortgage_payment(0.5, 0.5, 5)
    var _t1_mortgage_payment = perf_counter_ns()
    var _ns_mortgage_payment = Float64(_t1_mortgage_payment - _t0_mortgage_payment) / Float64(N)
    print("MOJO_TIMING real_estate::mortgage_payment", _ns_mortgage_payment, _acc_mortgage_payment)
    var _acc_price_per_sqft: Float64 = 0.0
    var _t0_price_per_sqft = perf_counter_ns()
    for _ in range(N):
        _acc_price_per_sqft += price_per_sqft(0.5, 0.5)
    var _t1_price_per_sqft = perf_counter_ns()
    var _ns_price_per_sqft = Float64(_t1_price_per_sqft - _t0_price_per_sqft) / Float64(N)
    print("MOJO_TIMING real_estate::price_per_sqft", _ns_price_per_sqft, _acc_price_per_sqft)
    var _acc_break_even_ratio: Float64 = 0.0
    var _t0_break_even_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_break_even_ratio += break_even_ratio(0.5, 0.5, 0.5)
    var _t1_break_even_ratio = perf_counter_ns()
    var _ns_break_even_ratio = Float64(_t1_break_even_ratio - _t0_break_even_ratio) / Float64(N)
    print("MOJO_TIMING real_estate::break_even_ratio", _ns_break_even_ratio, _acc_break_even_ratio)
    var _acc_internal_rate_of_return_approx: Float64 = 0.0
    var _t0_internal_rate_of_return_approx = perf_counter_ns()
    for _ in range(N):
        _acc_internal_rate_of_return_approx += internal_rate_of_return_approx(0.5, 0.5, 5)
    var _t1_internal_rate_of_return_approx = perf_counter_ns()
    var _ns_internal_rate_of_return_approx = Float64(_t1_internal_rate_of_return_approx - _t0_internal_rate_of_return_approx) / Float64(N)
    print("MOJO_TIMING real_estate::internal_rate_of_return_approx", _ns_internal_rate_of_return_approx, _acc_internal_rate_of_return_approx)
    var _acc_equity_buildup: Float64 = 0.0
    var _t0_equity_buildup = perf_counter_ns()
    for _ in range(N):
        _acc_equity_buildup += equity_buildup(0.5, 0.5)
    var _t1_equity_buildup = perf_counter_ns()
    var _ns_equity_buildup = Float64(_t1_equity_buildup - _t0_equity_buildup) / Float64(N)
    print("MOJO_TIMING real_estate::equity_buildup", _ns_equity_buildup, _acc_equity_buildup)
    var _acc_appreciation_value: Float64 = 0.0
    var _t0_appreciation_value = perf_counter_ns()
    for _ in range(N):
        _acc_appreciation_value += appreciation_value(0.5, 0.5, 5)
    var _t1_appreciation_value = perf_counter_ns()
    var _ns_appreciation_value = Float64(_t1_appreciation_value - _t0_appreciation_value) / Float64(N)
    print("MOJO_TIMING real_estate::appreciation_value", _ns_appreciation_value, _acc_appreciation_value)
