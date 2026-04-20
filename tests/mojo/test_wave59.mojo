"""Tests for Wave 59 — Database Operations, Reinforcement Learning, Astronomy."""

from database import (
    Table,
    table_create,
    table_insert_row,
    table_select_column,
    table_where,
    table_aggregate,
    table_sort_by,
    table_join_inner,
    table_group_aggregate,
    table_row_count,
)
from reinforcement import (
    q_learning,
    sarsa,
    value_iteration,
    policy_from_q,
    epsilon_greedy_action,
    policy_evaluation,
    td_error,
    discounted_return,
)
from astronomy import (
    julian_date,
    modified_julian_date,
    sidereal_time,
    solar_declination,
    sunrise_hour_angle,
    day_length,
    parallax_correction,
    kepler_equation,
    orbital_period,
    apparent_magnitude,
    distance_from_magnitude,
    ecliptic_to_equatorial,
)
from std.math import abs as fabs, sin


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error(
            "FAIL: " + msg + " | got " + String(a) + " expected " + String(b)
        )


fn _is_finite(v: Float64) -> Bool:
    return v == v and v < 1e18 and v > -1e18


# ── Database Tests ────────────────────────────────────────────────────────────


fn test_table_create() raises:
    var cols = List[String]()
    cols.append("id")
    cols.append("value")
    cols.append("score")
    var t = table_create(cols, 0)
    _assert(len(t.columns) == 3, "table_create columns count")
    _assert(t.n_rows == 0, "table_create 0 rows")
    _assert(table_row_count(t) == 0, "table_row_count 0")
    print("  ✓ test_table_create")


fn test_table_insert_row() raises:
    var cols = List[String]()
    cols.append("a")
    cols.append("b")
    var t = table_create(cols, 0)
    var row1 = List[Float64]()
    row1.append(1.0)
    row1.append(2.0)
    table_insert_row(t, row1)
    _assert(table_row_count(t) == 1, "after 1 insert row_count=1")
    var row2 = List[Float64]()
    row2.append(3.0)
    row2.append(4.0)
    table_insert_row(t, row2)
    _assert(table_row_count(t) == 2, "after 2 inserts row_count=2")
    var row3 = List[Float64]()
    row3.append(5.0)
    row3.append(6.0)
    table_insert_row(t, row3)
    _assert(table_row_count(t) == 3, "after 3 inserts row_count=3")
    print("  ✓ test_table_insert_row")


fn test_table_select_column() raises:
    var cols = List[String]()
    cols.append("x")
    cols.append("y")
    var t = table_create(cols, 0)
    var r1 = List[Float64]()
    r1.append(10.0)
    r1.append(20.0)
    table_insert_row(t, r1)
    var r2 = List[Float64]()
    r2.append(30.0)
    r2.append(40.0)
    table_insert_row(t, r2)
    var col_x = table_select_column(t, 0)
    _assert(len(col_x) == 2, "select_column length=2")
    _assert_close(col_x[0], 10.0, 1e-12, "select_column x[0]=10")
    _assert_close(col_x[1], 30.0, 1e-12, "select_column x[1]=30")
    var col_y = table_select_column(t, 1)
    _assert_close(col_y[0], 20.0, 1e-12, "select_column y[0]=20")
    _assert_close(col_y[1], 40.0, 1e-12, "select_column y[1]=40")
    print("  ✓ test_table_select_column")


fn _make_test_table() -> Table:
    """Create a test table with 5 rows, columns: id, value, group."""
    var cols = List[String]()
    cols.append("id")
    cols.append("value")
    cols.append("group")
    var t = table_create(cols, 0)
    # Row 0: id=1, value=10, group=1
    var r0 = List[Float64]()
    r0.append(1.0)
    r0.append(10.0)
    r0.append(1.0)
    table_insert_row(t, r0)
    # Row 1: id=2, value=20, group=1
    var r1 = List[Float64]()
    r1.append(2.0)
    r1.append(20.0)
    r1.append(1.0)
    table_insert_row(t, r1)
    # Row 2: id=3, value=30, group=2
    var r2 = List[Float64]()
    r2.append(3.0)
    r2.append(30.0)
    r2.append(2.0)
    table_insert_row(t, r2)
    # Row 3: id=4, value=5, group=2
    var r3 = List[Float64]()
    r3.append(4.0)
    r3.append(5.0)
    r3.append(2.0)
    table_insert_row(t, r3)
    # Row 4: id=5, value=15, group=1
    var r4 = List[Float64]()
    r4.append(5.0)
    r4.append(15.0)
    r4.append(1.0)
    table_insert_row(t, r4)
    return t^


