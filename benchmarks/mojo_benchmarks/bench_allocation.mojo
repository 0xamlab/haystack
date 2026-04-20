"""bench_allocation.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from allocation import equal_weight, inverse_variance, risk_parity_simple, max_sharpe_2asset, min_variance_2asset, portfolio_return, portfolio_variance_2asset, kelly_criterion, efficient_frontier_2asset, rebalance_threshold
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

    var _acc_equal_weight: Float64 = 0.0
    var _t0_equal_weight = perf_counter_ns()
    for _ in range(N):
        var _r_equal_weight = equal_weight(5)
        _acc_equal_weight += Float64(len(_r_equal_weight))
    var _t1_equal_weight = perf_counter_ns()
    var _ns_equal_weight = Float64(_t1_equal_weight - _t0_equal_weight) / Float64(N)
    print("MOJO_TIMING allocation::equal_weight", _ns_equal_weight, _acc_equal_weight)
    var _acc_inverse_variance: Float64 = 0.0
    var _t0_inverse_variance = perf_counter_ns()
    for _ in range(N):
        var _r_inverse_variance = inverse_variance(_lf5)
        _acc_inverse_variance += Float64(len(_r_inverse_variance))
    var _t1_inverse_variance = perf_counter_ns()
    var _ns_inverse_variance = Float64(_t1_inverse_variance - _t0_inverse_variance) / Float64(N)
    print("MOJO_TIMING allocation::inverse_variance", _ns_inverse_variance, _acc_inverse_variance)
    var _acc_risk_parity_simple: Float64 = 0.0
    var _t0_risk_parity_simple = perf_counter_ns()
    for _ in range(N):
        var _r_risk_parity_simple = risk_parity_simple(_lf5)
        _acc_risk_parity_simple += Float64(len(_r_risk_parity_simple))
    var _t1_risk_parity_simple = perf_counter_ns()
    var _ns_risk_parity_simple = Float64(_t1_risk_parity_simple - _t0_risk_parity_simple) / Float64(N)
    print("MOJO_TIMING allocation::risk_parity_simple", _ns_risk_parity_simple, _acc_risk_parity_simple)
    var _acc_max_sharpe_2asset: Float64 = 0.0
    var _t0_max_sharpe_2asset = perf_counter_ns()
    for _ in range(N):
        var _r_max_sharpe_2asset = max_sharpe_2asset(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
        _acc_max_sharpe_2asset += Float64(len(_r_max_sharpe_2asset))
    var _t1_max_sharpe_2asset = perf_counter_ns()
    var _ns_max_sharpe_2asset = Float64(_t1_max_sharpe_2asset - _t0_max_sharpe_2asset) / Float64(N)
    print("MOJO_TIMING allocation::max_sharpe_2asset", _ns_max_sharpe_2asset, _acc_max_sharpe_2asset)
    var _acc_min_variance_2asset: Float64 = 0.0
    var _t0_min_variance_2asset = perf_counter_ns()
    for _ in range(N):
        var _r_min_variance_2asset = min_variance_2asset(0.5, 0.5, 0.5)
        _acc_min_variance_2asset += Float64(len(_r_min_variance_2asset))
    var _t1_min_variance_2asset = perf_counter_ns()
    var _ns_min_variance_2asset = Float64(_t1_min_variance_2asset - _t0_min_variance_2asset) / Float64(N)
    print("MOJO_TIMING allocation::min_variance_2asset", _ns_min_variance_2asset, _acc_min_variance_2asset)
    var _acc_portfolio_return: Float64 = 0.0
    var _t0_portfolio_return = perf_counter_ns()
    for _ in range(N):
        _acc_portfolio_return += portfolio_return(_lf5, _lf5)
    var _t1_portfolio_return = perf_counter_ns()
    var _ns_portfolio_return = Float64(_t1_portfolio_return - _t0_portfolio_return) / Float64(N)
    print("MOJO_TIMING allocation::portfolio_return", _ns_portfolio_return, _acc_portfolio_return)
    var _acc_portfolio_variance_2asset: Float64 = 0.0
    var _t0_portfolio_variance_2asset = perf_counter_ns()
    for _ in range(N):
        _acc_portfolio_variance_2asset += portfolio_variance_2asset(0.5, 0.5, 0.5, 0.5)
    var _t1_portfolio_variance_2asset = perf_counter_ns()
    var _ns_portfolio_variance_2asset = Float64(_t1_portfolio_variance_2asset - _t0_portfolio_variance_2asset) / Float64(N)
    print("MOJO_TIMING allocation::portfolio_variance_2asset", _ns_portfolio_variance_2asset, _acc_portfolio_variance_2asset)
    var _acc_kelly_criterion: Float64 = 0.0
    var _t0_kelly_criterion = perf_counter_ns()
    for _ in range(N):
        _acc_kelly_criterion += kelly_criterion(0.5, 0.5)
    var _t1_kelly_criterion = perf_counter_ns()
    var _ns_kelly_criterion = Float64(_t1_kelly_criterion - _t0_kelly_criterion) / Float64(N)
    print("MOJO_TIMING allocation::kelly_criterion", _ns_kelly_criterion, _acc_kelly_criterion)
    var _acc_efficient_frontier_2asset: Float64 = 0.0
    var _t0_efficient_frontier_2asset = perf_counter_ns()
    for _ in range(N):
        var _r_efficient_frontier_2asset = efficient_frontier_2asset(0.5, 0.5, 0.5, 0.5, 0.5, 5)
        _acc_efficient_frontier_2asset += Float64(len(_r_efficient_frontier_2asset))
    var _t1_efficient_frontier_2asset = perf_counter_ns()
    var _ns_efficient_frontier_2asset = Float64(_t1_efficient_frontier_2asset - _t0_efficient_frontier_2asset) / Float64(N)
    print("MOJO_TIMING allocation::efficient_frontier_2asset", _ns_efficient_frontier_2asset, _acc_efficient_frontier_2asset)
    var _acc_rebalance_threshold: Float64 = 0.0
    var _t0_rebalance_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_rebalance_threshold += Float64(rebalance_threshold(_lf5, _lf5, 0.5))
    var _t1_rebalance_threshold = perf_counter_ns()
    var _ns_rebalance_threshold = Float64(_t1_rebalance_threshold - _t0_rebalance_threshold) / Float64(N)
    print("MOJO_TIMING allocation::rebalance_threshold", _ns_rebalance_threshold, _acc_rebalance_threshold)
