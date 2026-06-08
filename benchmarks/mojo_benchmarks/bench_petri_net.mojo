"""bench_petri_net.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from petri_net import is_transition_enabled_2p, fire_transition_2p, token_count_3p, is_deadlocked_1t_2p, is_deadlocked_2t_2p, reachable_from_firing, place_bounded, is_live_transition, coverability_check, incidence_value, siphon_empty_3p, is_transition_enabled_list, fire_transition_list
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

    var _acc_is_transition_enabled_2p: Float64 = 0.0
    var _t0_is_transition_enabled_2p = perf_counter_ns()
    for _ in range(N):
        _acc_is_transition_enabled_2p += Float64(is_transition_enabled_2p(5, 5, 5, 5))
    var _t1_is_transition_enabled_2p = perf_counter_ns()
    var _ns_is_transition_enabled_2p = Float64(_t1_is_transition_enabled_2p - _t0_is_transition_enabled_2p) / Float64(N)
    print("MOJO_TIMING petri_net::is_transition_enabled_2p", _ns_is_transition_enabled_2p, _acc_is_transition_enabled_2p)
    var _result_is_transition_enabled_2p = is_transition_enabled_2p(5, 5, 5, 5)
    var _summary_is_transition_enabled_2p = _summary_bool(_result_is_transition_enabled_2p)
    print("MOJO_RESULT petri_net::is_transition_enabled_2p", _summary_is_transition_enabled_2p)
    var _acc_fire_transition_2p: Float64 = 0.0
    var _t0_fire_transition_2p = perf_counter_ns()
    for _ in range(N):
        _acc_fire_transition_2p += Float64(fire_transition_2p(5, 5, 5, 5, 5, 5))
    var _t1_fire_transition_2p = perf_counter_ns()
    var _ns_fire_transition_2p = Float64(_t1_fire_transition_2p - _t0_fire_transition_2p) / Float64(N)
    print("MOJO_TIMING petri_net::fire_transition_2p", _ns_fire_transition_2p, _acc_fire_transition_2p)
    var _result_fire_transition_2p = fire_transition_2p(5, 5, 5, 5, 5, 5)
    var _summary_fire_transition_2p = _summary_int(_result_fire_transition_2p)
    print("MOJO_RESULT petri_net::fire_transition_2p", _summary_fire_transition_2p)
    var _acc_token_count_3p: Float64 = 0.0
    var _t0_token_count_3p = perf_counter_ns()
    for _ in range(N):
        _acc_token_count_3p += Float64(token_count_3p(5, 5, 5))
    var _t1_token_count_3p = perf_counter_ns()
    var _ns_token_count_3p = Float64(_t1_token_count_3p - _t0_token_count_3p) / Float64(N)
    print("MOJO_TIMING petri_net::token_count_3p", _ns_token_count_3p, _acc_token_count_3p)
    var _result_token_count_3p = token_count_3p(5, 5, 5)
    var _summary_token_count_3p = _summary_int(_result_token_count_3p)
    print("MOJO_RESULT petri_net::token_count_3p", _summary_token_count_3p)
    var _acc_is_deadlocked_1t_2p: Float64 = 0.0
    var _t0_is_deadlocked_1t_2p = perf_counter_ns()
    for _ in range(N):
        _acc_is_deadlocked_1t_2p += Float64(is_deadlocked_1t_2p(5, 5, 5, 5))
    var _t1_is_deadlocked_1t_2p = perf_counter_ns()
    var _ns_is_deadlocked_1t_2p = Float64(_t1_is_deadlocked_1t_2p - _t0_is_deadlocked_1t_2p) / Float64(N)
    print("MOJO_TIMING petri_net::is_deadlocked_1t_2p", _ns_is_deadlocked_1t_2p, _acc_is_deadlocked_1t_2p)
    var _result_is_deadlocked_1t_2p = is_deadlocked_1t_2p(5, 5, 5, 5)
    var _summary_is_deadlocked_1t_2p = _summary_bool(_result_is_deadlocked_1t_2p)
    print("MOJO_RESULT petri_net::is_deadlocked_1t_2p", _summary_is_deadlocked_1t_2p)
    var _acc_is_deadlocked_2t_2p: Float64 = 0.0
    var _t0_is_deadlocked_2t_2p = perf_counter_ns()
    for _ in range(N):
        _acc_is_deadlocked_2t_2p += Float64(is_deadlocked_2t_2p(5, 5, 5, 5, 5, 5))
    var _t1_is_deadlocked_2t_2p = perf_counter_ns()
    var _ns_is_deadlocked_2t_2p = Float64(_t1_is_deadlocked_2t_2p - _t0_is_deadlocked_2t_2p) / Float64(N)
    print("MOJO_TIMING petri_net::is_deadlocked_2t_2p", _ns_is_deadlocked_2t_2p, _acc_is_deadlocked_2t_2p)
    var _result_is_deadlocked_2t_2p = is_deadlocked_2t_2p(5, 5, 5, 5, 5, 5)
    var _summary_is_deadlocked_2t_2p = _summary_bool(_result_is_deadlocked_2t_2p)
    print("MOJO_RESULT petri_net::is_deadlocked_2t_2p", _summary_is_deadlocked_2t_2p)
    var _acc_reachable_from_firing: Float64 = 0.0
    var _t0_reachable_from_firing = perf_counter_ns()
    for _ in range(N):
        _acc_reachable_from_firing += Float64(reachable_from_firing(5, 5, 5))
    var _t1_reachable_from_firing = perf_counter_ns()
    var _ns_reachable_from_firing = Float64(_t1_reachable_from_firing - _t0_reachable_from_firing) / Float64(N)
    print("MOJO_TIMING petri_net::reachable_from_firing", _ns_reachable_from_firing, _acc_reachable_from_firing)
    var _result_reachable_from_firing = reachable_from_firing(5, 5, 5)
    var _summary_reachable_from_firing = _summary_int(_result_reachable_from_firing)
    print("MOJO_RESULT petri_net::reachable_from_firing", _summary_reachable_from_firing)
    var _acc_place_bounded: Float64 = 0.0
    var _t0_place_bounded = perf_counter_ns()
    for _ in range(N):
        _acc_place_bounded += Float64(place_bounded(5, 5))
    var _t1_place_bounded = perf_counter_ns()
    var _ns_place_bounded = Float64(_t1_place_bounded - _t0_place_bounded) / Float64(N)
    print("MOJO_TIMING petri_net::place_bounded", _ns_place_bounded, _acc_place_bounded)
    var _result_place_bounded = place_bounded(5, 5)
    var _summary_place_bounded = _summary_bool(_result_place_bounded)
    print("MOJO_RESULT petri_net::place_bounded", _summary_place_bounded)
    var _acc_is_live_transition: Float64 = 0.0
    var _t0_is_live_transition = perf_counter_ns()
    for _ in range(N):
        _acc_is_live_transition += is_live_transition(5, 5)
    var _t1_is_live_transition = perf_counter_ns()
    var _ns_is_live_transition = Float64(_t1_is_live_transition - _t0_is_live_transition) / Float64(N)
    print("MOJO_TIMING petri_net::is_live_transition", _ns_is_live_transition, _acc_is_live_transition)
    var _result_is_live_transition = is_live_transition(5, 5)
    var _summary_is_live_transition = _summary_float64(_result_is_live_transition)
    print("MOJO_RESULT petri_net::is_live_transition", _summary_is_live_transition)
    var _acc_coverability_check: Float64 = 0.0
    var _t0_coverability_check = perf_counter_ns()
    for _ in range(N):
        _acc_coverability_check += Float64(coverability_check(5, 5))
    var _t1_coverability_check = perf_counter_ns()
    var _ns_coverability_check = Float64(_t1_coverability_check - _t0_coverability_check) / Float64(N)
    print("MOJO_TIMING petri_net::coverability_check", _ns_coverability_check, _acc_coverability_check)
    var _result_coverability_check = coverability_check(5, 5)
    var _summary_coverability_check = _summary_bool(_result_coverability_check)
    print("MOJO_RESULT petri_net::coverability_check", _summary_coverability_check)
    var _acc_incidence_value: Float64 = 0.0
    var _t0_incidence_value = perf_counter_ns()
    for _ in range(N):
        _acc_incidence_value += Float64(incidence_value(5, 5))
    var _t1_incidence_value = perf_counter_ns()
    var _ns_incidence_value = Float64(_t1_incidence_value - _t0_incidence_value) / Float64(N)
    print("MOJO_TIMING petri_net::incidence_value", _ns_incidence_value, _acc_incidence_value)
    var _result_incidence_value = incidence_value(5, 5)
    var _summary_incidence_value = _summary_int(_result_incidence_value)
    print("MOJO_RESULT petri_net::incidence_value", _summary_incidence_value)
    var _acc_siphon_empty_3p: Float64 = 0.0
    var _t0_siphon_empty_3p = perf_counter_ns()
    for _ in range(N):
        _acc_siphon_empty_3p += Float64(siphon_empty_3p(5, 5, 5, True, True, True))
    var _t1_siphon_empty_3p = perf_counter_ns()
    var _ns_siphon_empty_3p = Float64(_t1_siphon_empty_3p - _t0_siphon_empty_3p) / Float64(N)
    print("MOJO_TIMING petri_net::siphon_empty_3p", _ns_siphon_empty_3p, _acc_siphon_empty_3p)
    var _result_siphon_empty_3p = siphon_empty_3p(5, 5, 5, True, True, True)
    var _summary_siphon_empty_3p = _summary_bool(_result_siphon_empty_3p)
    print("MOJO_RESULT petri_net::siphon_empty_3p", _summary_siphon_empty_3p)
    var _acc_is_transition_enabled_list: Float64 = 0.0
    var _t0_is_transition_enabled_list = perf_counter_ns()
    for _ in range(N):
        _acc_is_transition_enabled_list += Float64(is_transition_enabled_list(_li5, _li5, 5))
    var _t1_is_transition_enabled_list = perf_counter_ns()
    var _ns_is_transition_enabled_list = Float64(_t1_is_transition_enabled_list - _t0_is_transition_enabled_list) / Float64(N)
    print("MOJO_TIMING petri_net::is_transition_enabled_list", _ns_is_transition_enabled_list, _acc_is_transition_enabled_list)
    var _result_is_transition_enabled_list = is_transition_enabled_list(_li5, _li5, 5)
    var _summary_is_transition_enabled_list = _summary_bool(_result_is_transition_enabled_list)
    print("MOJO_RESULT petri_net::is_transition_enabled_list", _summary_is_transition_enabled_list)
    var _acc_fire_transition_list: Float64 = 0.0
    var _t0_fire_transition_list = perf_counter_ns()
    for _ in range(N):
        _acc_fire_transition_list += Float64(fire_transition_list(_li5, _li5, _li5, 5))
    var _t1_fire_transition_list = perf_counter_ns()
    var _ns_fire_transition_list = Float64(_t1_fire_transition_list - _t0_fire_transition_list) / Float64(N)
    print("MOJO_TIMING petri_net::fire_transition_list", _ns_fire_transition_list, _acc_fire_transition_list)
    var _result_fire_transition_list = fire_transition_list(_li5, _li5, _li5, 5)
    var _summary_fire_transition_list = _summary_int(_result_fire_transition_list)
    print("MOJO_RESULT petri_net::fire_transition_list", _summary_fire_transition_list)
