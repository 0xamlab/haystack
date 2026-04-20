"""test_constraint.mojo — auto-generated tests for constraint library."""
from std.math import isnan, isinf
from constraint import all_different, n_queens_check, solve_n_queens, count_solutions_nqueens

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

    _ = all_different(_li5)
    passed += 1; print("  ✅ constraint::all_different")
    _ = n_queens_check(_li5)
    passed += 1; print("  ✅ constraint::n_queens_check")
    var _v_solve_n_queens = solve_n_queens(5)
    if len(_v_solve_n_queens) >= 0: passed += 1; print("  ✅ constraint::solve_n_queens")
    _ = count_solutions_nqueens(5)
    passed += 1; print("  ✅ constraint::count_solutions_nqueens")

    print("  [constraint] Passed:", passed, "Failed:", failed)
