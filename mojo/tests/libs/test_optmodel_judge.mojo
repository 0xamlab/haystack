"""test_optmodel_judge.mojo — known-value tests for ground-truth judging and verdicts.

Hand-written. The two tolerance regimes are asserted to DISAGREE on the cases they are
designed to disagree on — a judge whose regimes always agree is one regime wearing two
names — and every classification has its mutated twin, so the three buckets are proved
reachable and proved distinct:

  * (103, 100): strict rejects (3e-2 > 1e-4), lineage accepts (3% <= 5%). (106, 100):
    lineage rejects too (6%). (100.000001, 100): both accept.
  * Near zero the strict regime is absolute (`max(1, |truth|)` floor): 5e-5 against a
    truth of 0 passes strict; 0.6 fails BOTH — rounding takes it to 1 against 0, and
    the OptMATH quotient `|1 - 0| / 0` does not exist, so the coded rule (`round(pred)
    must be 0`) is asserted directly.
  * (100.0, 99.6): lineage compares 100 to 100 and accepts; strict sees 4e-3 and
    rejects — the rounding half of the lineage rule, isolated from the 5% half.
  * A NaN truth or a negative tolerance is `not comparable` with BOTH match flags
    False — "not comparable" never scores as a pass.
  * End to end on the production LP (truth 12): VERIFIED under both regimes. Truth
    12.3: lineage still VERIFIED (rounds to 12), strict says WRONG — the measured gap
    between the regimes on one real solve. Truth 11: WRONG under both (9.1% off after
    rounding). The plane's answer is 12 every time; only the stated truth moves, which
    is exactly the harness's mutation gate.
  * The Wolsey MILP at `max_nodes = 3` is REFUSED under both regimes EVEN WHEN the
    stated truth equals the incumbent 39 — a refusal is never upgraded to a verdict by
    a lucky number. With room to finish it is VERIFIED against truth 40.
  * An infeasible model is REFUSED with the core still attached to the verdict, and a
    NaN truth refuses BEFORE the solve (`ground_truth_not_comparable`).
"""
from optimization.model import (
    MODEL_ERR_POLICY,
    MODEL_OK,
    SENSE_GE,
    SENSE_LE,
    VAR_CONTINUOUS,
    VAR_FLAG_HAS_LOWER,
    VAR_INTEGER,
)
from optmodel.formulation import (
    OPTM_ERR_GROUND_TRUTH,
    OPTM_REFUSED_INFEASIBLE,
    OPTM_REFUSED_SEARCH_LIMIT,
    OPTM_VERDICT_REFUSED,
    OPTM_VERDICT_VERIFIED,
    OPTM_VERDICT_WRONG,
)
from optmodel.judge import (
    OPTM_LINEAGE_REL_TOL,
    OPTM_STRICT_REL_TOL,
    formulation_verdict_default,
    judge_objective,
)


