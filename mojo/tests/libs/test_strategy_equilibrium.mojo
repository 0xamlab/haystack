"""test_strategy_equilibrium.mojo — known-value tests for N-player equilibrium solving.

Hand-written. Every number asserted below is derived by hand from the definition of a Nash
equilibrium, or read back from the FROZEN kernel that owns it, never from this module agreeing
with itself. Where a value can only be produced by the module (a regret-matching average), the
assertion is against arithmetic done here in the docstring, not against a recorded output.

What is proved here, and why each one earns a test
-------------------------------------------------
1. *The Prisoner's Dilemma has exactly ONE pure equilibrium and it is (defect, defect).* The
   payoff tensor is built by calling the frozen `game_theory.prisoners_dilemma_payoff`, so even
   the fixture is the frozen kernel's arithmetic: `[3, 0, 5, 1 | 3, 5, 0, 1]`. The enumeration
   must find exactly one equilibrium, at profile 3 = (1, 1), with residual exactly 0.0. At
   profile 0 = (cooperate, cooperate) each player gains 5 - 3 = 2 by defecting, so the residual
   there is exactly 2.0 — the value that separates "an equilibrium" from "a profile".

2. *The frozen closed form and the enumeration agree on that game.* `nash_2x2` returns
   `p = q = 0` — it CLAMPS its indifference solution, and here the clamp lands exactly on the
   pure equilibrium the enumeration found independently. Agreement between an exact closed form
   and an exhaustive search is the strongest correctness check available for this module, so it
   is asserted rather than described.

3. *Matching pennies has NO pure equilibrium, and that is reported as an exact finding.*
   `n_equilibria == 0`, `has_first == False`, and `residual == 2.0` because at every one of the
   four profiles the losing player moves from -1 to +1. A solver that always returned a profile
   would be a random number generator with extra steps; the assertion is the ABSENCE.

4. *The known mixed equilibrium of matching pennies is 50/50 with value 0.* Both come out of the
   frozen kernel — the mixture from `nash_2x2`, the value from `expected_payoff` — and the
   exploitability of that mixture is asserted to be exactly 0.0, which is what makes the
   CLOSED_FORM exactness claim a measurement.

5. *Regret matching agrees with the closed form where the equilibrium is UNIQUE.* On matching
   pennies its time-average is 0.5 to within 1e-12 of the frozen kernel's answer. That check is
   only valid under uniqueness and is deliberately NOT made on the coordination game, where
   there are three equilibria and two correct solvers may return different ones.

6. *Regret matching's average on a dominance game is exactly `1 - 0.5/T`.* In a game where each
   player's payoff is its own action index, iteration 1 plays uniform (all regrets zero) and
   every later iteration plays the dominant action, so the average weight on it is
   `(0.5 + (T-1))/T` and the residual is exactly `0.5/T`. At T = 200 that is 0.9975 and 0.0025 —
   hand arithmetic, asserted to 1e-12, not a recorded output.

7. *Fictitious play converges too, and much more slowly, and the report says so with a number.*
   Its residual on matching pennies falls monotonically across 100, 1000 and 20000 iterations
   and is still above regret matching's after 4000. Both are APPROXIMATE; the residual is what
   distinguishes them, which is the whole reason a converged flag alone is not enough.

8. *The coordination game has THREE equilibria and each one is verified alone.* The enumeration
   finds the two pure ones — profiles 0 and 3, in that order, because the profile order is total
   and declared — and the closed form finds the mixed one, 50/50 with value 0.5. All three have
   residual 0.0. That is asserted per equilibrium, because "the solvers agree" is false here and
   would be the wrong property to test.

9. *A dominated action is flagged by the frozen kernel, and the tensor generalisation agrees with
   it on the same data.* `dominated_strategy_check` says cooperate is strictly dominated for
   both players of the 2x2 Prisoner's Dilemma. Embedding that game in three players with a dummy
   third player forces the tensor scan instead, and it must return the same `[True, False]`. A
   generalisation that is never compared with the kernel it generalises is a second definition.

10. *Best-response dynamics settles on the Prisoner's Dilemma and provably does not on matching
    pennies.* Two rounds and two switches to reach profile 3 from profile 0, which is hand
    traceable; and on matching pennies `STRAT_ERR_NOT_CONVERGED` with the final profile and its
    2.0 residual still reported, because a cycling dynamic that returned its last profile as an
    equilibrium would be a wrong answer nothing downstream could catch.

11. *A wrapping multiply is real, and the profile count survives it.* `1024 ** 8` is 2^80, which
    wraps to exactly 0 in 64-bit arithmetic — asserted with the actual product — so a
    `total * n_actions <= limit` guard would PASS the largest game in the space. The
    division-based growth refuses it.

12. *The joint cell check is the binding one.* An 8-player 6-action game has 1,679,616 profiles,
    which is inside the cell ceiling, and 13,436,928 tensor cells, which is not. `eq_profile_count`
    returns the first and `eq_payoff_cells` returns -1, so a request inside every stated limit
    cannot allocate past all of them.

13. *The work budget refuses the shapes that measured over a second, and every refusal is typed.*
    Timed in the identical loop shape before the gate existed, enumerating a 2-player 512-action
    game took 1.16 s and 4000 regret-matching iterations of a 2-player 64-action game took 1.54 s;
    both are now refused with `STRAT_ERR_WORK_BUDGET`, while 100 iterations of that same game is
    accepted and answers. The charge edge is asserted exactly — 406 actions fits and 407 does
    not — so the gate is shown to be able to FAIL and not merely to exist.

14. *No input aborts the worker.* Counts above the list length, negative and over-range action
    indices, non-finite payoffs, non-distribution strategy rows, negative and NaN tolerances,
    zero and over-ceiling iteration counts, out-of-range profile and player indices: each is
    asserted to return its typed refusal, and the fact that the suite reaches the next line is
    the other half of the assertion, because the failure being prevented is an uncatchable abort
    that no `try` can observe.

15. *An absent quantity is 0.0 with its flag False.* Asserted on a refusal, because the dispatch
    refuses to serialise a non-finite and a NaN in one field would turn the whole response into
    a typed error.
"""
from std.math import abs as fabs