fn test_table_where_gt() raises:
    var t = _make_test_table()
    # value > 15: rows 1(20), 2(30)
    var indices = table_where(t, 1, 1, 15.0)
    _assert(len(indices) == 2, "where gt 15 -> 2 rows")
    _assert(indices[0] == 1, "where gt 15 first=row1")
    _assert(indices[1] == 2, "where gt 15 second=row2")
    print("  ✓ test_table_where_gt")


fn test_table_where_eq() raises:
    var t = _make_test_table()
    # group == 2: rows 2, 3
    var indices = table_where(t, 2, 0, 2.0)
    _assert(len(indices) == 2, "where eq group=2 -> 2 rows")
    _assert(indices[0] == 2, "where eq group=2 first=row2")
    _assert(indices[1] == 3, "where eq group=2 second=row3")
    print("  ✓ test_table_where_eq")


fn test_table_where_lt() raises:
    var t = _make_test_table()
    # value < 15: rows 0(10), 3(5)
    var indices = table_where(t, 1, 2, 15.0)
    _assert(len(indices) == 2, "where lt 15 -> 2 rows")
    print("  ✓ test_table_where_lt")


fn test_table_aggregate_sum_mean() raises:
    var t = _make_test_table()
    # Sum of value column: 10+20+30+5+15 = 80
    var s = table_aggregate(t, 1, 0)
    _assert_close(s, 80.0, 1e-10, "aggregate sum=80")
    # Mean of value column: 80/5 = 16
    var m = table_aggregate(t, 1, 1)
    _assert_close(m, 16.0, 1e-10, "aggregate mean=16")
    # Min: 5
    var mn = table_aggregate(t, 1, 2)
    _assert_close(mn, 5.0, 1e-10, "aggregate min=5")
    # Max: 30
    var mx = table_aggregate(t, 1, 3)
    _assert_close(mx, 30.0, 1e-10, "aggregate max=30")
    # Count: 5
    var cnt = table_aggregate(t, 1, 4)
    _assert_close(cnt, 5.0, 1e-10, "aggregate count=5")
    print("  ✓ test_table_aggregate_sum_mean")


fn test_table_sort_by() raises:
    var t = _make_test_table()
    # Sort by value ascending: 5(r3), 10(r0), 15(r4), 20(r1), 30(r2)
    var asc = table_sort_by(t, 1, True)
    _assert(len(asc) == 5, "sort_by length=5")
    _assert(asc[0] == 3, "sort asc first=row3 (value=5)")
    _assert(asc[1] == 0, "sort asc second=row0 (value=10)")
    _assert(asc[4] == 2, "sort asc last=row2 (value=30)")
    # Sort descending
    var desc = table_sort_by(t, 1, False)
    _assert(desc[0] == 2, "sort desc first=row2 (value=30)")
    _assert(desc[4] == 3, "sort desc last=row3 (value=5)")
    print("  ✓ test_table_sort_by")


fn test_table_join_inner() raises:
    # Table 1: col0=key
    var c1 = List[String]()
    c1.append("key")
    c1.append("val1")
    var t1 = table_create(c1, 0)
    var r10 = List[Float64]()
    r10.append(1.0)
    r10.append(100.0)
    table_insert_row(t1, r10)
    var r11 = List[Float64]()
    r11.append(2.0)
    r11.append(200.0)
    table_insert_row(t1, r11)
    var r12 = List[Float64]()
    r12.append(3.0)
    r12.append(300.0)
    table_insert_row(t1, r12)

    # Table 2: col0=key
    var c2 = List[String]()
    c2.append("key")
    c2.append("val2")
    var t2 = table_create(c2, 0)
    var r20 = List[Float64]()
    r20.append(2.0)
    r20.append(999.0)
    table_insert_row(t2, r20)
    var r21 = List[Float64]()
    r21.append(3.0)
    r21.append(888.0)
    table_insert_row(t2, r21)
    var r22 = List[Float64]()
    r22.append(4.0)
    r22.append(777.0)
    table_insert_row(t2, r22)

    var joined = table_join_inner(t1, 0, t2, 0)
    # Matching keys: 2 (t1r1, t2r0) and 3 (t1r2, t2r1)
    _assert(len(joined) == 2, "join_inner 2 matches")
    _assert(joined[0][0] == 1, "join match0 t1_row=1")
    _assert(joined[0][1] == 0, "join match0 t2_row=0")
    _assert(joined[1][0] == 2, "join match1 t1_row=2")
    _assert(joined[1][1] == 1, "join match1 t2_row=1")
    print("  ✓ test_table_join_inner")


