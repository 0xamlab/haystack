"""test_optimization_multiobjective.mojo — known-value tests for fronts, crowding,
hypervolume, lexicographic optimisation and a deterministic NSGA-II.

Hand-written. Every expected number below was worked out on paper before the code ran, and
the arithmetic was chosen so it can be: every objective value, reference point and bound is a
small integer or a dyadic fraction, so the hypervolume and crowding assertions use EXACT
equality. A tolerance there would hide a genuine mis-accumulation instead of absorbing a
rounding.

The five-point set is the spine of the file, because its fronts can be enumerated by hand:

    p0 = (1, 5)   p1 = (2, 3)   p2 = (4, 1)   p3 = (3, 6)   p4 = (5, 4)

minimising both. p0 is the only point with f0 = 1, so nothing can beat it; p1 loses to
nobody (p0 is worse in f1, p2 is worse in f0); p2 is the only point with f1 = 1. So front 0
is {p0, p1, p2}. p3 loses to p1 (2 <= 3, 3 <= 6) and p4 loses to both p1 and p2, and p3 and
p4 do not compare with each other (3 < 5 but 6 > 4), so front 1 is {p3, p4} and there are
exactly two fronts, ranks [0, 0, 0, 1, 1].

Three independent oracles are used rather than trusting this module:

  * the FROZEN `multi_objective.is_dominated` is compared against the flat shim over ALL 27
    sign patterns in three objectives — the cross-check the module's design depends on, done
    exhaustively rather than sampled, and with the four-case counts (7 dominating, 7
    dominated, 1 equal, 12 incomparable) asserted as known values;
  * the FROZEN `multi_objective.pareto_front` sizes the true front inside `pareto_certify`;
  * hypervolume is checked against inclusion-exclusion computed by hand: {(1,3), (2,1)}
    against (4,4) is 3 + 6 - 2 = 7 by hand and 3*1 + 2*2 = 7 by the sweep, and the
    three-objective case {(0,1,1), (1,0,1), (1,1,0)} against (2,2,2) is 6 - 3 + 1 = 4, which
    the Monte-Carlo estimate has to land on.

Two behaviours get their own adversarial cases because they are where a plausible answer
hides a wrong one:

  * DUPLICATE points. Two identical points do not dominate each other, so both are rank 0 and
    both are returned — and a hypervolume that counted the second one's rectangle again would
    report 24 where the answer is 12. Asserted.
  * a SUBSET of the true front. It is an antichain, and nothing outside beats it, so the two
    conditions a certificate usually checks both pass. Only maximality catches it. Asserted,
    because that is the omission that certified a cost-5 matching whose optimum was 1.

Determinism is asserted the way the module promises it: the same seed gives a BIT-IDENTICAL
answer and a different seed gives a different one, for both the GA and the Monte-Carlo
hypervolume. A heuristic that fails either is not usable in a decision anybody has to
explain.
"""
from std.math import isinf, isnan

from multi_objective import is_dominated, pareto_front
from optimization.model import (
    MODEL_ERR_BOUNDS_CROSSED,
    MODEL_ERR_DENSE_SHAPE,
    MODEL_ERR_DIMENSION_TOO_LARGE,
    MODEL_ERR_LENGTH_MISMATCH,
    MODEL_ERR_NON_FINITE_BOUND,
    MODEL_ERR_NON_FINITE_VALUE,
    MODEL_ERR_POLICY,
    MODEL_OK,
    SENSE_GE,
    SENSE_LE,
)
from optimization.integer import MILP_BOX_BELOW_ZERO
from optimization.linear import LP_DBL_EPSILON, LP_INFEASIBLE
from optimization.multiobjective import (
    MO_ERR_EMPTY_SET,
    MO_ERR_LP_STAGE_FAILED,
    MO_ERR_OBJECTIVE_COUNT,
    MO_ERR_PARAMETER,
    MO_ERR_REFERENCE_POINT,
    MO_ERR_VERIFICATION_FAILED,
    MO_ERR_WORK_LIMIT,
    MO_HV_ESTIMATE_CLAMPED,
    MO_HV_INEXACT,
    MO_MAX_GENERATIONS,
    MO_MAX_OBJECTIVES,
    MO_MAX_POINTS,
    MO_MAX_SAMPLES,
    MO_MAX_WORK,
    MO_SORT_PAIR_PASSES,
    MO_ULP_BUDGET,
    MO_UNPROVEN,
    crowding_distance,
    hypervolume,
    hypervolume_default,
    lexicographic_linear,
    lexicographic_linear_default,
    mo_dominance,
    mo_matrix_defect,
    mo_reference_point,
    mo_status_name,
    nondominated_sort,
    nsga2_linear,
    nsga2_select,
    pareto_certify,
)
from sparse_numerics.csr import MAX_CSR_DIM


