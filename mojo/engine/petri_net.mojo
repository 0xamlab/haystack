"""
petri_net.mojo — Petri Net Simulation Library. Zero Python imports.

Provides functions for modelling and analysing Petri nets including
transition firing, deadlock detection, boundedness, coverability,
siphon checking, and incidence computation.

Public API (scalar-friendly for small nets):
  is_transition_enabled_2p   — Check if transition can fire (2-place net)
  fire_transition_2p         — Fire transition in 2-place net
  token_count_3p             — Total tokens in 3-place net
  is_deadlocked_1t_2p        — Check deadlock for 1-transition 2-place net
  reachable_from_firing      — New total tokens after firing
  place_bounded              — Check if place never exceeds bound
  is_live_transition         — Liveness ratio
  coverability_check         — Check if marking covers target
  incidence_value            — Net effect of transition on a place
  siphon_empty_3p            — Check if siphon is empty (3-place)
  is_transition_enabled_list — Generic list-based check
  fire_transition_list       — Generic list-based fire
"""


# ── is_transition_enabled_2p ─────────────────────────────────────────────────


fn is_transition_enabled_2p(
    m0: Int, m1: Int, in0: Int, in1: Int
) -> Bool:
    """Check if transition can fire in a 2-place net.
    m0, m1 = tokens in places 0, 1.
    in0, in1 = input arc weights.
    """
    return m0 >= in0 and m1 >= in1


# ── fire_transition_2p ───────────────────────────────────────────────────────


fn fire_transition_2p(
    m0: Int, m1: Int,
    in0: Int, in1: Int,
    out0: Int, out1: Int,
) -> Int:
    """Fire transition in 2-place net. Returns new marking sum."""
    var new0 = m0 - in0 + out0
    var new1 = m1 - in1 + out1
    return new0 + new1


# ── token_count_3p ───────────────────────────────────────────────────────────


fn token_count_3p(m0: Int, m1: Int, m2: Int) -> Int:
    """Total tokens in a 3-place net."""
    return m0 + m1 + m2


# ── is_deadlocked_1t_2p ─────────────────────────────────────────────────────


fn is_deadlocked_1t_2p(m0: Int, m1: Int, in0: Int, in1: Int) -> Bool:
    """Check deadlock for 1-transition 2-place net.
    Deadlocked if the single transition is NOT enabled.
    """
    return not is_transition_enabled_2p(m0, m1, in0, in1)


# ── is_deadlocked_2t_2p ─────────────────────────────────────────────────────


fn is_deadlocked_2t_2p(
    m0: Int, m1: Int,
    t0_in0: Int, t0_in1: Int,
    t1_in0: Int, t1_in1: Int,
) -> Bool:
    """Check deadlock for 2-transition 2-place net.
    Deadlocked if NEITHER transition is enabled.
    """
    var t0_ok = m0 >= t0_in0 and m1 >= t0_in1
    var t1_ok = m0 >= t1_in0 and m1 >= t1_in1
    return not t0_ok and not t1_ok


# ── reachable_from_firing ────────────────────────────────────────────────────


fn reachable_from_firing(
    marking_sum: Int, input_sum: Int, output_sum: Int
) -> Int:
    """New total tokens after firing = marking_sum - input_sum + output_sum."""
    return marking_sum - input_sum + output_sum


# ── place_bounded ────────────────────────────────────────────────────────────


fn place_bounded(max_tokens: Int, bound: Int) -> Bool:
    """Check if a place never exceeds its bound."""
    return max_tokens <= bound


# ── is_live_transition ───────────────────────────────────────────────────────


fn is_live_transition(enabled_count: Int, total_markings: Int) -> Float64:
    """Ratio of markings where transition is enabled (liveness metric)."""
    if total_markings == 0:
        return 0.0
    return Float64(enabled_count) / Float64(total_markings)


# ── coverability_check ───────────────────────────────────────────────────────


fn coverability_check(marking_val: Int, target_val: Int) -> Bool:
    """Check if marking covers (>=) target for a single place."""
    return marking_val >= target_val


# ── incidence_value ──────────────────────────────────────────────────────────


fn incidence_value(output_weight: Int, input_weight: Int) -> Int:
    """Net effect of transition on a place = output_weight - input_weight."""
    return output_weight - input_weight


# ── siphon_empty_3p ──────────────────────────────────────────────────────────


fn siphon_empty_3p(
    t0: Int, t1: Int, t2: Int,
    s0: Bool, s1: Bool, s2: Bool,
) -> Bool:
    """Check if siphon is empty in a 3-place net.
    ti = tokens in place i, si = whether place i is a siphon member.
    Returns True if all siphon member places have 0 tokens.
    """
    if s0 and t0 > 0:
        return False
    if s1 and t1 > 0:
        return False
    if s2 and t2 > 0:
        return False
    return True


# ── Generic list-based variants ──────────────────────────────────────────────


fn is_transition_enabled_list(
    marking: List[Int], input_arcs: List[Int], n_places: Int
) -> Bool:
    """Check if transition can fire (all input places have enough tokens)."""
    for i in range(n_places):
        if marking[i] < input_arcs[i]:
            return False
    return True


fn fire_transition_list(
    marking: List[Int],
    input_arcs: List[Int],
    output_arcs: List[Int],
    n_places: Int,
) -> Int:
    """Fire transition: subtract inputs, add outputs. Returns new marking sum."""
    var total: Int = 0
    for i in range(n_places):
        var new_val: Int = marking[i] - input_arcs[i] + output_arcs[i]
        total += new_val
    return total