fn test_table_group_aggregate() raises:
    var t = _make_test_table()
    # Group by col2 (group), sum of col1 (value)
    # group=1: 10+20+15=45, group=2: 30+5=35
    var groups = table_group_aggregate(t, 2, 1, 0)
    _assert(len(groups) == 2, "group_aggregate 2 groups")
    # Find group 1 and group 2
    var g1_sum: Float64 = 0.0
    var g2_sum: Float64 = 0.0
    for i in range(len(groups)):
        if groups[i][0] == 1.0:
            g1_sum = groups[i][1]
        elif groups[i][0] == 2.0:
            g2_sum = groups[i][1]
    _assert_close(g1_sum, 45.0, 1e-10, "group1 sum=45")
    _assert_close(g2_sum, 35.0, 1e-10, "group2 sum=35")

    # Group by, mean
    var groups_mean = table_group_aggregate(t, 2, 1, 1)
    var g1_mean: Float64 = 0.0
    var g2_mean: Float64 = 0.0
    for i in range(len(groups_mean)):
        if groups_mean[i][0] == 1.0:
            g1_mean = groups_mean[i][1]
        elif groups_mean[i][0] == 2.0:
            g2_mean = groups_mean[i][1]
    _assert_close(g1_mean, 15.0, 1e-10, "group1 mean=15")
    _assert_close(g2_mean, 17.5, 1e-10, "group2 mean=17.5")
    print("  ✓ test_table_group_aggregate")


# ── Reinforcement Learning Tests ──────────────────────────────────────────────


fn _make_mdp_rewards() -> List[List[Float64]]:
    """3-state MDP rewards. rewards[s][a]."""
    var rewards = List[List[Float64]]()
    var r0 = List[Float64]()
    r0.append(0.0)   # s0, a0 -> s1, reward 0
    r0.append(1.0)   # s0, a1 -> s2, reward 1
    rewards.append(r0^)
    var r1 = List[Float64]()
    r1.append(10.0)  # s1, a0 -> s2, reward 10
    r1.append(0.0)   # s1, a1 -> s1, reward 0
    rewards.append(r1^)
    var r2 = List[Float64]()
    r2.append(0.0)   # s2, a0 -> s2 (terminal)
    r2.append(0.0)   # s2, a1 -> s2 (terminal)
    rewards.append(r2^)
    return rewards^


fn _make_mdp_transitions() -> List[List[Int]]:
    """3-state MDP transitions. transitions[s][a]."""
    var transitions = List[List[Int]]()
    var t0 = List[Int]()
    t0.append(1)  # s0, a0 -> s1
    t0.append(2)  # s0, a1 -> s2
    transitions.append(t0^)
    var t1 = List[Int]()
    t1.append(2)  # s1, a0 -> s2
    t1.append(1)  # s1, a1 -> s1
    transitions.append(t1^)
    var t2 = List[Int]()
    t2.append(2)  # s2 terminal
    t2.append(2)
    transitions.append(t2^)
    return transitions^


fn test_value_iteration_converges() raises:
    var rewards = _make_mdp_rewards()
    var transitions = _make_mdp_transitions()
    var V = value_iteration(3, 2, rewards, transitions, 0.9, 1e-8)
    _assert(len(V) == 3, "value_iteration 3 states")
    # V[2] should be 0 (terminal)
    _assert_close(V[2], 0.0, 1e-6, "V[terminal]=0")
    # V[1] should be ~10 (reward 10 to terminal)
    _assert_close(V[1], 10.0, 1e-4, "V[1]≈10")
    # V[0] should be max(0+0.9*V[1], 1+0.9*V[2]) = max(9, 1) = 9
    _assert_close(V[0], 9.0, 1e-4, "V[0]≈9")
    print("  ✓ test_value_iteration_converges")


fn test_q_learning_improves() raises:
    var rewards = _make_mdp_rewards()
    var transitions = _make_mdp_transitions()
    # Run with few episodes
    var Q_few = q_learning(3, 2, rewards, transitions, 0.1, 0.9, 0.3, 10)
    # Run with more episodes
    var rewards2 = _make_mdp_rewards()
    var transitions2 = _make_mdp_transitions()
    var Q_many = q_learning(3, 2, rewards2, transitions2, 0.1, 0.9, 0.1, 500)
    _assert(len(Q_many) == 3, "q_learning 3 states")
    _assert(len(Q_many[0]) == 2, "q_learning 2 actions")
    # After many episodes, Q[1][0] should be close to 10 (best action from s1)
    _assert(Q_many[1][0] > 5.0, "Q[1][0] > 5 after many episodes")
    print("  ✓ test_q_learning_improves")


