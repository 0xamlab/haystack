"""test_forecasting_hierarchy.mojo — known-value tests for reconciliation and coherence.

Hand-written. The hierarchy is deliberately tiny — one root, two children, horizon 2 — so every
number is a one-line calculation and can be `==` rather than approximately equal. All the values
are small integers, so the arithmetic is exact in binary.

    parent_of = [-1, 0, 0]        node 0 is the root, nodes 1 and 2 are its children

Five properties do the work:

1. *Reconciliation of an already-coherent hierarchy is the IDENTITY.* With root `[30, 70]` and
   children `[10, 20]` and `[20, 50]`, bottom-up must return the input BIT FOR BIT and
   `adjustment_l1` must be exactly 0.0. Anything else means the reconciler moves numbers it has
   no reason to move.

2. *Bottom-up does not touch a leaf, and top-down does not touch a root.* With an incoherent root
   of `[100, 100]`, bottom-up replaces the root with `[30, 70]` (the children win) while top-down
   keeps `[100, 100]` and splits it 10:20 and 20:50 — so 100 becomes 33.333... and 66.666... at
   step 0. Both are asserted, and they are asserted to differ, because the two methods keep
   DIFFERENT numbers fixed and a silently substituted method is a silently substituted answer.

3. *The refusal that matters.* When every child of a parent forecasts 0.0 at some step while the
   parent does not, no distribution exists that the children's own forecasts justify. That is
   FC_ERR_INCOHERENT with NO result, `max_residual` carrying the undistributable 100.0 and
   `worst_node` / `worst_step` naming it. It is specifically NOT an equal split — an invented
   share arriving under a success status.

4. *The audit measures, it does not assume.* On the incoherent input the residual at the root is
   exactly `100 - 30 = 70` at step 0 and `100 - 70 = 30` at step 1, with `n_incoherent_cells = 2`
   and `n_internal = 1`. Leaf cells are 0.0 because a leaf has no coherence condition at all,
   which is why `n_internal` is reported.

5. *Floating-point association is measured rather than hidden.* Children `[0.1, 0.2, 0.3]` are
   accumulated into their parent in DESCENDING index order and audited in ASCENDING order, so the
   residual is exactly one ulp of 0.6 (1.11e-16) — nonzero, inside the summation budget, and
   asserted as such against `fc_sum_tolerance` itself. With two children it is exactly 0.0, and
   that is asserted too. A suite that used a tolerance everywhere could not tell those apart.

The shape rule `parent_of[i] == -1 or 0 <= parent_of[i] < i` is what makes a cycle
unrepresentable, so `parent_of = [0, 0, 0]` (node 0 its own parent) is a shape refusal and there
is no cycle detector anywhere in the module.
"""
from std.math import abs as fabs

from forecasting.contract import (
    FC_ERR_EMPTY_SERIES,
    FC_ERR_HIERARCHY_SHAPE,
    FC_ERR_INCOHERENT,
    FC_ERR_LENGTH_MISMATCH,
    FC_ERR_METHOD,
    FC_ERR_NEGATIVE_VALUES,
    FC_ERR_NON_FINITE,
    FC_ERR_PARAM_RANGE,
    FC_INTERVAL_EMPIRICAL,
    FC_METHOD_DRIFT,
    FC_METHOD_MAX,
    FC_METHOD_NAIVE,
    FC_OK,
    HIER_BOTTOM_UP,
    HIER_METHOD_MAX,
    HIER_METHOD_MIN,
    HIER_TOP_DOWN,
    fc_method_family,
    fc_method_name,
    fc_sum_tolerance,
)
from forecasting.hierarchy import (
    Reconciliation,
    hierarchy_coherence_flat,
    hierarchy_shape_defect,
    reconcile_bottom_up_flat,
    reconcile_flat,
    reconcile_top_down_flat,
)


