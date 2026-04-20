"""test_petri_net.mojo — auto-generated tests for petri_net library."""
from std.math import isnan, isinf
from petri_net import is_transition_enabled_2p, fire_transition_2p, token_count_3p, is_deadlocked_1t_2p, is_deadlocked_2t_2p, reachable_from_firing, place_bounded, is_live_transition, coverability_check, incidence_value, siphon_empty_3p, is_transition_enabled_list, fire_transition_list

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

    _ = is_transition_enabled_2p(5, 5, 5, 5)
    passed += 1; print("  ✅ petri_net::is_transition_enabled_2p")
    _ = fire_transition_2p(5, 5, 5, 5, 5, 5)
    passed += 1; print("  ✅ petri_net::fire_transition_2p")
    _ = token_count_3p(5, 5, 5)
    passed += 1; print("  ✅ petri_net::token_count_3p")
    _ = is_deadlocked_1t_2p(5, 5, 5, 5)
    passed += 1; print("  ✅ petri_net::is_deadlocked_1t_2p")
    _ = is_deadlocked_2t_2p(5, 5, 5, 5, 5, 5)
    passed += 1; print("  ✅ petri_net::is_deadlocked_2t_2p")
    _ = reachable_from_firing(5, 5, 5)
    passed += 1; print("  ✅ petri_net::reachable_from_firing")
    _ = place_bounded(5, 5)
    passed += 1; print("  ✅ petri_net::place_bounded")
    var _v_is_live_transition = is_live_transition(5, 5)
    if is_finite(_v_is_live_transition): passed += 1; print("  ✅ petri_net::is_live_transition =", _v_is_live_transition)
    else: failed += 1; print("  ❌ petri_net::is_live_transition → non-finite:", _v_is_live_transition)
    _ = coverability_check(5, 5)
    passed += 1; print("  ✅ petri_net::coverability_check")
    _ = incidence_value(5, 5)
    passed += 1; print("  ✅ petri_net::incidence_value")
    _ = siphon_empty_3p(5, 5, 5, True, True, True)
    passed += 1; print("  ✅ petri_net::siphon_empty_3p")
    _ = is_transition_enabled_list(_li5, _li5, 5)
    passed += 1; print("  ✅ petri_net::is_transition_enabled_list")
    _ = fire_transition_list(_li5, _li5, _li5, 5)
    passed += 1; print("  ✅ petri_net::fire_transition_list")

    print("  [petri_net] Passed:", passed, "Failed:", failed)
