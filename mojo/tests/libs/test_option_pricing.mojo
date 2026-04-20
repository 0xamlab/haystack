"""test_option_pricing.mojo — auto-generated tests for option_pricing library."""
from std.math import isnan, isinf
from option_pricing import norm_cdf, black_scholes_call, black_scholes_put, delta_call, gamma, vega, theta_call, put_call_parity, binomial_tree_call, implied_volatility

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_norm_cdf = norm_cdf(0.5)
    if is_finite(_v_norm_cdf): passed += 1; print("  ✅ option_pricing::norm_cdf =", _v_norm_cdf)
    else: failed += 1; print("  ❌ option_pricing::norm_cdf → non-finite:", _v_norm_cdf)
    var _v_black_scholes_call = black_scholes_call(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_black_scholes_call): passed += 1; print("  ✅ option_pricing::black_scholes_call =", _v_black_scholes_call)
    else: failed += 1; print("  ❌ option_pricing::black_scholes_call → non-finite:", _v_black_scholes_call)
    var _v_black_scholes_put = black_scholes_put(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_black_scholes_put): passed += 1; print("  ✅ option_pricing::black_scholes_put =", _v_black_scholes_put)
    else: failed += 1; print("  ❌ option_pricing::black_scholes_put → non-finite:", _v_black_scholes_put)
    var _v_delta_call = delta_call(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_delta_call): passed += 1; print("  ✅ option_pricing::delta_call =", _v_delta_call)
    else: failed += 1; print("  ❌ option_pricing::delta_call → non-finite:", _v_delta_call)
    var _v_gamma = gamma(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_gamma): passed += 1; print("  ✅ option_pricing::gamma =", _v_gamma)
    else: failed += 1; print("  ❌ option_pricing::gamma → non-finite:", _v_gamma)
    var _v_vega = vega(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_vega): passed += 1; print("  ✅ option_pricing::vega =", _v_vega)
    else: failed += 1; print("  ❌ option_pricing::vega → non-finite:", _v_vega)
    var _v_theta_call = theta_call(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_theta_call): passed += 1; print("  ✅ option_pricing::theta_call =", _v_theta_call)
    else: failed += 1; print("  ❌ option_pricing::theta_call → non-finite:", _v_theta_call)
    var _v_put_call_parity = put_call_parity(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_put_call_parity): passed += 1; print("  ✅ option_pricing::put_call_parity =", _v_put_call_parity)
    else: failed += 1; print("  ❌ option_pricing::put_call_parity → non-finite:", _v_put_call_parity)
    var _v_binomial_tree_call = binomial_tree_call(0.5, 0.5, 0.5, 0.5, 0.5, 5)
    if is_finite(_v_binomial_tree_call): passed += 1; print("  ✅ option_pricing::binomial_tree_call =", _v_binomial_tree_call)
    else: failed += 1; print("  ❌ option_pricing::binomial_tree_call → non-finite:", _v_binomial_tree_call)
    var _v_implied_volatility = implied_volatility(0.5, 0.5, 0.5, 0.5, 0.5, True)
    if is_finite(_v_implied_volatility): passed += 1; print("  ✅ option_pricing::implied_volatility =", _v_implied_volatility)
    else: failed += 1; print("  ❌ option_pricing::implied_volatility → non-finite:", _v_implied_volatility)

    print("  [option_pricing] Passed:", passed, "Failed:", failed)
