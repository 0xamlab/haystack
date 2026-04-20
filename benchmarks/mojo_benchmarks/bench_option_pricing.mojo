"""bench_option_pricing.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from option_pricing import norm_cdf, black_scholes_call, black_scholes_put, delta_call, gamma, vega, theta_call, put_call_parity, binomial_tree_call, implied_volatility
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

    var _acc_norm_cdf: Float64 = 0.0
    var _t0_norm_cdf = perf_counter_ns()
    for _ in range(N):
        _acc_norm_cdf += norm_cdf(0.5)
    var _t1_norm_cdf = perf_counter_ns()
    var _ns_norm_cdf = Float64(_t1_norm_cdf - _t0_norm_cdf) / Float64(N)
    print("MOJO_TIMING option_pricing::norm_cdf", _ns_norm_cdf, _acc_norm_cdf)
    var _acc_black_scholes_call: Float64 = 0.0
    var _t0_black_scholes_call = perf_counter_ns()
    for _ in range(N):
        _acc_black_scholes_call += black_scholes_call(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_black_scholes_call = perf_counter_ns()
    var _ns_black_scholes_call = Float64(_t1_black_scholes_call - _t0_black_scholes_call) / Float64(N)
    print("MOJO_TIMING option_pricing::black_scholes_call", _ns_black_scholes_call, _acc_black_scholes_call)
    var _acc_black_scholes_put: Float64 = 0.0
    var _t0_black_scholes_put = perf_counter_ns()
    for _ in range(N):
        _acc_black_scholes_put += black_scholes_put(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_black_scholes_put = perf_counter_ns()
    var _ns_black_scholes_put = Float64(_t1_black_scholes_put - _t0_black_scholes_put) / Float64(N)
    print("MOJO_TIMING option_pricing::black_scholes_put", _ns_black_scholes_put, _acc_black_scholes_put)
    var _acc_delta_call: Float64 = 0.0
    var _t0_delta_call = perf_counter_ns()
    for _ in range(N):
        _acc_delta_call += delta_call(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_delta_call = perf_counter_ns()
    var _ns_delta_call = Float64(_t1_delta_call - _t0_delta_call) / Float64(N)
    print("MOJO_TIMING option_pricing::delta_call", _ns_delta_call, _acc_delta_call)
    var _acc_gamma: Float64 = 0.0
    var _t0_gamma = perf_counter_ns()
    for _ in range(N):
        _acc_gamma += gamma(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_gamma = perf_counter_ns()
    var _ns_gamma = Float64(_t1_gamma - _t0_gamma) / Float64(N)
    print("MOJO_TIMING option_pricing::gamma", _ns_gamma, _acc_gamma)
    var _acc_vega: Float64 = 0.0
    var _t0_vega = perf_counter_ns()
    for _ in range(N):
        _acc_vega += vega(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_vega = perf_counter_ns()
    var _ns_vega = Float64(_t1_vega - _t0_vega) / Float64(N)
    print("MOJO_TIMING option_pricing::vega", _ns_vega, _acc_vega)
    var _acc_theta_call: Float64 = 0.0
    var _t0_theta_call = perf_counter_ns()
    for _ in range(N):
        _acc_theta_call += theta_call(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_theta_call = perf_counter_ns()
    var _ns_theta_call = Float64(_t1_theta_call - _t0_theta_call) / Float64(N)
    print("MOJO_TIMING option_pricing::theta_call", _ns_theta_call, _acc_theta_call)
    var _acc_put_call_parity: Float64 = 0.0
    var _t0_put_call_parity = perf_counter_ns()
    for _ in range(N):
        _acc_put_call_parity += put_call_parity(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_put_call_parity = perf_counter_ns()
    var _ns_put_call_parity = Float64(_t1_put_call_parity - _t0_put_call_parity) / Float64(N)
    print("MOJO_TIMING option_pricing::put_call_parity", _ns_put_call_parity, _acc_put_call_parity)
    var _acc_binomial_tree_call: Float64 = 0.0
    var _t0_binomial_tree_call = perf_counter_ns()
    for _ in range(N):
        _acc_binomial_tree_call += binomial_tree_call(0.5, 0.5, 0.5, 0.5, 0.5, 5)
    var _t1_binomial_tree_call = perf_counter_ns()
    var _ns_binomial_tree_call = Float64(_t1_binomial_tree_call - _t0_binomial_tree_call) / Float64(N)
    print("MOJO_TIMING option_pricing::binomial_tree_call", _ns_binomial_tree_call, _acc_binomial_tree_call)
    var _acc_implied_volatility: Float64 = 0.0
    var _t0_implied_volatility = perf_counter_ns()
    for _ in range(N):
        _acc_implied_volatility += implied_volatility(0.5, 0.5, 0.5, 0.5, 0.5, True)
    var _t1_implied_volatility = perf_counter_ns()
    var _ns_implied_volatility = Float64(_t1_implied_volatility - _t0_implied_volatility) / Float64(N)
    print("MOJO_TIMING option_pricing::implied_volatility", _ns_implied_volatility, _acc_implied_volatility)