fn _f(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _i(*vals: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _five_points() -> List[Float64]:
    """The spine set: p0=(1,5) p1=(2,3) p2=(4,1) p3=(3,6) p4=(5,4), row-major."""
    return _f(1.0, 5.0, 2.0, 3.0, 4.0, 1.0, 3.0, 6.0, 5.0, 4.0)


fn _first_front() -> List[Float64]:
    """Front 0 of the spine set on its own: (1,5), (2,3), (4,1)."""
    return _f(1.0, 5.0, 2.0, 3.0, 4.0, 1.0)


fn _same_ints(a: List[Int], b: List[Int]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


fn _same_floats_exact(a: List[Float64], b: List[Float64]) -> Bool:
    """Bit-level equality. Used for determinism and for dyadic known values alike."""
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


fn _all_finite(v: List[Float64]) -> Bool:
    """No `inf` and no `nan` anywhere in a returned vector.

    Load-bearing for crowding distance: the textbook algorithm puts an infinity on every
    boundary point, and an `inf` a caller subtracts from another `inf` is a `nan`.
    """
    for i in range(len(v)):
        if isinf(v[i]) or isnan(v[i]):
            return False
    return True


fn _point_ceiling_fits(points: Int, passes: Int, shared_ceiling: Int) -> Bool:
    """True when `points^2 * passes` fits the one shared csr ceiling.

    Written with DIVISIONS, like `sparse_numerics.csr.dims_fit`: `points * points` is a
    wrapping 64-bit multiply, so a test written as a product would pass for a ceiling large
    enough to wrap — exactly the class of non-bound this assertion exists to catch. The three
    numbers are arguments so they stay runtime values and the comparisons are really executed
    instead of folded away at compile time.
    """
    if points <= 0 or passes <= 0 or shared_ceiling <= 0:
        return False
    var budget = shared_ceiling // passes
    if budget <= 0:
        return False
    return points <= budget // points


fn _dominates_pair(f: List[Float64], n_obj: Int, i: Int, j: Int) -> Bool:
    """Does point `i` strictly dominate point `j`, minimising all? Written independently.

    A third implementation on purpose: the module has its flat shim, the frozen kernel has the
    list form, and this one exists so the oracle below shares no code path with either.
    """
    var strictly_better = False
    for t in range(n_obj):
        var a = f[i * n_obj + t]
        var b = f[j * n_obj + t]
        if a > b:
            return False
        if a < b:
            strictly_better = True
    return strictly_better


fn _rank_by_longest_chain(f: List[Float64], n: Int, n_obj: Int) -> List[Int]:
    """`rank[i]` = the length of the longest strictly-dominating chain ending at `i`.

    An independent characterisation of the WHOLE front decomposition, not just of front 0:
    front `r` is exactly the set of points whose longest chain of dominators has length `r`.
    Computed by fixed-point relaxation over a DAG — `n + 1` rounds is more than the `n` a
    chain can need — so it shares nothing with the module's counting peel. If the peel ever
    assigns a point to a front its dominators do not justify, the two vectors diverge.
    """
    var rank = List[Int]()
    for _ in range(n):
        rank.append(0)
    for _ in range(n + 1):
        for i in range(n):
            var best = 0
            for j in range(n):
                if j == i:
                    continue
                if _dominates_pair(f, n_obj, j, i):
                    if rank[j] + 1 > best:
                        best = rank[j] + 1
            rank[i] = best
    return rank^


fn _near_list(a: List[Float64], b: List[Float64], tol: Float64) -> Bool:
    """Element-wise closeness. Used ONLY where a tolerance is the honest comparison.

    The lexicographic answers are the one place in this file that cannot be asserted
    exactly, and the reason is the module's own documented behaviour rather than sloppiness:
    a lock is `c_j.x <= opt_j + slack_j` with `slack_j` a DBL_EPSILON-sized rounding
    allowance, so a later stage may legitimately trade that much of an earlier objective. At
    `opt_0 = -5` the allowance is about 2.3e-12 and the second objective legitimately reaches
    -4.5e-12 instead of 0. Demanding 0.0 exactly would be asserting that the slack does not
    exist, and the slack is the point.
    """
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        var d = a[i] - b[i]
        if d < 0.0:
            d = -d
        if d > tol:
            return False
    return True


fn _dyadic_hv(hv_value: Float64, expected: Float64) -> Bool:
    """Exact equality. Every hypervolume asserted in this file is a dyadic rational."""
    return hv_value == expected


fn main() raises:
    var passed = 0
    var failed = 0

    # ── the dominance relation, exhaustively against the frozen kernel ────────
    # All 27 sign patterns in three objectives, a = (0,0,0) against b = (d0,d1,d2) with each
    # d in {-1, 0, +1}. Minimising, so a dominates b iff every d >= 0 and some d > 0 (7
    # patterns), b dominates a iff every d <= 0 and some d < 0 (7), they are equal in exactly
    # one, and the remaining 12 are incomparable. Those four counts are the known values, and
    # every pattern is also cross-checked against the FROZEN `is_dominated` — the agreement
    # the module's flat shim depends on.
    var n_a_dom = 0
    var n_b_dom = 0
    var n_equal = 0
    var n_incomparable = 0
    var frozen_agrees = True
    var exhaustive = True
    var weak_consistent = True
    for d0 in range(3):
        for d1 in range(3):
            for d2 in range(3):
                var a = _f(0.0, 0.0, 0.0)
                var b = _f(
                    Float64(d0) - 1.0, Float64(d1) - 1.0, Float64(d2) - 1.0
                )
                var r = mo_dominance(a, b, 3)
                if r.status != MODEL_OK:
                    exhaustive = False
                    continue
                var mask = _f()
                var flags = List[Bool]()
                for _ in range(3):
                    flags.append(False)
                # `is_dominated(x, y, mask)` answers "does y dominate x".
                if r.a_dominates_b != is_dominated(b, a, flags):
                    frozen_agrees = False
                if r.b_dominates_a != is_dominated(a, b, flags):
                    frozen_agrees = False
                _ = mask
                var count = 0
                if r.equal:
                    count += 1
                    n_equal += 1
                if r.a_dominates_b:
                    count += 1
                    n_a_dom += 1
                if r.b_dominates_a:
                    count += 1
                    n_b_dom += 1
                if r.incomparable:
                    count += 1
                    n_incomparable += 1
                if count != 1:
                    exhaustive = False
                # Weak dominance must hold in BOTH directions exactly when equal, and imply
                # the strict relation otherwise.
                if r.equal:
                    if not (r.a_weakly_dominates_b and r.b_weakly_dominates_a):
                        weak_consistent = False
                else:
                    if r.a_weakly_dominates_b != r.a_dominates_b:
                        weak_consistent = False
                    if r.b_weakly_dominates_a != r.b_dominates_a:
                        weak_consistent = False
    if frozen_agrees:
        passed += 1
        print("  ✅ the flat shim agrees with frozen is_dominated on all 27 sign patterns")
    else:
        failed += 1
        print("  ❌ shim and frozen is_dominated disagree")
    if exhaustive and n_a_dom == 7 and n_b_dom == 7 and n_equal == 1 and n_incomparable == 12:
        passed += 1
        print("  ✅ the four cases partition 27 patterns 7/7/1/12, exactly one per pattern")
    else:
        failed += 1
        print("  ❌ case partition:", n_a_dom, n_b_dom, n_equal, n_incomparable)
    if weak_consistent:
        passed += 1
        print("  ✅ weak dominance holds both ways iff equal, and matches strict otherwise")
    else:
        failed += 1
        print("  ❌ weak/strict dominance are inconsistent")

    # Two IDENTICAL points do not dominate each other — the case a comparison chain gets
    # wrong by accepting `<=` where it needs `<`.
    var same = mo_dominance(_f(2.0, 7.0), _f(2.0, 7.0), 2)
    if (
        same.status == MODEL_OK
        and same.equal
        and not same.a_dominates_b
        and not same.b_dominates_a
        and same.a_weakly_dominates_b
        and same.b_weakly_dominates_a
        and not same.incomparable
        and same.first_difference == -1
    ):
        passed += 1
        print("  ✅ identical points: equal, weakly dominant both ways, strictly neither")
    else:
        failed += 1
        print("  ❌ identical points:", same.equal, same.a_dominates_b, same.first_difference)

    # Equal in every objective but one IS dominated, and the difference is located.
    var one_off = mo_dominance(_f(2.0, 6.0), _f(2.0, 7.0), 2)
    if (
        one_off.status == MODEL_OK
        and one_off.a_dominates_b
        and not one_off.b_dominates_a
        and not one_off.equal
        and one_off.first_difference == 1
    ):
        passed += 1
        print("  ✅ better in exactly one objective and tied elsewhere dominates")
    else:
        failed += 1
        print("  ❌ one-objective difference:", one_off.a_dominates_b, one_off.first_difference)

    # Rejections carry no flags at all.
    var bad_k = mo_dominance(_f(1.0), _f(1.0), 0)
    var bad_len = mo_dominance(_f(1.0), _f(1.0, 2.0), 2)
    var inf_v = 1.0e308 * 10.0
    var bad_fin = mo_dominance(_f(inf_v, 1.0), _f(1.0, 1.0), 2)
    if (
        bad_k.status == MO_ERR_OBJECTIVE_COUNT
        and bad_len.status == MODEL_ERR_LENGTH_MISMATCH
        and bad_fin.status == MODEL_ERR_NON_FINITE_VALUE
        and not bad_fin.a_dominates_b
        and not bad_fin.incomparable
        and bad_fin.first_difference == -1
    ):
        passed += 1
        print("  ✅ a rejected pair carries no relation, not a False-flags 'incomparable'")
    else:
        failed += 1
        print("  ❌ dominance rejections:", bad_k.status, bad_len.status, bad_fin.status)

    # ── the five-point front decomposition, enumerated by hand ────────────────
    var five = _five_points()
    var sorted5 = nondominated_sort(five, 5, 2)
    if (
        sorted5.status == MODEL_OK
        and sorted5.verified
        and sorted5.n_fronts == 2
        and _same_ints(sorted5.rank, _i(0, 0, 0, 1, 1))
        and _same_ints(sorted5.front_start, _i(0, 3, 5))
        and _same_ints(sorted5.order, _i(0, 1, 2, 3, 4))
        and _same_ints(sorted5.first_front, _i(0, 1, 2))
        and sorted5.witness_a == -1
        and sorted5.witness_b == -1
    ):
        passed += 1
        print("  ✅ 5 points, 2 fronts, ranks [0,0,0,1,1] — hand-enumerated and verified")
    else:
        failed += 1
        print(
            "  ❌ five-point sort:", sorted5.status, sorted5.n_fronts,
            len(sorted5.rank), sorted5.witness_a,
        )

    # Every point non-dominated: ONE front. A staircase, so each point is better in one
    # objective and worse in the other.
    var stair = _f(1.0, 4.0, 2.0, 3.0, 3.0, 2.0, 4.0, 1.0)
    var s_stair = nondominated_sort(stair, 4, 2)
    if (
        s_stair.status == MODEL_OK
        and s_stair.n_fronts == 1
        and _same_ints(s_stair.rank, _i(0, 0, 0, 0))
        and len(s_stair.first_front) == 4
    ):
        passed += 1
        print("  ✅ a 4-point staircase is one front of four")
    else:
        failed += 1
        print("  ❌ single-front case:", s_stair.status, s_stair.n_fronts)

    # A total order: n fronts of one point each.
    var chain = _f(1.0, 1.0, 2.0, 2.0, 3.0, 3.0, 4.0, 4.0)
    var s_chain = nondominated_sort(chain, 4, 2)
    if (
        s_chain.status == MODEL_OK
        and s_chain.n_fronts == 4
        and _same_ints(s_chain.rank, _i(0, 1, 2, 3))
        and _same_ints(s_chain.front_start, _i(0, 1, 2, 3, 4))
    ):
        passed += 1
        print("  ✅ a totally ordered set is four fronts of one point each")
    else:
        failed += 1
        print("  ❌ total-order case:", s_chain.status, s_chain.n_fronts)

    # Duplicates share a front: neither dominates the other, so dropping one would discard a
    # decision.
    var dupes = _f(2.0, 2.0, 2.0, 2.0, 5.0, 5.0)
    var s_dupes = nondominated_sort(dupes, 3, 2)
    if (
        s_dupes.status == MODEL_OK
        and s_dupes.n_fronts == 2
        and _same_ints(s_dupes.rank, _i(0, 0, 1))
    ):
        passed += 1
        print("  ✅ two identical points are both rank 0, and both are kept")
    else:
        failed += 1
        print("  ❌ duplicate handling:", s_dupes.status, s_dupes.n_fronts)

    # ── EXHAUSTIVE differential: all 511 non-empty subsets of a 3x3 grid ─────
    # Nine points at every (f0, f1) in {0,1,2}^2, and every non-empty subset of them — 511
    # point sets covering every antichain and chain structure the grid admits, including
    # ties in one objective, ties in both (duplicates cannot occur here, the grid is
    # distinct) and total orders. For each, two independent oracles:
    #
    #   * the full rank vector against the longest-dominating-chain characterisation, which
    #     shares no code with the counting peel;
    #   * front 0 against the FROZEN `multi_objective.pareto_front`.
    #
    # Exhaustive rather than sampled, because a dominance bug shows up on a specific shape and
    # a sampled test is exactly how it survives.
    var grid = List[Float64]()
    for ga in range(3):
        for gb in range(3):
            grid.append(Float64(ga))
            grid.append(Float64(gb))
    var ranks_match = True
    var fronts_match = True
    var all_verified = True
    var subsets = 0
    for bits in range(1, 512):
        var pts = List[Float64]()
        var count = 0
        for pt in range(9):
            if ((bits >> pt) & 1) == 1:
                pts.append(grid[2 * pt])
                pts.append(grid[2 * pt + 1])
                count += 1
        var got = nondominated_sort(pts, count, 2)
        subsets += 1
        if got.status != MODEL_OK or not got.verified:
            all_verified = False
            continue
        if not _same_ints(got.rank, _rank_by_longest_chain(pts, count, 2)):
            ranks_match = False
        var nested = List[List[Float64]]()
        var no_max = List[Bool]()
        no_max.append(False)
        no_max.append(False)
        for i in range(count):
            var row = List[Float64]()
            row.append(pts[2 * i])
            row.append(pts[2 * i + 1])
            nested.append(row^)
        if not _same_ints(got.first_front, pareto_front(nested, no_max)):
            fronts_match = False
    if ranks_match and fronts_match and all_verified and subsets == 511:
        passed += 1
        print("  ✅ 511 subsets of a 3x3 grid: ranks match longest-chain, front 0 matches frozen")
    else:
        failed += 1
        print("  ❌ exhaustive differential:", ranks_match, fronts_match, all_verified, subsets)

    # ── shape, ceiling and resource guards ───────────────────────────────────
    # The wrapping-multiply case. 3 * 6148914691236517206 == 2, so a guard written as
    # `n_points * n_obj == len(f)` would pass this and then read far past the end of a
    # two-element list — an UNCATCHABLE process crash, reachable from the SDK.
    var tiny = _f(1.0, 2.0)
    var wrap = mo_matrix_defect(tiny, 6148914691236517206, 3)
    var wrap_sort = nondominated_sort(tiny, 6148914691236517206, 3)
    if wrap == MODEL_ERR_DENSE_SHAPE and wrap_sort.status == MODEL_ERR_DENSE_SHAPE:
        passed += 1
        print("  ✅ the wrapping product 3 * 6148914691236517206 == 2 is refused, not indexed")
    else:
        failed += 1
        print("  ❌ wrap guard:", wrap, wrap_sort.status)

    # A structurally consistent set one point above the ceiling. Consistent, and still
    # refused: the pair work is quadratic in a number the payload only bounds linearly.
    var over = List[Float64]()
    for i in range(MO_MAX_POINTS + 1):
        over.append(Float64(i))
    var over_defect = mo_matrix_defect(over, MO_MAX_POINTS + 1, 1)
    var at_ceiling_ok = _point_ceiling_fits(MO_MAX_POINTS, MO_SORT_PAIR_PASSES, MAX_CSR_DIM)
    var above_ceiling_bad = not _point_ceiling_fits(
        MO_MAX_POINTS * 2, MO_SORT_PAIR_PASSES, MAX_CSR_DIM
    )
    if over_defect == MODEL_ERR_DIMENSION_TOO_LARGE and at_ceiling_ok and above_ceiling_bad:
        passed += 1
        print("  ✅ MO_MAX_POINTS^2 * passes fits the shared ceiling and twice it does not")
    else:
        failed += 1
        print("  ❌ point ceiling:", over_defect, at_ceiling_ok, above_ceiling_bad)

    # The quadratic work product, refused up front rather than discovered halfway through.
    var wide = List[Float64]()
    for i in range(MO_MAX_POINTS * MO_MAX_OBJECTIVES):
        wide.append(Float64(i % 7))
    var work_defect = mo_matrix_defect(wide, MO_MAX_POINTS, MO_MAX_OBJECTIVES)
    if work_defect == MO_ERR_WORK_LIMIT:
        passed += 1
        print("  ✅ 2048 points x 64 objectives exceeds the work ceiling and is refused")
    else:
        failed += 1
        print("  ❌ work ceiling:", work_defect)

    # The remaining input doors, each with its own code.
    var empty_defect = mo_matrix_defect(_f(), 0, 2)
    var zero_k = mo_matrix_defect(_f(1.0), 1, 0)
    var many_k = mo_matrix_defect(_f(1.0), 1, MO_MAX_OBJECTIVES + 1)
    var nonfinite = mo_matrix_defect(_f(1.0, inf_v), 1, 2)
    if (
        empty_defect == MO_ERR_EMPTY_SET
        and zero_k == MO_ERR_OBJECTIVE_COUNT
        and many_k == MO_ERR_OBJECTIVE_COUNT
        and nonfinite == MODEL_ERR_NON_FINITE_VALUE
    ):
        passed += 1
        print("  ✅ empty / zero-objective / too-many / non-finite each get their own code")
    else:
        failed += 1
        print("  ❌ input doors:", empty_defect, zero_k, many_k, nonfinite)

    # A non-finite value never reaches a comparison: every comparison against a nan is False,
    # so a nan point would join every front as rank 0 and the frozen oracle would agree.
    var nan_v = inf_v - inf_v
    var nan_sort = nondominated_sort(_f(1.0, 2.0, nan_v, 3.0), 2, 2)
    if nan_sort.status == MODEL_ERR_NON_FINITE_VALUE and len(nan_sort.rank) == 0:
        passed += 1
        print("  ✅ a nan objective is refused before any comparison, with no ranks returned")
    else:
        failed += 1
        print("  ❌ nan handling:", nan_sort.status, len(nan_sort.rank))

    # ── crowding distance, with the boundary as a flag ────────────────────────
    # Front 0 = {(1,5), (2,3), (4,1)}. Objective 0 sorted 1,2,4: extremes p0 and p2, so p1's
    # gap is (4-1)/(4-1) = 1. Objective 1 sorted 1,3,5: extremes p2 and p0, p1's gap is
    # (5-1)/(5-1) = 1. So distance = [0, 2, 0] with p0 and p2 flagged boundary, and the order
    # is boundary-first (p0 then p2 by the index tie-break) then p1.
    var cd = crowding_distance(_first_front(), 3, 2)
    if (
        cd.status == MODEL_OK
        and _same_floats_exact(cd.distance, _f(0.0, 2.0, 0.0))
        and cd.is_boundary[0]
        and not cd.is_boundary[1]
        and cd.is_boundary[2]
        and cd.n_boundary == 2
        and cd.degenerate_objectives == 0
        and _same_ints(cd.order, _i(0, 2, 1))
        and _all_finite(cd.distance)
    ):
        passed += 1
        print("  ✅ crowding [0, 2, 0], two boundary points, order [0, 2, 1], no infinities")
    else:
        failed += 1
        print(
            "  ❌ crowding:", cd.status, cd.distance[0], cd.distance[1], cd.distance[2],
            cd.n_boundary,
        )

    # A degenerate objective contributes nothing and is counted; three objectives, the third
    # constant. Interior point: 1 from objective 0, 1 from objective 1, 0 from objective 2.
    var flat3 = _f(1.0, 5.0, 7.0, 2.0, 4.0, 7.0, 3.0, 3.0, 7.0)
    var cd3 = crowding_distance(flat3, 3, 3)
    if (
        cd3.status == MODEL_OK
        and _same_floats_exact(cd3.distance, _f(0.0, 2.0, 0.0))
        and cd3.degenerate_objectives == 1
        and _all_finite(cd3.distance)
    ):
        passed += 1
        print("  ✅ a zero-range objective adds nothing and is reported, with no division")
    else:
        failed += 1
        print("  ❌ degenerate objective:", cd3.status, cd3.degenerate_objectives)

    # WHICH points are boundary, asserted as the code does it rather than as a docstring once
    # claimed. `Crowding` said "among several points sharing an extreme value the LOWEST index
    # is the boundary one ... and the reason a duplicate of an extreme point is not itself
    # boundary". Both halves were false: the flags are the two ENDS of the stable ascending
    # order, so the lowest index wins at the MINIMUM and the HIGHEST index wins at the MAXIMUM.
    # This is the executed reproduction, verbatim: three identical points tie at both ends of
    # both objectives, and point 2 — a duplicate of the extreme point 0 — IS boundary.
    var cd_dup = crowding_distance(_f(2.0, 2.0, 2.0, 2.0, 2.0, 2.0), 3, 2)
    # CONTROL, non-degenerate and at unit scale, so the pattern is not an artefact of every
    # value being equal. One objective, keys [1, 5, 5]: the tie is at the MAXIMUM, so the
    # boundary flag goes to the HIGHEST index (p2) and p1 — the lowest index of the tied pair,
    # which the old statement named — is interior with distance (5-1)/4 = 1.
    var cd_hi = crowding_distance(_f(1.0, 5.0, 5.0), 3, 1)
    # The other half of the rule, and the half the old statement got right: keys [1, 1, 5] ties
    # at the MINIMUM, so the LOWEST index (p0) is boundary and p1 is interior.
    var cd_lo = crowding_distance(_f(1.0, 1.0, 5.0), 3, 1)
    if (
        cd_dup.status == MODEL_OK
        and cd_dup.n_boundary == 2
        and cd_dup.is_boundary[0]
        and not cd_dup.is_boundary[1]
        and cd_dup.is_boundary[2]
        and cd_dup.degenerate_objectives == 2
        and _same_floats_exact(cd_dup.distance, _f(0.0, 0.0, 0.0))
        and cd_hi.status == MODEL_OK
        and cd_hi.n_boundary == 2
        and cd_hi.is_boundary[0]
        and not cd_hi.is_boundary[1]
        and cd_hi.is_boundary[2]
        and cd_hi.degenerate_objectives == 0
        and _same_floats_exact(cd_hi.distance, _f(0.0, 1.0, 0.0))
        and cd_lo.status == MODEL_OK
        and cd_lo.is_boundary[0]
        and not cd_lo.is_boundary[1]
        and cd_lo.is_boundary[2]
        and _same_floats_exact(cd_lo.distance, _f(0.0, 1.0, 0.0))
    ):
        passed += 1
        print(
            "  ✅ boundary = the two ENDS of the sort: lowest index at the min, HIGHEST at the"
            " max, so a duplicate of an extreme point can be boundary itself"
        )
    else:
        failed += 1
        print(
            "  ❌ boundary determinism:", cd_dup.n_boundary, cd_dup.is_boundary[2],
            cd_hi.is_boundary[1], cd_hi.is_boundary[2], cd_lo.is_boundary[0],
        )

    # One and two points: every point is an extreme of every objective, so all are boundary
    # and no interior gap exists.
    var cd1 = crowding_distance(_f(1.0, 2.0), 1, 2)
    var cd2 = crowding_distance(_f(1.0, 2.0, 2.0, 1.0), 2, 2)
    if (
        cd1.status == MODEL_OK
        and cd1.n_boundary == 1
        and cd1.distance[0] == 0.0
        and cd2.status == MODEL_OK
        and cd2.n_boundary == 2
        and _all_finite(cd2.distance)
    ):
        passed += 1
        print("  ✅ one- and two-point fronts are all boundary, with finite zero distances")
    else:
        failed += 1
        print("  ❌ small fronts:", cd1.n_boundary, cd2.n_boundary)

    # ── environmental selection ──────────────────────────────────────────────
    # Four out of the five: all of front 0 (in index order), then front 1 truncated to one.
    # Both members of front 1 are boundary points with distance 0, so the stated index
    # tie-break picks p3.
    var sel4 = nsga2_select(five, 5, 2, 4)
    if (
        sel4.status == MODEL_OK
        and sel4.verified
        and sel4.n_selected == 4
        and _same_ints(sel4.chosen, _i(0, 1, 2, 3))
        and _same_ints(sel4.rank, _i(0, 0, 0, 1))
        and sel4.truncated_front == 1
        and sel4.n_fronts_used == 2
    ):
        passed += 1
        print("  ✅ selecting 4 of 5 takes front 0 whole and cuts front 1 by crowding")
    else:
        failed += 1
        print("  ❌ selection:", sel4.status, sel4.n_selected, sel4.truncated_front)

    var sel_all = nsga2_select(five, 5, 2, 99)
    var sel_none = nsga2_select(five, 5, 2, 0)
    var sel_bad = nsga2_select(five, 5, 2, -1)
    if (
        sel_all.status == MODEL_OK
        and sel_all.n_selected == 5
        and sel_all.truncated_front == -1
        and sel_none.status == MODEL_OK
        and sel_none.n_selected == 0
        and sel_bad.status == MO_ERR_PARAMETER
    ):
        passed += 1
        print("  ✅ over-asking selects everything, zero selects none, negative is refused")
    else:
        failed += 1
        print("  ❌ selection edges:", sel_all.n_selected, sel_none.n_selected, sel_bad.status)

    # ── the certificate, condition by condition ──────────────────────────────
    var cert_true = pareto_certify(five, 5, 2, _i(0, 1, 2))
    if (
        cert_true.status == MODEL_OK
        and cert_true.certified
        and cert_true.indices_valid
        and cert_true.mutually_nondominated
        and cert_true.unbeaten
        and cert_true.maximal
        and cert_true.n_claimed == 3
        and cert_true.n_true_front == 3
    ):
        passed += 1
        print("  ✅ the true front certifies, and the frozen oracle agrees it has 3 members")
    else:
        failed += 1
        print(
            "  ❌ true-front certificate:", cert_true.certified, cert_true.maximal,
            cert_true.n_true_front,
        )

    # THE OMITTED CONDITION. {p0, p1} is an antichain and nothing outside it dominates either
    # member, so a certificate checking only those two conditions returns True for a claim
    # that leaves a Pareto-optimal point out. Only maximality catches it.
    var cert_subset = pareto_certify(five, 5, 2, _i(0, 1))
    if (
        cert_subset.status == MODEL_OK
        and not cert_subset.certified
        and cert_subset.mutually_nondominated
        and cert_subset.unbeaten
        and not cert_subset.maximal
        and cert_subset.n_true_front == 3
    ):
        passed += 1
        print("  ✅ a SUBSET of the front passes antichain and unbeaten, and fails maximal")
    else:
        failed += 1
        print(
            "  ❌ subset certificate:", cert_subset.certified, cert_subset.mutually_nondominated,
            cert_subset.unbeaten, cert_subset.maximal,
        )

    # A claim containing a dominated point. p3 = (3,6) is dominated by p0 = (1,5) (1 <= 3,
    # 5 <= 6) AND by p1 = (2,3); the scan runs in claim order, so the witness is the FIRST
    # dominator, p0 — deterministic, and the reason the expected pair is (0, 3) rather than
    # either valid answer.
    var cert_extra = pareto_certify(five, 5, 2, _i(0, 1, 2, 3))
    if (
        cert_extra.status == MODEL_OK
        and not cert_extra.certified
        and not cert_extra.mutually_nondominated
        and cert_extra.witness_dominator == 0
        and cert_extra.witness_dominated == 3
    ):
        passed += 1
        print("  ✅ a front containing a dominated point fails, naming the pair (0, 3)")
    else:
        failed += 1
        print(
            "  ❌ dominated-member certificate:", cert_extra.mutually_nondominated,
            cert_extra.witness_dominator, cert_extra.witness_dominated,
        )

    var cert_dup = pareto_certify(five, 5, 2, _i(0, 0))
    var cert_range = pareto_certify(five, 5, 2, _i(0, 9))
    var cert_empty = pareto_certify(five, 5, 2, _i())
    if (
        not cert_dup.indices_valid
        and not cert_dup.certified
        and not cert_range.indices_valid
        and not cert_empty.certified
        and not cert_empty.maximal
    ):
        passed += 1
        print("  ✅ repeated, out-of-range and empty claims are all refused as claims")
    else:
        failed += 1
        print(
            "  ❌ claim validity:", cert_dup.indices_valid, cert_range.indices_valid,
            cert_empty.certified,
        )

    # RULE 4: NO FABRICATED NUMBER UNDER A SUCCESS STATUS. `n_true_front` is a property of the
    # POINT SET, not of the claim, so a rejected claim reports the same 3 a certified one does.
    # The two rejection paths used to DISAGREE — the invalid-index path returned a hardcoded 0
    # while the empty-claim path five lines later computed the real value — so `status =
    # MODEL_OK` came back alongside "the true Pareto front has no members", which no non-empty
    # point set can be. These are the executed reproductions, verbatim: claimed = [0, 0] and
    # claimed = [0, 9] on the spine, both of which returned 0.
    #
    # CONTROL, so this is not the constant 3 moved to a new line: a two-point set whose true
    # front has exactly ONE member, rejected the same way, has to report 1. And a matrix that
    # was REFUSED reports -1, absent, because there is no front to size — not 0, which reads as
    # a real and impossible count.
    var one_front = _f(1.0, 1.0, 2.0, 2.0)
    var cert_one = pareto_certify(one_front, 2, 2, _i(5))
    var nan_cert = pareto_certify(_f(1.0, 2.0, nan_v, 3.0), 2, 2, _i(0))
    if (
        cert_dup.status == MODEL_OK
        and cert_dup.n_true_front == 3
        and cert_range.status == MODEL_OK
        and cert_range.n_true_front == 3
        and cert_empty.n_true_front == 3
        and cert_true.n_true_front == 3
        and not cert_one.indices_valid
        and cert_one.status == MODEL_OK
        and cert_one.n_true_front == 1
        and nan_cert.status == MODEL_ERR_NON_FINITE_VALUE
        and nan_cert.n_true_front == -1
    ):
        passed += 1
        print(
            "  ✅ a refused claim reports the REAL true-front size (3 here, 1 for a"
            " one-member front) and a refused matrix reports -1, never a fabricated 0"
        )
    else:
        failed += 1
        print(
            "  ❌ n_true_front consistency:", cert_dup.n_true_front, cert_range.n_true_front,
            cert_empty.n_true_front, cert_one.n_true_front, nan_cert.n_true_front,
        )

    # ── hypervolume ──────────────────────────────────────────────────────────
    # One point (1,2) against (4,6) is the rectangle 3 * 4 = 12.
    var hv1 = hypervolume(_f(1.0, 2.0), 1, 2, _f(4.0, 6.0), 0, UInt64(1))
    if (
        hv1.status == MODEL_OK
        and hv1.exact
        and hv1.has_value
        and _dyadic_hv(hv1.value, 12.0)
        and hv1.n_nondominated == 1
        and hv1.degenerate_points == 0
        and _same_floats_exact(hv1.reference, _f(4.0, 6.0))
        and hv1.bound_lower == 12.0
        and hv1.bound_upper == 12.0
    ):
        passed += 1
        print("  ✅ one point against a reference is its rectangle, 3 * 4 = 12, exactly")
    else:
        failed += 1
        print("  ❌ single-point hypervolume:", hv1.status, hv1.value, hv1.bound_upper)

    # Two points, checked against inclusion-exclusion by hand: 3 + 6 - 2 = 7.
    var hv2 = hypervolume(_f(1.0, 3.0, 2.0, 1.0), 2, 2, _f(4.0, 4.0), 0, UInt64(1))
    # Three points {(1,5),(2,3),(4,1)} against (6,6): 5*1 + 4*2 + 2*2 = 17. By hand with
    # inclusion-exclusion over the three boxes 5, 12, 10: 27 - (4 + 2 + 6) + 2 = 17.
    var hv3 = hypervolume(_first_front(), 3, 2, _f(6.0, 6.0), 0, UInt64(1))
    if (
        _dyadic_hv(hv2.value, 7.0)
        and hv2.has_value
        and _dyadic_hv(hv3.value, 17.0)
        and hv3.has_value
        and hv3.n_nondominated == 3
    ):
        passed += 1
        print("  ✅ the staircase sweep matches inclusion-exclusion: 7 and 17, exactly")
    else:
        failed += 1
        print("  ❌ sweep values:", hv2.value, hv3.value)

    # DUPLICATES must not be counted twice, and a DOMINATED point must not add volume.
    var hv_dup = hypervolume(_f(1.0, 2.0, 1.0, 2.0), 2, 2, _f(4.0, 6.0), 0, UInt64(1))
    var hv_dom = hypervolume(_f(1.0, 2.0, 3.0, 5.0), 2, 2, _f(4.0, 6.0), 0, UInt64(1))
    if (
        _dyadic_hv(hv_dup.value, 12.0)
        and hv_dup.n_nondominated == 2
        and _dyadic_hv(hv_dom.value, 12.0)
        and hv_dom.n_nondominated == 1
    ):
        passed += 1
        print("  ✅ a duplicate is 12 not 24, and a dominated point adds nothing")
    else:
        failed += 1
        print("  ❌ duplicate/dominated volume:", hv_dup.value, hv_dom.value)

    # One objective: the union of nested intervals is the longest one, 10 - 3 = 7.
    var hv_1d = hypervolume(_f(3.0, 5.0), 2, 1, _f(10.0), 0, UInt64(1))
    if hv_1d.status == MODEL_OK and _dyadic_hv(hv_1d.value, 7.0) and hv_1d.exact:
        passed += 1
        print("  ✅ one objective: 10 - 3 = 7")
    else:
        failed += 1
        print("  ❌ 1-D hypervolume:", hv_1d.status, hv_1d.value)

    # A reference point a solution is strictly worse than has no volume, only a status.
    var hv_bad = hypervolume(_f(5.0, 2.0), 1, 2, _f(4.0, 6.0), 0, UInt64(1))
    if (
        hv_bad.status == MO_ERR_REFERENCE_POINT
        and not hv_bad.has_value
        and hv_bad.value == 0.0
        and len(hv_bad.reference) == 0
        and hv_bad.bound_upper == 0.0
    ):
        passed += 1
        print("  ✅ a reference not dominated by every point returns a status and no numbers")
    else:
        failed += 1
        print("  ❌ reference rejection:", hv_bad.status, hv_bad.value)

    # Touching the reference is admitted and counted: (4,2) has a zero-width box, so
    # {(1,5), (4,2)} against (4,6) is 3*1 + 0 = 3.
    var hv_touch = hypervolume(_f(1.0, 5.0, 4.0, 2.0), 2, 2, _f(4.0, 6.0), 0, UInt64(1))
    if (
        hv_touch.status == MODEL_OK
        and _dyadic_hv(hv_touch.value, 3.0)
        and hv_touch.degenerate_points == 1
    ):
        passed += 1
        print("  ✅ a point touching the reference contributes 0 and is counted, total 3")
    else:
        failed += 1
        print("  ❌ degenerate reference contact:", hv_touch.value, hv_touch.degenerate_points)

    # The exact value lies inside its own exact bounds — three numbers, three derivations.
    # bound_lower is the largest single box (12), bound_upper is min(sum of boxes 27,
    # spanning box (6-1)*(6-1) = 25) = 25.
    if (
        hv3.bound_lower <= hv3.value
        and hv3.value <= hv3.bound_upper
        and hv3.bound_lower == 12.0
        and hv3.bound_upper == 25.0
    ):
        passed += 1
        print("  ✅ 12 <= 17 <= 25: the largest box, the value and the spanning box agree")
    else:
        failed += 1
        print("  ❌ bounds bracket:", hv3.bound_lower, hv3.value, hv3.bound_upper)

    # THE SELF-CHECK'S TWO ARMS GET TWO BUDGETS. Found by sweep, not by a caller: the exact
    # path guarded BOTH `value >= bound_lower` and `value <= bound_upper` with one budget built
    # from `|bound_upper| + |value|`. `bound_upper` is min(spanning box, Σ over ALL the boxes),
    # so on the LOWER arm — a comparison against one box, the largest — the allowance was set by
    # an aggregate over every other box and grew with the caller's point count.
    # `bound_upper <= Σ boxes <= m * bound_lower` caps the inflation at `m`, which is the wrong
    # thing for it to be capped by.
    #
    # The three-point staircase {(0,3),(2,2),(3,0)} against (4,4) has three EQUAL boxes of 4, so
    # bound_lower = 4, bound_upper = 4+4+4 = 12 (under the spanning box 4*4 = 16), and the sweep
    # gives 4*1 + 2*1 + 1*2 = 8. Asserted against the module's own imported constants: the old
    # shared budget strictly exceeded this arm's own, and both are minute against the real
    # margin, so the gate is real either way at three points and loosens m-fold as m grows.
    var hv_stair_f = _f(0.0, 3.0, 2.0, 2.0, 3.0, 0.0)
    var hv_stair = hypervolume(hv_stair_f, 3, 2, _f(4.0, 4.0), 0, UInt64(1))
    var lower_arm = MO_ULP_BUDGET * LP_DBL_EPSILON * (hv_stair.bound_lower + hv_stair.value)
    var shared_arm = MO_ULP_BUDGET * LP_DBL_EPSILON * (hv_stair.bound_upper + hv_stair.value)
    # CONTROL at unit scale AND the same shape scaled by 1e6: a legitimate value near a bound is
    # still accepted at both scales, so the split is not a blanket tightening that refuses real
    # answers. Every number here is exact in Float64 (products up to 8e12 << 2^53).
    var hv_stair_big_f = _f(0.0, 3.0e6, 2.0e6, 2.0e6, 3.0e6, 0.0)
    var hv_big = hypervolume(hv_stair_big_f, 3, 2, _f(4.0e6, 4.0e6), 0, UInt64(1))
    if (
        hv_stair.status == MODEL_OK
        and _dyadic_hv(hv_stair.value, 8.0)
        and hv_stair.bound_lower == 4.0
        and hv_stair.bound_upper == 12.0
        and shared_arm > lower_arm
        and lower_arm < 1.0e-11
        and lower_arm < hv_stair.value - hv_stair.bound_lower
        and hv_big.status == MODEL_OK
        and _dyadic_hv(hv_big.value, 8.0e12)
        and hv_big.bound_lower == 4.0e12
        and hv_big.bound_upper == 12.0e12
    ):
        passed += 1
        print(
            "  ✅ the lower arm of the exact self-check is sized by bound_lower, not by the"
            " sum over every box: 2.7e-12 not 4.5e-12, and 8 in [4, 12] still verifies at 1e6"
        )
    else:
        failed += 1
        print(
            "  ❌ per-arm self-check budget:", hv_stair.value, hv_stair.bound_lower,
            hv_stair.bound_upper, lower_arm, shared_arm, hv_big.value,
        )

    # `mo_reference_point` with margin 0.5 on {(1,5),(2,3),(4,1)}: nadir (4,5), ideal (1,1),
    # spans 3 and 4, so the reference is (5.5, 7.0) and the sweep is
    # 4.5*2 + 3.5*2 + 1.5*2 = 9 + 7 + 3 = 19, all dyadic.
    var auto_ref = mo_reference_point(_first_front(), 3, 2, 0.5)
    var hv_auto = hypervolume(_first_front(), 3, 2, auto_ref, 0, UInt64(1))
    if (
        _same_floats_exact(auto_ref, _f(5.5, 7.0))
        and hv_auto.status == MODEL_OK
        and _dyadic_hv(hv_auto.value, 19.0)
    ):
        passed += 1
        print("  ✅ a derived reference (5.5, 7.0) gives the hand-computed 19.0")
    else:
        failed += 1
        print("  ❌ derived reference:", len(auto_ref), hv_auto.value)

    var ref_bad_margin = mo_reference_point(_first_front(), 3, 2, 0.0)
    var ref_bad_shape = mo_reference_point(_f(1.0), 2, 2, 0.5)
    if len(ref_bad_margin) == 0 and len(ref_bad_shape) == 0:
        passed += 1
        print("  ✅ a reference that does not exist comes back EMPTY, never as zeros")
    else:
        failed += 1
        print("  ❌ reference absence:", len(ref_bad_margin), len(ref_bad_shape))

    # Three objectives: no exact value is claimed. One point at the origin against (1,1,1)
    # dominates the whole unit cube, so every sample hits, the estimate is exactly 1.0, and
    # both exact bounds are 1.0 as well.
    #
    # This is the ONLY shape allowed to report `std_error == 0.0`, and the reason is the two
    # bounds COINCIDING — a volume proven exactly, where zero uncertainty is a statement about
    # the proof. A unanimous sample (`p = 1`, so the binomial variance estimate is 0) must never
    # be enough on its own, which is why the equality of the bounds is asserted here alongside
    # it: without that clause this assertion would also pass for the zero-hit case below.
    var hv_cube = hypervolume(_f(0.0, 0.0, 0.0), 1, 3, _f(1.0, 1.0, 1.0), 256, UInt64(5))
    if (
        hv_cube.status == MO_HV_INEXACT
        and not hv_cube.exact
        and not hv_cube.has_value
        and hv_cube.value == 0.0
        and hv_cube.has_estimate
        and hv_cube.estimate == 1.0
        and hv_cube.std_error == 0.0
        and hv_cube.bound_lower == hv_cube.bound_upper
        and hv_cube.bound_lower == 1.0
        and hv_cube.bound_upper == 1.0
    ):
        passed += 1
        print("  ✅ 3 objectives: no exact value, estimate 1.0 with bounds 1.0 and 1.0")
    else:
        failed += 1
        print(
            "  ❌ 3-D unit cube:", hv_cube.status, hv_cube.has_value, hv_cube.estimate,
            hv_cube.bound_lower,
        )

    # A real three-objective front: {(0,1,1), (1,0,1), (1,1,0)} against (2,2,2). Each box is
    # 2*1*1 = 2, each pairwise intersection is the unit cube at (1,1,1), and so is the triple,
    # so inclusion-exclusion gives 6 - 3 + 1 = 4 out of a spanning box of 8.
    var tri = _f(0.0, 1.0, 1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 0.0)
    var hv_tri = hypervolume(tri, 3, 3, _f(2.0, 2.0, 2.0), 1 << 14, UInt64(20260730))
    var tri_err = hv_tri.estimate - 4.0
    if tri_err < 0.0:
        tri_err = -tri_err
    if (
        hv_tri.status == MO_HV_INEXACT
        and hv_tri.has_estimate
        and tri_err < 0.2
        and hv_tri.bound_lower == 2.0
        and hv_tri.bound_upper == 6.0
        and hv_tri.estimate >= hv_tri.bound_lower
        and hv_tri.estimate <= hv_tri.bound_upper
        and hv_tri.std_error > 0.0
    ):
        passed += 1
        print("  ✅ the 3-objective estimate lands on the hand-computed 6 - 3 + 1 = 4")
    else:
        failed += 1
        print(
            "  ❌ 3-D estimate:", hv_tri.estimate, hv_tri.std_error, hv_tri.bound_lower,
            hv_tri.bound_upper,
        )

    # Same seed, bit-identical estimate; different seed, a different one. Both are required:
    # the first makes the number citable, the second proves the seed is really the source.
    var hv_same = hypervolume(tri, 3, 3, _f(2.0, 2.0, 2.0), 1 << 12, UInt64(99))
    var hv_same2 = hypervolume(tri, 3, 3, _f(2.0, 2.0, 2.0), 1 << 12, UInt64(99))
    var hv_other = hypervolume(tri, 3, 3, _f(2.0, 2.0, 2.0), 1 << 12, UInt64(100))
    if (
        hv_same.estimate == hv_same2.estimate
        and hv_same.estimate != hv_other.estimate
    ):
        passed += 1
        print("  ✅ the Monte-Carlo estimate is bit-identical per seed and moves with it")
    else:
        failed += 1
        print("  ❌ hypervolume determinism:", hv_same.estimate, hv_other.estimate)

    var hv_nosample = hypervolume(tri, 3, 3, _f(2.0, 2.0, 2.0), 0, UInt64(1))
    var hv_oversample = hypervolume(
        tri, 3, 3, _f(2.0, 2.0, 2.0), MO_MAX_SAMPLES + 1, UInt64(1)
    )
    if (
        hv_nosample.status == MO_HV_INEXACT
        and not hv_nosample.has_estimate
        and hv_nosample.bound_lower == 2.0
        and hv_oversample.status == MO_ERR_PARAMETER
        and hv_oversample.bound_upper == 0.0
    ):
        passed += 1
        print("  ✅ zero samples gives bounds only; a sample count past the ceiling is refused")
    else:
        failed += 1
        print("  ❌ sample count handling:", hv_nosample.has_estimate, hv_oversample.status)

    # REGRESSION, verbatim from the reproduction. An estimate is never returned outside the
    # EXACT bounds the same call computes, and zero hits is never reported as zero error.
    #
    # (a) UNDER the lower bound, with false certainty. The same three-point front against a
    # reference of 1.0001: each box is 1.0001 * 1e-4 * 1e-4 = 1.0001e-8 and the spanning box is
    # ~1.0003, so the dominated region is ~3e-8 of the sample space and 4096 uniform draws hit
    # it ZERO times. That used to come back as `estimate = 0.0, std_error = 0.0` with
    # `has_estimate = True` — a measurement with zero uncertainty, for a volume the same struct
    # simultaneously PROVES is at least 1.0001e-8 — which is the strongest possible claim from
    # the weakest possible data. Now: clamped to `bound_lower`, `std_error` positive, and the
    # status says the sampler was overridden.
    var tight_ref = _f(1.0001, 1.0001, 1.0001)
    var hv_zero_hits = hypervolume(tri, 3, 3, tight_ref, 4096, UInt64(7))
    var hv_zero_default = hypervolume_default(tri, 3, 3, tight_ref)
    if (
        hv_zero_hits.has_estimate
        and hv_zero_hits.estimate >= hv_zero_hits.bound_lower
        and hv_zero_hits.estimate <= hv_zero_hits.bound_upper
        and hv_zero_hits.estimate == hv_zero_hits.bound_lower
        and hv_zero_hits.std_error > 0.0
        and hv_zero_hits.status == MO_HV_ESTIMATE_CLAMPED
        and hv_zero_hits.bound_lower > 0.0
        and hv_zero_default.has_estimate
        and hv_zero_default.estimate >= hv_zero_default.bound_lower
        and hv_zero_default.std_error > 0.0
        and hv_zero_default.status == MO_HV_ESTIMATE_CLAMPED
    ):
        passed += 1
        print("  ✅ zero hits is clamped to the proven lower bound with a POSITIVE error")
    else:
        failed += 1
        print(
            "  ❌ zero-hit estimate:", hv_zero_hits.status, hv_zero_hits.estimate,
            hv_zero_hits.std_error, hv_zero_hits.bound_lower, hv_zero_default.estimate,
        )

    # (b) OVER the upper bound. {(0,1.9,1.9), (1.9,0,1.9), (1.9,1.9,0)} against (2,2,2): each
    # box is 2 * 0.1 * 0.1 = 0.02, so the sum of boxes — and hence `bound_upper` — is 0.06,
    # while the true volume is 0.06 - 3*0.001 + 0.001 = 0.058. The expected hit count is 3.7 out
    # of 512, so ordinary Poisson noise used to put the estimate at 0.078125 (seed 1) and
    # 0.109375 (seed 5), i.e. 82% ABOVE a bound the same struct proves. Both are now clamped
    # down to `bound_upper`.
    #
    # The two seeds show both halves of the error rule. Seed 1's raw 0.078125 is 0.018 above the
    # bound and the sampling error bar is already wider than that, so `estimate ± std_error`
    # still covers the raw draw. Seed 5's raw 0.109375 is 0.049 above it — further than the
    # proven interval `[0.02, 0.06]` is WIDE — so the error stops at that width: an error bar is
    # not stretched to cover a number the bounds have already refuted, and 0.04 is the largest
    # error two proofs leave room for.
    var thin = _f(0.0, 1.9, 1.9, 1.9, 0.0, 1.9, 1.9, 1.9, 0.0)
    var two_ref = _f(2.0, 2.0, 2.0)
    var hv_over = hypervolume(thin, 3, 3, two_ref, 512, UInt64(1))
    var hv_over5 = hypervolume(thin, 3, 3, two_ref, 512, UInt64(5))
    if (
        hv_over.estimate <= hv_over.bound_upper
        and hv_over.estimate == hv_over.bound_upper
        and hv_over.status == MO_HV_ESTIMATE_CLAMPED
        and hv_over.estimate + hv_over.std_error >= 0.078125
        and hv_over.std_error < hv_over.bound_upper - hv_over.bound_lower
        and hv_over5.estimate <= hv_over5.bound_upper
        and hv_over5.status == MO_HV_ESTIMATE_CLAMPED
        and hv_over5.std_error == hv_over5.bound_upper - hv_over5.bound_lower
        and hv_over5.std_error > 0.0
        and hv_over.bound_upper < 0.0600001
        and hv_over.bound_upper > 0.0599999
        and hv_over.bound_lower < 0.0200001
        and hv_over.bound_lower > 0.0199999
    ):
        passed += 1
        print("  ✅ an estimate above the proven upper bound is clamped, error bar widened")
    else:
        failed += 1
        print(
            "  ❌ over-bound estimate:", hv_over.status, hv_over.estimate,
            hv_over.bound_upper, hv_over.std_error, hv_over5.estimate,
        )

    # The invariant itself, over a seed sweep and three fronts: whenever an estimate is present
    # it lies inside the exact bounds of the SAME call, its error bar is positive unless the two
    # bounds coincide (which PROVES the volume, the only honest zero), and both bounds are
    # ordered. Asserted as a property rather than on the two seeds that happened to break it.
    var invariant_holds = True
    var checked = 0
    for s in range(1, 13):
        var probes = List[Int]()
        probes.append(64)
        probes.append(512)
        probes.append(4096)
        for pi in range(len(probes)):
            var hv_a = hypervolume(thin, 3, 3, two_ref, probes[pi], UInt64(s))
            var hv_b = hypervolume(tri, 3, 3, tight_ref, probes[pi], UInt64(s))
            var hv_c = hypervolume(tri, 3, 3, two_ref, probes[pi], UInt64(s))
            if not (
                hv_a.bound_lower <= hv_a.bound_upper
                and hv_b.bound_lower <= hv_b.bound_upper
                and hv_c.bound_lower <= hv_c.bound_upper
            ):
                invariant_holds = False
            if hv_a.has_estimate and not (
                hv_a.estimate >= hv_a.bound_lower and hv_a.estimate <= hv_a.bound_upper
                and (hv_a.std_error > 0.0 or hv_a.bound_lower == hv_a.bound_upper)
            ):
                invariant_holds = False
            if hv_b.has_estimate and not (
                hv_b.estimate >= hv_b.bound_lower and hv_b.estimate <= hv_b.bound_upper
                and (hv_b.std_error > 0.0 or hv_b.bound_lower == hv_b.bound_upper)
            ):
                invariant_holds = False
            if hv_c.has_estimate and not (
                hv_c.estimate >= hv_c.bound_lower and hv_c.estimate <= hv_c.bound_upper
                and (hv_c.std_error > 0.0 or hv_c.bound_lower == hv_c.bound_upper)
            ):
                invariant_holds = False
            checked += 3
    if invariant_holds and checked == 108:
        passed += 1
        print("  ✅ 108 estimates all inside their own exact bounds, none with zero error")
    else:
        failed += 1
        print("  ❌ estimate-inside-bounds invariant:", invariant_holds, checked)

    # ── lexicographic optimisation ───────────────────────────────────────────
    # Rows: x0 + 2*x1 <= 10 and x0 <= 4, variables x >= 0.
    #   Priority (max x1, then max x0), written as minimise (-x1, -x0): stage 1 gives
    #   x1 = 5 for -5, and locking it leaves x0 + 10 <= 10, so x0 = 0.
    #   Reversing the priority gives x0 = 4 for -4, and then 4 + 2*x1 <= 10 caps x1 at 3.
    # The two answers differ, which is what proves the priority order is really applied.
    var lex_a = _f(1.0, 2.0, 1.0, 0.0)
    var lex_senses = _i(SENSE_LE, SENSE_LE)
    var lex_rhs = _f(10.0, 4.0)
    var lex1 = lexicographic_linear_default(
        _f(0.0, -1.0, -1.0, 0.0), 2, 2, lex_a, 2, lex_senses, lex_rhs, 0.0
    )
    if (
        lex1.status == MODEL_OK
        and lex1.verified
        and lex1.has_solution
        and lex1.stages_solved == 2
        and lex1.optima[0] == -5.0
        and _near_list(lex1.optima, _f(-5.0, 0.0), 1e-9)
        and _near_list(lex1.x, _f(0.0, 5.0), 1e-9)
        and _near_list(lex1.objective_values, _f(-5.0, 0.0), 1e-9)
        and lex1.locked[0]
        and not lex1.locked[1]
        and lex1.max_deviation < 1e-9
    ):
        passed += 1
        print(
            "  ✅ lexicographic (max x1, then max x0) = (-5, 0) at x = (0, 5), obj 0 locked"
        )
    else:
        failed += 1
        print(
            "  ❌ lexicographic A:", lex1.status, lex1.stages_solved,
            lex1.optima[0] if len(lex1.optima) > 0 else 0.0,
            lex1.optima[1] if len(lex1.optima) > 1 else 0.0,
        )

    var lex2 = lexicographic_linear_default(
        _f(-1.0, 0.0, 0.0, -1.0), 2, 2, lex_a, 2, lex_senses, lex_rhs, 0.0
    )
    if (
        lex2.status == MODEL_OK
        and lex2.optima[0] == -4.0
        and _near_list(lex2.optima, _f(-4.0, -3.0), 1e-9)
        and _near_list(lex2.x, _f(4.0, 3.0), 1e-9)
    ):
        passed += 1
        print("  ✅ reversing the priority gives (-4, -3) at x = (4, 3) — order matters")
    else:
        failed += 1
        print("  ❌ lexicographic B:", lex2.status, len(lex2.optima))

    # A 20% relative slack on the first objective buys the second one exactly the trade the
    # arithmetic says: x1 >= 5 - 1 = 4 leaves x0 <= 10 - 8 = 2.
    var lex_tol = lexicographic_linear_default(
        _f(0.0, -1.0, -1.0, 0.0), 2, 2, lex_a, 2, lex_senses, lex_rhs, 0.2
    )
    var tol_gap = lex_tol.optima[1] + 2.0 if len(lex_tol.optima) > 1 else 99.0
    if tol_gap < 0.0:
        tol_gap = -tol_gap
    if (
        lex_tol.status == MODEL_OK
        and lex_tol.verified
        and tol_gap < 1e-6
        and lex_tol.slack[0] > 0.99
        and lex_tol.slack[0] < 1.01
    ):
        passed += 1
        print("  ✅ a 20% slack on objective 0 moves objective 1 from 0 to -2, as computed")
    else:
        failed += 1
        print("  ❌ lexicographic tolerance:", lex_tol.status, tol_gap)

    # RULE 4b. The lock's rounding allowance is sized by DBL_EPSILON and by objective 0's OWN
    # magnitude, so a HUGE first objective does not buy the second one free room. Rows:
    # x0 + x1 <= 1e9. Objective 0 is -x0 with optimum -1e9; objective 1 is -x1. A tolerance
    # of the shape `feas_tol * (1 + |opt|)` at 1e-9 would open a slack of 1.0 and report
    # optima[1] = -1.0; the DBL_EPSILON-sized allowance keeps it under 1e-3.
    var big = lexicographic_linear_default(
        _f(-1.0, 0.0, 0.0, -1.0), 2, 2, _f(1.0, 1.0), 1, _i(SENSE_LE), _f(1.0e9), 0.0
    )
    if (
        big.status == MODEL_OK
        and big.optima[0] == -1.0e9
        and big.optima[1] > -1.0e-3
        and big.optima[1] <= 0.0
    ):
        passed += 1
        print("  ✅ a 1e9 first objective does not buy the second one a free unit of slack")
    else:
        failed += 1
        print("  ❌ magnitude-scaled slack:", big.status, big.optima[1] if len(big.optima) > 1 else 0.0)

    # No feasible point: a status and no solution, with no stages claimed.
    var lex_inf = lexicographic_linear_default(
        _f(1.0, 0.0, 0.0, 1.0), 2, 2, _f(1.0, 0.0, 1.0, 0.0), 2,
        _i(SENSE_GE, SENSE_LE), _f(5.0, 4.0), 0.0,
    )
    if (
        lex_inf.status == LP_INFEASIBLE
        and not lex_inf.has_solution
        and len(lex_inf.x) == 0
        and lex_inf.stages_solved == 0
        and len(lex_inf.optima) == 0
    ):
        passed += 1
        print("  ✅ an infeasible model has no lexicographic answer and claims no stages")
    else:
        failed += 1
        print("  ❌ lexicographic infeasible:", lex_inf.status, len(lex_inf.x))

    var lex_par = lexicographic_linear(
        _f(1.0), 1, 1, _f(), 0, _i(), _f(), -1.0, 100, 1e-9, 1e-9
    )
    var lex_iter = lexicographic_linear(
        _f(1.0), 1, 1, _f(), 0, _i(), _f(), 0.0, 0, 1e-9, 1e-9
    )
    var lex_shape = lexicographic_linear_default(
        _f(1.0, 2.0), 2, 2, _f(), 0, _i(), _f(), 0.0
    )
    if (
        lex_par.status == MO_ERR_PARAMETER
        and lex_iter.status == MO_ERR_PARAMETER
        and lex_shape.status == MODEL_ERR_DENSE_SHAPE
    ):
        passed += 1
        print("  ✅ a negative tolerance, a zero iteration cap and a bad shape are refused")
    else:
        failed += 1
        print("  ❌ lexicographic rejections:", lex_par.status, lex_iter.status, lex_shape.status)

    # A CALLER'S INVALID POLICY IS NOT A SOLVER BREAKDOWN. `lexicographic_linear` validated
    # `tolerance` and `max_iterations` itself but never the two tolerances it forwards, so a
    # negative `feasibility_tol` reached `lp_solve`, which refused it correctly with
    # MODEL_ERR_POLICY — neither optimal nor infeasible nor unbounded — and the stage loop
    # relabelled that as MO_ERR_LP_STAGE_FAILED, "the inner LP did something inexplicable",
    # with the real code buried in `stage_status`. That sends the caller to debug the simplex
    # over their own argument. This is the executed reproduction, verbatim.
    var lex_negtol = lexicographic_linear(
        _f(1.0, 1.0), 1, 2, _f(1.0, 1.0), 1, _i(SENSE_LE), _f(1.0), 0.0, 100, -1.0, 1e-9
    )
    # A zero `optimality_tol` is the other half of `policy_defect`'s rule — zero is not "be
    # exact", it is "never converge" — and it must be refused by NAME here too.
    var lex_zeroopt = lexicographic_linear(
        _f(1.0, 1.0), 1, 2, _f(1.0, 1.0), 1, _i(SENSE_LE), _f(1.0), 0.0, 100, 1e-9, 0.0
    )
    # CONTROL, and the one that proves this is not a blanket rejection of small tolerances: a
    # ZERO `feasibility_tol` IS valid — exact feasibility is an askable question — so the same
    # model still solves, to the same answer, with the same status it has always had.
    var lex_zerofeas = lexicographic_linear(
        _f(1.0, 1.0), 1, 2, _f(1.0, 1.0), 1, _i(SENSE_LE), _f(1.0), 0.0, 100, 0.0, 1e-9
    )
    if (
        lex_negtol.status == MODEL_ERR_POLICY
        and lex_negtol.status != MO_ERR_LP_STAGE_FAILED
        and not lex_negtol.has_solution
        and lex_negtol.stage_status == MODEL_OK
        and lex_zeroopt.status == MODEL_ERR_POLICY
        and lex_zerofeas.status == MODEL_OK
        and lex_zerofeas.verified
        and _near_list(lex_zerofeas.optima, _f(0.0), 1e-12)
    ):
        passed += 1
        print(
            "  ✅ a negative feasibility_tol / zero optimality_tol is the CALLER's policy"
            " defect, not an inexplicable inner LP; a zero feasibility_tol still solves"
        )
    else:
        failed += 1
        print(
            "  ❌ lexicographic policy validation:", lex_negtol.status,
            lex_negtol.stage_status, lex_zeroopt.status, lex_zerofeas.status,
        )

    # ── NSGA-II ──────────────────────────────────────────────────────────────
    # f1 = x, f2 = -x over x in [0, 1]: every point is Pareto-optimal (any two distinct x are
    # incomparable), and f2 = -f1 EXACTLY because both objectives are single-term dot
    # products. The proven bound is the pair of single-objective LP optima, (0, -1).
    var ga_c = _f(1.0, -1.0)
    var ga = nsga2_linear(
        ga_c, 2, 1, _f(), 0, _i(), _f(), _f(0.0), _f(1.0),
        16, 8, 0.9, 0.2, 6, UInt64(4242),
    )
    var mirrored = ga.n_front > 0
    for t in range(ga.n_front):
        if ga.front_f[t * 2 + 1] != -ga.front_f[t * 2]:
            mirrored = False
    if (
        ga.status == MO_UNPROVEN
        and ga.status != MODEL_OK
        and ga.verified
        and ga.n_front == 6
        and mirrored
        and ga.has_ideal
        and _same_floats_exact(ga.ideal, _f(0.0, -1.0))
        and _same_floats_exact(ga.ideal_gap, _f(0.0, 0.0))
        and ga.max_violation == 0.0
        and ga.generations_run == 8
        and ga.evaluations == 16 * 9
    ):
        passed += 1
        print("  ✅ NSGA-II: 6 verified front points, f2 = -f1 exactly, ideal (0, -1), gap 0")
    else:
        failed += 1
        print(
            "  ❌ NSGA-II case 1:", ga.status, ga.n_front, mirrored, ga.max_violation,
            ga.evaluations,
        )

    # The status is never MODEL_OK and the struct carries no optimality flag: what is proven
    # is the LP bound, and `ideal_gap` is the only optimality statement in the result.
    if mo_status_name(ga.status) == "heuristic_front_not_proven_optimal":
        passed += 1
        print("  ✅ the heuristic's success status names itself as unproven")
    else:
        failed += 1
        print("  ❌ heuristic status name:", mo_status_name(ga.status))

    # Determinism, the property the whole module exists for.
    var ga_again = nsga2_linear(
        ga_c, 2, 1, _f(), 0, _i(), _f(), _f(0.0), _f(1.0),
        16, 8, 0.9, 0.2, 6, UInt64(4242),
    )
    var ga_other = nsga2_linear(
        ga_c, 2, 1, _f(), 0, _i(), _f(), _f(0.0), _f(1.0),
        16, 8, 0.9, 0.2, 6, UInt64(4243),
    )
    var identical = _same_floats_exact(ga.front_x, ga_again.front_x) and _same_floats_exact(
        ga.front_f, ga_again.front_f
    )
    var differs = not _same_floats_exact(ga.front_x, ga_other.front_x)
    if identical and differs:
        passed += 1
        print("  ✅ the same seed gives a bit-identical front; a different seed does not")
    else:
        failed += 1
        print("  ❌ GA determinism:", identical, differs)

    # A constrained model: minimise (-x0, -x1) subject to x0 + x1 <= 1 over the unit box. The
    # ideal point is (-1, -1) from two LPs, both extremes are seeded, and every returned point
    # must satisfy the caller's row — re-checked here, against the caller's own numbers.
    var ga2 = nsga2_linear(
        _f(-1.0, 0.0, 0.0, -1.0), 2, 2, _f(1.0, 1.0), 1, _i(SENSE_LE), _f(1.0),
        _f(0.0, 0.0), _f(1.0, 1.0), 20, 12, 0.9, 0.15, 8, UInt64(77),
    )
    var all_feasible = ga2.n_front > 0
    for t in range(ga2.n_front):
        var s = ga2.front_x[t * 2] + ga2.front_x[t * 2 + 1]
        if s > 1.0 + 1e-9:
            all_feasible = False
        if ga2.front_x[t * 2] < 0.0 or ga2.front_x[t * 2 + 1] < 0.0:
            all_feasible = False
    # No exact duplicate DECISIONS: the feasibility seed and a per-objective optimum coincide
    # in this model, so without the collapse two of the eight slots would hold the same point
    # twice and the truncation would have that much less to spend.
    var no_dupes = True
    for t in range(ga2.n_front):
        for u in range(t + 1, ga2.n_front):
            if (
                ga2.front_x[t * 2] == ga2.front_x[u * 2]
                and ga2.front_x[t * 2 + 1] == ga2.front_x[u * 2 + 1]
            ):
                no_dupes = False
    var recheck = nondominated_sort(ga2.front_f, ga2.n_front, 2)
    if (
        no_dupes
        and ga2.n_front == 8
        and (
        ga2.status == MO_UNPROVEN
        and ga2.verified
        and all_feasible
        and _same_floats_exact(ga2.ideal, _f(-1.0, -1.0))
        and ga2.ideal_gap[0] == 0.0
        and ga2.ideal_gap[1] == 0.0
        and recheck.status == MODEL_OK
        and recheck.n_fronts == 1
        )
    ):
        passed += 1
        print(
            "  ✅ constrained NSGA-II: 8 distinct feasible points, ideal (-1, -1), one front"
        )
    else:
        failed += 1
        print(
            "  ❌ NSGA-II case 2:", ga2.status, all_feasible, recheck.n_fronts,
            ga2.ideal_gap[0] if len(ga2.ideal_gap) > 0 else 99.0,
        )

    # Zero generations is an honest answer: the seeded population, and it says so.
    var ga_zero = nsga2_linear(
        ga_c, 2, 1, _f(), 0, _i(), _f(), _f(0.0), _f(1.0),
        8, 0, 0.9, 0.2, 3, UInt64(9),
    )
    if (
        ga_zero.status == MO_UNPROVEN
        and ga_zero.generations_run == 0
        and ga_zero.evaluations == 8
        and ga_zero.n_front == 3
        and ga_zero.verified
    ):
        passed += 1
        print("  ✅ zero generations returns the seeded population and reports 0 generations")
    else:
        failed += 1
        print("  ❌ zero-generation run:", ga_zero.status, ga_zero.generations_run, ga_zero.n_front)

    # An empty feasible region is PROVEN infeasible by the seed LP, not reported as a search
    # that found nothing: x0 >= 5 cannot hold inside the box [0, 1].
    var ga_inf = nsga2_linear(
        _f(1.0), 1, 1, _f(1.0), 1, _i(SENSE_GE), _f(5.0), _f(0.0), _f(1.0),
        8, 4, 0.9, 0.2, 4, UInt64(3),
    )
    if (
        ga_inf.status == LP_INFEASIBLE
        and ga_inf.n_front == 0
        and len(ga_inf.front_x) == 0
        and not ga_inf.has_ideal
        and not ga_inf.verified
    ):
        passed += 1
        print("  ✅ an empty feasible region is the proven LP_INFEASIBLE with no front")
    else:
        failed += 1
        print("  ❌ infeasible GA:", ga_inf.status, ga_inf.n_front, ga_inf.has_ideal)

    # Every parameter door, each with its own code.
    var p_small = nsga2_linear(
        ga_c, 2, 1, _f(), 0, _i(), _f(), _f(0.0), _f(1.0), 3, 4, 0.9, 0.2, 2, UInt64(1)
    )
    # Four objectives need `pop_size >= n_obj + 2 = 6` to hold the feasible seed, the four
    # per-objective optima and one random individual; five slots is one short.
    var p_seeds = nsga2_linear(
        _f(1.0, -1.0, 2.0, -2.0), 4, 1, _f(), 0, _i(), _f(), _f(0.0), _f(1.0),
        5, 4, 0.9, 0.2, 2, UInt64(1),
    )
    var p_front = nsga2_linear(
        ga_c, 2, 1, _f(), 0, _i(), _f(), _f(0.0), _f(1.0), 8, 4, 0.9, 0.2, 0, UInt64(1)
    )
    var p_rate = nsga2_linear(
        ga_c, 2, 1, _f(), 0, _i(), _f(), _f(0.0), _f(1.0), 8, 4, 1.5, 0.2, 2, UInt64(1)
    )
    var p_gen = nsga2_linear(
        ga_c, 2, 1, _f(), 0, _i(), _f(), _f(0.0), _f(1.0), 8, -1, 0.9, 0.2, 2, UInt64(1)
    )
    if (
        p_small.status == MO_ERR_PARAMETER
        and p_seeds.status == MO_ERR_PARAMETER
        and p_front.status == MO_ERR_PARAMETER
        and p_rate.status == MO_ERR_PARAMETER
        and p_gen.status == MO_ERR_PARAMETER
    ):
        passed += 1
        print("  ✅ population, front size, rate and generation-count limits are all enforced")
    else:
        failed += 1
        print(
            "  ❌ parameter doors:", p_small.status, p_seeds.status, p_front.status,
            p_rate.status, p_gen.status,
        )

    # A box below zero contradicts the solver's variable convention, and a crossed or
    # non-finite box cannot be sampled. Each is a distinct, already-allocated code.
    var b_neg = nsga2_linear(
        ga_c, 2, 1, _f(), 0, _i(), _f(), _f(-1.0), _f(1.0), 8, 2, 0.9, 0.2, 2, UInt64(1)
    )
    var b_cross = nsga2_linear(
        ga_c, 2, 1, _f(), 0, _i(), _f(), _f(2.0), _f(1.0), 8, 2, 0.9, 0.2, 2, UInt64(1)
    )
    var b_inf = nsga2_linear(
        ga_c, 2, 1, _f(), 0, _i(), _f(), _f(0.0), _f(inf_v), 8, 2, 0.9, 0.2, 2, UInt64(1)
    )
    var b_len = nsga2_linear(
        ga_c, 2, 1, _f(), 0, _i(), _f(), _f(0.0, 0.0), _f(1.0), 8, 2, 0.9, 0.2, 2, UInt64(1)
    )
    if (
        b_neg.status == MILP_BOX_BELOW_ZERO
        and b_cross.status == MODEL_ERR_BOUNDS_CROSSED
        and b_inf.status == MODEL_ERR_NON_FINITE_BOUND
        and b_len.status == MODEL_ERR_LENGTH_MISMATCH
    ):
        passed += 1
        print("  ✅ a negative, crossed, infinite or mis-sized box each get their own code")
    else:
        failed += 1
        print(
            "  ❌ box doors:", b_neg.status, b_cross.status, b_inf.status, b_len.status
        )

    # RULE 1c. A structurally valid request whose ALLOCATION the payload does not pay for.
    # One objective over 4097 variables is a 4097-float payload (33 KB), and the box rows make
    # the seed LP's matrix (2 * 4097) * 4097 = 33.6M cells — past `linear`'s own area ceiling,
    # and 8000 times the request. Refused before the matrix is built, not by `lp_solve` after.
    var wide_c = List[Float64]()
    for i in range(4097):
        wide_c.append(1.0 if i == 0 else 0.0)
    var wide_lo = List[Float64]()
    var wide_hi = List[Float64]()
    for _ in range(4097):
        wide_lo.append(0.0)
        wide_hi.append(1.0)
    var ga_wide = nsga2_linear(
        wide_c, 1, 4097, _f(), 0, _i(), _f(), wide_lo, wide_hi,
        8, 1, 0.9, 0.2, 2, UInt64(1),
    )
    if ga_wide.status == MODEL_ERR_DIMENSION_TOO_LARGE and ga_wide.n_front == 0:
        passed += 1
        print("  ✅ a 33 KB payload asking for a 33M-cell box matrix is refused up front")
    else:
        failed += 1
        print("  ❌ box-row amplification:", ga_wide.status)

    # RULE 1, and the lesson that BOUNDING MEMORY IS NOT BOUNDING WORK. Verbatim from the
    # reproduction: `n_obj = 2, n_vars = 1000, rows = 1000` — a diagonal inside a box, an 8 MB
    # payload, every allocation inside its ceiling and every pair comparison inside the
    # quadratic budget — with `pop_size = 64` and `generations = MO_MAX_GENERATIONS`. That was
    # ACCEPTED, because the only generation budget was `generations * (2*pop)^2 * n_obj`, which
    # never mentions a row or a variable: 262208 evaluations at 658 ms per generation MEASURED,
    # about 45 minutes in one call, holding every resident dataset in the worker and presenting
    # to the caller as a hang rather than an error. It is now refused before anything is
    # allocated, with the work code and no front.
    var big_n = 1000
    var big_c = List[Float64]()
    for k in range(2):
        for j in range(big_n):
            big_c.append(1.0 if k == 0 else -1.0)
    var big_a = List[Float64]()
    for i in range(big_n):
        for j in range(big_n):
            big_a.append(1.0 if i == j else 0.0)
    var big_senses = List[Int]()
    var big_rhs = List[Float64]()
    var big_lo = List[Float64]()
    var big_hi = List[Float64]()
    for _ in range(big_n):
        big_senses.append(SENSE_LE)
        big_rhs.append(1.0)
        big_lo.append(0.0)
        big_hi.append(1.0)
    var ga_work = nsga2_linear(
        big_c, 2, big_n, big_a, big_n, big_senses, big_rhs, big_lo, big_hi,
        64, MO_MAX_GENERATIONS, 0.9, 0.1, 8, UInt64(1),
    )
    # The arithmetic, restated here with DIVISIONS so this assertion is a statement about the
    # budget and not about one hard-coded pair of numbers: 64 * 4097 evaluations, each walking
    # every row twice and every objective once over 1000 variables.
    var eval_budget = MO_MAX_WORK // big_n
    eval_budget = eval_budget // (big_n + big_n + 2)
    eval_budget = eval_budget // 64
    if (
        ga_work.status == MO_ERR_WORK_LIMIT
        and ga_work.n_front == 0
        and len(ga_work.front_x) == 0
        and len(ga_work.front_f) == 0
        and not ga_work.verified
        and eval_budget < MO_MAX_GENERATIONS + 1
    ):
        passed += 1
        print("  ✅ an 8 MB request that would run for 45 minutes is refused, not run")
    else:
        failed += 1
        print("  ❌ GA evaluation work ceiling:", ga_work.status, ga_work.n_front, eval_budget)

    # And the ceiling discriminates on the COST, not on the shape: the same 100-variable,
    # 100-row model is refused at `generations = MO_MAX_GENERATIONS` and solved at 50, with only
    # that integer changing. A ceiling that refused both would be a shape limit wearing a work
    # limit's status code.
    var mid_n = 100
    var mid_c = List[Float64]()
    for k in range(2):
        for j in range(mid_n):
            mid_c.append(1.0 if k == 0 else -1.0)
    var mid_a = List[Float64]()
    for i in range(mid_n):
        for j in range(mid_n):
            mid_a.append(1.0 if i == j else 0.0)
    var mid_senses = List[Int]()
    var mid_rhs = List[Float64]()
    var mid_lo = List[Float64]()
    var mid_hi = List[Float64]()
    for _ in range(mid_n):
        mid_senses.append(SENSE_LE)
        mid_rhs.append(1.0)
        mid_lo.append(0.0)
        mid_hi.append(1.0)
    var mid_refused = nsga2_linear(
        mid_c, 2, mid_n, mid_a, mid_n, mid_senses, mid_rhs, mid_lo, mid_hi,
        64, MO_MAX_GENERATIONS, 0.9, 0.1, 6, UInt64(11),
    )
    var mid_ok = nsga2_linear(
        mid_c, 2, mid_n, mid_a, mid_n, mid_senses, mid_rhs, mid_lo, mid_hi,
        64, 50, 0.9, 0.1, 6, UInt64(11),
    )
    if (
        mid_refused.status == MO_ERR_WORK_LIMIT
        and mid_ok.status == MO_UNPROVEN
        and mid_ok.verified
        and mid_ok.max_violation == 0.0
        and mid_ok.evaluations == 64 * 51
    ):
        passed += 1
        print("  ✅ the work ceiling refuses 4096 generations and still solves 50 of them")
    else:
        failed += 1
        print(
            "  ❌ work-ceiling discrimination:", mid_refused.status, mid_ok.status,
            mid_ok.evaluations,
        )

    # The other multiplier this module puts on `lp_solve`: `n_obj + 1` seed solves. 64
    # objectives over 4097 variables... no: over 4096, where the augmented matrix is exactly
    # `linear`'s own cell ceiling and therefore ADMITTED by the area check, so 65 simplex solves
    # of an 8192 x 4096 tableau are what the request buys. `linear` bounds one solve; it cannot
    # bound sixty-five of them, and the count is a caller integer.
    var many_n = 4096
    var many_c = List[Float64]()
    for k in range(64):
        for j in range(many_n):
            many_c.append(1.0 if j == k else 0.0)
    var many_lo = List[Float64]()
    var many_hi = List[Float64]()
    for _ in range(many_n):
        many_lo.append(0.0)
        many_hi.append(1.0)
    var ga_seeds = nsga2_linear(
        many_c, 64, many_n, _f(), 0, _i(), _f(), many_lo, many_hi,
        66, 1, 0.9, 0.1, 4, UInt64(2),
    )
    if ga_seeds.status == MO_ERR_WORK_LIMIT and ga_seeds.n_front == 0:
        passed += 1
        print("  ✅ 65 seed LPs over an 8192 x 4096 tableau is refused as work, not attempted")
    else:
        failed += 1
        print("  ❌ seed-LP multiplier:", ga_seeds.status)

    # ── one name per status code, and they are all distinct ──────────────────
    # A duplicated name makes two defects indistinguishable in a log, which is the same
    # failure as a duplicated code — and this package has HAD a duplicated code.
    var names = List[String]()
    for code in range(140, 151):
        names.append(mo_status_name(code))
    var distinct = True
    for i in range(len(names)):
        if names[i] == "unknown_status":
            distinct = False
        for j in range(i + 1, len(names)):
            if names[i] == names[j]:
                distinct = False
    var falls_through = (
        mo_status_name(MODEL_OK) == "optimal"
        and mo_status_name(LP_INFEASIBLE) == "infeasible"
        and mo_status_name(MODEL_ERR_DENSE_SHAPE) == "dense_shape_invalid"
        and mo_status_name(151) == "unknown_status_151"
    )
    if distinct and falls_through and len(names) == 11:
        passed += 1
        print("  ✅ all 11 codes in 140-150 have distinct names and 151 falls through")
    else:
        failed += 1
        print("  ❌ status vocabulary:", distinct, falls_through)

    # The clamp is a STATUS, not a silent correction: a caller has to be able to tell "proof and
    # sample agreed" from "the sample was refused and the proof won", and a code with no name is
    # a number in a log nobody can read.
    if (
        mo_status_name(MO_HV_ESTIMATE_CLAMPED)
        == "hypervolume_estimate_clamped_into_its_exact_bounds"
        and MO_HV_ESTIMATE_CLAMPED != MO_HV_INEXACT
    ):
        passed += 1
        print("  ✅ the clamped-estimate outcome has its own named code, not a silent one")
    else:
        failed += 1
        print("  ❌ clamp status name:", mo_status_name(MO_HV_ESTIMATE_CLAMPED))

    # The two self-check codes have names too, even though nothing can reach them: they fire
    # only if the module's own invariants break, which is exactly when a bare number is worst.
    if (
        mo_status_name(MO_ERR_VERIFICATION_FAILED) == "answer_failed_verification_against_input"
        and mo_status_name(MO_ERR_WORK_LIMIT) == "work_limit"
    ):
        passed += 1
        print("  ✅ the self-check statuses are named, not left as bare integers")
    else:
        failed += 1
        print("  ❌ self-check names")

    print("  [optimization.multiobjective] Passed:", passed, "Failed:", failed)