fn _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _ints(*vals: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _same(a: List[Float64], b: List[Float64]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


fn _refused(r: Reconciliation) -> Bool:
    """A refusal carries no reconciled hierarchy at all, and is never reported coherent."""
    return (
        r.status != FC_OK
        and not r.has_result
        and not r.coherent
        and len(r.reconciled) == 0
        and r.n_incoherent_cells == 0
        and r.adjustment_l1 == 0.0
    )


fn main():
    var passed = 0
    var failed = 0
    print("\n[forecasting.hierarchy] known-value suite")

    var parent = _ints(-1, 0, 0)
    var coherent_base = _floats(30.0, 70.0, 10.0, 20.0, 20.0, 50.0)
    var incoherent_base = _floats(100.0, 100.0, 10.0, 20.0, 20.0, 50.0)

    # ══ 1. an already-coherent hierarchy reconciles to ITSELF ══════════════════════
    var identity = reconcile_bottom_up_flat(coherent_base, parent, 2, 0.0)
    if (
        identity.status == FC_OK
        and identity.has_result
        and _same(identity.reconciled, coherent_base)
        and identity.adjustment_l1 == 0.0
        and identity.coherent
        and identity.max_residual == 0.0
        and identity.n_incoherent_cells == 0
        and identity.n_leaves == 2
        and identity.n_roots == 1
        and identity.method_id == HIER_BOTTOM_UP
    ):
        passed += 1
        print("  ✅ coherent children in -> the IDENTITY out, bit for bit, l1 exactly 0.0")
    else:
        failed += 1
        print("  ❌ identity broken: l1", identity.adjustment_l1, identity.reconciled[0])

    # ══ 2. bottom-up keeps the leaves; top-down keeps the roots ════════════════════
    # bottom-up: root becomes 10+20 = 30 and 20+50 = 70, so it moved |100-30|+|100-70| = 100.
    var bottom_up = reconcile_bottom_up_flat(incoherent_base, parent, 2, 0.0)
    var leaves_untouched = (
        bottom_up.reconciled[2] == 10.0 and bottom_up.reconciled[3] == 20.0
        and bottom_up.reconciled[4] == 20.0 and bottom_up.reconciled[5] == 50.0
    )
    if (
        bottom_up.status == FC_OK
        and bottom_up.reconciled[0] == 30.0
        and bottom_up.reconciled[1] == 70.0
        and leaves_untouched
        and bottom_up.adjustment_l1 == 100.0
        and bottom_up.coherent
    ):
        passed += 1
        print("  ✅ bottom-up: root becomes 30/70, leaves untouched, l1 exactly 100.0")
    else:
        failed += 1
        print("  ❌ bottom-up wrong:", bottom_up.reconciled[0], bottom_up.adjustment_l1)

    # top-down: root stays 100/100; step 0 splits 100 by 10:20 -> 100/3 and 200/3.
    var top_down = reconcile_top_down_flat(incoherent_base, parent, 2, 0.0)
    var third = 100.0 * 10.0 / 30.0
    var two_thirds = 100.0 * 20.0 / 30.0
    if (
        top_down.status == FC_OK
        and top_down.reconciled[0] == 100.0
        and top_down.reconciled[1] == 100.0
        and top_down.reconciled[2] == third
        and top_down.reconciled[4] == two_thirds
        and top_down.coherent
        and top_down.method_id == HIER_TOP_DOWN
        and top_down.reconciled[0] != bottom_up.reconciled[0]
    ):
        passed += 1
        print("  ✅ top-down: root stays 100, split 10:20 -> 33.33/66.66, audit coherent")
    else:
        failed += 1
        print("  ❌ top-down wrong:", top_down.reconciled[0], top_down.reconciled[2])

    # The two methods must be reachable by id and must not substitute for each other.
    if (
        _same(
            reconcile_flat(incoherent_base, parent, 2, HIER_BOTTOM_UP, 0.0).reconciled,
            bottom_up.reconciled,
        )
        and _same(
            reconcile_flat(incoherent_base, parent, 2, HIER_TOP_DOWN, 0.0).reconciled,
            top_down.reconciled,
        )
        and reconcile_flat(incoherent_base, parent, 2, 7, 0.0).status == FC_ERR_METHOD
        and _refused(reconcile_flat(incoherent_base, parent, 2, 7, 0.0))
    ):
        passed += 1
        print("  ✅ the dispatch has no default: an unknown method id is refused outright")
    else:
        failed += 1
        print("  ❌ reconcile_flat dispatch wrong")

    # ══ 3. the refusal: a nonzero parent over children that are all zero ═══════════
    var undistributable = _floats(100.0, 5.0, 0.0, 1.0, 0.0, 4.0)
    var refusal = reconcile_top_down_flat(undistributable, parent, 2, 0.0)
    if (
        refusal.status == FC_ERR_INCOHERENT
        and _refused(refusal)
        and refusal.max_residual == 100.0
        and refusal.worst_node == 0
        and refusal.worst_step == 0
    ):
        passed += 1
        print("  ✅ an undistributable 100.0 is REFUSED and reported, never split equally")
    else:
        failed += 1
        print("  ❌ top-down did not refuse:", refusal.status, refusal.max_residual)

    # A zero parent over zero children IS coherent (0 = 0 + 0) and must not be an error.
    var zero_over_zero = _floats(0.0, 5.0, 0.0, 1.0, 0.0, 4.0)
    var zero_ok = reconcile_top_down_flat(zero_over_zero, parent, 2, 0.0)
    if (
        zero_ok.status == FC_OK
        and zero_ok.reconciled[2] == 0.0
        and zero_ok.reconciled[4] == 0.0
        and zero_ok.reconciled[3] == 1.0
        and zero_ok.reconciled[5] == 4.0
        and zero_ok.coherent
    ):
        passed += 1
        print("  ✅ a ZERO parent over zero children is coherent, not a refusal")
    else:
        failed += 1
        print("  ❌ zero-over-zero wrong:", zero_ok.status, zero_ok.reconciled[2])

    # ══ 4. the audit measures the residual and names where it is ═══════════════════
    var audit = hierarchy_coherence_flat(incoherent_base, parent, 2, 0.0)
    if (
        audit.status == FC_OK
        and audit.has_report
        and not audit.coherent
        and audit.residual[0] == 70.0
        and audit.residual[1] == 30.0
        and audit.residual[2] == 0.0
        and audit.residual[5] == 0.0
        and audit.max_residual == 70.0
        and audit.worst_node == 0
        and audit.worst_step == 0
        and audit.n_incoherent_cells == 2
        and audit.n_internal == 1
        and audit.n_nodes == 3
    ):
        passed += 1
        print("  ✅ audit: root residual 70 and 30, 2 incoherent cells, 1 internal node")
    else:
        failed += 1
        print("  ❌ audit wrong:", audit.residual[0], audit.n_incoherent_cells, audit.n_internal)

    # A caller-supplied ABSOLUTE tolerance is added, never multiplied by anything: 70.0 of
    # slack admits the 70.0 residual, 69.0 does not. That is all an absolute term does.
    var loose = hierarchy_coherence_flat(incoherent_base, parent, 2, 70.0)
    var tight = hierarchy_coherence_flat(incoherent_base, parent, 2, 69.0)
    if (
        loose.coherent
        and loose.max_residual == 70.0
        and not tight.coherent
        and tight.n_incoherent_cells == 1
    ):
        passed += 1
        print("  ✅ abs_tol is ADDITIVE: 70.0 admits the 70.0 residual, 69.0 does not")
    else:
        failed += 1
        print("  ❌ abs_tol behaviour wrong:", loose.coherent, tight.n_incoherent_cells)

    # ══ 5. association: exactly zero for two children, one ulp for three ═══════════
    var three_parent = _ints(-1, 0, 0, 0)
    var thirds = _floats(0.0, 0.1, 0.2, 0.3)
    var three = reconcile_bottom_up_flat(thirds, three_parent, 1, 0.0)
    var halves = _floats(0.0, 0.1, 0.2)
    var two = reconcile_bottom_up_flat(halves, parent, 1, 0.0)
    var one_ulp = 1.1102230246251565e-16
    # The budget for this residual: |parent| + sum|child| = 0.6 + 0.6, over 3 children + 1.
    var budget = fc_sum_tolerance(1.2, 4, 0.0)
    if (
        two.status == FC_OK
        and two.max_residual == 0.0
        and three.status == FC_OK
        and three.max_residual == one_ulp
        and one_ulp <= budget
        and three.coherent
        and three.n_incoherent_cells == 0
    ):
        passed += 1
        print("  ✅ residual EXACTLY 0.0 for two children, one ulp for three, inside budget")
    else:
        failed += 1
        print("  ❌ association residual:", two.max_residual, three.max_residual, budget)

    # ══ the shape rule, which makes a cycle unrepresentable ════════════════════════
    if (
        hierarchy_shape_defect(coherent_base, parent, 2) == FC_OK
        and hierarchy_shape_defect(coherent_base, _ints(0, 0, 0), 2) == FC_ERR_HIERARCHY_SHAPE
        and hierarchy_shape_defect(coherent_base, _ints(-1, 2, 0), 2) == FC_ERR_HIERARCHY_SHAPE
        and hierarchy_shape_defect(coherent_base, _ints(-1, 0, 5), 2) == FC_ERR_HIERARCHY_SHAPE
        and hierarchy_shape_defect(coherent_base, _ints(-1, -2, 0), 2)
            == FC_ERR_HIERARCHY_SHAPE
        and hierarchy_shape_defect(coherent_base, _ints(-1, 0), 2) == FC_ERR_LENGTH_MISMATCH
        and hierarchy_shape_defect(coherent_base, parent, 0) == FC_ERR_PARAM_RANGE
        and hierarchy_shape_defect(List[Float64](), parent, 2) == FC_ERR_EMPTY_SERIES
        and hierarchy_shape_defect(coherent_base, List[Int](), 2) == FC_ERR_EMPTY_SERIES
    ):
        passed += 1
        print("  ✅ parent_of[i] must be -1 or in [0,i): a cycle cannot even be expressed")
    else:
        failed += 1
        print("  ❌ shape validation wrong")

    # A forest is legal, and each tree is reconciled independently.
    var forest_parent = _ints(-1, 0, -1, 2)
    var forest_base = _floats(0.0, 5.0, 0.0, 11.0)
    var forest = reconcile_bottom_up_flat(forest_base, forest_parent, 1, 0.0)
    if (
        forest.status == FC_OK
        and forest.n_roots == 2
        and forest.n_leaves == 2
        and forest.reconciled[0] == 5.0
        and forest.reconciled[2] == 11.0
        and forest.coherent
    ):
        passed += 1
        print("  ✅ a forest of two trees is legal; each root gets its own subtree total")
    else:
        failed += 1
        print("  ❌ forest handling wrong:", forest.n_roots, forest.reconciled[0])

    # A NaN must be rejected BEFORE any tolerance is built from it: `tol = eps*(1+nan)` is nan,
    # every `|d| > nan` is False, and the audit would pass having counted zero violations.
    var nan = 0.0 / 0.0
    var poisoned = _floats(nan, 70.0, 10.0, 20.0, 20.0, 50.0)
    var poisoned_audit = hierarchy_coherence_flat(poisoned, parent, 2, 0.0)
    if (
        poisoned_audit.status == FC_ERR_NON_FINITE
        and not poisoned_audit.has_report
        and not poisoned_audit.coherent
        and len(poisoned_audit.residual) == 0
        and hierarchy_coherence_flat(coherent_base, parent, 2, nan).status
            == FC_ERR_PARAM_RANGE
        and hierarchy_coherence_flat(coherent_base, parent, 2, -1.0).status
            == FC_ERR_PARAM_RANGE
    ):
        passed += 1
        print("  ✅ a NaN value or a NaN tolerance is refused, NOT passed as coherent")
    else:
        failed += 1
        print("  ❌ NaN handling wrong:", poisoned_audit.status, poisoned_audit.coherent)

    # Top-down needs nonnegative bases; bottom-up does not (a hierarchy of net changes).
    var mixed = _floats(0.0, 0.0, -5.0, 1.0, 8.0, 2.0)
    var mixed_bu = reconcile_bottom_up_flat(mixed, parent, 2, 0.0)
    if (
        reconcile_top_down_flat(mixed, parent, 2, 0.0).status == FC_ERR_NEGATIVE_VALUES
        and _refused(reconcile_top_down_flat(mixed, parent, 2, 0.0))
        and mixed_bu.status == FC_OK
        and mixed_bu.reconciled[0] == 3.0
        and mixed_bu.reconciled[1] == 3.0
    ):
        passed += 1
        print("  ✅ top-down needs nonnegative shares; bottom-up sums signed values happily")
    else:
        failed += 1
        print("  ❌ negativity policy wrong:", mixed_bu.reconciled[0])

    # ══ the method_id says WHICH vocabulary it is in ═══════════════════════════════
    # `Reconciliation.method_id` used to be 0 and 1, numbered in `hierarchy.mojo` itself —
    # the same two numbers `interval.mojo` allocated for its own bands and the same two the
    # shared table gives to `FC_METHOD_NAIVE` and `FC_METHOD_DRIFT`. One number, three
    # meanings, in one package, and `reconcile_flat` DISPATCHES on it, so `method_id = 0` from
    # the wrong vocabulary silently selected bottom-up instead of being refused.
    var bu_id = reconcile_bottom_up_flat(incoherent_base, parent, 2, 0.0)
    var td_id = reconcile_top_down_flat(incoherent_base, parent, 2, 0.0)
    if (
        bu_id.method_id == HIER_BOTTOM_UP
        and td_id.method_id == HIER_TOP_DOWN
        # Disjoint from the forecasting range and from the interval range, both directions.
        and bu_id.method_id > FC_METHOD_MAX
        and HIER_METHOD_MIN > FC_INTERVAL_EMPIRICAL
        and bu_id.method_id != FC_METHOD_NAIVE
        and bu_id.method_id != FC_INTERVAL_EMPIRICAL
        # A bare id names itself and its family.
        and fc_method_name(bu_id.method_id) == "reconcile_bottom_up"
        and fc_method_name(td_id.method_id) == "reconcile_top_down"
        and fc_method_family(bu_id.method_id) == "reconciliation"
        and fc_method_family(td_id.method_id) == "reconciliation"
        and fc_method_family(FC_METHOD_NAIVE) == "forecast"
        and fc_method_family(FC_INTERVAL_EMPIRICAL) == "interval"
        # Every code in the reconciliation range is assigned, and nothing beside it is.
        and HIER_METHOD_MIN == HIER_BOTTOM_UP
        and HIER_METHOD_MAX == HIER_TOP_DOWN
        and fc_method_name(HIER_METHOD_MIN - 1) == "unknown"
        and fc_method_name(HIER_METHOD_MAX + 1) == "unknown"
        # THE dispatch consequence: an id from either of the other two vocabularies is
        # refused instead of selecting a reconciliation. Both of these used to RUN — 0 as
        # bottom-up, 1 as top-down — under FC_OK, with a full result.
        and reconcile_flat(incoherent_base, parent, 2, FC_METHOD_NAIVE, 0.0).status
        == FC_ERR_METHOD
        and _refused(reconcile_flat(incoherent_base, parent, 2, FC_METHOD_NAIVE, 0.0))
        and reconcile_flat(incoherent_base, parent, 2, FC_METHOD_DRIFT, 0.0).status
        == FC_ERR_METHOD
        and reconcile_flat(incoherent_base, parent, 2, FC_INTERVAL_EMPIRICAL, 0.0).status
        == FC_ERR_METHOD
        and _refused(
            reconcile_flat(incoherent_base, parent, 2, FC_INTERVAL_EMPIRICAL, 0.0)
        )
    ):
        passed += 1
        print("  ✅ reconciliation ids are their own range; a forecast id is now refused")
    else:
        failed += 1
        print(
            "  ❌ reconciliation method_id vocabulary:",
            bu_id.method_id,
            fc_method_name(bu_id.method_id),
            reconcile_flat(incoherent_base, parent, 2, FC_METHOD_NAIVE, 0.0).status,
        )

    print("  [forecasting.hierarchy] Passed:", passed, "Failed:", failed)
