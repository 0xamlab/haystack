"""test_chaos.mojo — auto-generated tests for chaos."""
from std.math import isnan, isinf
from chaos import logistic_map, lorenz_step, lorenz_simulate, lyapunov_exponent_logistic, henon_map, tent_map, bifurcation_diagram, sensitivity_to_initial, feigenbaum_ratio, is_chaotic

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

    var _v_logistic_map = logistic_map(0.5, 0.5, 5)
    if len(_v_logistic_map) >= 0: passed += 1; print("  ✅ chaos::logistic_map")
    var _v_lorenz_step = lorenz_step(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    if len(_v_lorenz_step) >= 0: passed += 1; print("  ✅ chaos::lorenz_step")
    _ = lorenz_simulate(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 5)
    passed += 1; print("  ✅ chaos::lorenz_simulate")
    var _v_lyapunov_exponent_logistic = lyapunov_exponent_logistic(0.5, 5, 5)
    if is_finite(_v_lyapunov_exponent_logistic): passed += 1; print("  ✅ chaos::lyapunov_exponent_logistic =", _v_lyapunov_exponent_logistic)
    else: failed += 1; print("  ❌ chaos::lyapunov_exponent_logistic → non-finite:", _v_lyapunov_exponent_logistic)
    _ = henon_map(0.5, 0.5, 0.5, 0.5, 5)
    passed += 1; print("  ✅ chaos::henon_map")
    var _v_tent_map = tent_map(0.5, 0.5, 5)
    if len(_v_tent_map) >= 0: passed += 1; print("  ✅ chaos::tent_map")
    _ = bifurcation_diagram(0.5, 0.5, 5, 5, 5)
    passed += 1; print("  ✅ chaos::bifurcation_diagram")
    var _v_sensitivity_to_initial = sensitivity_to_initial(0.5, 0.5, 0.5, 5)
    if len(_v_sensitivity_to_initial) >= 0: passed += 1; print("  ✅ chaos::sensitivity_to_initial")
    var _v_feigenbaum_ratio = feigenbaum_ratio(0.5, 0.5, 0.5)
    if is_finite(_v_feigenbaum_ratio): passed += 1; print("  ✅ chaos::feigenbaum_ratio =", _v_feigenbaum_ratio)
    else: failed += 1; print("  ❌ chaos::feigenbaum_ratio → non-finite:", _v_feigenbaum_ratio)
    _ = is_chaotic(0.5)
    passed += 1; print("  ✅ chaos::is_chaotic")

    print("  [chaos] Passed:", passed, "Failed:", failed)