from game_theory import dominated_strategy_check, prisoners_dilemma_payoff

from strategy.contract import (
    STRAT_ERR_ACTION_RANGE,
    STRAT_ERR_COUNT,
    STRAT_ERR_DEGENERATE,
    STRAT_ERR_DIMENSION_TOO_LARGE,
    STRAT_ERR_NON_FINITE,
    STRAT_ERR_NOT_CONVERGED,
    STRAT_ERR_NOT_EVALUABLE,
    STRAT_ERR_NOT_EXACT,
    STRAT_ERR_PLAYER_COUNT,
    STRAT_ERR_PROBABILITY,
    STRAT_ERR_SHAPE,
    STRAT_ERR_TOLERANCE,
    STRAT_ERR_WORK_BUDGET,
    STRAT_EXACT_APPROXIMATE,
    STRAT_EXACT_CLOSED_FORM,
    STRAT_EXACT_UNKNOWN,
    STRAT_OK,
)
from strategy.equilibrium import (
    EQ_MAX_ITERS,
    EQ_METHOD_BEST_RESPONSE,
    EQ_METHOD_CLOSED_FORM_2X2,
    EQ_METHOD_COUNT,
    EQ_METHOD_ENUMERATION,
    EQ_METHOD_REGRET_MATCHING,
    EQ_METHOD_TENSOR_DOMINANCE,
    eq_best_response_charge,
    eq_best_response_flat,
    eq_dominated_actions_flat,
    eq_enumeration_charge,
    eq_exploitability_flat,
    eq_fictitious_play_flat,
    eq_game_status,
    eq_iteration_charge,
    eq_method_name,
    eq_nash_2x2_flat,
    eq_payoff_cells,
    eq_profile_action,
    eq_profile_count,
    eq_profile_index,
    eq_profile_stride,
    eq_pure_gains_flat,
    eq_pure_nash_flat,
    eq_regret_matching_flat,
    eq_solve_flat,
    eq_tiebreak_rule,
    eq_zero_sum_bounds_flat,
)


fn _pd_tensor() -> List[Float64]:
    """The 2x2 Prisoner's Dilemma, from the FROZEN payoff kernel. Action 0 = cooperate.

    Player-major, profile = a0 * 2 + a1, so this is `[3, 0, 5, 1 | 3, 5, 0, 1]`.
    """
    var out = List[Float64]()
    for i in range(2):
        for a0 in range(2):
            for a1 in range(2):
                var pay = prisoners_dilemma_payoff(a0 == 0, a1 == 0)
                out.append(pay[i])
    return out^


fn _pennies_tensor() -> List[Float64]:
    """Matching pennies: +1 to player 0 on a match, -1 otherwise; player 1 is the negation."""
    var out = List[Float64]()
    for i in range(2):
        for a0 in range(2):
            for a1 in range(2):
                var v: Float64 = 1.0 if a0 == a1 else -1.0
                if i == 1:
                    v = -v
                out.append(v)
    return out^


fn _coord_tensor() -> List[Float64]:
    """A pure coordination game: both players get 1 on a match and 0 otherwise."""
    var out = List[Float64]()
    for _ in range(2):
        for a0 in range(2):
            for a1 in range(2):
                out.append(1.0 if a0 == a1 else 0.0)
    return out^


