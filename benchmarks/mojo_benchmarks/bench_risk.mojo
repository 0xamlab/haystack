"""bench_risk.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from risk import value_at_risk, conditional_var, max_drawdown, drawdown_series, sortino_ratio, sharpe_ratio, beta, alpha, information_ratio, calmar_ratio, downside_deviation
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

    var _acc_value_at_risk: Float64 = 0.0
    var _t0_value_at_risk = perf_counter_ns()
    for _ in range(N):
        _acc_value_at_risk += value_at_risk(_lf5, 0.5)
    var _t1_value_at_risk = perf_counter_ns()
    var _ns_value_at_risk = Float64(_t1_value_at_risk - _t0_value_at_risk) / Float64(N)
    print("MOJO_TIMING risk::value_at_risk", _ns_value_at_risk, _acc_value_at_risk)
    var _acc_conditional_var: Float64 = 0.0
    var _t0_conditional_var = perf_counter_ns()
    for _ in range(N):
        _acc_conditional_var += conditional_var(_lf5, 0.5)
    var _t1_conditional_var = perf_counter_ns()
    var _ns_conditional_var = Float64(_t1_conditional_var - _t0_conditional_var) / Float64(N)
    print("MOJO_TIMING risk::conditional_var", _ns_conditional_var, _acc_conditional_var)
    var _acc_max_drawdown: Float64 = 0.0
    var _t0_max_drawdown = perf_counter_ns()
    for _ in range(N):
        _acc_max_drawdown += max_drawdown(_lf5)
    var _t1_max_drawdown = perf_counter_ns()
    var _ns_max_drawdown = Float64(_t1_max_drawdown - _t0_max_drawdown) / Float64(N)
    print("MOJO_TIMING risk::max_drawdown", _ns_max_drawdown, _acc_max_drawdown)
    var _acc_drawdown_series: Float64 = 0.0
    var _t0_drawdown_series = perf_counter_ns()
    for _ in range(N):
        var _r_drawdown_series = drawdown_series(_lf5)
        _acc_drawdown_series += Float64(len(_r_drawdown_series))
    var _t1_drawdown_series = perf_counter_ns()
    var _ns_drawdown_series = Float64(_t1_drawdown_series - _t0_drawdown_series) / Float64(N)
    print("MOJO_TIMING risk::drawdown_series", _ns_drawdown_series, _acc_drawdown_series)
    var _acc_sortino_ratio: Float64 = 0.0
    var _t0_sortino_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_sortino_ratio += sortino_ratio(_lf5, 0.5)
    var _t1_sortino_ratio = perf_counter_ns()
    var _ns_sortino_ratio = Float64(_t1_sortino_ratio - _t0_sortino_ratio) / Float64(N)
    print("MOJO_TIMING risk::sortino_ratio", _ns_sortino_ratio, _acc_sortino_ratio)
    var _acc_sharpe_ratio: Float64 = 0.0
    var _t0_sharpe_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_sharpe_ratio += sharpe_ratio(_lf5, 0.5)
    var _t1_sharpe_ratio = perf_counter_ns()
    var _ns_sharpe_ratio = Float64(_t1_sharpe_ratio - _t0_sharpe_ratio) / Float64(N)
    print("MOJO_TIMING risk::sharpe_ratio", _ns_sharpe_ratio, _acc_sharpe_ratio)
    var _acc_beta: Float64 = 0.0
    var _t0_beta = perf_counter_ns()
    for _ in range(N):
        _acc_beta += beta(_lf5, _lf5)
    var _t1_beta = perf_counter_ns()
    var _ns_beta = Float64(_t1_beta - _t0_beta) / Float64(N)
    print("MOJO_TIMING risk::beta", _ns_beta, _acc_beta)
    var _acc_alpha: Float64 = 0.0
    var _t0_alpha = perf_counter_ns()
    for _ in range(N):
        _acc_alpha += alpha(_lf5, _lf5, 0.5)
    var _t1_alpha = perf_counter_ns()
    var _ns_alpha = Float64(_t1_alpha - _t0_alpha) / Float64(N)
    print("MOJO_TIMING risk::alpha", _ns_alpha, _acc_alpha)
    var _acc_information_ratio: Float64 = 0.0
    var _t0_information_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_information_ratio += information_ratio(_lf5, _lf5)
    var _t1_information_ratio = perf_counter_ns()
    var _ns_information_ratio = Float64(_t1_information_ratio - _t0_information_ratio) / Float64(N)
    print("MOJO_TIMING risk::information_ratio", _ns_information_ratio, _acc_information_ratio)
    var _acc_calmar_ratio: Float64 = 0.0
    var _t0_calmar_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_calmar_ratio += calmar_ratio(_lf5, _lf5)
    var _t1_calmar_ratio = perf_counter_ns()
    var _ns_calmar_ratio = Float64(_t1_calmar_ratio - _t0_calmar_ratio) / Float64(N)
    print("MOJO_TIMING risk::calmar_ratio", _ns_calmar_ratio, _acc_calmar_ratio)
    var _acc_downside_deviation: Float64 = 0.0
    var _t0_downside_deviation = perf_counter_ns()
    for _ in range(N):
        _acc_downside_deviation += downside_deviation(_lf5, 0.5)
    var _t1_downside_deviation = perf_counter_ns()
    var _ns_downside_deviation = Float64(_t1_downside_deviation - _t0_downside_deviation) / Float64(N)
    print("MOJO_TIMING risk::downside_deviation", _ns_downside_deviation, _acc_downside_deviation)
