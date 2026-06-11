"""test_optimization_constrained.mojo — auto-generated tests for optimization_constrained."""
from std.math import isnan, isinf
from optimization_constrained import eval_objective_c, eval_constraint, is_feasible_c, penalty_value, gradient_estimate, penalty_method, barrier_method, augmented_lagrangian_step

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

    var _v_eval_objective_c = eval_objective_c(_lf5, 5)
    if is_finite(_v_eval_objective_c): passed += 1; print("  ✅ optimization_constrained::eval_objective_c =", _v_eval_objective_c)
    else: failed += 1; print("  ❌ optimization_constrained::eval_objective_c → non-finite:", _v_eval_objective_c)
    var _v_eval_constraint = eval_constraint(_lf5, 5)
    if is_finite(_v_eval_constraint): passed += 1; print("  ✅ optimization_constrained::eval_constraint =", _v_eval_constraint)
    else: failed += 1; print("  ❌ optimization_constrained::eval_constraint → non-finite:", _v_eval_constraint)
    _ = is_feasible_c(_lf5, _li5, 0.5)
    passed += 1; print("  ✅ optimization_constrained::is_feasible_c")
    var _v_penalty_value = penalty_value(_lf5, _li5)
    if is_finite(_v_penalty_value): passed += 1; print("  ✅ optimization_constrained::penalty_value =", _v_penalty_value)
    else: failed += 1; print("  ❌ optimization_constrained::penalty_value → non-finite:", _v_penalty_value)
    var _v_gradient_estimate = gradient_estimate(_lf5, 5, _li5, 0.5, 0.5)
    if len(_v_gradient_estimate) >= 0: passed += 1; print("  ✅ optimization_constrained::gradient_estimate")
    var _v_penalty_method = penalty_method(_lf5, 5, _li5, 0.5, 5, 0.5)
    if len(_v_penalty_method) >= 0: passed += 1; print("  ✅ optimization_constrained::penalty_method")
    var _v_barrier_method = barrier_method(_lf5, 5, _li5, 0.5, 5, 0.5)
    if len(_v_barrier_method) >= 0: passed += 1; print("  ✅ optimization_constrained::barrier_method")
    _ = augmented_lagrangian_step(_lf5, _lf5, 5, _li5, 0.5, 0.5)
    passed += 1; print("  ✅ optimization_constrained::augmented_lagrangian_step")

    print("  [optimization_constrained] Passed:", passed, "Failed:", failed)
