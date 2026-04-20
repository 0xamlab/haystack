"""bench_boolean_algebra.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from boolean_algebra import bool_and, bool_or, bool_not, bool_xor, bool_implies, bool_iff, truth_table_2, eval_dnf, eval_cnf, is_tautology_2var, count_satisfying_2var, majority_vote, parity
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

    var _acc_bool_and: Float64 = 0.0
    var _t0_bool_and = perf_counter_ns()
    for _ in range(N):
        _acc_bool_and += Float64(bool_and(True, True))
    var _t1_bool_and = perf_counter_ns()
    var _ns_bool_and = Float64(_t1_bool_and - _t0_bool_and) / Float64(N)
    print("MOJO_TIMING boolean_algebra::bool_and", _ns_bool_and, _acc_bool_and)
    var _acc_bool_or: Float64 = 0.0
    var _t0_bool_or = perf_counter_ns()
    for _ in range(N):
        _acc_bool_or += Float64(bool_or(True, True))
    var _t1_bool_or = perf_counter_ns()
    var _ns_bool_or = Float64(_t1_bool_or - _t0_bool_or) / Float64(N)
    print("MOJO_TIMING boolean_algebra::bool_or", _ns_bool_or, _acc_bool_or)
    var _acc_bool_not: Float64 = 0.0
    var _t0_bool_not = perf_counter_ns()
    for _ in range(N):
        _acc_bool_not += Float64(bool_not(True))
    var _t1_bool_not = perf_counter_ns()
    var _ns_bool_not = Float64(_t1_bool_not - _t0_bool_not) / Float64(N)
    print("MOJO_TIMING boolean_algebra::bool_not", _ns_bool_not, _acc_bool_not)
    var _acc_bool_xor: Float64 = 0.0
    var _t0_bool_xor = perf_counter_ns()
    for _ in range(N):
        _acc_bool_xor += Float64(bool_xor(True, True))
    var _t1_bool_xor = perf_counter_ns()
    var _ns_bool_xor = Float64(_t1_bool_xor - _t0_bool_xor) / Float64(N)
    print("MOJO_TIMING boolean_algebra::bool_xor", _ns_bool_xor, _acc_bool_xor)
    var _acc_bool_implies: Float64 = 0.0
    var _t0_bool_implies = perf_counter_ns()
    for _ in range(N):
        _acc_bool_implies += Float64(bool_implies(True, True))
    var _t1_bool_implies = perf_counter_ns()
    var _ns_bool_implies = Float64(_t1_bool_implies - _t0_bool_implies) / Float64(N)
    print("MOJO_TIMING boolean_algebra::bool_implies", _ns_bool_implies, _acc_bool_implies)
    var _acc_bool_iff: Float64 = 0.0
    var _t0_bool_iff = perf_counter_ns()
    for _ in range(N):
        _acc_bool_iff += Float64(bool_iff(True, True))
    var _t1_bool_iff = perf_counter_ns()
    var _ns_bool_iff = Float64(_t1_bool_iff - _t0_bool_iff) / Float64(N)
    print("MOJO_TIMING boolean_algebra::bool_iff", _ns_bool_iff, _acc_bool_iff)
    var _acc_truth_table_2: Float64 = 0.0
    var _t0_truth_table_2 = perf_counter_ns()
    for _ in range(N):
        var _r_truth_table_2 = truth_table_2(5)
        _acc_truth_table_2 += Float64(len(_r_truth_table_2))
    var _t1_truth_table_2 = perf_counter_ns()
    var _ns_truth_table_2 = Float64(_t1_truth_table_2 - _t0_truth_table_2) / Float64(N)
    print("MOJO_TIMING boolean_algebra::truth_table_2", _ns_truth_table_2, _acc_truth_table_2)
    var _acc_eval_dnf: Float64 = 0.0
    var _t0_eval_dnf = perf_counter_ns()
    for _ in range(N):
        _acc_eval_dnf += Float64(eval_dnf(_lb5, [[0,1,1],[1,0,1],[1,1,0]]))
    var _t1_eval_dnf = perf_counter_ns()
    var _ns_eval_dnf = Float64(_t1_eval_dnf - _t0_eval_dnf) / Float64(N)
    print("MOJO_TIMING boolean_algebra::eval_dnf", _ns_eval_dnf, _acc_eval_dnf)
    var _acc_eval_cnf: Float64 = 0.0
    var _t0_eval_cnf = perf_counter_ns()
    for _ in range(N):
        _acc_eval_cnf += Float64(eval_cnf(_lb5, [[0,1,1],[1,0,1],[1,1,0]]))
    var _t1_eval_cnf = perf_counter_ns()
    var _ns_eval_cnf = Float64(_t1_eval_cnf - _t0_eval_cnf) / Float64(N)
    print("MOJO_TIMING boolean_algebra::eval_cnf", _ns_eval_cnf, _acc_eval_cnf)
    var _acc_is_tautology_2var: Float64 = 0.0
    var _t0_is_tautology_2var = perf_counter_ns()
    for _ in range(N):
        _acc_is_tautology_2var += Float64(is_tautology_2var(5))
    var _t1_is_tautology_2var = perf_counter_ns()
    var _ns_is_tautology_2var = Float64(_t1_is_tautology_2var - _t0_is_tautology_2var) / Float64(N)
    print("MOJO_TIMING boolean_algebra::is_tautology_2var", _ns_is_tautology_2var, _acc_is_tautology_2var)
    var _acc_count_satisfying_2var: Float64 = 0.0
    var _t0_count_satisfying_2var = perf_counter_ns()
    for _ in range(N):
        _acc_count_satisfying_2var += Float64(count_satisfying_2var(5))
    var _t1_count_satisfying_2var = perf_counter_ns()
    var _ns_count_satisfying_2var = Float64(_t1_count_satisfying_2var - _t0_count_satisfying_2var) / Float64(N)
    print("MOJO_TIMING boolean_algebra::count_satisfying_2var", _ns_count_satisfying_2var, _acc_count_satisfying_2var)
    var _acc_majority_vote: Float64 = 0.0
    var _t0_majority_vote = perf_counter_ns()
    for _ in range(N):
        _acc_majority_vote += Float64(majority_vote(_lb5))
    var _t1_majority_vote = perf_counter_ns()
    var _ns_majority_vote = Float64(_t1_majority_vote - _t0_majority_vote) / Float64(N)
    print("MOJO_TIMING boolean_algebra::majority_vote", _ns_majority_vote, _acc_majority_vote)
    var _acc_parity: Float64 = 0.0
    var _t0_parity = perf_counter_ns()
    for _ in range(N):
        _acc_parity += Float64(parity(_lb5))
    var _t1_parity = perf_counter_ns()
    var _ns_parity = Float64(_t1_parity - _t0_parity) / Float64(N)
    print("MOJO_TIMING boolean_algebra::parity", _ns_parity, _acc_parity)
