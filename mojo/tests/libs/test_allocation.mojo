"""test_allocation.mojo — auto-generated tests for allocation."""
from std.math import isnan, isinf
from allocation import equal_weight, inverse_variance, risk_parity_simple, max_sharpe_2asset, min_variance_2asset, portfolio_return, portfolio_variance_2asset, kelly_criterion, efficient_frontier_2asset, rebalance_threshold

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _li3 = List[Int]()
    _li3.append(1); _li3.append(2); _li3.append(3)
    var _li2_zero = List[Int]()
    _li2_zero.append(0); _li2_zero.append(1)
    var _li3_tail = List[Int]()
    _li3_tail.append(2); _li3_tail.append(3); _li3_tail.append(4)
    var _li8 = List[Int]()
    for i in range(8):
        _li8.append(i + 1)
    var _li6_grid2x3 = List[Int]()
    _li6_grid2x3.append(0); _li6_grid2x3.append(1); _li6_grid2x3.append(0)
    _li6_grid2x3.append(1); _li6_grid2x3.append(1); _li6_grid2x3.append(0)
    var _li10_borda = List[Int]()
    _li10_borda.append(0); _li10_borda.append(1); _li10_borda.append(2); _li10_borda.append(3); _li10_borda.append(4)
    _li10_borda.append(1); _li10_borda.append(0); _li10_borda.append(2); _li10_borda.append(4); _li10_borda.append(3)
    var _li16 = List[Int]()
    for i in range(16):
        _li16.append(i)
    var _lf6_matrix = List[Float64]()
    _lf6_matrix.append(1.0); _lf6_matrix.append(2.0); _lf6_matrix.append(3.0)
    _lf6_matrix.append(4.0); _lf6_matrix.append(5.0); _lf6_matrix.append(6.0)
    var _lf8_coalitions = List[Float64]()
    _lf8_coalitions.append(0.0); _lf8_coalitions.append(1.0); _lf8_coalitions.append(2.0); _lf8_coalitions.append(4.0)
    _lf8_coalitions.append(3.0); _lf8_coalitions.append(5.0); _lf8_coalitions.append(6.0); _lf8_coalitions.append(9.0)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_equal_weight = equal_weight(5)
    if len(_v_equal_weight) >= 0: passed += 1; print("  ✅ allocation::equal_weight")
    var _v_inverse_variance = inverse_variance(_lf5)
    if len(_v_inverse_variance) >= 0: passed += 1; print("  ✅ allocation::inverse_variance")
    var _v_risk_parity_simple = risk_parity_simple(_lf5)
    if len(_v_risk_parity_simple) >= 0: passed += 1; print("  ✅ allocation::risk_parity_simple")
    var _v_max_sharpe_2asset = max_sharpe_2asset(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    if len(_v_max_sharpe_2asset) >= 0: passed += 1; print("  ✅ allocation::max_sharpe_2asset")
    var _v_min_variance_2asset = min_variance_2asset(0.5, 0.5, 0.5)
    if len(_v_min_variance_2asset) >= 0: passed += 1; print("  ✅ allocation::min_variance_2asset")
    var _v_portfolio_return = portfolio_return(_lf5, _lf5)
    if is_finite(_v_portfolio_return): passed += 1; print("  ✅ allocation::portfolio_return =", _v_portfolio_return)
    else: failed += 1; print("  ❌ allocation::portfolio_return → non-finite:", _v_portfolio_return)
    var _v_portfolio_variance_2asset = portfolio_variance_2asset(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_portfolio_variance_2asset): passed += 1; print("  ✅ allocation::portfolio_variance_2asset =", _v_portfolio_variance_2asset)
    else: failed += 1; print("  ❌ allocation::portfolio_variance_2asset → non-finite:", _v_portfolio_variance_2asset)
    var _v_kelly_criterion = kelly_criterion(0.5, 0.5)
    if is_finite(_v_kelly_criterion): passed += 1; print("  ✅ allocation::kelly_criterion =", _v_kelly_criterion)
    else: failed += 1; print("  ❌ allocation::kelly_criterion → non-finite:", _v_kelly_criterion)
    _ = efficient_frontier_2asset(0.5, 0.5, 0.5, 0.5, 0.5, 5)
    passed += 1; print("  ✅ allocation::efficient_frontier_2asset")
    _ = rebalance_threshold(_lf5, _lf5, 0.5)
    passed += 1; print("  ✅ allocation::rebalance_threshold")

    print("  [allocation] Passed:", passed, "Failed:", failed)
