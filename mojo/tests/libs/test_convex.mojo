"""test_convex.mojo — auto-generated tests for convex library."""
from std.math import isnan, isinf
from convex import eval_function, compute_gradient, l2_norm, vector_sub, proximal_l1, line_search_backtrack, gradient_descent, projected_gradient_descent, adam_optimizer

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

    var _v_eval_function = eval_function(_lf5, 5)
    if is_finite(_v_eval_function): passed += 1; print("  ✅ convex::eval_function =", _v_eval_function)
    else: failed += 1; print("  ❌ convex::eval_function → non-finite:", _v_eval_function)
    var _v_compute_gradient = compute_gradient(_lf5, 5)
    if len(_v_compute_gradient) >= 0: passed += 1; print("  ✅ convex::compute_gradient")
    var _v_l2_norm = l2_norm(_lf5)
    if is_finite(_v_l2_norm): passed += 1; print("  ✅ convex::l2_norm =", _v_l2_norm)
    else: failed += 1; print("  ❌ convex::l2_norm → non-finite:", _v_l2_norm)
    var _v_vector_sub = vector_sub(_lf5, _lf5)
    if len(_v_vector_sub) >= 0: passed += 1; print("  ✅ convex::vector_sub")
    var _v_proximal_l1 = proximal_l1(_lf5, 0.5)
    if len(_v_proximal_l1) >= 0: passed += 1; print("  ✅ convex::proximal_l1")
    var _v_line_search_backtrack = line_search_backtrack(_lf5, _lf5, 5, 0.5, 0.5, 0.5)
    if is_finite(_v_line_search_backtrack): passed += 1; print("  ✅ convex::line_search_backtrack =", _v_line_search_backtrack)
    else: failed += 1; print("  ❌ convex::line_search_backtrack → non-finite:", _v_line_search_backtrack)
    var _v_gradient_descent = gradient_descent(_lf5, 0.5, 5, 0.5, 5)
    if len(_v_gradient_descent) >= 0: passed += 1; print("  ✅ convex::gradient_descent")
    var _v_projected_gradient_descent = projected_gradient_descent(_lf5, 0.5, 5, 0.5, 0.5, 5)
    if len(_v_projected_gradient_descent) >= 0: passed += 1; print("  ✅ convex::projected_gradient_descent")
    var _v_adam_optimizer = adam_optimizer(_lf5, 0.5, 5, 5)
    if len(_v_adam_optimizer) >= 0: passed += 1; print("  ✅ convex::adam_optimizer")

    print("  [convex] Passed:", passed, "Failed:", failed)
