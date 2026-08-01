"""test_strategy_policy.mojo — known-value tests for a policy as a first-class object.

Hand-written. Every expected value below is arithmetic done on paper, and every number that
enters the arithmetic is EXACTLY REPRESENTABLE in binary floating point (halves, quarters,
eighths), so the assertions are equalities and not tolerances wherever the mathematics is exact.
That is deliberate: a tolerance hides the difference between "the kernel computed the right
number" and "the kernel computed something close to it", and the one case here that genuinely
needs a tolerance — an iterative fixed point — states its bound and its reason.

Case 1 — the tie rule is a value
--------------------------------
`policy_tie_rule()` returns `argmax:lowest_index;threshold:closed_at_threshold/v1`. Asserted as a
literal, because it is the identifier a stored comparison carries and a silent change to either
half turns one set of inputs into a different ranking.

Case 2 — a threshold policy either side of its threshold, and exactly ON it
--------------------------------------------------------------------------
Row `[0.5, 0.25, 0.375]`: weights 0.5 and 0.25, threshold 0.375. Two factors, two actions.

    factors [0.5,  0.5 ]  score = 0.25   + 0.125  = 0.375  == threshold -> action 1, at_tie
    factors [0.5,  0.25]  score = 0.25   + 0.0625 = 0.3125 <  threshold -> action 0
    factors [0.75, 0.5 ]  score = 0.375  + 0.125  = 0.5    >  threshold -> action 1

Every product and sum there is exact in binary, so all three scores are asserted with `==`. The
middle case is the TIE CONVENTION: the comparison is closed on the threshold, so a score exactly
equal to it ACTS (action 1), and `at_tie` is True to say the decision sat inside the tolerance
while the answer itself stayed deterministic. A rule that answered 0 there would be equally
defensible and is not what this module does — which is exactly why the convention is a value
returned by `policy_tie_rule()` rather than a sentence.

Case 3 — a lookup policy at EVERY cell
--------------------------------------
Two strategies, four states, three actions, block `[2,0,1,1, 0,0,2,2]` row-major:

    strategy 0 -> [2, 0, 1, 1]        strategy 1 -> [0, 0, 2, 2]

All eight cells are asserted twice: once through `policy_action_flat` state by state and once
through `policy_tabular_actions`, which must agree cell for cell. A lookup that agreed on state 0
and disagreed on state 3 would pass a spot check.

Case 4 — a linear score per action, argmax hand-computable, with a deliberate tie
--------------------------------------------------------------------------------
Weights `[[1,0], [0,1], [0.5,0.5]]` over two factors:

    factors [0.25, 0.75] -> scores [0.25, 0.75, 0.5]  -> action 1, best 0.75, n_tied 1
    factors [0.5,  0.5 ] -> scores [0.5,  0.5,  0.5]  -> action 0, THREE-WAY TIE, n_tied 3

The tie case is the one that matters: the answer is the lowest-indexed maximum, deterministically,
AND `n_tied == 3` tells the caller the choice was arbitrary. Reporting only the winner would let
an arbitrary pick be read as a preference.

Case 5 — a mixed policy: greedy reduction, ties, and rows that are not distributions
-----------------------------------------------------------------------------------
`[0.25, 0.5, 0.25]` sums to exactly 1.0 -> argmax 1 with probability 0.5, `n_tied` 1.
`[0.5, 0.5, 0.0]`  sums to exactly 1.0 -> argmax 0 (lowest index of a two-way tie), `n_tied` 2.
`[0.5, 0.25, 0.1]` sums to 0.85       -> `STRAT_ERR_PROBABILITY`, refused, not normalised.
`[-0.1, 0.6, 0.5]` sums to 1.0 with a negative entry -> `STRAT_ERR_PROBABILITY`.
`[0.25, 0.5, 0.25 + 1e-13]` misses 1.0 by 1e-13, which is INSIDE a 1e-12 tolerance, so it is
accepted and the miss is REPORTED as `max_row_error` — a number in (5e-14, 2e-13).

Case 6 — absence is not zero
----------------------------
A constant policy's action is 0 for strategy 0 (present) while its SCORE does not exist
(`has_score` False, slot exactly 0.0). And `max_row_error` is 0.0 for BOTH a tabular block, where
no such quantity exists (`has_row_error` False), and an exact mixed block, where it exists and is
zero (`has_row_error` True). Same slot value, two different findings, distinguished only by the
flag — which is the whole rule.

Case 7 — the frozen argmax convention, asserted rather than assumed
------------------------------------------------------------------
`policy_from_q_flat` on Q = `[[0,1], [2,0], [3,3]]` must return `[1, 0, 0]`. The third row is a
deliberate TIE and the frozen `reinforcement.policy_from_q` resolves it to index 0 because its
`_argmax` advances only on a strict `>`. This module claims the same convention in
`policy_tie_rule()`, so the two are checked against each other here: if the frozen kernel ever
resolved a tie the other way, this module's declared rule would be a lie and this assertion is
what would catch it.

Case 8 — a value function computed from the Bellman equation by hand
-------------------------------------------------------------------
Two states, one action, rewards `[1, 0]`, transitions `[0, 1]` (both self-loops), gamma 0.5:

    V(0) = 1 + 0.5 V(0)  =>  V(0) = 2        V(1) = 0 + 0.5 V(1)  =>  V(1) = 0

V(1) is asserted EXACTLY 0.0 — every sweep computes `0 + 0.5*0`. V(0) is asserted within 1e-9,
and that tolerance has a derivation rather than being picked: the frozen iteration is a
contraction with ratio 0.5 from V=0, it stops when the sweep-to-sweep change falls below the
requested 1e-12, so it stops around 2 - 2^-40 and the remaining gap is ~9.1e-13. Demanding
exactly 2.0 would refuse a correct kernel; a tolerance of 1e-3 would accept a wrong one.

The status is OK, `exactness` is APPROXIMATE (it is an iteration, and the package says so rather
than storing an approximation as a fact), and the Bellman residual is reported and asserted below
1e-11. `work_charged` is 10000 * 2 = 20000: the sweep cap times the states.

Case 9 — an iteration that does not converge is REFUSED, with its residual
-------------------------------------------------------------------------
The same MDP at gamma = 1.0. The value function diverges, the frozen kernel simply stops at its
sweep cap, and what it returns is finite and plausible and not a value function: V(0) = 10000.0
exactly, because each of the 10000 sweeps adds exactly 1. The Bellman residual is then

    |1 + 1.0 * 10000 - 10000| = 1.0      exactly

so the status is `STRAT_ERR_NOT_CONVERGED`, `has_values` is False, `values` is EMPTY, and the
residual is asserted to be exactly 1.0. Returning the vector anyway is the silent-wrong-answer
this refuses: a caller cannot tell it from a converged one.

Case 10 — the two refusals that would otherwise be an UNCATCHABLE process abort
------------------------------------------------------------------------------
`reinforcement.policy_evaluation` evaluates `rewards[s][a] + gamma * V[transitions[s][a]]` with no
range check of its own, inside frozen code. So:

    transitions [0, 5] in a TWO-state MDP  -> `STRAT_ERR_STATE_RANGE`   (would read V[5])
    actions     [0, 3] with ONE action     -> `STRAT_ERR_ACTION_RANGE`  (would read a[3])

Both are refused before the kernel is entered. The suite runs them BEFORE later assertions and
prints its summary afterwards, so the fact that the process is still alive to print is itself the
assertion: a `try`/`except` could not have contained either one.

Case 11 — every other refusal is typed, and none of them aborts
---------------------------------------------------------------
Sixteen malformed requests, each expected to name its own defect: an unknown kind, a zero-state
tabular policy, a 40-wide row against a 12-state environment, a table entry of 3.0 where there are
three actions, a non-integral 1.5, a threshold policy against a ONE-action environment (it can
emit action 1, which that environment does not have), a lookup at state 4 of a four-state
environment, a strategy index past the block, `n_factors = 6` against a five-element factor list,
a NaN factor, a NaN parameter, a negative tolerance, a discount of 1.5, and three shape
mismatches. `n_factors = 6` against a five-element list is the one that would end the worker.

Case 12 — the work budget binds where it was measured to
-------------------------------------------------------
The frozen iteration sweeps every state up to 10000 times, and that work is bounded by nothing a
`List` length can express. The charge is weighted by MEASUREMENT — 44.4 ns per state update against
the 1.66 ns this package calls one unit, rounded up to 32 — and the boundary is asserted one state
either side: 1677 states is accepted (0.74s at the forced sweep cap) and 1678 is refused with
`STRAT_ERR_WORK_BUDGET` and a charge of -1, never 0, because 0 reads as "free". The first version
of this charge weighted an update at ONE unit, accepted 16384 states at 30.5% of the ceiling, and
ran for 4.20 seconds; a refusal that cannot fire is not a budget.

Case 13 — a randomised policy, reproducibly
-------------------------------------------
`policy_sample_mixed` inverse-transforms ONE addressed draw. Two rows make the action a known
value independent of the generator:

    [1, 0, 0] -> action 0 for every step, because u < 1 always
    [0, 0, 1] -> action 2 for every step, because the cumulative total only reaches u at the end

Asserted over eight steps each. The same coordinates twice give the same action (it is a pure
function of them). And the documented ceiling asymmetry is asserted: the strategy index rides in
the `dim1` slot, which `strat_coord_status` bounds by the FACTOR ceiling of 256, so strategy 255
is addressable and strategy 256 is refused with `STRAT_ERR_FACTOR_RANGE` even though 301
strategies is a legal block. Finally the spread of a `[0.5, 0.5, 0]` row over 256 steps is
MEASURED and printed — asserted only to be a split (both actions occur), because a suite that
asserted a count would be asserting the generator's values rather than this module's logic.
"""
from strategy.contract import (
    STRAT_ERR_ACTION_RANGE,
    STRAT_ERR_COUNT,
    STRAT_ERR_DISCOUNT_RANGE,
    STRAT_ERR_FACTOR_RANGE,
    STRAT_ERR_NON_FINITE,
    STRAT_ERR_NOT_CONVERGED,
    STRAT_ERR_NOT_EVALUABLE,
    STRAT_ERR_POLICY_ARITY,
    STRAT_ERR_POLICY_KIND,
    STRAT_ERR_PROBABILITY,
    STRAT_ERR_SHAPE,
    STRAT_ERR_STATE_RANGE,
    STRAT_ERR_TOLERANCE,
    STRAT_ERR_WORK_BUDGET,
    STRAT_EXACT_APPROXIMATE,
    STRAT_EXACT_CLOSED_FORM,
    STRAT_MAX_FACTORS,
    STRAT_MAX_WORK,
    STRAT_OK,
    STRAT_POLICY_CONSTANT,
    STRAT_POLICY_MIXED,
    STRAT_POLICY_TABULAR,
    STRAT_POLICY_THRESHOLD,
    strat_status_name,
)
from strategy.policy import (
    POLICY_EVAL_MAX_SWEEPS,
    POLICY_NO_ACTION,
    POLICY_SWEEP_WEIGHT,
    policy_action_flat,
    policy_evaluate_tabular,
    policy_from_q_flat,
    policy_linear_action,
    policy_sample_mixed,
    policy_tabular_actions,
    policy_tie_rule,
    policy_validate_flat,
)


