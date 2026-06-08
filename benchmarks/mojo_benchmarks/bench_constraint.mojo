"""bench_constraint.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from constraint import solve_backtrack, all_different, n_queens_check, solve_n_queens, magic_square_check, graph_coloring, sudoku_valid, count_solutions_nqueens, CSPResult
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
    var _result_all_different = all_different(_li5)
    var _summary_all_different = _summary_bool(_result_all_different)
    print("MOJO_RESULT constraint::all_different", _summary_all_different)
    var _acc_n_queens_check: Float64 = 0.0
    var _t0_n_queens_check = perf_counter_ns()
    for _ in range(N):
        _acc_n_queens_check += Float64(n_queens_check(_li5))
    var _t1_n_queens_check = perf_counter_ns()
    var _ns_n_queens_check = Float64(_t1_n_queens_check - _t0_n_queens_check) / Float64(N)
    print("MOJO_TIMING constraint::n_queens_check", _ns_n_queens_check, _acc_n_queens_check)
    var _result_n_queens_check = n_queens_check(_li5)
    var _summary_n_queens_check = _summary_bool(_result_n_queens_check)
    print("MOJO_RESULT constraint::n_queens_check", _summary_n_queens_check)
    var _acc_solve_n_queens: Float64 = 0.0
    var _t0_solve_n_queens = perf_counter_ns()
    for _ in range(N):
        var _r_solve_n_queens = solve_n_queens(5)
        _acc_solve_n_queens += Float64(len(_r_solve_n_queens))
    var _t1_solve_n_queens = perf_counter_ns()
    var _ns_solve_n_queens = Float64(_t1_solve_n_queens - _t0_solve_n_queens) / Float64(N)
    print("MOJO_TIMING constraint::solve_n_queens", _ns_solve_n_queens, _acc_solve_n_queens)
    var _result_solve_n_queens = solve_n_queens(5)
    var _summary_solve_n_queens = _summary_list_int(_result_solve_n_queens)
    print("MOJO_RESULT constraint::solve_n_queens", _summary_solve_n_queens)
    var _acc_magic_square_check: Float64 = 0.0
    var _t0_magic_square_check = perf_counter_ns()
    for _ in range(N):
        _acc_magic_square_check += Float64(magic_square_check([[0,1,1],[1,0,1],[1,1,0]]))
    var _t1_magic_square_check = perf_counter_ns()
    var _ns_magic_square_check = Float64(_t1_magic_square_check - _t0_magic_square_check) / Float64(N)
    print("MOJO_TIMING constraint::magic_square_check", _ns_magic_square_check, _acc_magic_square_check)
    var _result_magic_square_check = magic_square_check([[0,1,1],[1,0,1],[1,1,0]])
    var _summary_magic_square_check = _summary_bool(_result_magic_square_check)
    print("MOJO_RESULT constraint::magic_square_check", _summary_magic_square_check)
    var _acc_graph_coloring: Float64 = 0.0
    var _t0_graph_coloring = perf_counter_ns()
    for _ in range(N):
        var _r_graph_coloring = graph_coloring([[0,1,1],[1,0,1],[1,1,0]], 5)
        _acc_graph_coloring += Float64(len(_r_graph_coloring))
    var _t1_graph_coloring = perf_counter_ns()
    var _ns_graph_coloring = Float64(_t1_graph_coloring - _t0_graph_coloring) / Float64(N)
    print("MOJO_TIMING constraint::graph_coloring", _ns_graph_coloring, _acc_graph_coloring)
    var _result_graph_coloring = graph_coloring([[0,1,1],[1,0,1],[1,1,0]], 5)
    var _summary_graph_coloring = _summary_list_int(_result_graph_coloring)
    print("MOJO_RESULT constraint::graph_coloring", _summary_graph_coloring)
    var _acc_sudoku_valid: Float64 = 0.0
    var _t0_sudoku_valid = perf_counter_ns()
    for _ in range(N):
        _acc_sudoku_valid += Float64(sudoku_valid([[0,1,1],[1,0,1],[1,1,0]]))
    var _t1_sudoku_valid = perf_counter_ns()
    var _ns_sudoku_valid = Float64(_t1_sudoku_valid - _t0_sudoku_valid) / Float64(N)
    print("MOJO_TIMING constraint::sudoku_valid", _ns_sudoku_valid, _acc_sudoku_valid)
    var _result_sudoku_valid = sudoku_valid([[0,1,1],[1,0,1],[1,1,0]])
    var _summary_sudoku_valid = _summary_bool(_result_sudoku_valid)
    print("MOJO_RESULT constraint::sudoku_valid", _summary_sudoku_valid)
    var _acc_count_solutions_nqueens: Float64 = 0.0
    var _t0_count_solutions_nqueens = perf_counter_ns()
    for _ in range(N):
        _acc_count_solutions_nqueens += Float64(count_solutions_nqueens(5))
    var _t1_count_solutions_nqueens = perf_counter_ns()
    var _ns_count_solutions_nqueens = Float64(_t1_count_solutions_nqueens - _t0_count_solutions_nqueens) / Float64(N)
    print("MOJO_TIMING constraint::count_solutions_nqueens", _ns_count_solutions_nqueens, _acc_count_solutions_nqueens)
    var _result_count_solutions_nqueens = count_solutions_nqueens(5)
    var _summary_count_solutions_nqueens = _summary_int(_result_count_solutions_nqueens)
    print("MOJO_RESULT constraint::count_solutions_nqueens", _summary_count_solutions_nqueens)
