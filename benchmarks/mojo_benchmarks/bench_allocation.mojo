"""bench_allocation.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from allocation import equal_weight, inverse_variance, risk_parity_simple, max_sharpe_2asset, min_variance_2asset, portfolio_return, portfolio_variance_2asset, kelly_criterion, efficient_frontier_2asset, rebalance_threshold
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

    var _acc_equal_weight: Float64 = 0.0
    var _t0_equal_weight = perf_counter_ns()
    for _ in range(N):
        var _r_equal_weight = equal_weight(5)
        _acc_equal_weight += Float64(len(_r_equal_weight))
    var _t1_equal_weight = perf_counter_ns()
    var _ns_equal_weight = Float64(_t1_equal_weight - _t0_equal_weight) / Float64(N)
    print("MOJO_TIMING allocation::equal_weight", _ns_equal_weight, _acc_equal_weight)
    var _result_equal_weight = equal_weight(5)
    var _summary_equal_weight = _summary_list_float64(_result_equal_weight)
    print("MOJO_RESULT allocation::equal_weight", _summary_equal_weight)
    var _acc_inverse_variance: Float64 = 0.0
    var _t0_inverse_variance = perf_counter_ns()
    for _ in range(N):
        var _r_inverse_variance = inverse_variance(_lf5)
        _acc_inverse_variance += Float64(len(_r_inverse_variance))
    var _t1_inverse_variance = perf_counter_ns()
    var _ns_inverse_variance = Float64(_t1_inverse_variance - _t0_inverse_variance) / Float64(N)
    print("MOJO_TIMING allocation::inverse_variance", _ns_inverse_variance, _acc_inverse_variance)
    var _result_inverse_variance = inverse_variance(_lf5)
    var _summary_inverse_variance = _summary_list_float64(_result_inverse_variance)
    print("MOJO_RESULT allocation::inverse_variance", _summary_inverse_variance)
    var _acc_risk_parity_simple: Float64 = 0.0
    var _t0_risk_parity_simple = perf_counter_ns()
    for _ in range(N):
        var _r_risk_parity_simple = risk_parity_simple(_lf5)
        _acc_risk_parity_simple += Float64(len(_r_risk_parity_simple))
    var _t1_risk_parity_simple = perf_counter_ns()
    var _ns_risk_parity_simple = Float64(_t1_risk_parity_simple - _t0_risk_parity_simple) / Float64(N)
    print("MOJO_TIMING allocation::risk_parity_simple", _ns_risk_parity_simple, _acc_risk_parity_simple)
    var _result_risk_parity_simple = risk_parity_simple(_lf5)
    var _summary_risk_parity_simple = _summary_list_float64(_result_risk_parity_simple)
    print("MOJO_RESULT allocation::risk_parity_simple", _summary_risk_parity_simple)
    var _acc_max_sharpe_2asset: Float64 = 0.0
    var _t0_max_sharpe_2asset = perf_counter_ns()
    for _ in range(N):
        var _r_max_sharpe_2asset = max_sharpe_2asset(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
        _acc_max_sharpe_2asset += Float64(len(_r_max_sharpe_2asset))
    var _t1_max_sharpe_2asset = perf_counter_ns()
    var _ns_max_sharpe_2asset = Float64(_t1_max_sharpe_2asset - _t0_max_sharpe_2asset) / Float64(N)
    print("MOJO_TIMING allocation::max_sharpe_2asset", _ns_max_sharpe_2asset, _acc_max_sharpe_2asset)
    var _result_max_sharpe_2asset = max_sharpe_2asset(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_max_sharpe_2asset = _summary_list_float64(_result_max_sharpe_2asset)
    print("MOJO_RESULT allocation::max_sharpe_2asset", _summary_max_sharpe_2asset)
    var _acc_min_variance_2asset: Float64 = 0.0
    var _t0_min_variance_2asset = perf_counter_ns()
    for _ in range(N):
        var _r_min_variance_2asset = min_variance_2asset(0.5, 0.5, 0.5)
        _acc_min_variance_2asset += Float64(len(_r_min_variance_2asset))
    var _t1_min_variance_2asset = perf_counter_ns()
    var _ns_min_variance_2asset = Float64(_t1_min_variance_2asset - _t0_min_variance_2asset) / Float64(N)
    print("MOJO_TIMING allocation::min_variance_2asset", _ns_min_variance_2asset, _acc_min_variance_2asset)
    var _result_min_variance_2asset = min_variance_2asset(0.5, 0.5, 0.5)
    var _summary_min_variance_2asset = _summary_list_float64(_result_min_variance_2asset)
    print("MOJO_RESULT allocation::min_variance_2asset", _summary_min_variance_2asset)
    var _acc_portfolio_return: Float64 = 0.0
    var _t0_portfolio_return = perf_counter_ns()
    for _ in range(N):
        _acc_portfolio_return += portfolio_return(_lf5, _lf5)
    var _t1_portfolio_return = perf_counter_ns()
    var _ns_portfolio_return = Float64(_t1_portfolio_return - _t0_portfolio_return) / Float64(N)
    print("MOJO_TIMING allocation::portfolio_return", _ns_portfolio_return, _acc_portfolio_return)
    var _result_portfolio_return = portfolio_return(_lf5, _lf5)
    var _summary_portfolio_return = _summary_float64(_result_portfolio_return)
    print("MOJO_RESULT allocation::portfolio_return", _summary_portfolio_return)
    var _acc_portfolio_variance_2asset: Float64 = 0.0
    var _t0_portfolio_variance_2asset = perf_counter_ns()
    for _ in range(N):
        _acc_portfolio_variance_2asset += portfolio_variance_2asset(0.5, 0.5, 0.5, 0.5)
    var _t1_portfolio_variance_2asset = perf_counter_ns()
    var _ns_portfolio_variance_2asset = Float64(_t1_portfolio_variance_2asset - _t0_portfolio_variance_2asset) / Float64(N)
    print("MOJO_TIMING allocation::portfolio_variance_2asset", _ns_portfolio_variance_2asset, _acc_portfolio_variance_2asset)
    var _result_portfolio_variance_2asset = portfolio_variance_2asset(0.5, 0.5, 0.5, 0.5)
    var _summary_portfolio_variance_2asset = _summary_float64(_result_portfolio_variance_2asset)
    print("MOJO_RESULT allocation::portfolio_variance_2asset", _summary_portfolio_variance_2asset)
    var _acc_kelly_criterion: Float64 = 0.0
    var _t0_kelly_criterion = perf_counter_ns()
    for _ in range(N):
        _acc_kelly_criterion += kelly_criterion(0.5, 0.5)
    var _t1_kelly_criterion = perf_counter_ns()
    var _ns_kelly_criterion = Float64(_t1_kelly_criterion - _t0_kelly_criterion) / Float64(N)
    print("MOJO_TIMING allocation::kelly_criterion", _ns_kelly_criterion, _acc_kelly_criterion)
    var _result_kelly_criterion = kelly_criterion(0.5, 0.5)
    var _summary_kelly_criterion = _summary_float64(_result_kelly_criterion)
    print("MOJO_RESULT allocation::kelly_criterion", _summary_kelly_criterion)
    var _acc_efficient_frontier_2asset: Float64 = 0.0
    var _t0_efficient_frontier_2asset = perf_counter_ns()
    for _ in range(N):
        var _r_efficient_frontier_2asset = efficient_frontier_2asset(0.5, 0.5, 0.5, 0.5, 0.5, 5)
        _acc_efficient_frontier_2asset += Float64(len(_r_efficient_frontier_2asset))
    var _t1_efficient_frontier_2asset = perf_counter_ns()
    var _ns_efficient_frontier_2asset = Float64(_t1_efficient_frontier_2asset - _t0_efficient_frontier_2asset) / Float64(N)
    print("MOJO_TIMING allocation::efficient_frontier_2asset", _ns_efficient_frontier_2asset, _acc_efficient_frontier_2asset)
    var _result_efficient_frontier_2asset = efficient_frontier_2asset(0.5, 0.5, 0.5, 0.5, 0.5, 5)
    var _summary_efficient_frontier_2asset = _summary_list_list_float64(_result_efficient_frontier_2asset)
    print("MOJO_RESULT allocation::efficient_frontier_2asset", _summary_efficient_frontier_2asset)
    var _acc_rebalance_threshold: Float64 = 0.0
    var _t0_rebalance_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_rebalance_threshold += Float64(rebalance_threshold(_lf5, _lf5, 0.5))
    var _t1_rebalance_threshold = perf_counter_ns()
    var _ns_rebalance_threshold = Float64(_t1_rebalance_threshold - _t0_rebalance_threshold) / Float64(N)
    print("MOJO_TIMING allocation::rebalance_threshold", _ns_rebalance_threshold, _acc_rebalance_threshold)
    var _result_rebalance_threshold = rebalance_threshold(_lf5, _lf5, 0.5)
    var _summary_rebalance_threshold = _summary_bool(_result_rebalance_threshold)
    print("MOJO_RESULT allocation::rebalance_threshold", _summary_rebalance_threshold)