fn _f0() -> List[Float64]:
    return List[Float64]()


fn _f1(a: Float64) -> List[Float64]:
    var o = List[Float64]()
    o.append(a)
    return o^


fn _f2(a: Float64, b: Float64) -> List[Float64]:
    var o = List[Float64]()
    o.append(a); o.append(b)
    return o^


fn _f3(a: Float64, b: Float64, c: Float64) -> List[Float64]:
    var o = List[Float64]()
    o.append(a); o.append(b); o.append(c)
    return o^


fn _f4(a: Float64, b: Float64, c: Float64, d: Float64) -> List[Float64]:
    var o = List[Float64]()
    o.append(a); o.append(b); o.append(c); o.append(d)
    return o^


fn _f6(
    a: Float64, b: Float64, c: Float64, d: Float64, e: Float64, f: Float64
) -> List[Float64]:
    var o = List[Float64]()
    o.append(a); o.append(b); o.append(c); o.append(d); o.append(e); o.append(f)
    return o^


fn _f8(
    a: Float64, b: Float64, c: Float64, d: Float64,
    e: Float64, f: Float64, g: Float64, h: Float64,
) -> List[Float64]:
    var o = List[Float64]()
    o.append(a); o.append(b); o.append(c); o.append(d)
    o.append(e); o.append(f); o.append(g); o.append(h)
    return o^


