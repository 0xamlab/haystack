"""
forecasting.hierarchy — reconciling forecasts that must add up. Zero Python imports.

The problem
-----------
Forecasts are usually produced per series and consumed as a structure: three regions must add
to the country, twelve SKUs to the category, four quarters to the year. Forecast each series
independently and they will not add up — the errors do not cancel, and nothing in an
independent forecast knows the constraint exists. A set of numbers that does not add up cannot
be used as a plan, because two people reading it compute two different totals.

Two reconciliations, and each is EXACT by construction rather than iterative
---------------------------------------------------------------------------
`HIER_BOTTOM_UP` keeps the leaf forecasts and replaces every internal node by the sum of its
own subtree. Coherence then holds by construction — there is nothing to iterate towards — and
the leaves are untouched, which is the right choice when the leaves carry the information (the
detailed series were forecast from detailed data).

`HIER_TOP_DOWN` keeps the root forecasts and splits each parent among its children in
proportion to the children's OWN base forecasts. That is the right choice when the aggregate is
the reliable series (it is smoother, so it forecasts better) and the split is a share.

Both report `adjustment_l1`, the total absolute change from the base forecasts, so the price of
coherence is visible. A reconciliation that moved every number a long way is coherent and may
be worse than what it replaced.

The shape rule makes a cycle UNREPRESENTABLE
--------------------------------------------
`parent_of[i]` must be `-1` (a root) or in `[0, i)`. Every node's parent therefore has a
strictly smaller index, so the array IS a topological order: bottom-up is one descending pass,
top-down is one ascending pass, and no visited set, no depth limit and no cycle check exists
anywhere in this file because no cycle can be expressed. That is exactly the trick
`query.ir.validation_error` uses for expression arenas — a child index strictly less than its
parent's — and it is borrowed rather than reinvented. A forest (several roots) is legal and
`n_roots` reports it; each tree is reconciled independently, which is what a caller passing
several unrelated hierarchies at once means.

WHAT HAPPENS WHEN IT CANNOT BE DONE, per Rule 4
----------------------------------------------
Top-down needs a positive sibling total to form proportions. If every child of some parent
forecasts 0.0 at some step while the parent does not, there is NO distribution of the parent
over its children that the children's own forecasts justify. This driver refuses:
FC_ERR_INCOHERENT, `has_result = False`, and `max_residual` carries the parent value that could
not be distributed, with `worst_node` and `worst_step` naming where.

It specifically does NOT split the parent equally among the children, and does not scale the
children by anything. Splitting equally is an invented answer — it asserts a share the data
never suggested — and it would arrive under a success status, which is worse than the refusal
because a caller stops looking. When the parent is also 0.0 the children are 0.0 and that IS
coherent, so it is not an error.

Negative base values are refused for top-down (FC_ERR_NEGATIVE_VALUES): a "proportion" computed
from mixed signs can exceed 1 or be negative, so it is not a share, and a sibling total can be
zero while individual children are large. Bottom-up has no such requirement and accepts any
finite values.

The coherence tolerance is the ONE aggregate in this package
-----------------------------------------------------------
`parent - sum_j child_j` is a residual of a SUM, so its rounding budget legitimately involves
the magnitudes of the terms that form it and the number of them —
`contract.fc_sum_tolerance(|parent| + sum_j |child_j|, n_children + 1, abs_tol)`. Over THAT
parent's own children and no others: an aggregate over the whole hierarchy would let one
parent's units pay for another parent's real incoherence, which is rule 4b's first spelling and
the defect that returned LP_OPTIMAL for an infeasible program. Every other comparison in this
package goes through the per-item `fc_tolerance`.

Note also that coherence is measured, not assumed, even on the paths where it holds by
construction: bottom-up accumulates children into a parent in DESCENDING index order while the
audit sums them ascending, and floating-point addition is not associative, so the residual is
not identically zero for a node with three or more children. It is exactly 0.0 for one or two,
and the suite asserts that rather than papering over it with a tolerance.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_forecasting_hierarchy.mojo
benchmark: benchmarks/mojo_benchmarks/bench_forecasting.mojo
docs: none
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs

from forecasting.contract import (
    FC_ERR_DIMENSION_TOO_LARGE,
    FC_ERR_EMPTY_SERIES,
    FC_ERR_HIERARCHY_SHAPE,
    FC_ERR_INCOHERENT,
    FC_ERR_LENGTH_MISMATCH,
    FC_ERR_METHOD,
    FC_ERR_NEGATIVE_VALUES,
    FC_ERR_NON_FINITE,
    FC_ERR_PARAM_RANGE,
    FC_OK,
    HIER_BOTTOM_UP,
    HIER_TOP_DOWN,
    MAX_FC_NODES,
    fc_all_finite,
    fc_cells_fit,
    fc_finite,
    fc_status_name,
    fc_sum_tolerance,
)



@fieldwise_init
struct Reconciliation(Copyable, Movable):
    """A coherent set of forecasts, plus what it cost and whether it really is coherent.

    `reconciled` is row-major `n_nodes x horizon`, same layout as the `base` it came from, so
    cell `(i, h)` is at `i * horizon + h`.

    `method_id` is `HIER_BOTTOM_UP` (200) or `HIER_TOP_DOWN` (201), allocated in
    `forecasting.contract` out of the RECONCILIATION range (200-201) rather than in this file.
    It used to be 0 and 1 numbered here, which made `Reconciliation.method_id == 0`
    indistinguishable from `FC_METHOD_NAIVE` and from `interval`'s `FC_INTERVAL_EMPIRICAL`.
    `contract.fc_method_name(method_id)` names it and `contract.fc_method_family(method_id)`
    returns `"reconciliation"`. `reconcile_flat` DISPATCHES on this id, so the range is also
    what it accepts: a forecasting id or an interval id is now FC_ERR_METHOD instead of `0`
    quietly selecting bottom-up.

    `coherent` is MEASURED after the fact, not asserted from the algorithm: `max_residual` is
    the largest `|parent - sum of children|` over every internal node and step, judged against
    that parent's own summation budget. `worst_node` and `worst_step` name where it occurred
    (lowest index on a tie, so the report does not depend on scan order), and
    `n_incoherent_cells` counts how many cells exceeded their budget. On a clean run the
    residual is 0.0 or a few ulps and `n_incoherent_cells` is 0.

    `adjustment_l1` is `sum |reconciled - base|` over every cell — the total distance travelled
    to reach coherence. A large value is not an error and is not hidden: it says the base
    forecasts disagreed badly, which is information about them.

    On any refusal `reconciled` is EMPTY and `has_result` is False, and `max_residual` carries
    the quantity that could not be reconciled rather than 0.0.
    """

    var status: Int
    var method_id: Int
    var n_nodes: Int
    var horizon: Int
    var n_leaves: Int
    var n_roots: Int
    var reconciled: List[Float64]
    var has_result: Bool
    var coherent: Bool
    var max_residual: Float64
    var worst_node: Int
    var worst_step: Int
    var n_incoherent_cells: Int
    var adjustment_l1: Float64
    var status_name: String


@fieldwise_init
struct CoherenceReport(Copyable, Movable):
    """An audit of a hierarchy SOMEBODY ELSE produced: does it add up, and where does it not.

    `residual` is row-major `n_nodes x horizon`, holding `parent - sum of children` at every
    INTERNAL node and 0.0 at every leaf. A leaf has no children, so it has no coherence
    condition; 0.0 there is padding and not a claim, which is why `n_internal` is reported —
    a caller can tell how many cells the audit actually judged.

    WHAT THIS CERTIFICATE COVERS: for every internal node and every step, that
    `|parent - sum of its children|` is within `fc_sum_tolerance` of that node's own terms. It
    covers nothing else. It does NOT claim the forecasts are accurate, that the hierarchy is the
    right one, that a leaf's value is plausible, or that the values are nonnegative. An
    incomplete certificate is worse than none because a caller stops looking, so the boundary is
    stated rather than implied.

    `coherent` is True only when `n_incoherent_cells == 0`, and on a shape refusal `has_report`
    is False with an empty `residual` — an audit of a hierarchy that could not be read is not a
    pass.
    """

    var status: Int
    var n_nodes: Int
    var horizon: Int
    var n_internal: Int
    var residual: List[Float64]
    var has_report: Bool
    var coherent: Bool
    var max_residual: Float64
    var worst_node: Int
    var worst_step: Int
    var n_incoherent_cells: Int
    var status_name: String


def _no_reconciliation(
    status: Int, method_id: Int, n_nodes: Int, horizon: Int,
    residual: Float64, node: Int, step: Int
) -> Reconciliation:
    """A refusal that names the quantity it could not reconcile and where it lives."""
    return Reconciliation(
        status, method_id, n_nodes, horizon, 0, 0, List[Float64](), False, False,
        residual, node, step, 0, 0.0, fc_status_name(status),
    )


def _no_coherence(status: Int, n_nodes: Int, horizon: Int) -> CoherenceReport:
    """A refusal: no residual matrix, and NOT a pass."""
    return CoherenceReport(
        status, n_nodes, horizon, 0, List[Float64](), False, False,
        0.0, -1, -1, 0, fc_status_name(status),
    )


def hierarchy_shape_defect(
    base: List[Float64], parent_of: List[Int], horizon: Int
) -> Int:
    """Validate a flat hierarchy: the mapping, the cell count and finiteness.

    `n_nodes` is `len(parent_of)`, never a caller-supplied integer, so there is no count that
    can disagree with a length. The conditions, all of them:

      * `n_nodes >= 1` and `n_nodes <= MAX_FC_NODES`;
      * `horizon >= 1`;
      * `n_nodes * horizon == len(base)`, tested through `contract.fc_cells_fit` (a DIVISION —
        the product is a wrapping multiply and therefore not a bound);
      * `parent_of[i] == -1` or `0 <= parent_of[i] < i` for every `i`, which makes a cycle
        unrepresentable and the array a topological order;
      * every element of `base` finite, because a NaN defeats any tolerance computed from it
        silently: `tol = eps * (1 + nan)` is `nan`, every `|d| > nan` is False, and an audit
        passes having counted zero violations.

    Returns FC_OK or the specific defect. Exposed publicly so a caller can validate a
    hierarchy once and then call several reconcilers without re-deriving the rules — and so the
    rules have one definition rather than three copies at three strengths, which is how
    `optimization/` ended up with one invariant enforced under three status codes.

    @capability hierarchy_shape_defect
    complexity: O(n_nodes * horizon)
    counts:
    - dim horizon [kernel_validated]
    @endcapability
    """
    var n_nodes = len(parent_of)
    if n_nodes == 0 or len(base) == 0:
        return FC_ERR_EMPTY_SERIES
    if n_nodes > MAX_FC_NODES:
        return FC_ERR_DIMENSION_TOO_LARGE
    if horizon < 1:
        return FC_ERR_PARAM_RANGE
    if not fc_cells_fit(n_nodes, horizon, len(base)):
        return FC_ERR_LENGTH_MISMATCH
    for i in range(n_nodes):
        var parent = parent_of[i]
        if parent == -1:
            continue
        if parent < 0 or parent >= i:
            return FC_ERR_HIERARCHY_SHAPE
    if not fc_all_finite(base):
        return FC_ERR_NON_FINITE
    return FC_OK


def _child_census(parent_of: List[Int]) -> List[Int]:
    """`child_count[i]`, one pass. A node with zero children is a leaf; the rest are internal."""
    var counts = List[Int]()
    for _ in range(len(parent_of)):
        counts.append(0)
    for i in range(len(parent_of)):
        var parent = parent_of[i]
        if parent >= 0:
            counts[parent] += 1
    return counts^


def _audit(
    values: List[Float64], parent_of: List[Int], horizon: Int, abs_tol: Float64
) -> CoherenceReport:
    """The coherence audit itself, shared by the reconcilers and the public auditor.

    One definition, three call sites: `reconcile_bottom_up_flat` and
    `reconcile_top_down_flat` both report `coherent` on their own output, and
    `hierarchy_coherence_flat` audits somebody else's. Three copies would be three chances for
    the reconcilers to grade themselves more leniently than the auditor grades them, which is
    precisely the "one invariant, three strengths" defect rule 3 names.

    Assumes the shape has already been validated. Called only behind
    `hierarchy_shape_defect`.
    """
    var n_nodes = len(parent_of)
    var cells = n_nodes * horizon
    var child_sum = List[Float64]()
    var child_abs = List[Float64]()
    var residual = List[Float64]()
    for _ in range(cells):
        child_sum.append(0.0)
        child_abs.append(0.0)
        residual.append(0.0)
    var counts = _child_census(parent_of)

    for i in range(n_nodes):
        var parent = parent_of[i]
        if parent < 0:
            continue
        for h in range(horizon):
            var v = values[i * horizon + h]
            child_sum[parent * horizon + h] += v
            child_abs[parent * horizon + h] += fabs(v)

    var n_internal = 0
    var worst_value: Float64 = 0.0
    var worst_node = -1
    var worst_step = -1
    var incoherent = 0
    for p in range(n_nodes):
        if counts[p] == 0:
            continue
        n_internal += 1
        for h in range(horizon):
            var cell = p * horizon + h
            var parent_value = values[cell]
            var difference = parent_value - child_sum[cell]
            residual[cell] = difference
            var magnitude = fabs(difference)
            if magnitude > worst_value:
                worst_value = magnitude
                worst_node = p
                worst_step = h
            var budget = fc_sum_tolerance(
                fabs(parent_value) + child_abs[cell], counts[p] + 1, abs_tol
            )
            if magnitude > budget:
                incoherent += 1

    # `residual` and `worst_value` were returned unchecked with `has_report` hardcoded True. There
    # is no `has_max_residual` field, so there is no per-value absence channel here -- which means a
    # non-finite has nowhere honest to go and the whole report is what has to be refused. `coherent`
    # would be the worst field to get this wrong: it is computed from `magnitude > budget`, and a nan
    # compares False against every budget, so a hierarchy whose residuals are nan would be reported
    # COHERENT.
    for i in range(len(residual)):
        if not fc_finite(residual[i]):
            return _no_coherence(FC_ERR_NON_FINITE, n_nodes, horizon)
    if not fc_finite(worst_value):
        return _no_coherence(FC_ERR_NON_FINITE, n_nodes, horizon)

    return CoherenceReport(
        FC_OK, n_nodes, horizon, n_internal, residual^, True, incoherent == 0,
        worst_value, worst_node, worst_step, incoherent, fc_status_name(FC_OK),
    )


def hierarchy_coherence_flat(
    values: List[Float64], parent_of: List[Int], horizon: Int, abs_tol: Float64
) -> CoherenceReport:
    """Audit an EXISTING hierarchy: does every parent equal the sum of its children?

    `values` is row-major `n_nodes x horizon` and `n_nodes` is `len(parent_of)`. `abs_tol` is
    the caller's ABSOLUTE allowance, added to the summation rounding budget rather than
    multiplied by anything — see `contract.fc_sum_tolerance`. Pass 0.0 to require coherence to
    within rounding alone.

    See `CoherenceReport` for exactly what the certificate covers. A negative or non-finite
    `abs_tol` is FC_ERR_PARAM_RANGE, checked BEFORE any tolerance is built from it, because a
    NaN tolerance makes every comparison false and turns the audit into an unconditional pass.

    @capability hierarchy_coherence_flat
    complexity: O(n_nodes * horizon)
    counts:
    - dim horizon [kernel_validated]
    @endcapability
    """
    var n_nodes = len(parent_of)
    if not fc_finite(abs_tol) or abs_tol < 0.0:
        return _no_coherence(FC_ERR_PARAM_RANGE, n_nodes, horizon)
    var defect = hierarchy_shape_defect(values, parent_of, horizon)
    if defect != FC_OK:
        return _no_coherence(defect, n_nodes, horizon)
    return _audit(values, parent_of, horizon, abs_tol)


def reconcile_bottom_up_flat(
    base: List[Float64], parent_of: List[Int], horizon: Int, abs_tol: Float64
) -> Reconciliation:
    """Bottom-up: keep the leaves, replace every internal node by its subtree total.

    One descending pass over the node indices is sufficient and correct because
    `parent_of[i] < i`, so a node's own total is complete before it is added into its parent.
    No recursion, no visited set, no depth limit.

    Leaves keep their base values EXACTLY — `reconciled[leaf] == base[leaf]` bit for bit, which
    the suite asserts, because bottom-up that moves a leaf is not bottom-up.

    A hierarchy whose children ALREADY sum to their parents is reconciled to itself: the
    identity, asserted exactly in the suite on integer-valued input where the arithmetic is
    exact.

    Accepts any finite values, including negative ones (a hierarchy of net changes is a real
    thing). `abs_tol` only affects the reported `coherent` verdict, never the numbers.

    @capability reconcile_bottom_up_flat
    complexity: O(n_nodes * horizon)
    counts:
    - dim horizon [kernel_validated]
    @endcapability
    """
    var n_nodes = len(parent_of)
    if not fc_finite(abs_tol) or abs_tol < 0.0:
        return _no_reconciliation(
            FC_ERR_PARAM_RANGE, HIER_BOTTOM_UP, n_nodes, horizon, 0.0, -1, -1
        )
    var defect = hierarchy_shape_defect(base, parent_of, horizon)
    if defect != FC_OK:
        return _no_reconciliation(
            defect, HIER_BOTTOM_UP, n_nodes, horizon, 0.0, -1, -1
        )

    var counts = _child_census(parent_of)
    var n_leaves = 0
    var n_roots = 0
    for i in range(n_nodes):
        if counts[i] == 0:
            n_leaves += 1
        if parent_of[i] == -1:
            n_roots += 1

    var out = List[Float64]()
    for i in range(n_nodes):
        for h in range(horizon):
            out.append(base[i * horizon + h] if counts[i] == 0 else 0.0)
    for i in range(n_nodes - 1, -1, -1):
        var parent = parent_of[i]
        if parent < 0:
            continue
        for h in range(horizon):
            out[parent * horizon + h] += out[i * horizon + h]
    if not fc_all_finite(out):
        return _no_reconciliation(
            FC_ERR_NON_FINITE, HIER_BOTTOM_UP, n_nodes, horizon, 0.0, -1, -1
        )

    var moved: Float64 = 0.0
    for cell in range(n_nodes * horizon):
        moved += fabs(out[cell] - base[cell])
    var audit = _audit(out, parent_of, horizon, abs_tol)
    return Reconciliation(
        FC_OK, HIER_BOTTOM_UP, n_nodes, horizon, n_leaves, n_roots, out^, True,
        audit.coherent, audit.max_residual, audit.worst_node, audit.worst_step,
        audit.n_incoherent_cells, moved, fc_status_name(FC_OK),
    )


def reconcile_top_down_flat(
    base: List[Float64], parent_of: List[Int], horizon: Int, abs_tol: Float64
) -> Reconciliation:
    """Top-down: keep the roots, split each parent by its children's own base proportions.

    One ascending pass, correct because `parent_of[i] < i` means a parent is final before any
    child is computed. Roots keep their base values EXACTLY.

    `child = parent * base_child / sum(base over siblings)`.

    THE REFUSAL THAT MATTERS: when the sibling total is 0.0 at some step and the parent is not,
    no distribution exists that the children's own forecasts justify. That is FC_ERR_INCOHERENT
    with no result, `max_residual` carrying the undistributable parent value and
    `worst_node` / `worst_step` naming it — never an equal split, never a rescale. When the
    parent is 0.0 too, the children are 0.0 and that is coherent.

    Requires every base value to be NONNEGATIVE (FC_ERR_NEGATIVE_VALUES): a proportion built
    from mixed signs is not a share, and a sibling total can be zero with large children in it.

    @capability reconcile_top_down_flat
    complexity: O(n_nodes * horizon)
    counts:
    - dim horizon [kernel_validated]
    @endcapability
    """
    var n_nodes = len(parent_of)
    if not fc_finite(abs_tol) or abs_tol < 0.0:
        return _no_reconciliation(
            FC_ERR_PARAM_RANGE, HIER_TOP_DOWN, n_nodes, horizon, 0.0, -1, -1
        )
    var defect = hierarchy_shape_defect(base, parent_of, horizon)
    if defect != FC_OK:
        return _no_reconciliation(
            defect, HIER_TOP_DOWN, n_nodes, horizon, 0.0, -1, -1
        )
    for cell in range(len(base)):
        if base[cell] < 0.0:
            return _no_reconciliation(
                FC_ERR_NEGATIVE_VALUES, HIER_TOP_DOWN, n_nodes, horizon,
                base[cell], cell // horizon, cell % horizon,
            )

    var counts = _child_census(parent_of)
    var n_leaves = 0
    var n_roots = 0
    for i in range(n_nodes):
        if counts[i] == 0:
            n_leaves += 1
        if parent_of[i] == -1:
            n_roots += 1

    # Sibling totals of the BASE forecasts, one pass. These are the proportions' denominators
    # and they are read, never written, once computed.
    var sibling_total = List[Float64]()
    for _ in range(n_nodes * horizon):
        sibling_total.append(0.0)
    for i in range(n_nodes):
        var parent = parent_of[i]
        if parent >= 0:
            for h in range(horizon):
                sibling_total[parent * horizon + h] += base[i * horizon + h]

    var out = List[Float64]()
    for _ in range(n_nodes * horizon):
        out.append(0.0)
    for i in range(n_nodes):
        var parent = parent_of[i]
        if parent < 0:
            for h in range(horizon):
                out[i * horizon + h] = base[i * horizon + h]
            continue
        for h in range(horizon):
            var total = sibling_total[parent * horizon + h]
            var parent_value = out[parent * horizon + h]
            if total > 0.0:
                out[i * horizon + h] = parent_value * base[i * horizon + h] / total
            elif parent_value == 0.0:
                out[i * horizon + h] = 0.0
            else:
                return _no_reconciliation(
                    FC_ERR_INCOHERENT, HIER_TOP_DOWN, n_nodes, horizon,
                    parent_value, parent, h,
                )
    if not fc_all_finite(out):
        return _no_reconciliation(
            FC_ERR_NON_FINITE, HIER_TOP_DOWN, n_nodes, horizon, 0.0, -1, -1
        )

    var moved: Float64 = 0.0
    for cell in range(n_nodes * horizon):
        moved += fabs(out[cell] - base[cell])
    var audit = _audit(out, parent_of, horizon, abs_tol)
    return Reconciliation(
        FC_OK, HIER_TOP_DOWN, n_nodes, horizon, n_leaves, n_roots, out^, True,
        audit.coherent, audit.max_residual, audit.worst_node, audit.worst_step,
        audit.n_incoherent_cells, moved, fc_status_name(FC_OK),
    )


def reconcile_flat(
    base: List[Float64], parent_of: List[Int], horizon: Int,
    method_id: Int, abs_tol: Float64
) -> Reconciliation:
    """Dispatch to one of the two reconcilers by `method_id`. No default.

    HIER_BOTTOM_UP or HIER_TOP_DOWN. Anything else is FC_ERR_METHOD with no result: falling
    back to bottom-up would answer a question nobody asked, and the two methods keep DIFFERENT
    numbers fixed, so a silently substituted method is a silently substituted answer.

    @capability reconcile_flat
    complexity: O(n_nodes * horizon)
    counts:
    - dim horizon [kernel_validated]
    @endcapability
    """
    if method_id == HIER_BOTTOM_UP:
        return reconcile_bottom_up_flat(base, parent_of, horizon, abs_tol)
    if method_id == HIER_TOP_DOWN:
        return reconcile_top_down_flat(base, parent_of, horizon, abs_tol)
    return _no_reconciliation(
        FC_ERR_METHOD, method_id, len(parent_of), horizon, 0.0, -1, -1
    )
