"""bench_fuzzy_logic.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from fuzzy_logic import triangular_mf, trapezoidal_mf, gaussian_mf, fuzzy_and, fuzzy_or, fuzzy_not, defuzzify_centroid, defuzzify_bisector, defuzzify_mom, fuzzy_rule_eval, alpha_cut
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

    var _acc_triangular_mf: Float64 = 0.0
    var _t0_triangular_mf = perf_counter_ns()
    for _ in range(N):
        _acc_triangular_mf += triangular_mf(0.5, 0.5, 0.5, 0.5)
    var _t1_triangular_mf = perf_counter_ns()
    var _ns_triangular_mf = Float64(_t1_triangular_mf - _t0_triangular_mf) / Float64(N)
    print("MOJO_TIMING fuzzy_logic::triangular_mf", _ns_triangular_mf, _acc_triangular_mf)
    var _acc_trapezoidal_mf: Float64 = 0.0
    var _t0_trapezoidal_mf = perf_counter_ns()
    for _ in range(N):
        _acc_trapezoidal_mf += trapezoidal_mf(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_trapezoidal_mf = perf_counter_ns()
    var _ns_trapezoidal_mf = Float64(_t1_trapezoidal_mf - _t0_trapezoidal_mf) / Float64(N)
    print("MOJO_TIMING fuzzy_logic::trapezoidal_mf", _ns_trapezoidal_mf, _acc_trapezoidal_mf)
    var _acc_gaussian_mf: Float64 = 0.0
    var _t0_gaussian_mf = perf_counter_ns()
    for _ in range(N):
        _acc_gaussian_mf += gaussian_mf(0.5, 0.5, 0.5)
    var _t1_gaussian_mf = perf_counter_ns()
    var _ns_gaussian_mf = Float64(_t1_gaussian_mf - _t0_gaussian_mf) / Float64(N)
    print("MOJO_TIMING fuzzy_logic::gaussian_mf", _ns_gaussian_mf, _acc_gaussian_mf)
    var _acc_fuzzy_and: Float64 = 0.0
    var _t0_fuzzy_and = perf_counter_ns()
    for _ in range(N):
        _acc_fuzzy_and += fuzzy_and(0.5, 0.5)
    var _t1_fuzzy_and = perf_counter_ns()
    var _ns_fuzzy_and = Float64(_t1_fuzzy_and - _t0_fuzzy_and) / Float64(N)
    print("MOJO_TIMING fuzzy_logic::fuzzy_and", _ns_fuzzy_and, _acc_fuzzy_and)
    var _acc_fuzzy_or: Float64 = 0.0
    var _t0_fuzzy_or = perf_counter_ns()
    for _ in range(N):
        _acc_fuzzy_or += fuzzy_or(0.5, 0.5)
    var _t1_fuzzy_or = perf_counter_ns()
    var _ns_fuzzy_or = Float64(_t1_fuzzy_or - _t0_fuzzy_or) / Float64(N)
    print("MOJO_TIMING fuzzy_logic::fuzzy_or", _ns_fuzzy_or, _acc_fuzzy_or)
    var _acc_fuzzy_not: Float64 = 0.0
    var _t0_fuzzy_not = perf_counter_ns()
    for _ in range(N):
        _acc_fuzzy_not += fuzzy_not(0.5)
    var _t1_fuzzy_not = perf_counter_ns()
    var _ns_fuzzy_not = Float64(_t1_fuzzy_not - _t0_fuzzy_not) / Float64(N)
    print("MOJO_TIMING fuzzy_logic::fuzzy_not", _ns_fuzzy_not, _acc_fuzzy_not)
    var _acc_defuzzify_centroid: Float64 = 0.0
    var _t0_defuzzify_centroid = perf_counter_ns()
    for _ in range(N):
        _acc_defuzzify_centroid += defuzzify_centroid(_lf5, _lf5)
    var _t1_defuzzify_centroid = perf_counter_ns()
    var _ns_defuzzify_centroid = Float64(_t1_defuzzify_centroid - _t0_defuzzify_centroid) / Float64(N)
    print("MOJO_TIMING fuzzy_logic::defuzzify_centroid", _ns_defuzzify_centroid, _acc_defuzzify_centroid)
    var _acc_defuzzify_bisector: Float64 = 0.0
    var _t0_defuzzify_bisector = perf_counter_ns()
    for _ in range(N):
        _acc_defuzzify_bisector += defuzzify_bisector(_lf5, _lf5)
    var _t1_defuzzify_bisector = perf_counter_ns()
    var _ns_defuzzify_bisector = Float64(_t1_defuzzify_bisector - _t0_defuzzify_bisector) / Float64(N)
    print("MOJO_TIMING fuzzy_logic::defuzzify_bisector", _ns_defuzzify_bisector, _acc_defuzzify_bisector)
    var _acc_defuzzify_mom: Float64 = 0.0
    var _t0_defuzzify_mom = perf_counter_ns()
    for _ in range(N):
        _acc_defuzzify_mom += defuzzify_mom(_lf5, _lf5)
    var _t1_defuzzify_mom = perf_counter_ns()
    var _ns_defuzzify_mom = Float64(_t1_defuzzify_mom - _t0_defuzzify_mom) / Float64(N)
    print("MOJO_TIMING fuzzy_logic::defuzzify_mom", _ns_defuzzify_mom, _acc_defuzzify_mom)
    var _acc_fuzzy_rule_eval: Float64 = 0.0
    var _t0_fuzzy_rule_eval = perf_counter_ns()
    for _ in range(N):
        _acc_fuzzy_rule_eval += fuzzy_rule_eval(_lf5, 5)
    var _t1_fuzzy_rule_eval = perf_counter_ns()
    var _ns_fuzzy_rule_eval = Float64(_t1_fuzzy_rule_eval - _t0_fuzzy_rule_eval) / Float64(N)
    print("MOJO_TIMING fuzzy_logic::fuzzy_rule_eval", _ns_fuzzy_rule_eval, _acc_fuzzy_rule_eval)
    var _acc_alpha_cut: Float64 = 0.0
    var _t0_alpha_cut = perf_counter_ns()
    for _ in range(N):
        var _r_alpha_cut = alpha_cut(_lf5, _lf5, 0.5)
        _acc_alpha_cut += Float64(len(_r_alpha_cut))
    var _t1_alpha_cut = perf_counter_ns()
    var _ns_alpha_cut = Float64(_t1_alpha_cut - _t0_alpha_cut) / Float64(N)
    print("MOJO_TIMING fuzzy_logic::alpha_cut", _ns_alpha_cut, _acc_alpha_cut)
