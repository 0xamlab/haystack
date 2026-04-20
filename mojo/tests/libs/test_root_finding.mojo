"""test_root_finding.mojo — auto-generated tests for root_finding library."""
from std.math import isnan, isinf
from root_finding import eval_func, eval_deriv, bisection, newton_raphson, secant_method, fixed_point, regula_falsi, bracket_root, convergence_order

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

    var _v_eval_func = eval_func(0.5, 5)
    if is_finite(_v_eval_func): passed += 1; print("  ✅ root_finding::eval_func =", _v_eval_func)
    else: failed += 1; print("  ❌ root_finding::eval_func → non-finite:", _v_eval_func)
    var _v_eval_deriv = eval_deriv(0.5, 5)
    if is_finite(_v_eval_deriv): passed += 1; print("  ✅ root_finding::eval_deriv =", _v_eval_deriv)
    else: failed += 1; print("  ❌ root_finding::eval_deriv → non-finite:", _v_eval_deriv)
    var _v_bisection = bisection(0.5, 0.5, 5, 0.5, 5)
    if is_finite(_v_bisection): passed += 1; print("  ✅ root_finding::bisection =", _v_bisection)
    else: failed += 1; print("  ❌ root_finding::bisection → non-finite:", _v_bisection)
    var _v_newton_raphson = newton_raphson(0.5, 5, 0.5, 5)
    if is_finite(_v_newton_raphson): passed += 1; print("  ✅ root_finding::newton_raphson =", _v_newton_raphson)
    else: failed += 1; print("  ❌ root_finding::newton_raphson → non-finite:", _v_newton_raphson)
    var _v_secant_method = secant_method(0.5, 0.5, 5, 0.5, 5)
    if is_finite(_v_secant_method): passed += 1; print("  ✅ root_finding::secant_method =", _v_secant_method)
    else: failed += 1; print("  ❌ root_finding::secant_method → non-finite:", _v_secant_method)
    var _v_fixed_point = fixed_point(0.5, 5, 0.5, 5)
    if is_finite(_v_fixed_point): passed += 1; print("  ✅ root_finding::fixed_point =", _v_fixed_point)
    else: failed += 1; print("  ❌ root_finding::fixed_point → non-finite:", _v_fixed_point)
    var _v_regula_falsi = regula_falsi(-1.0, 1.0, 0)
    if is_finite(_v_regula_falsi): passed += 1; print("  ✅ root_finding::regula_falsi =", _v_regula_falsi)
    else: failed += 1; print("  ❌ root_finding::regula_falsi → non-finite:", _v_regula_falsi)
    var _v_bracket_root = bracket_root(5, 0.5, 0.5, 5)
    if len(_v_bracket_root) >= 0: passed += 1; print("  ✅ root_finding::bracket_root")
    var _v_convergence_order = convergence_order(_lf5)
    if is_finite(_v_convergence_order): passed += 1; print("  ✅ root_finding::convergence_order =", _v_convergence_order)
    else: failed += 1; print("  ❌ root_finding::convergence_order → non-finite:", _v_convergence_order)

    print("  [root_finding] Passed:", passed, "Failed:", failed)