fn _dominance3_tensor() -> List[Float64]:
    """Three players, two actions, `u_i = own action index`. Unique pure equilibrium at (1,1,1).

    Action 1 strictly dominates action 0 for every player, so the equilibrium is profile
    1*4 + 1*2 + 1 = 7 and every other profile is off it.
    """
    var out = List[Float64]()
    for i in range(3):
        for g in range(8):
            var s = 1
            for _ in range(3 - 1 - i):
                s = s * 2
            out.append(Float64((g // s) % 2))
    return out^


fn _pd3_tensor() -> List[Float64]:
    """The 2x2 Prisoner's Dilemma embedded in three players, the third a dummy.

    `u_0` and `u_1` ignore player 2 entirely and `u_2` is constant 0. Player 0's dominance
    structure is therefore IDENTICAL to the 2x2 game's, while the shape forces the tensor scan
    rather than the frozen two-player kernel — which is what makes the two paths comparable.
    """
    var pd = _pd_tensor()
    var out = List[Float64]()
    for i in range(3):
        for g in range(8):
            var a0 = (g // 4) % 2
            var a1 = (g // 2) % 2
            if i == 2:
                out.append(0.0)
            else:
                out.append(pd[i * 4 + a0 * 2 + a1])
    return out^


fn _onehot(n_players: Int, n_actions: Int, actions: List[Int]) -> List[Float64]:
    var out = List[Float64]()
    for i in range(n_players):
        for a in range(n_actions):
            out.append(1.0 if a == actions[i] else 0.0)
    return out^


fn _pair(first: Int, second: Int) -> List[Int]:
    var out = List[Int]()
    out.append(first)
    out.append(second)
    return out^


fn main():
    var passed = 0
    var failed = 0
    print("\n[strategy.equilibrium] known-value suite")

    var pd = _pd_tensor()
    var mp = _pennies_tensor()
    var coord = _coord_tensor()

    # ── 1. the fixture is the frozen kernel's arithmetic ──────────────────────
    var fixture_ok = len(pd) == 8
    fixture_ok = fixture_ok and pd[0] == 3.0 and pd[1] == 0.0 and pd[2] == 5.0 and pd[3] == 1.0
    fixture_ok = fixture_ok and pd[4] == 3.0 and pd[5] == 5.0 and pd[6] == 0.0 and pd[7] == 1.0
    fixture_ok = fixture_ok and eq_game_status(pd, 2, 2) == STRAT_OK
    if fixture_ok:
        passed += 1
        print("  ✅ PD tensor from game_theory.prisoners_dilemma_payoff: [3,0,5,1 | 3,5,0,1]")
    else:
        failed += 1
        print("  ❌ PD fixture is not the frozen kernel's payoffs:", len(pd))

    # ── 2. the profile layout round-trips at every profile ────────────────────
    var round_trip = True
    var n34 = eq_profile_count(3, 4)
    for g in range(n34):
        var tuple = List[Int]()
        for i in range(3):
            tuple.append(eq_profile_action(g, i, 3, 4))
        if eq_profile_index(tuple, 3, 4) != g:
            round_trip = False
    var strides_ok = eq_profile_stride(0, 3, 4) == 16 and eq_profile_stride(1, 3, 4) == 4
    strides_ok = strides_ok and eq_profile_stride(2, 3, 4) == 1
    if round_trip and n34 == 64 and strides_ok:
        passed += 1
        print("  ✅ decode/encode round-trip at all 64 profiles of a 3-player 4-action game")
    else:
        failed += 1
        print("  ❌ profile layout is not invertible:", n34, round_trip, strides_ok)

    # ── 3. PD: exactly one pure equilibrium, at (defect, defect) ──────────────
    var pd_nash = eq_pure_nash_flat(pd, 2, 2, 0.0)
    var pd_ok = pd_nash.status == STRAT_OK and pd_nash.n_profiles == 4
    pd_ok = pd_ok and pd_nash.n_equilibria == 1 and pd_nash.has_first
    pd_ok = pd_ok and pd_nash.first_profile == 3 and pd_nash.best_profile == 3
    pd_ok = pd_ok and pd_nash.has_residual and pd_nash.residual == 0.0
    pd_ok = pd_ok and pd_nash.exactness == STRAT_EXACT_CLOSED_FORM
    pd_ok = pd_ok and not pd_nash.listed_truncated and len(pd_nash.equilibria) == 1
    pd_ok = pd_ok and pd_nash.method == EQ_METHOD_ENUMERATION
    if pd_ok:
        passed += 1
        print("  ✅ PD has exactly 1 pure equilibrium, profile 3 = (defect, defect), residual 0")
    else:
        failed += 1
        print("  ❌ PD enumeration wrong:", pd_nash.n_equilibria, pd_nash.first_profile,
              pd_nash.residual)

    # A profile is not an equilibrium just because it is jointly better: at (C, C) each
    # player gains 5 - 3 = 2 by defecting, so the residual is exactly 2.0.
    var cc = eq_pure_gains_flat(pd, 2, 2, _pair(0, 0), 0.0)
    var cc_ok = cc.status == STRAT_OK and cc.residual == 2.0 and not cc.is_equilibrium
    cc_ok = cc_ok and cc.values[0] == 3.0 and cc.values[1] == 3.0
    cc_ok = cc_ok and cc.gains[0] == 2.0 and cc.gains[1] == 2.0 and cc.worst_player == 0
    var dd = eq_pure_gains_flat(pd, 2, 2, _pair(1, 1), 0.0)
    var dd_ok = dd.status == STRAT_OK and dd.residual == 0.0 and dd.is_equilibrium
    dd_ok = dd_ok and dd.values[0] == 1.0 and dd.values[1] == 1.0
    if cc_ok and dd_ok:
        passed += 1
        print("  ✅ (C,C) pays 3 each and leaks 2 each; (D,D) pays 1 each and leaks nothing")
    else:
        failed += 1
        print("  ❌ pure gains wrong:", cc.residual, cc.values[0], dd.residual, dd.values[0])

    # ── 4. table lookup and product measure reach the same number ─────────────
    var dd_mixed = eq_exploitability_flat(pd, 2, 2, _onehot(2, 2, _pair(1, 1)), 0.0)
    var cc_mixed = eq_exploitability_flat(pd, 2, 2, _onehot(2, 2, _pair(0, 0)), 0.0)
    var agree = dd_mixed.status == STRAT_OK and dd_mixed.residual == dd.residual
    agree = agree and dd_mixed.value == dd.value and dd_mixed.is_equilibrium == dd.is_equilibrium
    agree = agree and cc_mixed.status == STRAT_OK and cc_mixed.residual == cc.residual
    agree = agree and cc_mixed.value == cc.value
    if agree:
        passed += 1
        print("  ✅ pure table lookup and one-hot product measure agree exactly on both profiles")
    else:
        failed += 1
        print("  ❌ the two routes to one residual disagree:", dd.residual, dd_mixed.residual,
              cc.residual, cc_mixed.residual)

    # ── 5. the frozen closed form, and its agreement with the enumeration ─────
    var pd_a = List[Float64]()
    var pd_b = List[Float64]()
    for t in range(4):
        pd_a.append(pd[t])
        pd_b.append(pd[4 + t])
    var pd_closed = eq_nash_2x2_flat(pd_a, pd_b, 0.0)
    var closed_ok = pd_closed.status == STRAT_OK and pd_closed.method == EQ_METHOD_CLOSED_FORM_2X2
    closed_ok = closed_ok and pd_closed.strategy[0] == 0.0 and pd_closed.strategy[1] == 1.0
    closed_ok = closed_ok and pd_closed.strategy[2] == 0.0 and pd_closed.strategy[3] == 1.0
    closed_ok = closed_ok and pd_closed.has_value and pd_closed.value == 1.0
    closed_ok = closed_ok and pd_closed.has_residual and pd_closed.residual == 0.0
    closed_ok = closed_ok and pd_closed.exactness == STRAT_EXACT_CLOSED_FORM
    closed_ok = closed_ok and not pd_closed.default_mix_used
    # The closed form's mixture is the pure profile the exhaustive search found.
    var same_profile = eq_profile_index(_pair(1, 1), 2, 2) == pd_nash.first_profile
    if closed_ok and same_profile:
        passed += 1
        print("  ✅ frozen nash_2x2 gives (0,0) -> pure (D,D), value 1.0, residual 0, and that",
              "is profile 3 — the equilibrium the enumeration found independently")
    else:
        failed += 1
        print("  ❌ closed form and enumeration disagree on PD:", pd_closed.strategy[0],
              pd_closed.value, pd_closed.residual, pd_nash.first_profile)

    # ── 6. matching pennies has NO pure equilibrium ───────────────────────────
    var mp_nash = eq_pure_nash_flat(mp, 2, 2, 0.0)
    var mp_ok = mp_nash.status == STRAT_OK and mp_nash.n_equilibria == 0
    mp_ok = mp_ok and not mp_nash.has_first and mp_nash.first_profile == -1
    mp_ok = mp_ok and mp_nash.has_residual and mp_nash.residual == 2.0
    mp_ok = mp_ok and mp_nash.exactness == STRAT_EXACT_CLOSED_FORM
    mp_ok = mp_ok and len(mp_nash.equilibria) == 0
    if mp_ok:
        passed += 1
        print("  ✅ matching pennies: 0 pure equilibria reported as an exact finding, and the",
              "closest profile still leaks exactly 2.0")
    else:
        failed += 1
        print("  ❌ pure enumeration invented an equilibrium:", mp_nash.n_equilibria,
              mp_nash.residual)

    # ── 7. its known mixed equilibrium is 50/50 with value 0 ──────────────────
    var mp_a = List[Float64]()
    var mp_b = List[Float64]()
    for t in range(4):
        mp_a.append(mp[t])
        mp_b.append(mp[4 + t])
    var mp_closed = eq_nash_2x2_flat(mp_a, mp_b, 0.0)
    var mixed_ok = mp_closed.status == STRAT_OK
    mixed_ok = mixed_ok and mp_closed.strategy[0] == 0.5 and mp_closed.strategy[2] == 0.5
    mixed_ok = mixed_ok and mp_closed.value == 0.0
    mixed_ok = mixed_ok and mp_closed.residual == 0.0 and mp_closed.converged
    mixed_ok = mixed_ok and mp_closed.exactness == STRAT_EXACT_CLOSED_FORM
    mixed_ok = mixed_ok and not mp_closed.default_mix_used
    if mixed_ok:
        passed += 1
        print("  ✅ matching pennies mixed equilibrium 50/50, value 0, exploitability 0 —",
              "the CLOSED_FORM claim is measured, not asserted")
    else:
        failed += 1
        print("  ❌ mixed equilibrium wrong:", mp_closed.strategy[0], mp_closed.value,
              mp_closed.residual)

    # ── 8. regret matching agrees with the closed form under UNIQUENESS ───────
    var mp_rm = eq_regret_matching_flat(mp, 2, 2, 200, 1.0e-9)
    var rm_ok = mp_rm.status == STRAT_OK and mp_rm.method == EQ_METHOD_REGRET_MATCHING
    rm_ok = rm_ok and mp_rm.iterations == 200
    rm_ok = rm_ok and fabs(mp_rm.strategy[0] - mp_closed.strategy[0]) <= 1.0e-12
    rm_ok = rm_ok and fabs(mp_rm.strategy[2] - mp_closed.strategy[2]) <= 1.0e-12
    rm_ok = rm_ok and mp_rm.has_residual and mp_rm.residual <= 1.0e-12
    # Never CLOSED_FORM from an iterative method, even at residual 0: exactness is a claim
    # about the result of a method that only guarantees an approximation.
    rm_ok = rm_ok and mp_rm.exactness == STRAT_EXACT_APPROXIMATE
    if rm_ok:
        passed += 1
        print("  ✅ regret matching's time-average matches frozen nash_2x2 to 1e-12 on the",
              "unique-equilibrium game, residual", mp_rm.residual, "— still APPROXIMATE")
    else:
        failed += 1
        print("  ❌ regret matching disagrees with the closed form:", mp_rm.strategy[0],
              mp_rm.residual, mp_rm.exactness)

    # ── 9. regret matching's average on a dominance game is 1 - 0.5/T ─────────
    # Iteration 1 has all regrets zero and plays uniform; every later iteration plays the
    # dominant action. Average weight on it = (0.5 + (T-1))/T, so at T = 200 it is 0.9975 and
    # the residual is exactly 0.5/T = 0.0025.
    var d3 = _dominance3_tensor()
    var d3_rm = eq_regret_matching_flat(d3, 3, 2, 200, 1.0e-9)
    var d3_ok = d3_rm.status == STRAT_OK
    d3_ok = d3_ok and fabs(d3_rm.strategy[1] - 0.9975) <= 1.0e-12
    d3_ok = d3_ok and fabs(d3_rm.strategy[3] - 0.9975) <= 1.0e-12
    d3_ok = d3_ok and fabs(d3_rm.strategy[5] - 0.9975) <= 1.0e-12
    d3_ok = d3_ok and fabs(d3_rm.residual - 0.0025) <= 1.0e-12
    d3_ok = d3_ok and d3_rm.exactness == STRAT_EXACT_APPROXIMATE and not d3_rm.converged
    if d3_ok:
        passed += 1
        print("  ✅ 3-player dominance: average 1 - 0.5/200 = 0.9975 on the dominant action and",
              "residual exactly 0.5/200 = 0.0025, both by hand")
    else:
        failed += 1
        print("  ❌ regret-matching average is not 1 - 0.5/T:", d3_rm.strategy[1],
              d3_rm.residual)

    var d3_nash = eq_pure_nash_flat(d3, 3, 2, 0.0)
    var d3_pure_ok = d3_nash.status == STRAT_OK and d3_nash.n_profiles == 8
    d3_pure_ok = d3_pure_ok and d3_nash.n_equilibria == 1 and d3_nash.first_profile == 7
    d3_pure_ok = d3_pure_ok and d3_nash.residual == 0.0
    if d3_pure_ok:
        passed += 1
        print("  ✅ the same 3-player game has one pure equilibrium, profile 7 = (1,1,1)")
    else:
        failed += 1
        print("  ❌ 3-player enumeration wrong:", d3_nash.n_equilibria, d3_nash.first_profile)

    # ── 10. fictitious play converges, and slowly, and says so ────────────────
    var fp_100 = eq_fictitious_play_flat(mp, 2, 2, 100, 1.0e-9)
    var fp_1000 = eq_fictitious_play_flat(mp, 2, 2, 1000, 1.0e-9)
    var fp_20000 = eq_fictitious_play_flat(mp, 2, 2, 20000, 1.0e-9)
    var fp_ok = fp_100.status == STRAT_OK and fp_1000.status == STRAT_OK
    fp_ok = fp_ok and fp_20000.status == STRAT_OK
    fp_ok = fp_ok and fp_1000.residual < fp_100.residual
    fp_ok = fp_ok and fp_20000.residual < fp_1000.residual
    fp_ok = fp_ok and fp_20000.residual <= 0.01
    fp_ok = fp_ok and fabs(fp_20000.strategy[0] - 0.5) <= 0.01
    # Slower than regret matching on the same game, which is why a residual and not a flag.
    fp_ok = fp_ok and fp_20000.residual > mp_rm.residual
    if fp_ok:
        passed += 1
        print("  ✅ fictitious play residual falls", fp_100.residual, "->", fp_1000.residual,
              "->", fp_20000.residual, "and stays above regret matching's")
    else:
        failed += 1
        print("  ❌ fictitious play did not converge monotonically:", fp_100.residual,
              fp_1000.residual, fp_20000.residual)

    # ── 11. the coordination game: three equilibria, each verified alone ──────
    var co_nash = eq_pure_nash_flat(coord, 2, 2, 0.0)
    var co_a = List[Float64]()
    var co_b = List[Float64]()
    for t in range(4):
        co_a.append(coord[t])
        co_b.append(coord[4 + t])
    var co_closed = eq_nash_2x2_flat(co_a, co_b, 0.0)
    var co_ok = co_nash.status == STRAT_OK and co_nash.n_equilibria == 2
    co_ok = co_ok and co_nash.equilibria[0] == 0 and co_nash.equilibria[1] == 3
    co_ok = co_ok and co_nash.first_profile == 0 and co_nash.residual == 0.0
    co_ok = co_ok and co_closed.status == STRAT_OK
    co_ok = co_ok and co_closed.strategy[0] == 0.5 and co_closed.strategy[2] == 0.5
    co_ok = co_ok and co_closed.value == 0.5 and co_closed.residual == 0.0
    co_ok = co_ok and co_closed.exactness == STRAT_EXACT_CLOSED_FORM
    # Each pure equilibrium verified on its own, since "the solvers agree" is FALSE here.
    var co_pure0 = eq_pure_gains_flat(coord, 2, 2, _pair(0, 0), 0.0)
    var co_pure3 = eq_pure_gains_flat(coord, 2, 2, _pair(1, 1), 0.0)
    var co_off = eq_pure_gains_flat(coord, 2, 2, _pair(0, 1), 0.0)
    co_ok = co_ok and co_pure0.residual == 0.0 and co_pure3.residual == 0.0
    co_ok = co_ok and co_off.residual == 1.0 and not co_off.is_equilibrium
    if co_ok:
        passed += 1
        print("  ✅ coordination game: pure equilibria at profiles 0 and 3 (residual 0 each),",
              "mixed 50/50 at value 0.5 (residual 0) — three correct answers, not one")
    else:
        failed += 1
        print("  ❌ coordination game wrong:", co_nash.n_equilibria, co_closed.strategy[0],
              co_closed.value, co_off.residual)

    # ── 12. dominance: the frozen kernel, and the generalisation agreeing ─────
    var frozen_matrix = List[List[Float64]]()
    for a0 in range(2):
        var row = List[Float64]()
        for a1 in range(2):
            row.append(pd[a0 * 2 + a1])
        frozen_matrix.append(row^)
    var frozen_rows = dominated_strategy_check(frozen_matrix)
    var dom0 = eq_dominated_actions_flat(pd, 2, 2, 0)
    var dom1 = eq_dominated_actions_flat(pd, 2, 2, 1)
    var dom_ok = dom0.status == STRAT_OK and dom0.method == EQ_METHOD_CLOSED_FORM_2X2
    dom_ok = dom_ok and len(dom0.dominated) == 2 and dom0.dominated[0] and not dom0.dominated[1]
    dom_ok = dom_ok and dom0.n_dominated == 1
    dom_ok = dom_ok and dom1.status == STRAT_OK and dom1.dominated[0] and not dom1.dominated[1]
    dom_ok = dom_ok and len(frozen_rows) == 2
    dom_ok = dom_ok and dom0.dominated[0] == frozen_rows[0]
    dom_ok = dom_ok and dom0.dominated[1] == frozen_rows[1]
    # The same dominance structure, embedded in three players so the tensor scan must run.
    var pd3 = _pd3_tensor()
    var dom3 = eq_dominated_actions_flat(pd3, 3, 2, 0)
    var dom3_dummy = eq_dominated_actions_flat(pd3, 3, 2, 2)
    dom_ok = dom_ok and dom3.status == STRAT_OK and dom3.method == EQ_METHOD_TENSOR_DOMINANCE
    dom_ok = dom_ok and dom3.dominated[0] and not dom3.dominated[1] and dom3.n_dominated == 1
    dom_ok = dom_ok and dom3_dummy.status == STRAT_OK and dom3_dummy.n_dominated == 0
    if dom_ok:
        passed += 1
        print("  ✅ cooperate is strictly dominated for both PD players by the frozen kernel,",
              "and the 3-player tensor scan returns the same [True, False] on the same game")
    else:
        failed += 1
        print("  ❌ dominance paths disagree:", dom0.n_dominated, dom3.n_dominated,
              dom3_dummy.n_dominated)

    # ── 13. best-response dynamics: settles, and provably does not ────────────
    var pd_path = eq_best_response_flat(pd, 2, 2, 0, 50, 0.0)
    var path_ok = pd_path.status == STRAT_OK and pd_path.converged
    path_ok = path_ok and pd_path.final_profile == 3 and pd_path.start_profile == 0
    path_ok = path_ok and pd_path.rounds == 2 and pd_path.n_switches == 2
    path_ok = path_ok and pd_path.has_residual and pd_path.residual == 0.0
    path_ok = path_ok and pd_path.exactness == STRAT_EXACT_CLOSED_FORM
    var mp_path = eq_best_response_flat(mp, 2, 2, 0, 50, 0.0)
    path_ok = path_ok and mp_path.status == STRAT_ERR_NOT_CONVERGED and not mp_path.converged
    path_ok = path_ok and mp_path.rounds == 50 and mp_path.has_residual
    path_ok = path_ok and mp_path.residual == 2.0
    path_ok = path_ok and mp_path.exactness == STRAT_EXACT_APPROXIMATE
    if path_ok:
        passed += 1
        print("  ✅ best response reaches (D,D) in 2 rounds / 2 switches on PD, and refuses with",
              "not_converged after 50 rounds of the matching-pennies cycle, residual 2.0")
    else:
        failed += 1
        print("  ❌ best-response dynamics wrong:", pd_path.rounds, pd_path.final_profile,
              mp_path.status, mp_path.residual)

    # ── 14. the zero-sum bounds, from the frozen minimax kernel ───────────────
    var mp_bounds = eq_zero_sum_bounds_flat(mp_a, mp_b, 2, 2, 0.0)
    var bounds_ok = mp_bounds.status == STRAT_OK
    bounds_ok = bounds_ok and mp_bounds.has_lower and mp_bounds.lower_value == -1.0
    bounds_ok = bounds_ok and mp_bounds.has_upper and mp_bounds.upper_value == 1.0
    bounds_ok = bounds_ok and mp_bounds.has_gap and mp_bounds.gap == 2.0
    bounds_ok = bounds_ok and not mp_bounds.saddle and mp_bounds.sum_defect == 0.0
    # A matrix with a pure saddle: rows (3,1) and (2,0) -> maximin 1 at row 0, minimax 1 at
    # column 1, so the gap is 0 and no mixing is needed.
    var saddle_a = List[Float64]()
    saddle_a.append(3.0)
    saddle_a.append(1.0)
    saddle_a.append(2.0)
    saddle_a.append(0.0)
    var saddle_b = List[Float64]()
    for t in range(4):
        saddle_b.append(-saddle_a[t])
    var saddle = eq_zero_sum_bounds_flat(saddle_a, saddle_b, 2, 2, 0.0)
    bounds_ok = bounds_ok and saddle.status == STRAT_OK and saddle.lower_value == 1.0
    bounds_ok = bounds_ok and saddle.upper_value == 1.0 and saddle.gap == 0.0 and saddle.saddle
    # The Prisoner's Dilemma is not zero-sum, and that is measured, not assumed.
    var pd_bounds = eq_zero_sum_bounds_flat(pd_a, pd_b, 2, 2, 0.0)
    bounds_ok = bounds_ok and pd_bounds.status == STRAT_ERR_NOT_EVALUABLE
    bounds_ok = bounds_ok and pd_bounds.has_sum_defect and pd_bounds.sum_defect == 6.0
    bounds_ok = bounds_ok and not pd_bounds.has_lower and pd_bounds.lower_value == 0.0
    if bounds_ok:
        passed += 1
        print("  ✅ matching pennies bounds [-1, +1], gap 2, no saddle; (3,1;2,0) gap 0 with a",
              "saddle; the PD is refused as not zero-sum with defect 6.0")
    else:
        failed += 1
        print("  ❌ zero-sum bounds wrong:", mp_bounds.lower_value, mp_bounds.upper_value,
              saddle.gap, pd_bounds.status, pd_bounds.sum_defect)

    # ── 15. the dispatcher uses the exact answer, and refuses to fake one ─────
    var solved_2x2 = eq_solve_flat(pd, 2, 2, 500, 0.0, False)
    var solve_ok = solved_2x2.status == STRAT_OK
    solve_ok = solve_ok and solved_2x2.method == EQ_METHOD_CLOSED_FORM_2X2
    solve_ok = solve_ok and solved_2x2.exactness == STRAT_EXACT_CLOSED_FORM
    solve_ok = solve_ok and solved_2x2.iterations == 1
    var solved_3p = eq_solve_flat(d3, 3, 2, 200, 1.0e-9, False)
    solve_ok = solve_ok and solved_3p.status == STRAT_OK
    solve_ok = solve_ok and solved_3p.method == EQ_METHOD_REGRET_MATCHING
    solve_ok = solve_ok and solved_3p.exactness == STRAT_EXACT_APPROXIMATE
    var demanded = eq_solve_flat(d3, 3, 2, 200, 1.0e-9, True)
    solve_ok = solve_ok and demanded.status == STRAT_ERR_NOT_EXACT
    solve_ok = solve_ok and demanded.exactness == STRAT_EXACT_UNKNOWN
    solve_ok = solve_ok and not demanded.has_residual and demanded.residual == 0.0
    solve_ok = solve_ok and len(demanded.strategy) == 0
    var demanded_2x2 = eq_solve_flat(pd, 2, 2, 200, 0.0, True)
    solve_ok = solve_ok and demanded_2x2.status == STRAT_OK
    if solve_ok:
        passed += 1
        print("  ✅ a 2x2 game routes to the frozen closed form (1 iteration, not 500); above it",
              "require_exact returns not_exact instead of an approximation")
    else:
        failed += 1
        print("  ❌ dispatcher wrong:", solved_2x2.method, solved_3p.method, demanded.status)

    # ── 16. the frozen kernel's own denominator floor, mirrored ───────────────
    # `nash_2x2` compares `fabs(denominator) > 1e-12`. b = (d, 0, 0, 0) gives denominator d, so
    # d = 1e-12 falls back to 0.5 and d = 2e-12 does not.
    var zeros4 = List[Float64]()
    for _ in range(4):
        zeros4.append(0.0)
    var at_floor = List[Float64]()
    at_floor.append(1.0e-12)
    for _ in range(3):
        at_floor.append(0.0)
    var above_floor = List[Float64]()
    above_floor.append(2.0e-12)
    for _ in range(3):
        above_floor.append(0.0)
    var floor_case = eq_nash_2x2_flat(zeros4, at_floor, 0.0)
    var above_case = eq_nash_2x2_flat(zeros4, above_floor, 0.0)
    var floor_ok = floor_case.status == STRAT_OK and floor_case.default_mix_used
    floor_ok = floor_ok and floor_case.strategy[0] == 0.5
    floor_ok = floor_ok and above_case.status == STRAT_OK and above_case.strategy[0] == 0.0
    # The row player's own matrix is all zeros, so its own denominator is 0 and its side is a
    # fallback in both cases; the flag is per RESULT, so it stays True for `above_case` too.
    floor_ok = floor_ok and above_case.default_mix_used
    if floor_ok:
        passed += 1
        print("  ✅ denominator 1e-12 falls back to 0.5 and 2e-12 does not — the frozen 1e-12",
              "floor is mirrored, and default_mix_used reports the fallback")
    else:
        failed += 1
        print("  ❌ the mirrored denominator floor does not match the frozen kernel:",
              floor_case.strategy[0], above_case.strategy[0], floor_case.default_mix_used)

    # ── 17. a wrapping multiply is real, and the profile count survives it ────
    var wrapped = 1
    for _ in range(8):
        wrapped = wrapped * 1024
    var wrap_ok = wrapped == 0 and eq_profile_count(8, 1024) == -1
    wrap_ok = wrap_ok and eq_profile_count(8, 5) == 390625
    wrap_ok = wrap_ok and eq_payoff_cells(8, 5) == 3125000
    # The JOINT check is the binding one: 6^8 profiles fit the cell ceiling and 8 * 6^8 do not.
    wrap_ok = wrap_ok and eq_profile_count(8, 6) == 1679616 and eq_payoff_cells(8, 6) == -1
    wrap_ok = wrap_ok and eq_game_status(pd, 8, 6) == STRAT_ERR_DIMENSION_TOO_LARGE
    if wrap_ok:
        passed += 1
        print("  ✅ 1024**8 wraps to exactly 0 in 64-bit, and the division-based growth refuses",
              "it; 6^8 = 1679616 profiles fit but 8 * 6^8 cells do not")
    else:
        failed += 1
        print("  ❌ the profile count is not wrap-safe:", wrapped, eq_profile_count(8, 1024),
              eq_payoff_cells(8, 6))

    # ── 18. the work budget refuses the shapes that measured over a second ────
    # Timed in the identical loop shape before the gate existed: enumerating 2 players x 512
    # actions took 1.16 s and 4000 regret-matching iterations of 2 x 64 took 1.54 s. Both are
    # refused now, and the refusal is typed rather than a wait.
    var big_scan = eq_enumeration_charge(2, 512)
    var big_iter = eq_iteration_charge(2, 64, 4000)
    var small_scan = eq_enumeration_charge(8, 5)
    var small_iter = eq_iteration_charge(2, 2, 1000)
    var budget_ok = big_scan == -1 and big_iter == -1
    budget_ok = budget_ok and small_scan == 75000000 and small_iter == 576000
    budget_ok = budget_ok and eq_iteration_charge(2, 2, 0) == -1
    budget_ok = budget_ok and eq_iteration_charge(2, 2, EQ_MAX_ITERS + 1) == -1
    # The gate is able to FAIL, and its edge is exact: 406 actions is the largest two-player
    # enumeration that fits (536,706,016 of 536,870,912 units) and 407 does not.
    budget_ok = budget_ok and eq_enumeration_charge(2, 406) == 536706016
    budget_ok = budget_ok and eq_enumeration_charge(2, 407) == -1
    # The best-response charge is its own, because a round does not sweep the tensor: charging
    # it with the sweep would refuse 64 rounds of a dynamic that costs microseconds.
    budget_ok = budget_ok and eq_best_response_charge(2, 1024, 64) == 524288
    budget_ok = budget_ok and eq_iteration_charge(2, 1024, 64) == -1
    # Driver-level, with correctly shaped tensors, so the refusal is the budget and not a shape.
    var wide = List[Float64]()
    for k in range(2 * 407 * 407):
        wide.append(Float64(k % 7))
    var narrow = List[Float64]()
    for k in range(2 * 64 * 64):
        narrow.append(Float64(k % 7))
    var refused_scan = eq_pure_nash_flat(wide, 2, 407, 0.0)
    var refused_iter = eq_regret_matching_flat(narrow, 2, 64, 4000, 0.0)
    var allowed_iter = eq_regret_matching_flat(narrow, 2, 64, 100, 1.0e-9)
    budget_ok = budget_ok and refused_scan.status == STRAT_ERR_WORK_BUDGET
    budget_ok = budget_ok and refused_iter.status == STRAT_ERR_WORK_BUDGET
    budget_ok = budget_ok and not refused_scan.has_residual and refused_scan.residual == 0.0
    budget_ok = budget_ok and allowed_iter.status == STRAT_OK and allowed_iter.has_residual
    if budget_ok:
        passed += 1
        print("  ✅ the two shapes measured above a second are refused with work_budget, 100",
              "iterations of the same 64-action game is not, and the charge edge is exact at",
              "406 vs 407 actions")
    else:
        failed += 1
        print("  ❌ the work budget does not bite:", big_scan, big_iter, small_scan, small_iter,
              refused_scan.status, refused_iter.status, allowed_iter.status)

    # ── 19. every refusal is typed, and the process survives all of them ──────
    var nan_tensor = pd.copy()
    nan_tensor[2] = 0.0 / 0.0
    var short_tensor = List[Float64]()
    for t in range(6):
        short_tensor.append(pd[t])
    var bad_dist = List[Float64]()
    bad_dist.append(0.3)
    bad_dist.append(0.3)
    bad_dist.append(0.5)
    bad_dist.append(0.5)
    var refusals = True
    refusals = refusals and eq_game_status(pd, 1, 2) == STRAT_ERR_PLAYER_COUNT
    refusals = refusals and eq_game_status(pd, 9, 2) == STRAT_ERR_PLAYER_COUNT
    refusals = refusals and eq_game_status(pd, 2, 1) == STRAT_ERR_DEGENERATE
    refusals = refusals and eq_game_status(pd, 2, 2000) == STRAT_ERR_ACTION_RANGE
    refusals = refusals and eq_game_status(short_tensor, 2, 2) == STRAT_ERR_SHAPE
    refusals = refusals and eq_game_status(nan_tensor, 2, 2) == STRAT_ERR_NON_FINITE
    refusals = refusals and eq_pure_nash_flat(pd, 2, 2, -1.0).status == STRAT_ERR_TOLERANCE
    refusals = refusals and eq_pure_nash_flat(pd, 2, 2, 0.0 / 0.0).status == STRAT_ERR_TOLERANCE
    # A count above the list length: refused, and the next line still runs.
    refusals = refusals and eq_profile_index(_pair(1, 1), 3, 2) == -1
    var three_needed = eq_pure_gains_flat(pd3, 3, 2, _pair(1, 1), 0.0)
    refusals = refusals and three_needed.status == STRAT_ERR_COUNT
    refusals = refusals and len(three_needed.gains) == 0
    var over_action = eq_pure_gains_flat(pd, 2, 2, _pair(0, 2), 0.0)
    var negative_action = eq_pure_gains_flat(pd, 2, 2, _pair(0, -1), 0.0)
    refusals = refusals and over_action.status == STRAT_ERR_ACTION_RANGE
    refusals = refusals and negative_action.status == STRAT_ERR_ACTION_RANGE
    refusals = refusals and eq_exploitability_flat(pd, 2, 2, bad_dist, 0.0).status \
        == STRAT_ERR_PROBABILITY
    refusals = refusals and eq_exploitability_flat(pd, 2, 2, short_tensor, 0.0).status \
        == STRAT_ERR_SHAPE
    refusals = refusals and eq_regret_matching_flat(pd, 2, 2, 0, 0.0).status \
        == STRAT_ERR_DIMENSION_TOO_LARGE
    refusals = refusals and eq_regret_matching_flat(pd, 2, 2, EQ_MAX_ITERS + 1, 0.0).status \
        == STRAT_ERR_DIMENSION_TOO_LARGE
    refusals = refusals and eq_best_response_flat(pd, 2, 2, -1, 10, 0.0).status \
        == STRAT_ERR_ACTION_RANGE
    refusals = refusals and eq_best_response_flat(pd, 2, 2, 4, 10, 0.0).status \
        == STRAT_ERR_ACTION_RANGE
    refusals = refusals and eq_dominated_actions_flat(pd, 2, 2, -1).status \
        == STRAT_ERR_PLAYER_COUNT
    refusals = refusals and eq_dominated_actions_flat(pd, 2, 2, 2).status \
        == STRAT_ERR_PLAYER_COUNT
    refusals = refusals and eq_zero_sum_bounds_flat(mp_a, mp_b, 3, 3, 0.0).status \
        == STRAT_ERR_SHAPE
    refusals = refusals and eq_profile_action(4, 0, 2, 2) == -1
    refusals = refusals and eq_profile_stride(-1, 2, 2) == -1
    if refusals:
        passed += 1
        print("  ✅ 22 malformed requests each returned their own typed refusal and the process",
              "reached this line — a count past a List end aborts the worker, uncatchably")
    else:
        failed += 1
        print("  ❌ a malformed request was accepted or mis-typed")

    # ── 20. absence is 0.0 with the flag False, never a non-finite ────────────
    var absent = eq_regret_matching_flat(nan_tensor, 2, 2, 10, 0.0)
    var absence_ok = absent.status == STRAT_ERR_NON_FINITE
    absence_ok = absence_ok and not absent.has_residual and absent.residual == 0.0
    absence_ok = absence_ok and not absent.has_value and absent.value == 0.0
    absence_ok = absence_ok and len(absent.strategy) == 0
    absence_ok = absence_ok and absent.exactness == STRAT_EXACT_UNKNOWN
    absence_ok = absence_ok and absent.iterations == 0
    if absence_ok:
        passed += 1
        print("  ✅ a refused result carries 0.0 in every value slot with has_* False, so the",
              "dispatch never meets a non-finite field")
    else:
        failed += 1
        print("  ❌ a refusal leaked a value or a non-finite:", absent.residual, absent.value)

    # ── 21. the vocabulary: distinct names, and a named tie-break rule ────────
    var names_ok = eq_tiebreak_rule() == "lowest_action_index/v1"
    names_ok = names_ok and EQ_METHOD_COUNT == 6
    names_ok = names_ok and eq_method_name(EQ_METHOD_COUNT) == "unknown_method"
    names_ok = names_ok and eq_method_name(-1) == "unknown_method"
    for i in range(EQ_METHOD_COUNT):
        if eq_method_name(i) == "unknown_method":
            names_ok = False
        for j in range(i + 1, EQ_METHOD_COUNT):
            if eq_method_name(i) == eq_method_name(j):
                names_ok = False
    # A method tag must never be readable as a status: the tags are 0-based.
    names_ok = names_ok and EQ_METHOD_BEST_RESPONSE < STRAT_OK
    if names_ok:
        passed += 1
        print("  ✅ six method tags, all uniquely named, all below the 450 status floor; the",
              "tie-break rule is a versioned function:", eq_tiebreak_rule())
    else:
        failed += 1
        print("  ❌ method tags collide, share a name, or overlap the status range")

    print("  [strategy.equilibrium] Passed:", passed, "Failed:", failed)