fn _ints(*vals: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn main() raises:
    var passed = 0
    var failed = 0

    # ── the two regimes disagree exactly where designed ───────────────────────
    var j3 = judge_objective(103.0, 100.0, OPTM_STRICT_REL_TOL, OPTM_LINEAGE_REL_TOL)
    var j6 = judge_objective(106.0, 100.0, OPTM_STRICT_REL_TOL, OPTM_LINEAGE_REL_TOL)
    var j_exact = judge_objective(
        100.000001, 100.0, OPTM_STRICT_REL_TOL, OPTM_LINEAGE_REL_TOL
    )
    if (
        j3.comparable and not j3.strict_match and j3.lineage_match
        and j3.rel_error == 0.03
        and j6.comparable and not j6.strict_match and not j6.lineage_match
        and j_exact.strict_match and j_exact.lineage_match
    ):
        passed += 1
        print("  ✅ 103 vs 100: lineage-only; 106 vs 100: neither; 100.000001: both")
    else:
        failed += 1
        print(
            "  ❌ regime disagreement wrong:", j3.strict_match, j3.lineage_match,
            j6.lineage_match, j_exact.strict_match,
        )

    # ── near zero: strict goes absolute, lineage needs round(pred) == 0 ───────
    var near_zero = judge_objective(5e-5, 0.0, OPTM_STRICT_REL_TOL, OPTM_LINEAGE_REL_TOL)
    var off_zero = judge_objective(0.6, 0.0, OPTM_STRICT_REL_TOL, OPTM_LINEAGE_REL_TOL)
    if (
        near_zero.strict_match and near_zero.lineage_match
        and near_zero.rounded_objective == 0.0 and near_zero.rounded_truth == 0.0
        and not off_zero.strict_match and not off_zero.lineage_match
        and off_zero.rounded_objective == 1.0
    ):
        passed += 1
        print("  ✅ truth 0: 5e-5 passes both; 0.6 rounds to 1 and fails both")
    else:
        failed += 1
        print(
            "  ❌ zero handling wrong:", near_zero.strict_match,
            near_zero.lineage_match, off_zero.lineage_match,
        )

    # ── the rounding half of the lineage rule, isolated ───────────────────────
    var rounds = judge_objective(100.0, 99.6, OPTM_STRICT_REL_TOL, OPTM_LINEAGE_REL_TOL)
    if (
        rounds.comparable and not rounds.strict_match and rounds.lineage_match
        and rounds.rounded_objective == 100.0 and rounds.rounded_truth == 100.0
    ):
        passed += 1
        print("  ✅ 100.0 vs 99.6: rounding makes lineage exact while strict rejects")
    else:
        failed += 1
        print("  ❌ rounding half wrong:", rounds.strict_match, rounds.lineage_match)

    # ── not comparable never scores ───────────────────────────────────────────
    var nan = 0.0 / 0.0
    var bad_truth = judge_objective(12.0, nan, OPTM_STRICT_REL_TOL, OPTM_LINEAGE_REL_TOL)
    var bad_tol = judge_objective(12.0, 12.0, -1e-4, OPTM_LINEAGE_REL_TOL)
    if (
        not bad_truth.comparable and bad_truth.status == OPTM_ERR_GROUND_TRUTH
        and not bad_truth.strict_match and not bad_truth.lineage_match
        and not bad_tol.comparable and bad_tol.status == MODEL_ERR_POLICY
        and not bad_tol.strict_match
    ):
        passed += 1
        print("  ✅ NaN truth and negative tolerance are defects, never passes")
    else:
        failed += 1
        print("  ❌ comparability wrong:", bad_truth.status, bad_tol.status)

    # ── end to end: one solve, three stated truths, three classifications ─────
    var truth_right = formulation_verdict_default(
        2, 2, True, _floats(3.0, 2.0), 0.0, _floats(1.0, 1.0, 1.0, 3.0),
        _ints(SENSE_LE, SENSE_LE), _floats(4.0, 6.0),
        _ints(VAR_CONTINUOUS, VAR_CONTINUOUS), _floats(0.0, 0.0), _floats(0.0, 0.0),
        _ints(VAR_FLAG_HAS_LOWER, VAR_FLAG_HAS_LOWER), 12.0, 100,
    )
    var truth_near = formulation_verdict_default(
        2, 2, True, _floats(3.0, 2.0), 0.0, _floats(1.0, 1.0, 1.0, 3.0),
        _ints(SENSE_LE, SENSE_LE), _floats(4.0, 6.0),
        _ints(VAR_CONTINUOUS, VAR_CONTINUOUS), _floats(0.0, 0.0), _floats(0.0, 0.0),
        _ints(VAR_FLAG_HAS_LOWER, VAR_FLAG_HAS_LOWER), 12.3, 100,
    )
    var truth_wrong = formulation_verdict_default(
        2, 2, True, _floats(3.0, 2.0), 0.0, _floats(1.0, 1.0, 1.0, 3.0),
        _ints(SENSE_LE, SENSE_LE), _floats(4.0, 6.0),
        _ints(VAR_CONTINUOUS, VAR_CONTINUOUS), _floats(0.0, 0.0), _floats(0.0, 0.0),
        _ints(VAR_FLAG_HAS_LOWER, VAR_FLAG_HAS_LOWER), 11.0, 100,
    )
    if (
        truth_right.solved and truth_right.verdict_strict == OPTM_VERDICT_VERIFIED
        and truth_right.verdict_lineage == OPTM_VERDICT_VERIFIED
        and truth_right.objective == 12.0 and truth_right.message == "optimal"
        and truth_near.verdict_strict == OPTM_VERDICT_WRONG
        and truth_near.verdict_lineage == OPTM_VERDICT_VERIFIED
        and truth_wrong.verdict_strict == OPTM_VERDICT_WRONG
        and truth_wrong.verdict_lineage == OPTM_VERDICT_WRONG
        and truth_wrong.solved
    ):
        passed += 1
        print("  ✅ truth 12 verified; 12.3 splits the regimes; 11 is WRONG under both")
    else:
        failed += 1
        print(
            "  ❌ end-to-end verdicts wrong:", truth_right.verdict_strict,
            truth_near.verdict_strict, truth_near.verdict_lineage,
            truth_wrong.verdict_lineage,
        )

    # ── a refusal is never upgraded by a lucky truth ──────────────────────────
    var capped_lucky = formulation_verdict_default(
        2, 2, True, _floats(5.0, 8.0), 0.0, _floats(1.0, 1.0, 5.0, 9.0),
        _ints(SENSE_LE, SENSE_LE), _floats(6.0, 45.0),
        _ints(VAR_INTEGER, VAR_INTEGER), _floats(0.0, 0.0), _floats(0.0, 0.0),
        _ints(VAR_FLAG_HAS_LOWER, VAR_FLAG_HAS_LOWER), 39.0, 3,
    )
    var completed = formulation_verdict_default(
        2, 2, True, _floats(5.0, 8.0), 0.0, _floats(1.0, 1.0, 5.0, 9.0),
        _ints(SENSE_LE, SENSE_LE), _floats(6.0, 45.0),
        _ints(VAR_INTEGER, VAR_INTEGER), _floats(0.0, 0.0), _floats(0.0, 0.0),
        _ints(VAR_FLAG_HAS_LOWER, VAR_FLAG_HAS_LOWER), 40.0, 500,
    )
    if (
        capped_lucky.refused
        and capped_lucky.status == OPTM_REFUSED_SEARCH_LIMIT
        and capped_lucky.verdict_strict == OPTM_VERDICT_REFUSED
        and capped_lucky.verdict_lineage == OPTM_VERDICT_REFUSED
        and not capped_lucky.has_objective
        and capped_lucky.message == "refused_search_limit"
        and completed.solved and completed.objective == 40.0
        and completed.verdict_strict == OPTM_VERDICT_VERIFIED
    ):
        passed += 1
        print("  ✅ node-limited Wolsey refuses even at truth 39; finished run verifies 40")
    else:
        failed += 1
        print(
            "  ❌ refusal honesty broken:", capped_lucky.verdict_strict,
            capped_lucky.has_objective, completed.verdict_strict,
        )

    # ── refusal evidence rides the verdict; a NaN truth refuses pre-solve ─────
    var infeasible = formulation_verdict_default(
        1, 2, True, _floats(1.0), 0.0, _floats(1.0, 1.0),
        _ints(SENSE_LE, SENSE_GE), _floats(2.0, 5.0), _ints(VAR_CONTINUOUS),
        _floats(0.0), _floats(0.0), _ints(VAR_FLAG_HAS_LOWER), 7.0, 100,
    )
    var nan_truth = formulation_verdict_default(
        1, 1, True, _floats(1.0), 0.0, _floats(1.0), _ints(SENSE_LE), _floats(3.0),
        _ints(VAR_CONTINUOUS), _floats(0.0), _floats(0.0),
        _ints(VAR_FLAG_HAS_LOWER), nan, 100,
    )
    if (
        infeasible.refused and infeasible.status == OPTM_REFUSED_INFEASIBLE
        and infeasible.verdict_strict == OPTM_VERDICT_REFUSED
        and infeasible.core_size == 2
        and len(infeasible.core_constraints) == 2
        and infeasible.core_constraints[0] == 0
        and infeasible.core_constraints[1] == 1
        and nan_truth.refused and nan_truth.status == OPTM_ERR_GROUND_TRUTH
        and nan_truth.message == "ground_truth_not_comparable"
        and nan_truth.nodes_explored == 0
    ):
        passed += 1
        print("  ✅ the core rides the verdict; a NaN truth refuses before solving")
    else:
        failed += 1
        print(
            "  ❌ verdict evidence wrong:", infeasible.core_size,
            nan_truth.status, nan_truth.message,
        )

    # ── the generated A–Z fixed shape refuses, never crashes ──────────────────
    var az = formulation_verdict_default(
        5, 5, True, _floats(0.5, 0.5, 0.5, 0.5, 0.5), 0.5,
        _floats(0.5, 0.5, 0.5, 0.5, 0.5), _ints(5, 5, 5, 5, 5),
        _floats(0.5, 0.5, 0.5, 0.5, 0.5), _ints(5, 5, 5, 5, 5),
        _floats(0.5, 0.5, 0.5, 0.5, 0.5), _floats(0.5, 0.5, 0.5, 0.5, 0.5),
        _ints(5, 5, 5, 5, 5), 0.5, 5,
    )
    if (
        az.refused and az.verdict_strict == OPTM_VERDICT_REFUSED
        and not az.solved and not az.has_objective
    ):
        passed += 1
        print("  ✅ the A–Z fixed shape (5-lists, Ints of 5) refuses instead of indexing")
    else:
        failed += 1
        print("  ❌ A–Z shape not refused:", az.status, az.solved)

    print("  [optmodel.judge] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("optmodel.judge suite failed")
