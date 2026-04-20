"""bench_petri_net.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from petri_net import is_transition_enabled_2p, fire_transition_2p, token_count_3p, is_deadlocked_1t_2p, is_deadlocked_2t_2p, reachable_from_firing, place_bounded, is_live_transition, coverability_check, incidence_value, siphon_empty_3p, is_transition_enabled_list, fire_transition_list
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

    var _acc_is_transition_enabled_2p: Float64 = 0.0
    var _t0_is_transition_enabled_2p = perf_counter_ns()
    for _ in range(N):
        _acc_is_transition_enabled_2p += Float64(is_transition_enabled_2p(5, 5, 5, 5))
    var _t1_is_transition_enabled_2p = perf_counter_ns()
    var _ns_is_transition_enabled_2p = Float64(_t1_is_transition_enabled_2p - _t0_is_transition_enabled_2p) / Float64(N)
    print("MOJO_TIMING petri_net::is_transition_enabled_2p", _ns_is_transition_enabled_2p, _acc_is_transition_enabled_2p)
    var _acc_fire_transition_2p: Float64 = 0.0
    var _t0_fire_transition_2p = perf_counter_ns()
    for _ in range(N):
        _acc_fire_transition_2p += Float64(fire_transition_2p(5, 5, 5, 5, 5, 5))
    var _t1_fire_transition_2p = perf_counter_ns()
    var _ns_fire_transition_2p = Float64(_t1_fire_transition_2p - _t0_fire_transition_2p) / Float64(N)
    print("MOJO_TIMING petri_net::fire_transition_2p", _ns_fire_transition_2p, _acc_fire_transition_2p)
    var _acc_token_count_3p: Float64 = 0.0
    var _t0_token_count_3p = perf_counter_ns()
    for _ in range(N):
        _acc_token_count_3p += Float64(token_count_3p(5, 5, 5))
    var _t1_token_count_3p = perf_counter_ns()
    var _ns_token_count_3p = Float64(_t1_token_count_3p - _t0_token_count_3p) / Float64(N)
    print("MOJO_TIMING petri_net::token_count_3p", _ns_token_count_3p, _acc_token_count_3p)
    var _acc_is_deadlocked_1t_2p: Float64 = 0.0
    var _t0_is_deadlocked_1t_2p = perf_counter_ns()
    for _ in range(N):
        _acc_is_deadlocked_1t_2p += Float64(is_deadlocked_1t_2p(5, 5, 5, 5))
    var _t1_is_deadlocked_1t_2p = perf_counter_ns()
    var _ns_is_deadlocked_1t_2p = Float64(_t1_is_deadlocked_1t_2p - _t0_is_deadlocked_1t_2p) / Float64(N)
    print("MOJO_TIMING petri_net::is_deadlocked_1t_2p", _ns_is_deadlocked_1t_2p, _acc_is_deadlocked_1t_2p)
    var _acc_is_deadlocked_2t_2p: Float64 = 0.0
    var _t0_is_deadlocked_2t_2p = perf_counter_ns()
    for _ in range(N):
        _acc_is_deadlocked_2t_2p += Float64(is_deadlocked_2t_2p(5, 5, 5, 5, 5, 5))
    var _t1_is_deadlocked_2t_2p = perf_counter_ns()
    var _ns_is_deadlocked_2t_2p = Float64(_t1_is_deadlocked_2t_2p - _t0_is_deadlocked_2t_2p) / Float64(N)
    print("MOJO_TIMING petri_net::is_deadlocked_2t_2p", _ns_is_deadlocked_2t_2p, _acc_is_deadlocked_2t_2p)
    var _acc_reachable_from_firing: Float64 = 0.0
    var _t0_reachable_from_firing = perf_counter_ns()
    for _ in range(N):
        _acc_reachable_from_firing += Float64(reachable_from_firing(5, 5, 5))
    var _t1_reachable_from_firing = perf_counter_ns()
    var _ns_reachable_from_firing = Float64(_t1_reachable_from_firing - _t0_reachable_from_firing) / Float64(N)
    print("MOJO_TIMING petri_net::reachable_from_firing", _ns_reachable_from_firing, _acc_reachable_from_firing)
    var _acc_place_bounded: Float64 = 0.0
    var _t0_place_bounded = perf_counter_ns()
    for _ in range(N):
        _acc_place_bounded += Float64(place_bounded(5, 5))
    var _t1_place_bounded = perf_counter_ns()
    var _ns_place_bounded = Float64(_t1_place_bounded - _t0_place_bounded) / Float64(N)
    print("MOJO_TIMING petri_net::place_bounded", _ns_place_bounded, _acc_place_bounded)
    var _acc_is_live_transition: Float64 = 0.0
    var _t0_is_live_transition = perf_counter_ns()
    for _ in range(N):
        _acc_is_live_transition += is_live_transition(5, 5)
    var _t1_is_live_transition = perf_counter_ns()
    var _ns_is_live_transition = Float64(_t1_is_live_transition - _t0_is_live_transition) / Float64(N)
    print("MOJO_TIMING petri_net::is_live_transition", _ns_is_live_transition, _acc_is_live_transition)
    var _acc_coverability_check: Float64 = 0.0
    var _t0_coverability_check = perf_counter_ns()
    for _ in range(N):
        _acc_coverability_check += Float64(coverability_check(5, 5))
    var _t1_coverability_check = perf_counter_ns()
    var _ns_coverability_check = Float64(_t1_coverability_check - _t0_coverability_check) / Float64(N)
    print("MOJO_TIMING petri_net::coverability_check", _ns_coverability_check, _acc_coverability_check)
    var _acc_incidence_value: Float64 = 0.0
    var _t0_incidence_value = perf_counter_ns()
    for _ in range(N):
        _acc_incidence_value += Float64(incidence_value(5, 5))
    var _t1_incidence_value = perf_counter_ns()
    var _ns_incidence_value = Float64(_t1_incidence_value - _t0_incidence_value) / Float64(N)
    print("MOJO_TIMING petri_net::incidence_value", _ns_incidence_value, _acc_incidence_value)
    var _acc_siphon_empty_3p: Float64 = 0.0
    var _t0_siphon_empty_3p = perf_counter_ns()
    for _ in range(N):
        _acc_siphon_empty_3p += Float64(siphon_empty_3p(5, 5, 5, True, True, True))
    var _t1_siphon_empty_3p = perf_counter_ns()
    var _ns_siphon_empty_3p = Float64(_t1_siphon_empty_3p - _t0_siphon_empty_3p) / Float64(N)
    print("MOJO_TIMING petri_net::siphon_empty_3p", _ns_siphon_empty_3p, _acc_siphon_empty_3p)
    var _acc_is_transition_enabled_list: Float64 = 0.0
    var _t0_is_transition_enabled_list = perf_counter_ns()
    for _ in range(N):
        _acc_is_transition_enabled_list += Float64(is_transition_enabled_list(_li5, _li5, 5))
    var _t1_is_transition_enabled_list = perf_counter_ns()
    var _ns_is_transition_enabled_list = Float64(_t1_is_transition_enabled_list - _t0_is_transition_enabled_list) / Float64(N)
    print("MOJO_TIMING petri_net::is_transition_enabled_list", _ns_is_transition_enabled_list, _acc_is_transition_enabled_list)
    var _acc_fire_transition_list: Float64 = 0.0
    var _t0_fire_transition_list = perf_counter_ns()
    for _ in range(N):
        _acc_fire_transition_list += Float64(fire_transition_list(_li5, _li5, _li5, 5))
    var _t1_fire_transition_list = perf_counter_ns()
    var _ns_fire_transition_list = Float64(_t1_fire_transition_list - _t0_fire_transition_list) / Float64(N)
    print("MOJO_TIMING petri_net::fire_transition_list", _ns_fire_transition_list, _acc_fire_transition_list)
