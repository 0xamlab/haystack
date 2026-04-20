"""bench_economic_indicators.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from economic_indicators import gdp_growth, inflation_rate, unemployment_rate, real_gdp, gini_coefficient, phillips_curve, okuns_law, velocity_of_money, fisher_equation, trade_balance, gdp_per_capita, purchasing_power_parity
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

    var _acc_gdp_growth: Float64 = 0.0
    var _t0_gdp_growth = perf_counter_ns()
    for _ in range(N):
        _acc_gdp_growth += gdp_growth(0.5, 0.5)
    var _t1_gdp_growth = perf_counter_ns()
    var _ns_gdp_growth = Float64(_t1_gdp_growth - _t0_gdp_growth) / Float64(N)
    print("MOJO_TIMING economic_indicators::gdp_growth", _ns_gdp_growth, _acc_gdp_growth)
    var _acc_inflation_rate: Float64 = 0.0
    var _t0_inflation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_inflation_rate += inflation_rate(0.5, 0.5)
    var _t1_inflation_rate = perf_counter_ns()
    var _ns_inflation_rate = Float64(_t1_inflation_rate - _t0_inflation_rate) / Float64(N)
    print("MOJO_TIMING economic_indicators::inflation_rate", _ns_inflation_rate, _acc_inflation_rate)
    var _acc_unemployment_rate: Float64 = 0.0
    var _t0_unemployment_rate = perf_counter_ns()
    for _ in range(N):
        _acc_unemployment_rate += unemployment_rate(0.5, 0.5)
    var _t1_unemployment_rate = perf_counter_ns()
    var _ns_unemployment_rate = Float64(_t1_unemployment_rate - _t0_unemployment_rate) / Float64(N)
    print("MOJO_TIMING economic_indicators::unemployment_rate", _ns_unemployment_rate, _acc_unemployment_rate)
    var _acc_real_gdp: Float64 = 0.0
    var _t0_real_gdp = perf_counter_ns()
    for _ in range(N):
        _acc_real_gdp += real_gdp(0.5, 0.5)
    var _t1_real_gdp = perf_counter_ns()
    var _ns_real_gdp = Float64(_t1_real_gdp - _t0_real_gdp) / Float64(N)
    print("MOJO_TIMING economic_indicators::real_gdp", _ns_real_gdp, _acc_real_gdp)
    var _acc_gini_coefficient: Float64 = 0.0
    var _t0_gini_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_gini_coefficient += gini_coefficient(_lf5)
    var _t1_gini_coefficient = perf_counter_ns()
    var _ns_gini_coefficient = Float64(_t1_gini_coefficient - _t0_gini_coefficient) / Float64(N)
    print("MOJO_TIMING economic_indicators::gini_coefficient", _ns_gini_coefficient, _acc_gini_coefficient)
    var _acc_phillips_curve: Float64 = 0.0
    var _t0_phillips_curve = perf_counter_ns()
    for _ in range(N):
        _acc_phillips_curve += phillips_curve(0.5, 0.5, 0.5)
    var _t1_phillips_curve = perf_counter_ns()
    var _ns_phillips_curve = Float64(_t1_phillips_curve - _t0_phillips_curve) / Float64(N)
    print("MOJO_TIMING economic_indicators::phillips_curve", _ns_phillips_curve, _acc_phillips_curve)
    var _acc_okuns_law: Float64 = 0.0
    var _t0_okuns_law = perf_counter_ns()
    for _ in range(N):
        _acc_okuns_law += okuns_law(0.5, 0.5)
    var _t1_okuns_law = perf_counter_ns()
    var _ns_okuns_law = Float64(_t1_okuns_law - _t0_okuns_law) / Float64(N)
    print("MOJO_TIMING economic_indicators::okuns_law", _ns_okuns_law, _acc_okuns_law)
    var _acc_velocity_of_money: Float64 = 0.0
    var _t0_velocity_of_money = perf_counter_ns()
    for _ in range(N):
        _acc_velocity_of_money += velocity_of_money(0.5, 0.5)
    var _t1_velocity_of_money = perf_counter_ns()
    var _ns_velocity_of_money = Float64(_t1_velocity_of_money - _t0_velocity_of_money) / Float64(N)
    print("MOJO_TIMING economic_indicators::velocity_of_money", _ns_velocity_of_money, _acc_velocity_of_money)
    var _acc_fisher_equation: Float64 = 0.0
    var _t0_fisher_equation = perf_counter_ns()
    for _ in range(N):
        _acc_fisher_equation += fisher_equation(0.5, 0.5)
    var _t1_fisher_equation = perf_counter_ns()
    var _ns_fisher_equation = Float64(_t1_fisher_equation - _t0_fisher_equation) / Float64(N)
    print("MOJO_TIMING economic_indicators::fisher_equation", _ns_fisher_equation, _acc_fisher_equation)
    var _acc_trade_balance: Float64 = 0.0
    var _t0_trade_balance = perf_counter_ns()
    for _ in range(N):
        _acc_trade_balance += trade_balance(0.5, 0.5)
    var _t1_trade_balance = perf_counter_ns()
    var _ns_trade_balance = Float64(_t1_trade_balance - _t0_trade_balance) / Float64(N)
    print("MOJO_TIMING economic_indicators::trade_balance", _ns_trade_balance, _acc_trade_balance)
    var _acc_gdp_per_capita: Float64 = 0.0
    var _t0_gdp_per_capita = perf_counter_ns()
    for _ in range(N):
        _acc_gdp_per_capita += gdp_per_capita(0.5, 0.5)
    var _t1_gdp_per_capita = perf_counter_ns()
    var _ns_gdp_per_capita = Float64(_t1_gdp_per_capita - _t0_gdp_per_capita) / Float64(N)
    print("MOJO_TIMING economic_indicators::gdp_per_capita", _ns_gdp_per_capita, _acc_gdp_per_capita)
    var _acc_purchasing_power_parity: Float64 = 0.0
    var _t0_purchasing_power_parity = perf_counter_ns()
    for _ in range(N):
        _acc_purchasing_power_parity += purchasing_power_parity(0.5, 0.5)
    var _t1_purchasing_power_parity = perf_counter_ns()
    var _ns_purchasing_power_parity = Float64(_t1_purchasing_power_parity - _t0_purchasing_power_parity) / Float64(N)
    print("MOJO_TIMING economic_indicators::purchasing_power_parity", _ns_purchasing_power_parity, _acc_purchasing_power_parity)