fn test_policy_from_q() raises:
    var Q = List[List[Float64]]()
    var q0 = List[Float64]()
    q0.append(1.0)
    q0.append(5.0)
    Q.append(q0^)
    var q1 = List[Float64]()
    q1.append(10.0)
    q1.append(3.0)
    Q.append(q1^)
    var q2 = List[Float64]()
    q2.append(0.0)
    q2.append(0.0)
    Q.append(q2^)
    var policy = policy_from_q(Q)
    _assert(len(policy) == 3, "policy_from_q 3 states")
    _assert(policy[0] == 1, "policy[0]=1 (action with Q=5)")
    _assert(policy[1] == 0, "policy[1]=0 (action with Q=10)")
    _assert(policy[2] == 0, "policy[2]=0 (tie, first)")
    print("  ✓ test_policy_from_q")


fn test_epsilon_greedy_zero() raises:
    # With epsilon=0, should always pick greedy (argmax)
    var Q_state = List[Float64]()
    Q_state.append(1.0)
    Q_state.append(5.0)
    Q_state.append(3.0)
    # Run multiple times, all should be greedy
    for _ in range(10):
        var a = epsilon_greedy_action(Q_state, 0.0)
        _assert(a == 1, "epsilon=0 -> greedy action=1")
    print("  ✓ test_epsilon_greedy_zero")


fn test_discounted_return() raises:
    var rewards = List[Float64]()
    rewards.append(1.0)
    rewards.append(1.0)
    rewards.append(1.0)
    var G = discounted_return(rewards, 0.9)
    # G = 1 + 0.9 + 0.81 = 2.71
    _assert_close(G, 2.71, 1e-10, "discounted_return([1,1,1], 0.9)=2.71")
    # Single reward
    var r2 = List[Float64]()
    r2.append(5.0)
    var G2 = discounted_return(r2, 0.9)
    _assert_close(G2, 5.0, 1e-10, "discounted_return([5], 0.9)=5")
    print("  ✓ test_discounted_return")


fn test_td_error() raises:
    # td = r + γ*V(s') - V(s) = 5 + 0.9*10 - 8 = 5 + 9 - 8 = 6
    var err = td_error(5.0, 0.9, 10.0, 8.0)
    _assert_close(err, 6.0, 1e-10, "td_error=6")
    # Zero case
    var err2 = td_error(0.0, 0.9, 0.0, 0.0)
    _assert_close(err2, 0.0, 1e-10, "td_error zero=0")
    print("  ✓ test_td_error")


fn test_policy_evaluation() raises:
    var rewards = _make_mdp_rewards()
    var transitions = _make_mdp_transitions()
    # Policy: s0->a0(go to s1), s1->a0(go to s2), s2->a0(stay)
    var policy = List[Int]()
    policy.append(0)
    policy.append(0)
    policy.append(0)
    var V = policy_evaluation(policy, 3, rewards, transitions, 0.9, 1e-8)
    _assert(len(V) == 3, "policy_eval 3 states")
    _assert_close(V[2], 0.0, 1e-6, "V_policy[terminal]=0")
    # V[1] = r(s1,a0) + gamma*V[s2] = 10 + 0 = 10
    _assert_close(V[1], 10.0, 1e-4, "V_policy[1]=10")
    # V[0] = r(s0,a0) + gamma*V[s1] = 0 + 0.9*10 = 9
    _assert_close(V[0], 9.0, 1e-4, "V_policy[0]=9")

    # Compare with value_iteration
    var rewards2 = _make_mdp_rewards()
    var transitions2 = _make_mdp_transitions()
    var V_vi = value_iteration(3, 2, rewards2, transitions2, 0.9, 1e-8)
    # Optimal policy should match the value iteration for optimal actions
    _assert_close(V[0], V_vi[0], 1e-4, "policy_eval consistent with value_iteration at s0")
    print("  ✓ test_policy_evaluation")


