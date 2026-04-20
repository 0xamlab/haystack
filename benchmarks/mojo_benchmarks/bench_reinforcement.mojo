"""bench_reinforcement.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from reinforcement import epsilon_greedy_action, q_learning, sarsa, value_iteration, policy_from_q, policy_evaluation, td_error, discounted_return
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

    var _acc_epsilon_greedy_action: Float64 = 0.0
    var _t0_epsilon_greedy_action = perf_counter_ns()
    for _ in range(N):
        _acc_epsilon_greedy_action += Float64(epsilon_greedy_action(_lf5, 0.5))
    var _t1_epsilon_greedy_action = perf_counter_ns()
    var _ns_epsilon_greedy_action = Float64(_t1_epsilon_greedy_action - _t0_epsilon_greedy_action) / Float64(N)
    print("MOJO_TIMING reinforcement::epsilon_greedy_action", _ns_epsilon_greedy_action, _acc_epsilon_greedy_action)
    var _acc_q_learning: Float64 = 0.0
    var _t0_q_learning = perf_counter_ns()
    for _ in range(N):
        var _r_q_learning = q_learning(5, 5, [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0,1,1],[1,0,1],[1,1,0]], 0.5, 0.5, 0.5, 5)
        _acc_q_learning += Float64(len(_r_q_learning))
    var _t1_q_learning = perf_counter_ns()
    var _ns_q_learning = Float64(_t1_q_learning - _t0_q_learning) / Float64(N)
    print("MOJO_TIMING reinforcement::q_learning", _ns_q_learning, _acc_q_learning)
    var _acc_sarsa: Float64 = 0.0
    var _t0_sarsa = perf_counter_ns()
    for _ in range(N):
        var _r_sarsa = sarsa(5, 5, [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0,1,1],[1,0,1],[1,1,0]], 0.5, 0.5, 0.5, 5)
        _acc_sarsa += Float64(len(_r_sarsa))
    var _t1_sarsa = perf_counter_ns()
    var _ns_sarsa = Float64(_t1_sarsa - _t0_sarsa) / Float64(N)
    print("MOJO_TIMING reinforcement::sarsa", _ns_sarsa, _acc_sarsa)
    var _acc_value_iteration: Float64 = 0.0
    var _t0_value_iteration = perf_counter_ns()
    for _ in range(N):
        var _r_value_iteration = value_iteration(5, 5, [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0,1,1],[1,0,1],[1,1,0]], 0.5, 0.5)
        _acc_value_iteration += Float64(len(_r_value_iteration))
    var _t1_value_iteration = perf_counter_ns()
    var _ns_value_iteration = Float64(_t1_value_iteration - _t0_value_iteration) / Float64(N)
    print("MOJO_TIMING reinforcement::value_iteration", _ns_value_iteration, _acc_value_iteration)
    var _acc_policy_from_q: Float64 = 0.0
    var _t0_policy_from_q = perf_counter_ns()
    for _ in range(N):
        var _r_policy_from_q = policy_from_q([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_policy_from_q += Float64(len(_r_policy_from_q))
    var _t1_policy_from_q = perf_counter_ns()
    var _ns_policy_from_q = Float64(_t1_policy_from_q - _t0_policy_from_q) / Float64(N)
    print("MOJO_TIMING reinforcement::policy_from_q", _ns_policy_from_q, _acc_policy_from_q)
    var _acc_policy_evaluation: Float64 = 0.0
    var _t0_policy_evaluation = perf_counter_ns()
    for _ in range(N):
        var _r_policy_evaluation = policy_evaluation(_li5, 5, [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0,1,1],[1,0,1],[1,1,0]], 0.5, 0.5)
        _acc_policy_evaluation += Float64(len(_r_policy_evaluation))
    var _t1_policy_evaluation = perf_counter_ns()
    var _ns_policy_evaluation = Float64(_t1_policy_evaluation - _t0_policy_evaluation) / Float64(N)
    print("MOJO_TIMING reinforcement::policy_evaluation", _ns_policy_evaluation, _acc_policy_evaluation)
    var _acc_td_error: Float64 = 0.0
    var _t0_td_error = perf_counter_ns()
    for _ in range(N):
        _acc_td_error += td_error(0.5, 0.5, 0.5, 0.5)
    var _t1_td_error = perf_counter_ns()
    var _ns_td_error = Float64(_t1_td_error - _t0_td_error) / Float64(N)
    print("MOJO_TIMING reinforcement::td_error", _ns_td_error, _acc_td_error)
    var _acc_discounted_return: Float64 = 0.0
    var _t0_discounted_return = perf_counter_ns()
    for _ in range(N):
        _acc_discounted_return += discounted_return(_lf5, 0.5)
    var _t1_discounted_return = perf_counter_ns()
    var _ns_discounted_return = Float64(_t1_discounted_return - _t0_discounted_return) / Float64(N)
    print("MOJO_TIMING reinforcement::discounted_return", _ns_discounted_return, _acc_discounted_return)
