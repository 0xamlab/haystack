"""bench_accounting.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from accounting import straight_line_depreciation, declining_balance, sum_of_years_digits, future_value, present_value_single, gross_profit_margin, net_profit_margin, current_ratio, debt_to_equity, return_on_equity, break_even_units, compound_annual_growth
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

    var _acc_straight_line_depreciation: Float64 = 0.0
    var _t0_straight_line_depreciation = perf_counter_ns()
    for _ in range(N):
        _acc_straight_line_depreciation += straight_line_depreciation(0.5, 0.5, 5)
    var _t1_straight_line_depreciation = perf_counter_ns()
    var _ns_straight_line_depreciation = Float64(_t1_straight_line_depreciation - _t0_straight_line_depreciation) / Float64(N)
    print("MOJO_TIMING accounting::straight_line_depreciation", _ns_straight_line_depreciation, _acc_straight_line_depreciation)
    var _acc_declining_balance: Float64 = 0.0
    var _t0_declining_balance = perf_counter_ns()
    for _ in range(N):
        _acc_declining_balance += declining_balance(0.5, 0.5, 5)
    var _t1_declining_balance = perf_counter_ns()
    var _ns_declining_balance = Float64(_t1_declining_balance - _t0_declining_balance) / Float64(N)
    print("MOJO_TIMING accounting::declining_balance", _ns_declining_balance, _acc_declining_balance)
    var _acc_sum_of_years_digits: Float64 = 0.0
    var _t0_sum_of_years_digits = perf_counter_ns()
    for _ in range(N):
        _acc_sum_of_years_digits += sum_of_years_digits(0.5, 0.5, 5, 5)
    var _t1_sum_of_years_digits = perf_counter_ns()
    var _ns_sum_of_years_digits = Float64(_t1_sum_of_years_digits - _t0_sum_of_years_digits) / Float64(N)
    print("MOJO_TIMING accounting::sum_of_years_digits", _ns_sum_of_years_digits, _acc_sum_of_years_digits)
    var _acc_future_value: Float64 = 0.0
    var _t0_future_value = perf_counter_ns()
    for _ in range(N):
        _acc_future_value += future_value(0.5, 0.5, 5)
    var _t1_future_value = perf_counter_ns()
    var _ns_future_value = Float64(_t1_future_value - _t0_future_value) / Float64(N)
    print("MOJO_TIMING accounting::future_value", _ns_future_value, _acc_future_value)
    var _acc_present_value_single: Float64 = 0.0
    var _t0_present_value_single = perf_counter_ns()
    for _ in range(N):
        _acc_present_value_single += present_value_single(0.5, 0.5, 5)
    var _t1_present_value_single = perf_counter_ns()
    var _ns_present_value_single = Float64(_t1_present_value_single - _t0_present_value_single) / Float64(N)
    print("MOJO_TIMING accounting::present_value_single", _ns_present_value_single, _acc_present_value_single)
    var _acc_gross_profit_margin: Float64 = 0.0
    var _t0_gross_profit_margin = perf_counter_ns()
    for _ in range(N):
        _acc_gross_profit_margin += gross_profit_margin(0.5, 0.5)
    var _t1_gross_profit_margin = perf_counter_ns()
    var _ns_gross_profit_margin = Float64(_t1_gross_profit_margin - _t0_gross_profit_margin) / Float64(N)
    print("MOJO_TIMING accounting::gross_profit_margin", _ns_gross_profit_margin, _acc_gross_profit_margin)
    var _acc_net_profit_margin: Float64 = 0.0
    var _t0_net_profit_margin = perf_counter_ns()
    for _ in range(N):
        _acc_net_profit_margin += net_profit_margin(0.5, 0.5)
    var _t1_net_profit_margin = perf_counter_ns()
    var _ns_net_profit_margin = Float64(_t1_net_profit_margin - _t0_net_profit_margin) / Float64(N)
    print("MOJO_TIMING accounting::net_profit_margin", _ns_net_profit_margin, _acc_net_profit_margin)
    var _acc_current_ratio: Float64 = 0.0
    var _t0_current_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_current_ratio += current_ratio(0.5, 0.5)
    var _t1_current_ratio = perf_counter_ns()
    var _ns_current_ratio = Float64(_t1_current_ratio - _t0_current_ratio) / Float64(N)
    print("MOJO_TIMING accounting::current_ratio", _ns_current_ratio, _acc_current_ratio)
    var _acc_debt_to_equity: Float64 = 0.0
    var _t0_debt_to_equity = perf_counter_ns()
    for _ in range(N):
        _acc_debt_to_equity += debt_to_equity(0.5, 0.5)
    var _t1_debt_to_equity = perf_counter_ns()
    var _ns_debt_to_equity = Float64(_t1_debt_to_equity - _t0_debt_to_equity) / Float64(N)
    print("MOJO_TIMING accounting::debt_to_equity", _ns_debt_to_equity, _acc_debt_to_equity)
    var _acc_return_on_equity: Float64 = 0.0
    var _t0_return_on_equity = perf_counter_ns()
    for _ in range(N):
        _acc_return_on_equity += return_on_equity(0.5, 0.5)
    var _t1_return_on_equity = perf_counter_ns()
    var _ns_return_on_equity = Float64(_t1_return_on_equity - _t0_return_on_equity) / Float64(N)
    print("MOJO_TIMING accounting::return_on_equity", _ns_return_on_equity, _acc_return_on_equity)
    var _acc_break_even_units: Float64 = 0.0
    var _t0_break_even_units = perf_counter_ns()
    for _ in range(N):
        _acc_break_even_units += break_even_units(0.5, 0.5, 0.5)
    var _t1_break_even_units = perf_counter_ns()
    var _ns_break_even_units = Float64(_t1_break_even_units - _t0_break_even_units) / Float64(N)
    print("MOJO_TIMING accounting::break_even_units", _ns_break_even_units, _acc_break_even_units)
    var _acc_compound_annual_growth: Float64 = 0.0
    var _t0_compound_annual_growth = perf_counter_ns()
    for _ in range(N):
        _acc_compound_annual_growth += compound_annual_growth(0.5, 0.5, 5)
    var _t1_compound_annual_growth = perf_counter_ns()
    var _ns_compound_annual_growth = Float64(_t1_compound_annual_growth - _t0_compound_annual_growth) / Float64(N)
    print("MOJO_TIMING accounting::compound_annual_growth", _ns_compound_annual_growth, _acc_compound_annual_growth)