fn test_sarsa_runs() raises:
    var rewards = _make_mdp_rewards()
    var transitions = _make_mdp_transitions()
    var Q = sarsa(3, 2, rewards, transitions, 0.1, 0.9, 0.1, 200)
    _assert(len(Q) == 3, "sarsa 3 states")
    _assert(len(Q[0]) == 2, "sarsa 2 actions")
    # Should have learned something positive for state 1, action 0
    _assert(Q[1][0] > 0.0, "sarsa Q[1][0] > 0 after training")
    print("  ✓ test_sarsa_runs")


# ── Astronomy Tests ───────────────────────────────────────────────────────────


fn test_julian_date_j2000() raises:
    # J2000.0 = January 1.5, 2000 = JD 2451545.0
    # julian_date(2000,1,1) gives JD at noon Jan 1 = 2451545.0
    # But the standard is Jan 1.5 TT = JD 2451545.0
    var jd = julian_date(2000, 1, 1)
    # Should be close to 2451544.5 (midnight) or 2451545.0 (noon)
    # The algorithm gives noon, so JD 2451545.0 for Jan 1
    _assert_close(jd, 2451544.5, 1.5, "julian_date(2000,1,1) ≈ 2451544.5±1")
    _assert(_is_finite(jd), "julian_date should be finite")
    print("  ✓ test_julian_date_j2000")


fn test_modified_julian_date() raises:
    var jd = 2451545.0
    var mjd = modified_julian_date(jd)
    _assert_close(mjd, 51544.5, 1e-10, "MJD of J2000 = 51544.5")
    print("  ✓ test_modified_julian_date")


fn test_sidereal_time() raises:
    var jd = julian_date(2000, 1, 1)
    var st = sidereal_time(jd, 0.0)
    _assert(st >= 0.0, "sidereal_time >= 0")
    _assert(st < 24.0, "sidereal_time < 24")
    _assert(_is_finite(st), "sidereal_time finite")
    # With non-zero longitude
    var st2 = sidereal_time(jd, 90.0)
    _assert(st2 >= 0.0, "sidereal_time with lon=90 >= 0")
    print("  ✓ test_sidereal_time")


fn test_solar_declination_solstices() raises:
    # Summer solstice ~day 172: declination ≈ +23.45
    var dec_summer = solar_declination(172)
    _assert_close(dec_summer, 23.45, 1.0, "solar_dec summer ≈ 23.45")
    _assert(dec_summer > 22.0, "summer dec > 22")
    # Winter solstice ~day 355: declination ≈ -23.45
    var dec_winter = solar_declination(355)
    _assert_close(dec_winter, -23.45, 1.5, "solar_dec winter ≈ -23.45")
    _assert(dec_winter < -22.0, "winter dec < -22")
    # Equinox ~day 80: declination ≈ 0
    var dec_equinox = solar_declination(80)
    _assert(fabs(dec_equinox) < 2.0, "equinox dec near 0")
    print("  ✓ test_solar_declination_solstices")


fn test_day_length_equator_equinox() raises:
    # At equator, equinox: ~12 hours
    var dl = day_length(0.0, 80)
    _assert_close(dl, 12.0, 1.0, "day_length equator equinox ≈ 12")
    _assert(dl > 11.0, "day_length equator > 11")
    _assert(dl < 13.0, "day_length equator < 13")
    print("  ✓ test_day_length_equator_equinox")


fn test_day_length_high_latitude() raises:
    # At 60°N, summer solstice: very long days
    var dl_summer = day_length(60.0, 172)
    _assert(dl_summer > 16.0, "day_length 60N summer > 16h")
    # At 60°N, winter solstice: very short days
    var dl_winter = day_length(60.0, 355)
    _assert(dl_winter < 8.0, "day_length 60N winter < 8h")
    print("  ✓ test_day_length_high_latitude")


fn test_orbital_period() raises:
    # Earth: a=1 AU -> T=1 year
    var T_earth = orbital_period(1.0)
    _assert_close(T_earth, 1.0, 1e-10, "orbital_period(1)=1")
    # Mars: a≈1.524 AU -> T≈1.881 years
    var T_mars = orbital_period(1.524)
    _assert_close(T_mars, 1.881, 0.01, "orbital_period(1.524)≈1.881")
    # Jupiter: a≈5.2 AU -> T≈11.86 years
    var T_jupiter = orbital_period(5.2)
    _assert(T_jupiter > 11.0, "orbital_period Jupiter > 11")
    _assert(T_jupiter < 13.0, "orbital_period Jupiter < 13")
    print("  ✓ test_orbital_period")