fn _i2(a: Int, b: Int) -> List[Int]:
    var o = List[Int]()
    o.append(a); o.append(b)
    return o^


fn _repeat_rows(n_rows: Int, a: Float64, b: Float64, c: Float64) -> List[Float64]:
    var o = List[Float64]()
    for _ in range(n_rows):
        o.append(a); o.append(b); o.append(c)
    return o^


fn main():
    var passed = 0
    var failed = 0
    var tol: Float64 = 1e-12
    print("\n[strategy.policy] known-value suite")

    # ── 1. the tie rule is a value, not a comment ─────────────────────────────
    if policy_tie_rule() == "argmax:lowest_index;threshold:closed_at_threshold/v1":
        passed += 1
        print("  ✅ tie rule names itself:", policy_tie_rule())
    else:
        failed += 1
        print("  ❌ tie rule identifier changed:", policy_tie_rule())

    # ── 2. a threshold policy either side of its threshold, and exactly ON it ─
    var thr = _f3(0.5, 0.25, 0.375)
    var below = policy_action_flat(
        thr, 1, 0, STRAT_POLICY_THRESHOLD, _f2(0.5, 0.25), 2, 0, 2, 0, tol
    )
    var on = policy_action_flat(
        thr, 1, 0, STRAT_POLICY_THRESHOLD, _f2(0.5, 0.5), 2, 0, 2, 0, tol
    )
    var above = policy_action_flat(
        thr, 1, 0, STRAT_POLICY_THRESHOLD, _f2(0.75, 0.5), 2, 0, 2, 0, tol
    )
    var thr_ok = below.status == STRAT_OK and on.status == STRAT_OK
    thr_ok = thr_ok and above.status == STRAT_OK
    thr_ok = thr_ok and below.score == 0.3125 and below.action == 0 and not below.at_tie
    thr_ok = thr_ok and on.score == 0.375 and on.action == 1 and on.at_tie
    thr_ok = thr_ok and on.n_tied == 2
    thr_ok = thr_ok and above.score == 0.5 and above.action == 1 and not above.at_tie
    thr_ok = thr_ok and below.has_score and on.has_score and above.has_score
    if thr_ok:
        passed += 1
        print(
            "  ✅ threshold 0.375: score", below.score, "-> action", below.action,
            "| score", on.score, "-> action", on.action, "(ON the threshold, at_tie",
            on.at_tie, ") | score", above.score, "-> action", above.action,
        )
    else:
        failed += 1
        print(
            "  ❌ threshold policy wrong:", below.score, below.action, on.score,
            on.action, on.at_tie, above.score, above.action,
        )

    # ── 3. a lookup policy at every cell, two strategies ─────────────────────
    var tab = _f8(2.0, 0.0, 1.0, 1.0, 0.0, 0.0, 2.0, 2.0)
    var want0 = List[Int](); want0.append(2); want0.append(0); want0.append(1); want0.append(1)
    var want1 = List[Int](); want1.append(0); want1.append(0); want1.append(2); want1.append(2)
    var cells_ok = True
    for s in range(4):
        var a0 = policy_action_flat(tab, 2, 0, STRAT_POLICY_TABULAR, _f0(), 0, s, 3, 4, tol)
        var a1 = policy_action_flat(tab, 2, 1, STRAT_POLICY_TABULAR, _f0(), 0, s, 3, 4, tol)
        if a0.status != STRAT_OK or a0.action != want0[s]:
            cells_ok = False
        if a1.status != STRAT_OK or a1.action != want1[s]:
            cells_ok = False
        if a0.has_score or a1.has_score or a0.score != 0.0:
            cells_ok = False
    var table0 = policy_tabular_actions(tab, 2, 0, 3, 4)
    var table1 = policy_tabular_actions(tab, 2, 1, 3, 4)
    var table_ok = table0.status == STRAT_OK and table1.status == STRAT_OK
    table_ok = table_ok and table0.has_actions and len(table0.actions) == 4
    table_ok = table_ok and table0.exactness == STRAT_EXACT_CLOSED_FORM
    for s in range(4):
        if table0.actions[s] != want0[s] or table1.actions[s] != want1[s]:
            table_ok = False
    if cells_ok and table_ok:
        passed += 1
        print(
            "  ✅ lookup policy, all 8 cells: strategy 0 ->",
            table0.actions[0], table0.actions[1], table0.actions[2], table0.actions[3],
            "| strategy 1 ->",
            table1.actions[0], table1.actions[1], table1.actions[2], table1.actions[3],
        )
    else:
        failed += 1
        print("  ❌ lookup policy disagreed with the block or with itself")

    # ── 4. a linear score per action, with a deliberate three-way tie ────────
    var w = _f6(1.0, 0.0, 0.0, 1.0, 0.5, 0.5)
    var clear = policy_linear_action(w, 3, 2, _f2(0.25, 0.75), tol)
    var tie3 = policy_linear_action(w, 3, 2, _f2(0.5, 0.5), tol)
    var lin_ok = clear.status == STRAT_OK and tie3.status == STRAT_OK
    lin_ok = lin_ok and len(clear.scores) == 3 and len(tie3.scores) == 3
    lin_ok = lin_ok and clear.scores[0] == 0.25 and clear.scores[1] == 0.75
    lin_ok = lin_ok and clear.scores[2] == 0.5
    lin_ok = lin_ok and clear.action == 1 and clear.best_score == 0.75
    lin_ok = lin_ok and clear.n_tied == 1 and not clear.at_tie
    lin_ok = lin_ok and tie3.scores[0] == 0.5 and tie3.scores[1] == 0.5
    lin_ok = lin_ok and tie3.scores[2] == 0.5
    lin_ok = lin_ok and tie3.action == 0 and tie3.n_tied == 3 and tie3.at_tie
    if lin_ok:
        passed += 1
        print(
            "  ✅ linear argmax: scores", clear.scores[0], clear.scores[1],
            clear.scores[2], "-> action", clear.action, "| tie", tie3.scores[0],
            tie3.scores[1], tie3.scores[2], "-> action", tie3.action, "n_tied",
            tie3.n_tied,
        )
    else:
        failed += 1
        print("  ❌ linear argmax or its tie rule is wrong")

    # ── 5. a mixed policy: greedy reduction, ties, non-distributions ─────────
    var mixed = _f6(0.25, 0.5, 0.25, 0.5, 0.5, 0.0)
    var m0 = policy_action_flat(mixed, 2, 0, STRAT_POLICY_MIXED, _f0(), 0, 0, 3, 0, tol)
    var m1 = policy_action_flat(mixed, 2, 1, STRAT_POLICY_MIXED, _f0(), 0, 0, 3, 0, tol)
    var mixed_ok = m0.status == STRAT_OK and m1.status == STRAT_OK
    mixed_ok = mixed_ok and m0.action == 1 and m0.score == 0.5 and m0.n_tied == 1
    mixed_ok = mixed_ok and not m0.at_tie
    mixed_ok = mixed_ok and m1.action == 0 and m1.score == 0.5 and m1.n_tied == 2
    mixed_ok = mixed_ok and m1.at_tie
    var not_dist = policy_validate_flat(
        _f3(0.5, 0.25, 0.1), 1, STRAT_POLICY_MIXED, 0, 3, 0, tol
    )
    var negative = policy_validate_flat(
        _f3(-0.1, 0.6, 0.5), 1, STRAT_POLICY_MIXED, 0, 3, 0, tol
    )
    var near = policy_validate_flat(
        _f3(0.25, 0.5, 0.25 + 1e-13), 1, STRAT_POLICY_MIXED, 0, 3, 0, tol
    )
    mixed_ok = mixed_ok and not_dist.status == STRAT_ERR_PROBABILITY
    mixed_ok = mixed_ok and negative.status == STRAT_ERR_PROBABILITY
    mixed_ok = mixed_ok and near.status == STRAT_OK and near.has_row_error
    mixed_ok = mixed_ok and near.max_row_error > 5e-14 and near.max_row_error < 2e-13
    if mixed_ok:
        passed += 1
        print(
            "  ✅ mixed policy: argmax", m0.action, "at p =", m0.score,
            "| tie -> action", m1.action, "n_tied", m1.n_tied,
            "| a row 1e-13 off 1.0 is accepted and its miss reported:",
            near.max_row_error,
        )
    else:
        failed += 1
        print(
            "  ❌ mixed policy wrong:", m0.action, m0.score, m1.action, m1.n_tied,
            strat_status_name(not_dist.status), near.max_row_error,
        )

    # ── 6. absence is not zero ───────────────────────────────────────────────
    var const_block = _f2(0.0, 2.0)
    var c0 = policy_action_flat(const_block, 2, 0, STRAT_POLICY_CONSTANT, _f0(), 0, 0, 3, 0, tol)
    var c1 = policy_action_flat(const_block, 2, 1, STRAT_POLICY_CONSTANT, _f0(), 0, 0, 3, 0, tol)
    var tab_audit = policy_validate_flat(tab, 2, STRAT_POLICY_TABULAR, 0, 3, 4, tol)
    var mix_audit = policy_validate_flat(mixed, 2, STRAT_POLICY_MIXED, 0, 3, 0, tol)
    var absence_ok = c0.status == STRAT_OK and c1.status == STRAT_OK
    absence_ok = absence_ok and c0.has_action and c0.action == 0 and c1.action == 2
    absence_ok = absence_ok and not c0.has_score and c0.score == 0.0
    absence_ok = absence_ok and tab_audit.status == STRAT_OK
    absence_ok = absence_ok and not tab_audit.has_row_error and tab_audit.max_row_error == 0.0
    absence_ok = absence_ok and tab_audit.arity == 4 and tab_audit.n_action_cells == 8
    absence_ok = absence_ok and mix_audit.status == STRAT_OK and mix_audit.has_row_error
    absence_ok = absence_ok and mix_audit.max_row_error == 0.0
    absence_ok = absence_ok and mix_audit.n_action_cells == 0
    if absence_ok:
        passed += 1
        print(
            "  ✅ absence: action 0 is an ANSWER (has_action True) while that same",
            "constant policy's score is ABSENT (has_score False, slot", c0.score,
            "); max_row_error is 0.0 with the flag False for a table and True for an",
            "exact mixed block",
        )
    else:
        failed += 1
        print("  ❌ an absent quantity was reported as zero, or a present one as absent")

    # ── 7. the frozen argmax tie convention, asserted not assumed ────────────
    var greedy = policy_from_q_flat(_f6(0.0, 1.0, 2.0, 0.0, 3.0, 3.0), 3, 2)
    var greedy_ok = greedy.status == STRAT_OK and greedy.has_actions
    greedy_ok = greedy_ok and len(greedy.actions) == 3
    greedy_ok = greedy_ok and greedy.actions[0] == 1 and greedy.actions[1] == 0
    greedy_ok = greedy_ok and greedy.actions[2] == 0
    greedy_ok = greedy_ok and greedy.exactness == STRAT_EXACT_CLOSED_FORM
    if greedy_ok:
        passed += 1
        print(
            "  ✅ frozen policy_from_q: Q [[0,1],[2,0],[3,3]] -> policy",
            greedy.actions[0], greedy.actions[1], greedy.actions[2],
            "— the tied row resolves to the LOWEST index, matching policy_tie_rule()",
        )
    else:
        failed += 1
        print("  ❌ the frozen argmax convention no longer matches the declared tie rule")

    # ── 8. a value function derived from the Bellman equation by hand ────────
    var rewards = _f2(1.0, 0.0)
    var transitions = _i2(0, 1)
    var acts = _i2(0, 0)
    var v = policy_evaluate_tabular(acts, 2, 1, rewards, transitions, 0.5, tol)
    var v_gap: Float64 = 1.0
    if v.has_values and len(v.values) == 2:
        v_gap = v.values[0] - 2.0
        if v_gap < 0.0:
            v_gap = -v_gap
    var v_ok = v.status == STRAT_OK and v.has_values and len(v.values) == 2
    v_ok = v_ok and v_gap < 1e-9 and v.values[1] == 0.0
    v_ok = v_ok and v.exactness == STRAT_EXACT_APPROXIMATE
    v_ok = v_ok and v.has_residual and v.residual < 1e-11 and v.converged
    v_ok = v_ok and v.work_charged == POLICY_SWEEP_WEIGHT * POLICY_EVAL_MAX_SWEEPS * 2 + 2
    if v_ok:
        passed += 1
        print(
            "  ✅ V(0) = 1 + 0.5 V(0) = 2:", v.values[0], "| V(1) exactly",
            v.values[1], "| residual", v.residual, "| approximate-with-residual, work",
            v.work_charged,
        )
    else:
        failed += 1
        print("  ❌ policy evaluation known value wrong:", v.status, v.residual)

    # ── 9. an iteration that does not converge is refused, with its residual ─
    var diverge = policy_evaluate_tabular(acts, 2, 1, rewards, transitions, 1.0, tol)
    var div_ok = diverge.status == STRAT_ERR_NOT_CONVERGED
    div_ok = div_ok and not diverge.has_values and len(diverge.values) == 0
    div_ok = div_ok and diverge.has_residual and diverge.residual == 1.0
    div_ok = div_ok and not diverge.converged
    if div_ok:
        passed += 1
        print(
            "  ✅ gamma = 1.0 on a recurrent MDP: residual exactly", diverge.residual,
            "-> ", strat_status_name(diverge.status),
            ", values withheld (len", len(diverge.values), ")",
        )
    else:
        failed += 1
        print(
            "  ❌ a non-fixed-point was reported as a value function:",
            strat_status_name(diverge.status), diverge.residual, diverge.has_values,
        )

    # ── 10. the two refusals that would otherwise abort the worker ───────────
    var bad_state = policy_evaluate_tabular(acts, 2, 1, rewards, _i2(0, 5), 0.5, tol)
    var bad_action = policy_evaluate_tabular(_i2(0, 3), 2, 1, rewards, transitions, 0.5, tol)
    if (
        bad_state.status == STRAT_ERR_STATE_RANGE
        and bad_action.status == STRAT_ERR_ACTION_RANGE
        and not bad_state.has_values
        and not bad_action.has_values
    ):
        passed += 1
        print(
            "  ✅ a transition naming state 5 in a 2-state MDP ->",
            strat_status_name(bad_state.status),
            "; an action index 3 with 1 action ->",
            strat_status_name(bad_action.status),
            "— both would have read past a List inside frozen code",
        )
    else:
        failed += 1
        print("  ❌ an out-of-range MDP index was not refused before the frozen kernel")

    # ── 11. every other refusal is typed, and none of them aborts ────────────
    var refusals = True
    var unknown_kind = policy_validate_flat(_f1(0.0), 1, 99, 2, 2, 2, tol)
    refusals = refusals and unknown_kind.status == STRAT_ERR_POLICY_KIND
    refusals = refusals and unknown_kind.arity == -1 and not unknown_kind.evaluable
    var zero_states = policy_validate_flat(_f4(0.0, 1.0, 0.0, 1.0), 1, STRAT_POLICY_TABULAR, 0, 2, 0, tol)
    refusals = refusals and zero_states.status == STRAT_ERR_POLICY_ARITY
    var wide_row = policy_validate_flat(_f4(0.0, 1.0, 0.0, 1.0), 1, STRAT_POLICY_TABULAR, 0, 2, 12, tol)
    refusals = refusals and wide_row.status == STRAT_ERR_SHAPE
    var action_too_big = policy_validate_flat(_f4(3.0, 0.0, 1.0, 1.0), 1, STRAT_POLICY_TABULAR, 0, 3, 4, tol)
    refusals = refusals and action_too_big.status == STRAT_ERR_ACTION_RANGE
    var fractional = policy_validate_flat(_f4(1.5, 0.0, 1.0, 1.0), 1, STRAT_POLICY_TABULAR, 0, 3, 4, tol)
    refusals = refusals and fractional.status == STRAT_ERR_ACTION_RANGE
    var one_action = policy_validate_flat(thr, 1, STRAT_POLICY_THRESHOLD, 2, 1, 0, tol)
    refusals = refusals and one_action.status == STRAT_ERR_ACTION_RANGE
    var bad_lookup = policy_action_flat(tab, 2, 0, STRAT_POLICY_TABULAR, _f0(), 0, 4, 3, 4, tol)
    refusals = refusals and bad_lookup.status == STRAT_ERR_STATE_RANGE
    refusals = refusals and bad_lookup.action == POLICY_NO_ACTION
    var no_such_strategy = policy_action_flat(tab, 2, 7, STRAT_POLICY_TABULAR, _f0(), 0, 0, 3, 4, tol)
    refusals = refusals and no_such_strategy.status == STRAT_ERR_NOT_EVALUABLE
    var negative_strategy = policy_action_flat(tab, 2, -1, STRAT_POLICY_TABULAR, _f0(), 0, 0, 3, 4, tol)
    refusals = refusals and negative_strategy.status == STRAT_ERR_NOT_EVALUABLE
    # THE ONE THAT WOULD END THE WORKER: a count larger than the list it bounds.
    var over_count = policy_action_flat(
        thr, 1, 0, STRAT_POLICY_THRESHOLD, _f2(0.5, 0.5), 6, 0, 2, 0, tol
    )
    refusals = refusals and over_count.status == STRAT_ERR_COUNT
    var nan_factor = policy_action_flat(
        thr, 1, 0, STRAT_POLICY_THRESHOLD, _f2(0.0 / 0.0, 0.5), 2, 0, 2, 0, tol
    )
    refusals = refusals and nan_factor.status == STRAT_ERR_NON_FINITE
    var nan_param = policy_validate_flat(
        _f3(0.5, 0.0 / 0.0, 0.375), 1, STRAT_POLICY_THRESHOLD, 2, 2, 0, tol
    )
    refusals = refusals and nan_param.status == STRAT_ERR_NON_FINITE
    var bad_tol = policy_validate_flat(thr, 1, STRAT_POLICY_THRESHOLD, 2, 2, 0, -1.0)
    refusals = refusals and bad_tol.status == STRAT_ERR_TOLERANCE
    var bad_gamma = policy_evaluate_tabular(acts, 2, 1, rewards, transitions, 1.5, tol)
    refusals = refusals and bad_gamma.status == STRAT_ERR_DISCOUNT_RANGE
    var short_actions = policy_evaluate_tabular(acts, 5, 1, rewards, transitions, 0.5, tol)
    refusals = refusals and short_actions.status == STRAT_ERR_COUNT
    var bad_q = policy_from_q_flat(_f3(1.0, 2.0, 3.0), 3, 2)
    refusals = refusals and bad_q.status == STRAT_ERR_SHAPE
    var bad_weights = policy_linear_action(_f3(1.0, 0.0, 0.0), 3, 2, _f2(0.5, 0.5), tol)
    refusals = refusals and bad_weights.status == STRAT_ERR_SHAPE
    var short_factors = policy_linear_action(_f6(1.0, 0.0, 0.0, 1.0, 0.5, 0.5), 3, 2, _f1(0.5), tol)
    refusals = refusals and short_factors.status == STRAT_ERR_COUNT
    var overflow = policy_evaluate_tabular(acts, 2, 1, _f2(1e308, 0.0), transitions, 1.0, tol)
    refusals = refusals and overflow.status == STRAT_ERR_NON_FINITE
    if refusals:
        passed += 1
        print(
            "  ✅ 19 malformed requests, each refused with the code naming its own",
            "defect, and the process is still running to say so",
        )
    else:
        failed += 1
        print(
            "  ❌ a malformed request was accepted or mis-typed:",
            strat_status_name(unknown_kind.status), strat_status_name(wide_row.status),
            strat_status_name(over_count.status), strat_status_name(overflow.status),
        )

    # ── 12. the work budget is a REACHABLE refusal, one state either side ────
    # One action per state, so the reward and transition blocks are `n_states` cells exactly —
    # a product RELATION, which means each side of the boundary needs its own pair.
    var edge_states = 1677
    var edge_acts = List[Int]()
    var in_rewards = List[Float64]()
    var in_trans = List[Int]()
    var out_rewards = List[Float64]()
    var out_trans = List[Int]()
    for s in range(edge_states + 1):
        edge_acts.append(0)
        out_rewards.append(1.0)
        out_trans.append(s)
        if s < edge_states:
            in_rewards.append(1.0)
            in_trans.append(s)
    var accepted = policy_evaluate_tabular(
        edge_acts, edge_states, 1, in_rewards, in_trans, 0.5, tol
    )
    var refused = policy_evaluate_tabular(
        edge_acts, edge_states + 1, 1, out_rewards, out_trans, 0.5, tol
    )
    var budget_ok = accepted.status == STRAT_OK and accepted.has_values
    budget_ok = budget_ok and accepted.work_charged <= STRAT_MAX_WORK
    budget_ok = budget_ok and refused.status == STRAT_ERR_WORK_BUDGET
    budget_ok = budget_ok and refused.work_charged == -1
    budget_ok = budget_ok and not refused.has_values
    if budget_ok:
        passed += 1
        print(
            "  ✅ work budget: 1677 states accepted at", accepted.work_charged,
            "units (measured 0.74s at the forced sweep cap) and 1678 refused ->",
            strat_status_name(refused.status), "with charge", refused.work_charged,
        )
    else:
        failed += 1
        print(
            "  ❌ the work budget does not bind where it was measured to:",
            accepted.status, accepted.work_charged, strat_status_name(refused.status),
        )

    # ── 13. a randomised policy, reproducibly, on the policy stream ──────────
    var certain0 = _f3(1.0, 0.0, 0.0)
    var certain2 = _f3(0.0, 0.0, 1.0)
    var sample_ok = True
    for step in range(8):
        var s0 = policy_sample_mixed(certain0, 1, 0, 3, 7, 1, 0, step, tol)
        var s2 = policy_sample_mixed(certain2, 1, 0, 3, 7, 1, 0, step, tol)
        if s0.status != STRAT_OK or s0.action != 0:
            sample_ok = False
        if s2.status != STRAT_OK or s2.action != 2:
            sample_ok = False
    var repeat_a = policy_sample_mixed(mixed, 2, 0, 3, 7, 1, 3, 11, tol)
    var repeat_b = policy_sample_mixed(mixed, 2, 0, 3, 7, 1, 3, 11, tol)
    sample_ok = sample_ok and repeat_a.status == STRAT_OK
    sample_ok = sample_ok and repeat_a.action == repeat_b.action
    var big = _repeat_rows(301, 1.0, 0.0, 0.0)
    var last_addressable = policy_sample_mixed(big, 301, STRAT_MAX_FACTORS - 1, 3, 7, 1, 0, 0, tol)
    var past_dim1 = policy_sample_mixed(big, 301, STRAT_MAX_FACTORS, 3, 7, 1, 0, 0, tol)
    sample_ok = sample_ok and last_addressable.status == STRAT_OK
    sample_ok = sample_ok and past_dim1.status == STRAT_ERR_FACTOR_RANGE
    var even = _f3(0.5, 0.5, 0.0)
    var zeros = 0
    for step in range(256):
        var pick = policy_sample_mixed(even, 1, 0, 3, 99, 1, 0, step, tol)
        if pick.status == STRAT_OK and pick.action == 0:
            zeros += 1
    sample_ok = sample_ok and zeros > 0 and zeros < 256
    if sample_ok:
        passed += 1
        print(
            "  ✅ sampled mixed policy: [1,0,0] -> 0 and [0,0,1] -> 2 at every step;",
            "identical coordinates repeat; strategy 255 addressable and 256 refused",
            "(dim1 carries the strategy); a [0.5,0.5,0] row split", zeros, "/ 256",
        )
    else:
        failed += 1
        print(
            "  ❌ sampling wrong:", last_addressable.status,
            strat_status_name(past_dim1.status), "split", zeros,
        )

    print("  [strategy.policy] Passed:", passed, "Failed:", failed)
