"""bench_constraint.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from constraint import solve_backtrack, all_different, n_queens_check, solve_n_queens, magic_square_check, graph_coloring, sudoku_valid, count_solutions_nqueens, CSPResult
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

    var _keeper_solve_backtrack = List[CSPResult]()
    _keeper_solve_backtrack.append(solve_backtrack([[0,1,1],[1,0,1],[1,1,0]], [[0,1,1],[1,0,1],[1,1,0]]))
    var _acc_solve_backtrack: Float64 = 0.0
    var _t0_solve_backtrack = perf_counter_ns()
    for _ in range(N):
        _keeper_solve_backtrack[0] = solve_backtrack([[0,1,1],[1,0,1],[1,1,0]], [[0,1,1],[1,0,1],[1,1,0]])
        _acc_solve_backtrack += Float64(len(_keeper_solve_backtrack))
    var _t1_solve_backtrack = perf_counter_ns()
    var _ns_solve_backtrack = Float64(_t1_solve_backtrack - _t0_solve_backtrack) / Float64(N)
    print("MOJO_TIMING constraint::solve_backtrack", _ns_solve_backtrack, _acc_solve_backtrack)
    var _acc_all_different: Float64 = 0.0
    var _t0_all_different = perf_counter_ns()
    for _ in range(N):
        _acc_all_different += Float64(all_different(_li5))
    var _t1_all_different = perf_counter_ns()
    var _ns_all_different = Float64(_t1_all_different - _t0_all_different) / Float64(N)
    print("MOJO_TIMING constraint::all_different", _ns_all_different, _acc_all_different)
    var _acc_n_queens_check: Float64 = 0.0
    var _t0_n_queens_check = perf_counter_ns()
    for _ in range(N):
        _acc_n_queens_check += Float64(n_queens_check(_li5))
    var _t1_n_queens_check = perf_counter_ns()
    var _ns_n_queens_check = Float64(_t1_n_queens_check - _t0_n_queens_check) / Float64(N)
    print("MOJO_TIMING constraint::n_queens_check", _ns_n_queens_check, _acc_n_queens_check)
    var _acc_solve_n_queens: Float64 = 0.0
    var _t0_solve_n_queens = perf_counter_ns()
    for _ in range(N):
        var _r_solve_n_queens = solve_n_queens(5)
        _acc_solve_n_queens += Float64(len(_r_solve_n_queens))
    var _t1_solve_n_queens = perf_counter_ns()
    var _ns_solve_n_queens = Float64(_t1_solve_n_queens - _t0_solve_n_queens) / Float64(N)
    print("MOJO_TIMING constraint::solve_n_queens", _ns_solve_n_queens, _acc_solve_n_queens)
    var _acc_magic_square_check: Float64 = 0.0
    var _t0_magic_square_check = perf_counter_ns()
    for _ in range(N):
        _acc_magic_square_check += Float64(magic_square_check([[0,1,1],[1,0,1],[1,1,0]]))
    var _t1_magic_square_check = perf_counter_ns()
    var _ns_magic_square_check = Float64(_t1_magic_square_check - _t0_magic_square_check) / Float64(N)
    print("MOJO_TIMING constraint::magic_square_check", _ns_magic_square_check, _acc_magic_square_check)
    var _acc_graph_coloring: Float64 = 0.0
    var _t0_graph_coloring = perf_counter_ns()
    for _ in range(N):
        var _r_graph_coloring = graph_coloring([[0,1,1],[1,0,1],[1,1,0]], 5)
        _acc_graph_coloring += Float64(len(_r_graph_coloring))
    var _t1_graph_coloring = perf_counter_ns()
    var _ns_graph_coloring = Float64(_t1_graph_coloring - _t0_graph_coloring) / Float64(N)
    print("MOJO_TIMING constraint::graph_coloring", _ns_graph_coloring, _acc_graph_coloring)
    var _acc_sudoku_valid: Float64 = 0.0
    var _t0_sudoku_valid = perf_counter_ns()
    for _ in range(N):
        _acc_sudoku_valid += Float64(sudoku_valid([[0,1,1],[1,0,1],[1,1,0]]))
    var _t1_sudoku_valid = perf_counter_ns()
    var _ns_sudoku_valid = Float64(_t1_sudoku_valid - _t0_sudoku_valid) / Float64(N)
    print("MOJO_TIMING constraint::sudoku_valid", _ns_sudoku_valid, _acc_sudoku_valid)
    var _acc_count_solutions_nqueens: Float64 = 0.0
    var _t0_count_solutions_nqueens = perf_counter_ns()
    for _ in range(N):
        _acc_count_solutions_nqueens += Float64(count_solutions_nqueens(5))
    var _t1_count_solutions_nqueens = perf_counter_ns()
    var _ns_count_solutions_nqueens = Float64(_t1_count_solutions_nqueens - _t0_count_solutions_nqueens) / Float64(N)
    print("MOJO_TIMING constraint::count_solutions_nqueens", _ns_count_solutions_nqueens, _acc_count_solutions_nqueens)