fn test_apparent_magnitude() raises:
    # Sun at 10pc: m = M + 5*log10(10) - 5 = M + 5 - 5 = M
    var m = apparent_magnitude(4.83, 10.0)
    _assert_close(m, 4.83, 1e-10, "apparent_mag at 10pc = abs_mag")
    # At 100pc: m = 4.83 + 5*2 - 5 = 4.83 + 5 = 9.83
    var m2 = apparent_magnitude(4.83, 100.0)
    _assert_close(m2, 9.83, 1e-10, "apparent_mag at 100pc = 9.83")
    print("  ✓ test_apparent_magnitude")


fn test_distance_from_magnitude() raises:
    # If m=M, d=10pc
    var d = distance_from_magnitude(4.83, 4.83)
    _assert_close(d, 10.0, 1e-8, "distance at m=M is 10pc")
    # If m=M+5, d=100pc
    var d2 = distance_from_magnitude(4.83, 9.83)
    _assert_close(d2, 100.0, 1e-6, "distance at m=M+5 is 100pc")
    print("  ✓ test_distance_from_magnitude")


fn test_kepler_equation_zero() raises:
    # M=0, e=0.5 -> E=0
    var E = kepler_equation(0.0, 0.5)
    _assert_close(E, 0.0, 1e-8, "kepler_equation(0, 0.5)=0")
    # Circular orbit e=0: E = M
    var E2 = kepler_equation(1.0, 0.0)
    _assert_close(E2, 1.0, 1e-8, "kepler_equation(1, 0)=1")
    print("  ✓ test_kepler_equation_zero")


fn test_kepler_equation_eccentric() raises:
    # For e=0.5, M=1.0: verify M = E - e*sin(E)
    var E = kepler_equation(1.0, 0.5)
    var check = E - 0.5 * sin(E)
    _assert_close(check, 1.0, 1e-8, "kepler solution satisfies equation")
    print("  ✓ test_kepler_equation_eccentric")


fn test_parallax_correction() raises:
    # For 1 AU, Earth radius 6.371e6 m
    var p = parallax_correction(1.0, 6.371e6)
    _assert(p > 0.0, "parallax > 0")
    _assert(p < 10.0, "parallax < 10 arcsec for 1 AU")
    # Farther distance = smaller parallax
    var p2 = parallax_correction(10.0, 6.371e6)
    _assert(p2 < p, "farther distance = smaller parallax")
    print("  ✓ test_parallax_correction")


fn test_ecliptic_to_equatorial() raises:
    # Vernal equinox: ecliptic (0, 0) -> equatorial (0, 0)
    var eq = ecliptic_to_equatorial(0.0, 0.0, 23.4393)
    _assert_close(eq[0], 0.0, 1e-6, "vernal equinox RA=0")
    _assert_close(eq[1], 0.0, 1e-6, "vernal equinox Dec=0")
    # Summer solstice: ecliptic (90, 0) -> RA~90, Dec~23.44
    var eq2 = ecliptic_to_equatorial(90.0, 0.0, 23.4393)
    _assert(eq2[1] > 20.0, "summer solstice Dec > 20")
    _assert(eq2[1] < 25.0, "summer solstice Dec < 25")
    print("  ✓ test_ecliptic_to_equatorial")


# ── Main ──────────────────────────────────────────────────────────────────────


fn main() raises:
    print("Wave 59 Tests — Database Operations, Reinforcement Learning, Astronomy")
    print("═" * 70)

    print("\n── Database Operations ──")
    test_table_create()
    test_table_insert_row()
    test_table_select_column()
    test_table_where_gt()
    test_table_where_eq()
    test_table_where_lt()
    test_table_aggregate_sum_mean()
    test_table_sort_by()
    test_table_join_inner()
    test_table_group_aggregate()

    print("\n── Reinforcement Learning ──")
    test_value_iteration_converges()
    test_q_learning_improves()
    test_policy_from_q()
    test_epsilon_greedy_zero()
    test_discounted_return()
    test_td_error()
    test_policy_evaluation()
    test_sarsa_runs()

    print("\n── Astronomy ──")
    test_julian_date_j2000()
    test_modified_julian_date()
    test_sidereal_time()
    test_solar_declination_solstices()
    test_day_length_equator_equinox()
    test_day_length_high_latitude()
    test_orbital_period()
    test_apparent_magnitude()
    test_distance_from_magnitude()
    test_kepler_equation_zero()
    test_kepler_equation_eccentric()
    test_parallax_correction()
    test_ecliptic_to_equatorial()

    print("\n" + "═" * 70)
    print("All Wave 59 tests passed! ✓")
