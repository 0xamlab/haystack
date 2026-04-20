"""bench_linear_programming.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from linear_programming import line_intersection_2d, is_feasible, objective_value, enumerate_vertices_2d, lp_solve_2var, dual_value, sensitivity_rhs, transportation_cost
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

    var _acc_line_intersection_2d: Float64 = 0.0
    var _t0_line_intersection_2d = perf_counter_ns()
    for _ in range(N):
        var _r_line_intersection_2d = line_intersection_2d(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
        _acc_line_intersection_2d += Float64(len(_r_line_intersection_2d))
    var _t1_line_intersection_2d = perf_counter_ns()
    var _ns_line_intersection_2d = Float64(_t1_line_intersection_2d - _t0_line_intersection_2d) / Float64(N)
    print("MOJO_TIMING linear_programming::line_intersection_2d", _ns_line_intersection_2d, _acc_line_intersection_2d)
    var _acc_is_feasible: Float64 = 0.0
    var _t0_is_feasible = perf_counter_ns()
    for _ in range(N):
        _acc_is_feasible += Float64(is_feasible(_lf5, [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5))
    var _t1_is_feasible = perf_counter_ns()
    var _ns_is_feasible = Float64(_t1_is_feasible - _t0_is_feasible) / Float64(N)
    print("MOJO_TIMING linear_programming::is_feasible", _ns_is_feasible, _acc_is_feasible)
    var _acc_objective_value: Float64 = 0.0
    var _t0_objective_value = perf_counter_ns()
    for _ in range(N):
        _acc_objective_value += objective_value(_lf5, _lf5)
    var _t1_objective_value = perf_counter_ns()
    var _ns_objective_value = Float64(_t1_objective_value - _t0_objective_value) / Float64(N)
    print("MOJO_TIMING linear_programming::objective_value", _ns_objective_value, _acc_objective_value)
    var _acc_enumerate_vertices_2d: Float64 = 0.0
    var _t0_enumerate_vertices_2d = perf_counter_ns()
    for _ in range(N):
        var _r_enumerate_vertices_2d = enumerate_vertices_2d([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5)
        _acc_enumerate_vertices_2d += Float64(len(_r_enumerate_vertices_2d))
    var _t1_enumerate_vertices_2d = perf_counter_ns()
    var _ns_enumerate_vertices_2d = Float64(_t1_enumerate_vertices_2d - _t0_enumerate_vertices_2d) / Float64(N)
    print("MOJO_TIMING linear_programming::enumerate_vertices_2d", _ns_enumerate_vertices_2d, _acc_enumerate_vertices_2d)
    var _acc_lp_solve_2var: Float64 = 0.0
    var _t0_lp_solve_2var = perf_counter_ns()
    for _ in range(N):
        var _r_lp_solve_2var = lp_solve_2var(_lf5, [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5)
        _acc_lp_solve_2var += Float64(len(_r_lp_solve_2var))
    var _t1_lp_solve_2var = perf_counter_ns()
    var _ns_lp_solve_2var = Float64(_t1_lp_solve_2var - _t0_lp_solve_2var) / Float64(N)
    print("MOJO_TIMING linear_programming::lp_solve_2var", _ns_lp_solve_2var, _acc_lp_solve_2var)
    var _acc_dual_value: Float64 = 0.0
    var _t0_dual_value = perf_counter_ns()
    for _ in range(N):
        _acc_dual_value += dual_value([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, _lf5)
    var _t1_dual_value = perf_counter_ns()
    var _ns_dual_value = Float64(_t1_dual_value - _t0_dual_value) / Float64(N)
    print("MOJO_TIMING linear_programming::dual_value", _ns_dual_value, _acc_dual_value)
    var _acc_sensitivity_rhs: Float64 = 0.0
    var _t0_sensitivity_rhs = perf_counter_ns()
    for _ in range(N):
        _acc_sensitivity_rhs += sensitivity_rhs(_lf5, [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5, 5, 0.5)
    var _t1_sensitivity_rhs = perf_counter_ns()
    var _ns_sensitivity_rhs = Float64(_t1_sensitivity_rhs - _t0_sensitivity_rhs) / Float64(N)
    print("MOJO_TIMING linear_programming::sensitivity_rhs", _ns_sensitivity_rhs, _acc_sensitivity_rhs)
    var _acc_transportation_cost: Float64 = 0.0
    var _t0_transportation_cost = perf_counter_ns()
    for _ in range(N):
        _acc_transportation_cost += transportation_cost(_lf5, _lf5, [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_transportation_cost = perf_counter_ns()
    var _ns_transportation_cost = Float64(_t1_transportation_cost - _t0_transportation_cost) / Float64(N)
    print("MOJO_TIMING linear_programming::transportation_cost", _ns_transportation_cost, _acc_transportation_cost)
