"""test_optimization_flow.mojo — known-value tests for max flow, min cut and min-cost flow.

Hand-written, and every number below was computed with pen and paper before the code ran.

The load-bearing assertion is max-flow == min-cut, and it is checked on EVERY network this
file builds, through `_invariants_hold`. It is worth that much repetition because the two
sides come from different data: the value is the sum of the augmentations, the cut is a
residual reachability sweep priced with the ORIGINAL capacities. A bug in the augmentation
or in the cut extraction breaks the equality, and nothing else in a flow answer is
self-checking that way. `_invariants_hold` also re-derives the cut in test code (a third
implementation), prices the same partition through the public `cut_capacity_of`, and runs
the returned flow through `flow_audit_flat` for capacity and conservation.

Two independent oracles from other modules are used rather than trusting this one:

  * `graph_analytics.adjacency.graph_dijkstra_from_triplets` answers "is the sink
    reachable at all", which must agree with a max flow of 0.0, and — priced with the COST
    array instead of the capacity array — gives the cheapest s-to-t path cost, which must
    equal the cost of a single-unit min-cost flow. That is a real check on the
    reduced-cost shortest-path phase, since it reaches the same number by a completely
    different route (raw Dijkstra on original costs, no potentials, no residual network).
  * `flow_audit_flat` prices an ALTERNATIVE max flow of the same value that a human
    constructed, showing that the successive-shortest-path answer (7) is strictly cheaper
    than the same flow value routed differently (12). Cost-optimality claimed without such
    a comparison would be untested, because a wrong cost is still a plausible number.

Cost-optimality is additionally certified structurally: the returned potentials must leave
every residual arc with a non-negative reduced cost. That is dual feasibility, so it rules
out a negative-cost residual cycle without enumerating cycles.

Exact equality is used for every capacity, flow and cost here. All of them are small
integers or dyadic fractions (1.5, 4.0), so a tolerance would hide a genuine
mis-accumulation rather than absorb a rounding.

One group of tests works at 1e12 instead, and it is about the THRESHOLDS rather than the
arithmetic: every tolerance in `flow.mojo` must be built from the magnitude of the one
quantity it judges, with a relative term in ulps of that magnitude and never a 1e-9 fraction
of it. Each of those tests carries the violation that was executed on the shipped code, a
CONTROL repeating the same violation at magnitude 1.0 (so a fix cannot be a blanket
tightening that only bites at 1e12), and a CONTROL in the other direction where a legitimate
near-zero at 1e12 must still pass (so it cannot be a blanket tightening either). Values at
that scale are still exact — 1e12, 3e12 and 1e12 + 1000.0 all have exact Float64
representations — except where a decimal like 1.001 is deliberately used, and there the
measured magnitude is bracketed rather than compared for equality.
"""
from graph_analytics.adjacency import graph_dijkstra_from_triplets
from graph_decision import flow_augment_amount, flow_residual_capacity
from optimization.flow import (
    FLOW_ERR_EDGE_OUT_OF_RANGE,
    FLOW_ERR_EMPTY_NETWORK,
    FLOW_ERR_EMPTY_PATH,
    FLOW_ERR_INVALID_DIMENSIONS,
    FLOW_ERR_LENGTH_MISMATCH,
    FLOW_ERR_NEGATIVE_CAPACITY,
    FLOW_ERR_NEGATIVE_COST,
    FLOW_ERR_NEGATIVE_TARGET,
    FLOW_ERR_NODE_OUT_OF_RANGE,
    FLOW_ERR_NON_FINITE_CAPACITY,
    FLOW_ERR_NON_FINITE_FLOW,
    FLOW_ERR_NON_FINITE_TARGET,
    FLOW_ERR_PATH_INDEX,
    FLOW_ERR_SAME_TERMINALS,
    FLOW_ERR_TARGET_UNREACHABLE,
    FLOW_MAX_NODES,
    FLOW_NODE_ARRAYS,
    FLOW_OK,
    MaxFlow,
    cut_capacity_of,
    edge_residuals,
    flow_audit_flat,
    flow_network_check,
    flow_status_name,
    is_saturated,
    max_flow_dinic,
    min_cost_flow,
    min_cost_max_flow,
    path_bottleneck,
)
from sparse_numerics.csr import MAX_CSR_DIM


def _ints(*vals: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


def _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


def _bools(*vals: Bool) -> List[Bool]:
    var out = List[Bool]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


def _same_floats(a: List[Float64], b: List[Float64]) -> Bool:
    """Exact equality. Every value compared with this helper is a small integer or a
    dyadic fraction, so a tolerance would hide a genuine mis-accumulation."""
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


def _node_ceiling_fits(nodes: Int, arrays: Int, shared_ceiling: Int) -> Bool:
    """True when `arrays` arrays of `nodes` slots fit the one shared csr budget.

    Written with a DIVISION, like `sparse_numerics.csr.dims_fit`: `nodes * arrays` is a
    wrapping 64-bit multiply, so a test written that way would pass for a ceiling large
    enough to wrap — exactly the class of non-bound this assertion exists to catch. Taking
    the three numbers as arguments also keeps them runtime values, so the comparisons are
    really executed instead of folded away as comptime constants.
    """
    if nodes <= 0 or shared_ceiling <= 0:
        return False
    # Six is the measured floor: the triplet census alone holds six per-node Int arrays
    # live (dst_count, dst_start, cursor, out_count, row_ptr, fill), so a count below that
    # is not a divisor anyone counted the arrays for.
    if arrays < 6:
        return False
    if nodes >= shared_ceiling:
        return False
    return nodes <= shared_ceiling // arrays


def _no_answer(r: MaxFlow) -> Bool:
    """A rejected request carries no numbers at all — not "value 0.0 plus a status"."""
    return (
        not r.has_value
        and r.value == 0.0
        and r.cut_capacity == 0.0
        and r.cut_edge_count == 0
        and r.source_side_count == 0
        and len(r.edge_flow) == 0
        and len(r.source_side) == 0
        and len(r.cut_edges) == 0
    )


def _invariants_hold(
    r: MaxFlow,
    src: List[Int],
    dst: List[Int],
    cap: List[Float64],
    n: Int,
    s: Int,
    t: Int,
) -> Bool:
    """max-flow == min-cut, plus capacity and conservation, on one solved network.

    Every network in this file goes through here. The cut is recomputed from the returned
    partition in test code — a third implementation, independent of both the driver's own
    sweep and the public pricer — because an extraction bug that also fed the value would
    otherwise agree with itself.
    """
    if r.status != FLOW_OK or not r.has_value:
        return False
    if r.n_nodes != n or r.n_edges != len(src) or r.source != s or r.sink != t:
        return False
    if len(r.edge_flow) != len(src) or len(r.source_side) != n:
        return False

    # The identity. Exact, because every capacity here is a small integer.
    if r.value != r.cut_capacity:
        return False

    # The cut, re-derived here from the partition and the original capacities.
    var mine: Float64 = 0.0
    var crossing = List[Int]()
    for k in range(len(src)):
        if r.source_side[src[k]] and not r.source_side[dst[k]]:
            mine += cap[k]
            crossing.append(k)
    if mine != r.cut_capacity or len(crossing) != r.cut_edge_count:
        return False
    if len(crossing) != len(r.cut_edges):
        return False
    for i in range(len(crossing)):
        if crossing[i] != r.cut_edges[i]:
            return False

    # The same partition priced through the public entry point.
    var priced = cut_capacity_of(src, dst, cap, n, r.source_side)
    if priced.status != FLOW_OK or not priced.has_value:
        return False
    if priced.value != r.cut_capacity or priced.index != r.cut_edge_count:
        return False

    # A cut has the source on one side and the sink on the other, or it is not a cut.
    if not r.source_side[s] or r.source_side[t]:
        return False
    var inside = 0
    for v in range(n):
        if r.source_side[v]:
            inside += 1
    if inside != r.source_side_count:
        return False

    # Capacity on every edge, checked here as well as inside the audit: the audit is the
    # code under test too.
    for k in range(len(src)):
        if r.edge_flow[k] < 0.0 or r.edge_flow[k] > cap[k]:
            return False

    # Conservation at every non-terminal node, and the value as the source's net outflow.
    var audit = flow_audit_flat(
        src, dst, cap, List[Float64](), n, s, t, r.edge_flow
    )
    if audit.status != FLOW_OK or not audit.feasible or not audit.has_value:
        return False
    if audit.value != r.value:
        return False
    if audit.capacity_violations != 0 or audit.conservation_violations != 0:
        return False
    # No cost array was supplied, so this flow has no cost — not a cost of 0.0.
    if audit.has_cost or audit.cost != 0.0:
        return False
    return True


# ── the classic four-node network ─────────────────────────────────────────────
#         3        2
#   s ────────► a ────► t
#   │           │ 5     ▲
#   │ 2         ▼       │ 3
#   └────────►  b ──────┘
#
# 0 = s, 1 = a, 2 = b, 3 = t.
#   e0 s→a 3   e1 s→b 2   e2 a→b 5   e3 a→t 2   e4 b→t 3
#
# Cuts by hand: {s} = 3+2 = 5;  {s,a} = 2+5+2 = 9;  {s,b} = 3+3 = 6;
#               {s,a,b} = 2+3 = 5.   Minimum = 5, so the max flow is 5.
# The flow that achieves it: s→a 3, s→b 2, a→t 2, a→b 1, b→t 3.
# Both s's out-edges saturate, so the residual-reachable source side is {s} ALONE — the
# minimal min cut — and the cut edges are e0 and e1.


def _classic_src() -> List[Int]:
    return _ints(0, 0, 1, 1, 2)


def _classic_dst() -> List[Int]:
    return _ints(1, 2, 2, 3, 3)


def _classic_cap() -> List[Float64]:
    return _floats(3.0, 2.0, 5.0, 2.0, 3.0)


# ── the CLRS six-node network ─────────────────────────────────────────────────
# 0 = s, 1 = v1, 2 = v2, 3 = v3, 4 = v4, 5 = t.
#   s→v1 16, s→v2 13, v1→v2 10, v2→v1 4, v1→v3 12, v3→v2 9,
#   v2→v4 14, v4→v3 7, v3→t 20, v4→t 4
# The textbook max flow is 23, certified by the cut ({s,v1,v2,v4}, {v3,t}) whose capacity
# is v1→v3 (12) + v4→v3 (7) + v4→t (4) = 23. Competing cuts: {s} = 29, {s,v1} = 35,
# {s,v2} = 34, {s,v1,v2} = 26, {s,v1,v2,v3,v4} = 24. So the minimum is unique at 23 and
# the source side has four nodes and three crossing edges.


def _clrs_src() -> List[Int]:
    return _ints(0, 0, 1, 2, 1, 3, 2, 4, 3, 4)


def _clrs_dst() -> List[Int]:
    return _ints(1, 2, 2, 1, 3, 2, 4, 3, 5, 5)


def _clrs_cap() -> List[Float64]:
    return _floats(16.0, 13.0, 10.0, 4.0, 12.0, 9.0, 14.0, 7.0, 20.0, 4.0)


# ── the min-cost network ──────────────────────────────────────────────────────
# 0 = s, 1 = a, 2 = b, 3 = t.
#   e0 s→a cap 2 cost 0
#   e1 a→b cap 2 cost 1
#   e2 a→t cap 2 cost 6      the expensive direct edge
#   e3 b→t cap 1 cost 0      cheap, but only one unit fits
#
# Max flow = 2 (the cut {s} is e0 alone). Two units must leave a, and only one can go
# through b, so the second one has to pay 6. Minimum cost = 1*(1+0) + 1*(0+6) = 7, and
# the flow is s→a 2, a→b 1, a→t 1, b→t 1.
#
# The alternative max flow s→a 2, a→t 2 has the SAME value 2 and costs 12. That pair is
# what makes "cost-optimal" a measurement instead of a claim: an augmentation that took
# the expensive edge first would still report a max flow of 2.


def _cost_src() -> List[Int]:
    return _ints(0, 1, 1, 2)


def _cost_dst() -> List[Int]:
    return _ints(1, 2, 3, 3)


def _cost_cap() -> List[Float64]:
    return _floats(2.0, 2.0, 2.0, 1.0)


def _cost_cost() -> List[Float64]:
    return _floats(0.0, 1.0, 6.0, 0.0)


def main() raises:
    var passed = 0
    var failed = 0

    # ── the classic network, value and cut and the traced schedule ────────────
    var classic = max_flow_dinic(
        _classic_src(), _classic_dst(), _classic_cap(), 4, 0, 3
    )
    if (
        _invariants_hold(
            classic, _classic_src(), _classic_dst(), _classic_cap(), 4, 0, 3
        )
        and classic.value == 5.0
        and classic.cut_capacity == 5.0
        and classic.cut_edge_count == 2
        and classic.cut_edges[0] == 0
        and classic.cut_edges[1] == 1
        and classic.source_side_count == 1
        and _same_floats(classic.edge_flow, _floats(3.0, 2.0, 1.0, 2.0, 3.0))
    ):
        passed += 1
        print("  ✅ classic 4-node: flow 5 == cut 5, source side {s}, flows exact")
    else:
        failed += 1
        print(
            "  ❌ classic 4-node:",
            classic.status,
            classic.value,
            classic.cut_capacity,
            classic.cut_edge_count,
            classic.source_side_count,
        )

    # The phase and augmentation counts are the hand-traced Dinic schedule, not a
    # tolerance: phase 1 finds s→a→t (2) and s→b→t (2), phase 2 finds s→a→b→t (1), and
    # phase 3's level graph cannot reach the sink. A change here means the level graph or
    # the current-arc pointer changed behaviour, which is worth being told about.
    if classic.phases == 2 and classic.augmentations == 3:
        passed += 1
        print("  ✅ classic 4-node solves in 2 phases and 3 augmentations")
    else:
        failed += 1
        print(
            "  ❌ classic schedule:", classic.phases, classic.augmentations
        )

    # ── the CLRS network: 23, with a unique minimum cut of three edges ────────
    var clrs = max_flow_dinic(_clrs_src(), _clrs_dst(), _clrs_cap(), 6, 0, 5)
    if (
        _invariants_hold(clrs, _clrs_src(), _clrs_dst(), _clrs_cap(), 6, 0, 5)
        and clrs.value == 23.0
        and clrs.cut_capacity == 23.0
        and clrs.cut_edge_count == 3
        and clrs.source_side_count == 4
        and clrs.source_side[0]
        and clrs.source_side[1]
        and clrs.source_side[2]
        and clrs.source_side[4]
        and not clrs.source_side[3]
        and not clrs.source_side[5]
    ):
        passed += 1
        print("  ✅ CLRS 6-node: flow 23 == cut 23 across {s,v1,v2,v4} | {v3,t}")
    else:
        failed += 1
        print(
            "  ❌ CLRS 6-node:",
            clrs.status,
            clrs.value,
            clrs.cut_capacity,
            clrs.cut_edge_count,
            clrs.source_side_count,
        )

    # ── a sink nothing can reach: flow 0.0 is an ANSWER, and the cut is {s} ───
    # The source has no out-edge at all, so the residual sweep stops immediately and the
    # min cut is the source side alone with zero crossing edges. Cross-checked against the
    # frozen-adjacent Dijkstra, which must agree that node 2 is unreachable.
    var lone_src = _ints(1)
    var lone_dst = _ints(2)
    var lone_cap = _floats(4.0)
    var lone = max_flow_dinic(lone_src, lone_dst, lone_cap, 3, 0, 2)
    var lone_reach = graph_dijkstra_from_triplets(lone_src, lone_dst, lone_cap, 3, 0)
    if (
        _invariants_hold(lone, lone_src, lone_dst, lone_cap, 3, 0, 2)
        and lone.has_value
        and lone.value == 0.0
        and lone.cut_capacity == 0.0
        and lone.cut_edge_count == 0
        and lone.source_side_count == 1
        and lone.phases == 0
        and lone.augmentations == 0
        and not lone_reach.reached[2]
        and _same_floats(lone.edge_flow, _floats(0.0))
    ):
        passed += 1
        print("  ✅ unreachable sink: value 0.0 present, cut is {s} with no edges")
    else:
        failed += 1
        print(
            "  ❌ unreachable sink:",
            lone.status,
            lone.has_value,
            lone.value,
            lone.cut_edge_count,
            lone.source_side_count,
        )

    # A disconnected sink reached from the other end: the source side grows to everything
    # the source can still reach, and the cut is still empty and still equal to the flow.
    var strand_src = _ints(0, 1)
    var strand_dst = _ints(1, 2)
    var strand_cap = _floats(3.0, 2.0)
    var strand = max_flow_dinic(strand_src, strand_dst, strand_cap, 4, 0, 3)
    if (
        _invariants_hold(strand, strand_src, strand_dst, strand_cap, 4, 0, 3)
        and strand.value == 0.0
        and strand.cut_capacity == 0.0
        and strand.source_side_count == 3
        and strand.cut_edge_count == 0
    ):
        passed += 1
        print("  ✅ stranded sink: flow 0.0 == cut 0.0 with a 3-node source side")
    else:
        failed += 1
        print(
            "  ❌ stranded sink:",
            strand.status,
            strand.value,
            strand.source_side_count,
            strand.cut_edge_count,
        )

    # ── a zero-capacity edge is in the cut and contributes nothing ────────────
    # 0→1 cap 0.0, 1→2 cap 5, 0→2 cap 2. Only the direct edge can carry anything, so the
    # flow is 2, and the cut {0} crosses TWO edges whose capacities sum to 0 + 2 = 2.
    var zed_src = _ints(0, 1, 0)
    var zed_dst = _ints(1, 2, 2)
    var zed_cap = _floats(0.0, 5.0, 2.0)
    var zed = max_flow_dinic(zed_src, zed_dst, zed_cap, 3, 0, 2)
    if (
        _invariants_hold(zed, zed_src, zed_dst, zed_cap, 3, 0, 2)
        and zed.value == 2.0
        and zed.cut_edge_count == 2
        and zed.cut_edges[0] == 0
        and zed.cut_edges[1] == 2
        and zed.source_side_count == 1
        and _same_floats(zed.edge_flow, _floats(0.0, 0.0, 2.0))
    ):
        passed += 1
        print("  ✅ zero-capacity edge crosses the cut and adds 0.0 to it")
    else:
        failed += 1
        print(
            "  ❌ zero-capacity edge:",
            zed.status,
            zed.value,
            zed.cut_edge_count,
            zed.source_side_count,
        )

    # ── parallel edges are two edges, and a self-loop is not a route ──────────
    # Two s→t edges of 2 and 3 give 5. The self-loop 1→1 of capacity 7 is reported by the
    # census and cannot appear in a cut (both endpoints are always on the same side).
    var par_src = _ints(0, 0, 1)
    var par_dst = _ints(2, 2, 1)
    var par_cap = _floats(2.0, 3.0, 7.0)
    var par = max_flow_dinic(par_src, par_dst, par_cap, 3, 0, 2)
    var par_census = flow_network_check(par_src, par_dst, par_cap, 3)
    if (
        _invariants_hold(par, par_src, par_dst, par_cap, 3, 0, 2)
        and par.value == 5.0
        and par.cut_edge_count == 2
        and _same_floats(par.edge_flow, _floats(2.0, 3.0, 0.0))
        and par_census.status == FLOW_OK
        and par_census.n_edges == 3
        and par_census.n_arcs == 6
        and par_census.self_loops == 1
        and par_census.parallel_edges == 1
        and par_census.zero_capacity_edges == 0
        and par_census.total_capacity == 12.0
    ):
        passed += 1
        print("  ✅ parallel edges sum to 5; the self-loop is counted, never routed")
    else:
        failed += 1
        print(
            "  ❌ parallel/self-loop:",
            par.status,
            par.value,
            par_census.self_loops,
            par_census.parallel_edges,
            par_census.total_capacity,
        )

    # ── a negative capacity is refused, and the refusal carries no numbers ────
    var neg = max_flow_dinic(
        _ints(0, 1), _ints(1, 2), _floats(3.0, -1.0), 3, 0, 2
    )
    var neg_census = flow_network_check(
        _ints(0, 1), _ints(1, 2), _floats(3.0, -1.0), 3
    )
    if (
        neg.status == FLOW_ERR_NEGATIVE_CAPACITY
        and _no_answer(neg)
        and flow_status_name(neg.status) == "negative_capacity"
        and neg_census.status == FLOW_ERR_NEGATIVE_CAPACITY
        and neg_census.negative_capacities == 1
        and neg_census.total_capacity == 3.0
    ):
        passed += 1
        print("  ✅ negative capacity rejected; census counts it and totals only 3.0")
    else:
        failed += 1
        print(
            "  ❌ negative capacity:",
            neg.status,
            neg.has_value,
            neg_census.status,
            neg_census.negative_capacities,
        )

    # An infinite capacity is refused too, which is why there is no "unbounded" outcome to
    # report: every accepted network has a finite capacity sum.
    var inf_cap = max_flow_dinic(
        _ints(0), _ints(1), _floats(1.0e308 * 10.0), 2, 0, 1
    )
    if (
        inf_cap.status == FLOW_ERR_NON_FINITE_CAPACITY
        and _no_answer(inf_cap)
        and flow_status_name(inf_cap.status) == "non_finite_capacity"
    ):
        passed += 1
        print("  ✅ non-finite capacity rejected before any allocation")
    else:
        failed += 1
        print("  ❌ non-finite capacity:", inf_cap.status)

    # Two finite capacities whose SUM overflows: the flow value becomes infinite, and so
    # does the cut, so `inf - inf` is NaN and `NaN > tol` is False — the cut check would
    # pass and hand back an infinite flow value as an answer. The finiteness test in front
    # of it is what stops that, and this is the input that reaches it.
    var overflow = max_flow_dinic(
        _ints(0, 0), _ints(1, 1), _floats(1.0e308, 1.0e308), 2, 0, 1
    )
    if (
        overflow.status == FLOW_ERR_NON_FINITE_FLOW
        and _no_answer(overflow)
        and flow_status_name(overflow.status) == "non_finite_flow"
    ):
        passed += 1
        print("  ✅ a capacity sum that overflows to infinity is not a flow value")
    else:
        failed += 1
        print("  ❌ overflowing capacity sum:", overflow.status, overflow.value)

    # ── min-cost flow spends the cheap route first ────────────────────────────
    # One unit: the cheap route only. The frozen-adjacent Dijkstra priced with the COST
    # array is the independent oracle for that number — it reaches 1.0 with no potentials
    # and no residual network at all.
    var cheap_oracle = graph_dijkstra_from_triplets(
        _cost_src(), _cost_dst(), _cost_cost(), 4, 0
    )
    var one_unit = min_cost_flow(
        _cost_src(), _cost_dst(), _cost_cap(), _cost_cost(), 4, 0, 3, 1.0
    )
    if (
        one_unit.status == FLOW_OK
        and one_unit.has_value
        and one_unit.has_cost
        and one_unit.value == 1.0
        and one_unit.cost == 1.0
        and one_unit.target_met
        and one_unit.augmentations == 1
        and _same_floats(one_unit.edge_flow, _floats(1.0, 1.0, 0.0, 1.0))
        and _same_floats(one_unit.potential, _floats(0.0, 0.0, 1.0, 1.0))
        and cheap_oracle.reached[3]
        and cheap_oracle.distance[3] == 1.0
    ):
        passed += 1
        print("  ✅ one unit takes the cheap route at cost 1.0 (Dijkstra agrees)")
    else:
        failed += 1
        print(
            "  ❌ one unit:",
            one_unit.status,
            one_unit.value,
            one_unit.cost,
            cheap_oracle.distance[3],
        )

    # Two units: the cheap route holds only one, so the second pays 6. 7, not 12, and not
    # 2 (which is what pricing both units at the first shortest-path length would give).
    var two_units = min_cost_flow(
        _cost_src(), _cost_dst(), _cost_cap(), _cost_cost(), 4, 0, 3, 2.0
    )
    var full = min_cost_max_flow(
        _cost_src(), _cost_dst(), _cost_cap(), _cost_cost(), 4, 0, 3
    )
    var cost_maxflow = max_flow_dinic(
        _cost_src(), _cost_dst(), _cost_cap(), 4, 0, 3
    )
    if (
        two_units.status == FLOW_OK
        and two_units.value == 2.0
        and two_units.cost == 7.0
        and two_units.augmentations == 2
        and two_units.target_met
        and _same_floats(two_units.edge_flow, _floats(2.0, 1.0, 1.0, 1.0))
        and _same_floats(two_units.potential, _floats(0.0, 0.0, 1.0, 6.0))
        and full.status == FLOW_OK
        and full.value == 2.0
        and full.cost == 7.0
        and _invariants_hold(
            cost_maxflow, _cost_src(), _cost_dst(), _cost_cap(), 4, 0, 3
        )
        and cost_maxflow.value == full.value
    ):
        passed += 1
        print("  ✅ the expensive edge is used only after the cheap one saturates: 7.0")
    else:
        failed += 1
        print(
            "  ❌ two units:",
            two_units.status,
            two_units.value,
            two_units.cost,
            two_units.augmentations,
            full.cost,
        )

    # The same flow value routed differently costs strictly more, priced by the audit —
    # which is a different code path from the solver's own accumulation.
    var alternative = _floats(2.0, 0.0, 2.0, 0.0)
    var alt_audit = flow_audit_flat(
        _cost_src(), _cost_dst(), _cost_cap(), _cost_cost(), 4, 0, 3, alternative
    )
    var ssp_audit = flow_audit_flat(
        _cost_src(),
        _cost_dst(),
        _cost_cap(),
        _cost_cost(),
        4,
        0,
        3,
        two_units.edge_flow,
    )
    if (
        alt_audit.status == FLOW_OK
        and alt_audit.feasible
        and alt_audit.has_value
        and alt_audit.has_cost
        and alt_audit.value == 2.0
        and alt_audit.cost == 12.0
        and ssp_audit.feasible
        and ssp_audit.value == 2.0
        and ssp_audit.cost == 7.0
        and ssp_audit.cost < alt_audit.cost
    ):
        passed += 1
        print("  ✅ an alternative max flow of the same value 2.0 costs 12.0, not 7.0")
    else:
        failed += 1
        print(
            "  ❌ alternative pricing:",
            alt_audit.status,
            alt_audit.value,
            alt_audit.cost,
            ssp_audit.cost,
        )

    # Dual feasibility on the returned potentials: every residual arc must have a
    # non-negative reduced cost. That certifies there is no negative-cost residual cycle,
    # hence no cheaper flow of the same value, without enumerating cycles.
    var dual_ok = True
    for k in range(4):
        var u = _cost_src()[k]
        var v = _cost_dst()[k]
        var f = two_units.edge_flow[k]
        var pi = two_units.potential.copy()
        if flow_residual_capacity(_cost_cap()[k], f) > 0.0:
            if _cost_cost()[k] + pi[u] - pi[v] < 0.0:
                dual_ok = False
        if f > 0.0:
            if -_cost_cost()[k] + pi[v] - pi[u] < 0.0:
                dual_ok = False
    if dual_ok:
        passed += 1
        print("  ✅ every residual arc has a non-negative reduced cost (dual feasible)")
    else:
        failed += 1
        print("  ❌ the returned potentials are not dual feasible")

    # A fractional target splits across the two routes: 1 unit at cost 1 plus half a unit
    # at cost 6 is 4.0. Exact in binary floating point, so asserted exactly.
    var half = min_cost_flow(
        _cost_src(), _cost_dst(), _cost_cap(), _cost_cost(), 4, 0, 3, 1.5
    )
    if (
        half.status == FLOW_OK
        and half.value == 1.5
        and half.cost == 4.0
        and half.augmentations == 2
        and _same_floats(half.edge_flow, _floats(1.5, 1.0, 0.5, 1.0))
    ):
        passed += 1
        print("  ✅ a target of 1.5 costs 4.0, split 1.0 cheap + 0.5 expensive")
    else:
        failed += 1
        print("  ❌ fractional target:", half.status, half.value, half.cost)

    # Routing nothing is a real answer with a real cost of 0.0 — the same rule that makes
    # a model with no variables solvable — while a target above the max flow has NEITHER a
    # value nor a cost, and must not report the largest flow it managed.
    var nothing = min_cost_flow(
        _cost_src(), _cost_dst(), _cost_cap(), _cost_cost(), 4, 0, 3, 0.0
    )
    var too_much = min_cost_flow(
        _cost_src(), _cost_dst(), _cost_cap(), _cost_cost(), 4, 0, 3, 3.0
    )
    if (
        nothing.status == FLOW_OK
        and nothing.has_value
        and nothing.has_cost
        and nothing.value == 0.0
        and nothing.cost == 0.0
        and nothing.target_met
        and _same_floats(nothing.edge_flow, _floats(0.0, 0.0, 0.0, 0.0))
        and too_much.status == FLOW_ERR_TARGET_UNREACHABLE
        and not too_much.has_value
        and not too_much.has_cost
        and too_much.value == 0.0
        and too_much.cost == 0.0
        and not too_much.target_met
        and len(too_much.edge_flow) == 0
        and flow_status_name(too_much.status) == "target_flow_exceeds_max_flow"
    ):
        passed += 1
        print("  ✅ a target of 0.0 costs 0.0; a target of 3.0 has no answer at all")
    else:
        failed += 1
        print(
            "  ❌ degenerate targets:",
            nothing.status,
            nothing.cost,
            too_much.status,
            too_much.has_value,
        )

    # A negative cost is refused rather than answered with a Dijkstra that does not apply.
    var neg_cost = min_cost_max_flow(
        _cost_src(), _cost_dst(), _cost_cap(), _floats(0.0, -1.0, 6.0, 0.0), 4, 0, 3
    )
    var neg_target = min_cost_flow(
        _cost_src(), _cost_dst(), _cost_cap(), _cost_cost(), 4, 0, 3, -1.0
    )
    var nan_target = min_cost_flow(
        _cost_src(), _cost_dst(), _cost_cap(), _cost_cost(), 4, 0, 3,
        1.0e308 * 10.0,
    )
    if (
        neg_cost.status == FLOW_ERR_NEGATIVE_COST
        and not neg_cost.has_value
        and len(neg_cost.potential) == 0
        and flow_status_name(neg_cost.status)
        == "negative_cost_needs_cycle_cancelling"
        and neg_target.status == FLOW_ERR_NEGATIVE_TARGET
        and nan_target.status == FLOW_ERR_NON_FINITE_TARGET
    ):
        passed += 1
        print("  ✅ negative cost, negative target and infinite target each refused")
    else:
        failed += 1
        print(
            "  ❌ cost/target guards:",
            neg_cost.status,
            neg_target.status,
            nan_target.status,
        )

    # ── the minimum cost requires CANCELLING flow already routed ──────────────
    # 0 = s, 1 = a, 2 = b, 3 = t.
    #   f0 s→a cap 1 cost 0    f1 s→b cap 1 cost 2    f2 a→b cap 1 cost 0
    #   f3 b→t cap 1 cost 0    f4 a→t cap 1 cost 3
    # Max flow 2 (the cut {s} is f0 + f1). The first shortest path is s→a→b→t at cost 0,
    # and after it the ONLY way to route the second unit is s→b, back along f2 to a, then
    # a→t: cost 2 + 0 + 3 = 5. That second path traverses the REVERSE arc of f2 and
    # cancels the unit the first augmentation put there, so f2 ends at 0.0.
    #
    # This is the case a residual network exists for, and it is not reachable by any
    # forward-only search: the alternative that keeps f2 at 1.0 pushes two units into b and
    # one out, which is not a flow at all. So a driver whose reverse arc did not work would
    # either stop at a flow of 1 or return an infeasible vector — never a wrong cost that
    # still audits.
    var canc_src = _ints(0, 0, 1, 2, 1)
    var canc_dst = _ints(1, 2, 2, 3, 3)
    var canc_cap = _floats(1.0, 1.0, 1.0, 1.0, 1.0)
    var canc_cost = _floats(0.0, 2.0, 0.0, 0.0, 3.0)
    var cancelled = min_cost_max_flow(
        canc_src, canc_dst, canc_cap, canc_cost, 4, 0, 3
    )
    var canc_maxflow = max_flow_dinic(canc_src, canc_dst, canc_cap, 4, 0, 3)
    var canc_audit = flow_audit_flat(
        canc_src, canc_dst, canc_cap, canc_cost, 4, 0, 3, cancelled.edge_flow
    )
    if (
        cancelled.status == FLOW_OK
        and cancelled.value == 2.0
        and cancelled.cost == 5.0
        and cancelled.augmentations == 2
        and _same_floats(cancelled.edge_flow, _floats(1.0, 1.0, 0.0, 1.0, 1.0))
        and _same_floats(cancelled.potential, _floats(0.0, 2.0, 2.0, 5.0))
        and _invariants_hold(canc_maxflow, canc_src, canc_dst, canc_cap, 4, 0, 3)
        and canc_maxflow.value == 2.0
        and canc_audit.feasible
        and canc_audit.value == 2.0
        and canc_audit.cost == 5.0
    ):
        passed += 1
        print("  ✅ min-cost flow cancels a routed unit through the reverse arc: 5.0")
    else:
        failed += 1
        print(
            "  ❌ cancellation:",
            cancelled.status,
            cancelled.value,
            cancelled.cost,
            cancelled.augmentations,
            canc_audit.cost,
        )

    # ── the audit is a verifier, so it must catch a flow that is not one ──────
    # 2 units into a, 1 out of it: conservation fails at node 1 and nowhere else, so the
    # vector has no flow value even though every capacity is respected.
    var broken = flow_audit_flat(
        _cost_src(), _cost_dst(), _cost_cap(), _cost_cost(), 4, 0, 3,
        _floats(2.0, 1.0, 0.0, 1.0),
    )
    var over_cap = flow_audit_flat(
        _cost_src(), _cost_dst(), _cost_cap(), _cost_cost(), 4, 0, 3,
        _floats(2.0, 1.0, 1.0, 5.0),
    )
    if (
        broken.status == FLOW_OK
        and not broken.feasible
        and not broken.has_value
        and not broken.has_cost
        and broken.value == 0.0
        and broken.conservation_violations == 1
        and broken.first_bad_node == 1
        and broken.worst_conservation_violation == 1.0
        and broken.capacity_violations == 0
        and over_cap.capacity_violations == 1
        and over_cap.first_bad_edge == 3
        and over_cap.worst_capacity_violation == 4.0
        and not over_cap.feasible
    ):
        passed += 1
        print("  ✅ the audit refuses a non-conserving vector and an over-capacity one")
    else:
        failed += 1
        print(
            "  ❌ audit:",
            broken.feasible,
            broken.conservation_violations,
            broken.first_bad_node,
            over_cap.capacity_violations,
            over_cap.first_bad_edge,
        )

    # ── a tolerance is built from the quantity it judges, at ULP scale ────────
    # REGRESSION, executed on the shipped code before the fix. `_tolerance` was
    # `FLOW_TOL + FLOW_TOL * |scale|`, i.e. the relative term was a 1e-9 FRACTION of the
    # magnitude — about 4.5 million ulps — so the allowance grew with the network while the
    # violation stayed a violation. The reproduction is verbatim: ONE edge of capacity 1e12
    # carrying 1e12 + 1000.0 came back `feasible = True`, `capacity_violations = 0`,
    # `worst_capacity_violation = 0.0`, `value = 1000000001000.0`. A thousand whole units of
    # overload certified as a feasible flow by the function whose entire job is to say
    # whether somebody else's flow is valid.
    #
    # 1000.0 at magnitude 1e12 is ~8.2 million ulps: nowhere near what floating point can
    # explain away. The budget is now `FLOW_TOL + 1024 * DBL_EPSILON * magnitude` = 0.227 at
    # this scale, so the overload is 4000x over it.
    var huge_over = flow_audit_flat(
        _ints(0), _ints(1), _floats(1e12), List[Float64](), 2, 0, 1,
        _floats(1e12 + 1000.0),
    )
    # CONTROL at unit scale: the SAME violation shape on a capacity of 1.0 must still be
    # caught, so the fix is a correct scale and not a blanket tightening that only bites at
    # 1e12. 1.001 - 1.0 is not exactly 0.001 in binary, so the measured excess is bracketed
    # rather than compared for equality.
    var unit_over = flow_audit_flat(
        _ints(0), _ints(1), _floats(1.0), List[Float64](), 2, 0, 1, _floats(1.001)
    )
    # CONTROL the other way: a legitimate near-zero at 1e12 must still PASS. One thousandth
    # of a unit on a 1e12 edge is a handful of ulps of rounding, not an overload, and it must
    # come back feasible — AND it must come back with the near-miss visible, because the
    # measured magnitude is reported whether or not it crossed the threshold.
    var big_slack_flow = 1e12 + 0.001
    var big_excess = big_slack_flow - 1e12
    var near_miss = flow_audit_flat(
        _ints(0), _ints(1), _floats(1e12), List[Float64](), 2, 0, 1,
        _floats(big_slack_flow),
    )
    # And an exactly-saturated 1e12 edge is feasible with nothing measured above capacity, so
    # 0.0 still means 0.0.
    var exact_big = flow_audit_flat(
        _ints(0), _ints(1), _floats(1e12), List[Float64](), 2, 0, 1, _floats(1e12)
    )
    if (
        huge_over.status == FLOW_OK
        and not huge_over.feasible
        and not huge_over.has_value
        and huge_over.value == 0.0
        and huge_over.capacity_violations == 1
        and huge_over.first_bad_edge == 0
        # The measured magnitude, reported as measured. This was 0.0 on the shipped code:
        # the threshold that let the violation through also erased the evidence of it.
        and huge_over.worst_capacity_violation == 1000.0
        and unit_over.capacity_violations == 1
        and not unit_over.feasible
        and unit_over.first_bad_edge == 0
        and unit_over.worst_capacity_violation > 0.0009
        and unit_over.worst_capacity_violation < 0.0011
        and near_miss.status == FLOW_OK
        and near_miss.feasible
        and near_miss.has_value
        and near_miss.value == big_slack_flow
        and near_miss.capacity_violations == 0
        # Feasible AND the near-miss is not hidden behind the verdict.
        and near_miss.worst_capacity_violation == big_excess
        and big_excess > 0.0
        and exact_big.feasible
        and exact_big.value == 1e12
        and exact_big.worst_capacity_violation == 0.0
        and exact_big.capacity_violations == 0
    ):
        passed += 1
        print("  ✅ 1000 units over a 1e12 capacity is a violation, and it is reported")
    else:
        failed += 1
        print(
            "  ❌ capacity tolerance:",
            huge_over.feasible,
            huge_over.capacity_violations,
            huge_over.worst_capacity_violation,
            unit_over.capacity_violations,
            near_miss.feasible,
            near_miss.worst_capacity_violation,
        )

    # The SAME threshold was deciding a second, different question: `f >= 0`. Zero has no
    # magnitude, so nothing about the capacity may pay for a flow running backwards — but the
    # audit compared `-f` against a tolerance built from the capacity, so an edge of capacity
    # 1e12 carrying a flow of -100.0 audited as feasible (with a "value" of -100.0). A hundred
    # units the wrong way down a one-way arc is not a rounding artefact at any capacity.
    var backwards = flow_audit_flat(
        _ints(0), _ints(1), _floats(1e12), List[Float64](), 2, 0, 1, _floats(-100.0)
    )
    # And the case that pins the bound apart from the ULP budget rather than from the old
    # 1e-9 fraction: -0.1 is BELOW 1024 ulps of 1e12 (0.227), so a lower bound that borrows the
    # capacity's magnitude still swallows it however tight the relative term is. A tenth of a
    # unit backwards is a violation; only the absolute floor may forgive anything here.
    var mild_backwards = flow_audit_flat(
        _ints(0), _ints(1), _floats(1e12), List[Float64](), 2, 0, 1, _floats(-0.1)
    )
    # CONTROL at unit scale: a thousandth of a unit backwards on a capacity of 1.0 is still
    # caught, so the lower bound is absolute at BOTH scales and not merely re-scaled.
    var unit_backwards = flow_audit_flat(
        _ints(0), _ints(1), _floats(1.0), List[Float64](), 2, 0, 1, _floats(-0.001)
    )
    # CONTROL the other way: -1e-12 is a caller's rounding against zero, under the absolute
    # floor, and stays feasible at BOTH capacities — measured and reported either way.
    var tiny_backwards = flow_audit_flat(
        _ints(0), _ints(1), _floats(1e12), List[Float64](), 2, 0, 1, _floats(-1e-12)
    )
    var tiny_backwards_unit = flow_audit_flat(
        _ints(0), _ints(1), _floats(1.0), List[Float64](), 2, 0, 1, _floats(-1e-12)
    )
    if (
        backwards.status == FLOW_OK
        and not backwards.feasible
        and not backwards.has_value
        and backwards.capacity_violations == 1
        and backwards.first_bad_edge == 0
        and backwards.worst_capacity_violation == 100.0
        and not mild_backwards.feasible
        and mild_backwards.capacity_violations == 1
        and mild_backwards.first_bad_edge == 0
        and mild_backwards.worst_capacity_violation == 0.1
        and not unit_backwards.feasible
        and unit_backwards.capacity_violations == 1
        and unit_backwards.worst_capacity_violation > 0.0009
        and unit_backwards.worst_capacity_violation < 0.0011
        and tiny_backwards.feasible
        and tiny_backwards.capacity_violations == 0
        and tiny_backwards.worst_capacity_violation == 1e-12
        and tiny_backwards_unit.feasible
        and tiny_backwards_unit.worst_capacity_violation == 1e-12
    ):
        passed += 1
        print("  ✅ a flow of -100 is not made feasible by a capacity of 1e12")
    else:
        failed += 1
        print(
            "  ❌ negative-flow bound:",
            backwards.feasible,
            backwards.capacity_violations,
            backwards.worst_capacity_violation,
            mild_backwards.feasible,
            unit_backwards.feasible,
            tiny_backwards.feasible,
            tiny_backwards.worst_capacity_violation,
        )

    # Same defect at the conservation test, same 1e-9-fraction cause. Node 1 takes in 1e12
    # and passes on 1e12 - 1000: it loses a thousand units. Its gross throughput is ~2e12, so
    # the old threshold was 1e-9 * 2e12 = 2000 and the 1000-unit leak conserved.
    var leak = flow_audit_flat(
        _ints(0, 1), _ints(1, 2), _floats(1e12, 1e12), List[Float64](), 3, 0, 2,
        _floats(1e12, 1e12 - 1000.0),
    )
    # CONTROL at unit scale: the same leak shape at magnitude 1.0 is still caught.
    var unit_leak = flow_audit_flat(
        _ints(0, 1), _ints(1, 2), _floats(1.0, 1.0), List[Float64](), 3, 0, 2,
        _floats(1.0, 0.999),
    )
    # CONTROL the other way: a thousandth of a unit lost at a node moving 2e12 is rounding,
    # and must still conserve — with the imbalance reported as measured.
    var tiny_leak_flow = 1e12 - 0.001
    var tiny_imbalance = 1e12 - tiny_leak_flow
    var tiny_leak = flow_audit_flat(
        _ints(0, 1), _ints(1, 2), _floats(1e12, 1e12), List[Float64](), 3, 0, 2,
        _floats(1e12, tiny_leak_flow),
    )
    if (
        leak.status == FLOW_OK
        and not leak.feasible
        and not leak.has_value
        and leak.conservation_violations == 1
        and leak.first_bad_node == 1
        and leak.worst_conservation_violation == 1000.0
        and leak.capacity_violations == 0
        and not unit_leak.feasible
        and unit_leak.conservation_violations == 1
        and unit_leak.first_bad_node == 1
        and unit_leak.worst_conservation_violation > 0.0009
        and unit_leak.worst_conservation_violation < 0.0011
        and tiny_leak.feasible
        and tiny_leak.conservation_violations == 0
        and tiny_leak.worst_conservation_violation == tiny_imbalance
        and tiny_imbalance > 0.0
    ):
        passed += 1
        print("  ✅ a 1000-unit leak at a node moving 2e12 units is not conservation")
    else:
        failed += 1
        print(
            "  ❌ conservation tolerance:",
            leak.feasible,
            leak.conservation_violations,
            leak.worst_conservation_violation,
            unit_leak.conservation_violations,
            tiny_leak.feasible,
            tiny_leak.worst_conservation_violation,
        )

    # The same fraction sized the "did we reach the target" test, and that one is a CLAIM:
    # `target_met` is the field a caller reads to learn whether its demand was routed. A
    # single edge of capacity 1e12 - 1000 asked for 1e12 came back FLOW_OK with
    # `target_met = True`, 1000 units short, because 1e-9 * 1e12 == 1000 exactly. It is now
    # FLOW_ERR_TARGET_UNREACHABLE with no value and no cost.
    var short_target = min_cost_flow(
        _ints(0), _ints(1), _floats(1e12 - 1000.0), _floats(1.0), 2, 0, 1, 1e12
    )
    # CONTROL at unit scale: a target of 1.0 on a capacity of 0.999 is still unreachable.
    var unit_target = min_cost_flow(
        _ints(0), _ints(1), _floats(0.999), _floats(1.0), 2, 0, 1, 1.0
    )
    # CONTROL the other way: a target of 1e12 that IS routable is still met, priced, and not
    # turned into a false rejection by the tighter budget.
    var big_target = min_cost_flow(
        _ints(0), _ints(1), _floats(1e12), _floats(1.0), 2, 0, 1, 1e12
    )
    if (
        short_target.status == FLOW_ERR_TARGET_UNREACHABLE
        and not short_target.has_value
        and not short_target.has_cost
        and not short_target.target_met
        and unit_target.status == FLOW_ERR_TARGET_UNREACHABLE
        and not unit_target.target_met
        and big_target.status == FLOW_OK
        and big_target.target_met
        and big_target.value == 1e12
        and big_target.cost == 1e12
    ):
        passed += 1
        print("  ✅ a 1e12 demand routed 1000 units short is unreachable, not met")
    else:
        failed += 1
        print(
            "  ❌ target tolerance:",
            short_target.status,
            short_target.target_met,
            unit_target.status,
            big_target.status,
            big_target.target_met,
        )

    # The max-flow == min-cut self-check and the dual-feasibility check use the same
    # `_tolerance`, and tightening a SELF-check risks the opposite failure: a correct answer
    # rejected as a defect. Both must still solve at 1e12 capacities and 1e12 costs, with the
    # identity exact and the potentials dual feasible — the tolerance was tightened, not the
    # arithmetic.
    # The classic network's own capacities, every one of them scaled by 1e12: the max flow
    # scales with them, so the answer is 5e12 and it is exact in binary (3e12 and 5e12 both
    # have exact Float64 representations, and so does their sum).
    var big_cap = _floats(3e12, 2e12, 5e12, 2e12, 3e12)
    var big_flow = max_flow_dinic(
        _classic_src(), _classic_dst(), big_cap, 4, 0, 3
    )
    var big_costs = _floats(0.0, 1e12, 6e12, 0.0)
    var big_priced = min_cost_max_flow(
        _cost_src(), _cost_dst(), _cost_cap(), big_costs, 4, 0, 3
    )
    # The other end of the range, asserted because `FLOW_EPS` documents it as a consequence:
    # an arc whose whole capacity is below the 1e-12 progress floor is never usable, so the
    # max flow is 0.0. What matters here is that the answer stays COHERENT — the absolute term
    # of the tolerance keeps the identity check from turning a documented floor into a
    # FLOW_ERR_CUT_MISMATCH, and the cut still prices the arc it declined to push on.
    var below_floor = max_flow_dinic(
        _ints(0), _ints(1), _floats(1e-13), 2, 0, 1
    )
    var big_dual_ok = True
    for k in range(4):
        var u = _cost_src()[k]
        var v = _cost_dst()[k]
        var f = big_priced.edge_flow[k]
        var pi = big_priced.potential.copy()
        if flow_residual_capacity(_cost_cap()[k], f) > 0.0:
            if big_costs[k] + pi[u] - pi[v] < 0.0:
                big_dual_ok = False
        if f > 0.0:
            if -big_costs[k] + pi[v] - pi[u] < 0.0:
                big_dual_ok = False
    if (
        big_flow.status == FLOW_OK
        and _invariants_hold(
            big_flow, _classic_src(), _classic_dst(), big_cap, 4, 0, 3
        )
        and big_flow.value == big_flow.cut_capacity
        and big_flow.value == 5e12
        and big_priced.status == FLOW_OK
        and big_priced.value == 2.0
        and big_priced.cost == 7e12
        and big_dual_ok
        and below_floor.status == FLOW_OK
        and below_floor.has_value
        and below_floor.value == 0.0
        and below_floor.cut_capacity == 1e-13
    ):
        passed += 1
        print("  ✅ 1e12 capacities and costs: identity exact, potentials dual feasible")
    else:
        failed += 1
        print(
            "  ❌ large-scale self-checks:",
            big_flow.status,
            big_flow.value,
            big_flow.cut_capacity,
            big_priced.status,
            big_priced.cost,
            big_dual_ok,
        )

    # ── the per-step scalars, exposed and folded ──────────────────────────────
    # On the classic network at zero flow, the path s→a→t (edges 0 and 3) has bottleneck
    # min(3, 2) = 2, and the binding edge is e3. On the SOLVED network the same path has
    # no capacity left, and `is_saturated` must agree with the residual.
    var fresh = _floats(0.0, 0.0, 0.0, 0.0, 0.0)
    var open_path = path_bottleneck(_classic_cap(), fresh, _ints(0, 3))
    var used_path = path_bottleneck(_classic_cap(), classic.edge_flow, _ints(0, 3))
    var residuals = edge_residuals(_classic_cap(), classic.edge_flow)
    var empty_path = path_bottleneck(_classic_cap(), fresh, List[Int]())
    if (
        open_path.status == FLOW_OK
        and open_path.has_value
        and open_path.value == 2.0
        and open_path.index == 3
        and used_path.value == 0.0
        and used_path.has_value
        and residuals.status == FLOW_OK
        and residuals.length == 5
        and _same_floats(residuals.values, _floats(0.0, 0.0, 4.0, 0.0, 0.0))
        and is_saturated(_classic_cap()[0], classic.edge_flow[0], 0.0)
        and not is_saturated(_classic_cap()[2], classic.edge_flow[2], 0.0)
        and empty_path.status == FLOW_ERR_EMPTY_PATH
        and not empty_path.has_value
        and empty_path.value == 0.0
        and empty_path.index == -1
    ):
        passed += 1
        print("  ✅ bottleneck fold, residuals and saturation agree; empty path absent")
    else:
        failed += 1
        print(
            "  ❌ per-step scalars:",
            open_path.value,
            open_path.index,
            used_path.value,
            residuals.length,
            empty_path.status,
        )

    # The fold really is the frozen `flow_augment_amount`, so folding it by hand over the
    # same residuals must reproduce the driver's bottleneck exactly.
    var by_hand = flow_augment_amount(
        flow_residual_capacity(_classic_cap()[0], 0.0),
        flow_residual_capacity(_classic_cap()[3], 0.0),
    )
    if by_hand == open_path.value:
        passed += 1
        print("  ✅ path_bottleneck matches a hand fold of the frozen scalars")
    else:
        failed += 1
        print("  ❌ fold disagrees with the frozen scalars:", by_hand, open_path.value)

    # ── terminals and dimensions ─────────────────────────────────────────────
    var same = max_flow_dinic(
        _classic_src(), _classic_dst(), _classic_cap(), 4, 2, 2
    )
    var empty_net = max_flow_dinic(
        List[Int](), List[Int](), List[Float64](), 0, 0, 0
    )
    var huge = max_flow_dinic(
        List[Int](), List[Int](), List[Float64](), FLOW_MAX_NODES + 1, 0, 1
    )
    var ragged = max_flow_dinic(_ints(0, 1), _ints(1), _floats(1.0, 2.0), 3, 0, 2)
    var stray = max_flow_dinic(_ints(0, 9), _ints(1, 2), _floats(1.0, 2.0), 3, 0, 2)
    if (
        same.status == FLOW_ERR_SAME_TERMINALS
        and _no_answer(same)
        and empty_net.status == FLOW_ERR_EMPTY_NETWORK
        and huge.status == FLOW_ERR_INVALID_DIMENSIONS
        and ragged.status == FLOW_ERR_LENGTH_MISMATCH
        and stray.status == FLOW_ERR_EDGE_OUT_OF_RANGE
        and _no_answer(stray)
        and flow_status_name(stray.status) == "edge_endpoint_out_of_range"
    ):
        passed += 1
        print("  ✅ same terminals, empty, oversized, ragged and stray all refused")
    else:
        failed += 1
        print(
            "  ❌ terminal/dimension guards:",
            same.status,
            empty_net.status,
            huge.status,
            ragged.status,
            stray.status,
        )

    # ── the TOTAL allocation a request can trigger is bounded ────────────────
    # Regression, from a measured defect: `FLOW_MAX_NODES` used to be `MAX_CSR_DIM` raw.
    # That bounded each array to the ~512 MiB the csr ceiling was justified for — as the
    # limit for ONE object — while every entry point here allocates several arrays of
    # length n_nodes at once (the triplet census peaks at six on its own, then the level
    # array, the potentials, the arc pointer, the masks). So an EMPTY edge list with
    # n_nodes at the shared ceiling was a structurally consistent request, with nothing in
    # it to solve, that allocated several times the whole budget before answering 0.
    #
    # The ceiling is now MAX_CSR_DIM // FLOW_NODE_ARRAYS, so the product nodes x arrays x
    # 8 bytes is that same 512 MiB and the REQUEST is what is bounded. Asserted on every
    # entry point that allocates per-node state, because a bound on one of them is exactly
    # the mistake being fixed.
    var bomb_flow = max_flow_dinic(
        List[Int](), List[Int](), List[Float64](), MAX_CSR_DIM, 0, 1
    )
    var bomb_cost = min_cost_flow(
        List[Int](), List[Int](), List[Float64](), List[Float64](),
        MAX_CSR_DIM, 0, 1, 1.0,
    )
    var bomb_maxcost = min_cost_max_flow(
        List[Int](), List[Int](), List[Float64](), List[Float64](),
        MAX_CSR_DIM, 0, 1,
    )
    var bomb_audit = flow_audit_flat(
        List[Int](), List[Int](), List[Float64](), List[Float64](),
        MAX_CSR_DIM, 0, 1, List[Float64](),
    )
    var bomb_census = flow_network_check(
        List[Int](), List[Int](), List[Float64](), MAX_CSR_DIM
    )
    if (
        bomb_flow.status == FLOW_ERR_INVALID_DIMENSIONS
        and _no_answer(bomb_flow)
        and bomb_cost.status == FLOW_ERR_INVALID_DIMENSIONS
        and not bomb_cost.has_value
        and not bomb_cost.has_cost
        and len(bomb_cost.potential) == 0
        and bomb_maxcost.status == FLOW_ERR_INVALID_DIMENSIONS
        and bomb_audit.status == FLOW_ERR_INVALID_DIMENSIONS
        and not bomb_audit.feasible
        and not bomb_audit.has_value
        and bomb_census.status == FLOW_ERR_INVALID_DIMENSIONS
    ):
        passed += 1
        print("  ✅ empty edges + n_nodes at the shared csr ceiling: refused, not sized")
    else:
        failed += 1
        print(
            "  ❌ allocation bomb accepted:",
            bomb_flow.status,
            bomb_cost.status,
            bomb_maxcost.status,
            bomb_audit.status,
            bomb_census.status,
        )

    # The ceiling's arithmetic, asserted rather than described: the total (nodes x arrays)
    # must fit the shared single-object budget, and it must still be a real ceiling well
    # above any network a caller would hand over.
    if _node_ceiling_fits(FLOW_MAX_NODES, FLOW_NODE_ARRAYS, MAX_CSR_DIM):
        passed += 1
        print("  ✅ node ceiling x per-node arrays fits the one shared csr budget")
    else:
        failed += 1
        print("  ❌ node ceiling arithmetic:", FLOW_MAX_NODES, FLOW_NODE_ARRAYS)

    # And the bound is on ALLOCATION, not on the edge count: a network whose nodes mostly
    # sit isolated is still a well-posed question (32 declared nodes, 2 edges, 30 of them
    # mentioned by nothing), and it must still solve — with the full 32-slot partition the
    # caller asked for. Max flow here is 2: s→a has capacity 3 but a→t only carries 2, so
    # the cut is {0, 1} with the single edge a→t crossing it.
    var sparse_flow = max_flow_dinic(
        _ints(0, 1), _ints(1, 2), _floats(3.0, 2.0), 32, 0, 2
    )
    if (
        _invariants_hold(
            sparse_flow, _ints(0, 1), _ints(1, 2), _floats(3.0, 2.0), 32, 0, 2
        )
        and sparse_flow.value == 2.0
        and sparse_flow.cut_capacity == 2.0
        and sparse_flow.cut_edge_count == 1
        and sparse_flow.cut_edges[0] == 1
        and sparse_flow.source_side_count == 2
        and len(sparse_flow.source_side) == 32
        and _same_floats(sparse_flow.edge_flow, _floats(2.0, 2.0))
    ):
        passed += 1
        print("  ✅ 32 nodes / 2 edges still solves: isolated nodes are not a rejection")
    else:
        failed += 1
        print(
            "  ❌ sparse network refused or mis-solved:",
            sparse_flow.status,
            sparse_flow.value,
            sparse_flow.cut_capacity,
            sparse_flow.source_side_count,
        )

    # ── the generated contract suite's argument pattern is REFUSED ───────────
    # Every contract function is called by the generated A–Z suite with a 5-element list
    # for each List and 5 for each Int. An unguarded `n_nodes`/`source` there would index
    # far past the end, which is an uncatchable process crash that takes the worker down
    # with every resident dataset — not an exception a caller can see.
    var lf5 = _floats(0.5, 0.6, 0.7, 0.4, 0.3)
    var li5 = _ints(1, 2, 3, 4, 5)
    var lb5 = _bools(True, False, True, True, False)
    var gen_flow = max_flow_dinic(li5, li5, lf5, 5, 5, 5)
    var gen_cost = min_cost_flow(li5, li5, lf5, lf5, 5, 5, 5, 0.5)
    var gen_maxcost = min_cost_max_flow(li5, li5, lf5, lf5, 5, 5, 5)
    var gen_audit = flow_audit_flat(li5, li5, lf5, lf5, 5, 5, 5, lf5)
    var gen_census = flow_network_check(li5, li5, lf5, 5)
    var gen_path = path_bottleneck(lf5, lf5, li5)
    var gen_cut = cut_capacity_of(li5, li5, lf5, 5, lb5)
    var gen_residuals = edge_residuals(lf5, lf5)
    if (
        gen_flow.status == FLOW_ERR_NODE_OUT_OF_RANGE
        and _no_answer(gen_flow)
        and gen_cost.status == FLOW_ERR_NODE_OUT_OF_RANGE
        and gen_maxcost.status == FLOW_ERR_NODE_OUT_OF_RANGE
        and gen_audit.status == FLOW_ERR_NODE_OUT_OF_RANGE
        and gen_census.status == FLOW_ERR_EDGE_OUT_OF_RANGE
        and gen_census.out_of_range_edges == 1
        and gen_census.self_loops == 4
        and gen_path.status == FLOW_ERR_PATH_INDEX
        and gen_path.index == 5
        and gen_cut.status == FLOW_ERR_EDGE_OUT_OF_RANGE
        and gen_residuals.status == FLOW_OK
        and gen_residuals.length == 5
    ):
        passed += 1
        print("  ✅ the generated (_lf5, _li5, 5) pattern is refused, never indexed")
    else:
        failed += 1
        print(
            "  ❌ generated pattern:",
            gen_flow.status,
            gen_cost.status,
            gen_audit.status,
            gen_census.status,
            gen_path.status,
            gen_cut.status,
        )

    # A partition of the wrong length is refused before it is indexed, and the pricer
    # reports the crossing count alongside the capacity.
    var short_side = cut_capacity_of(
        _classic_src(), _classic_dst(), _classic_cap(), 4, _bools(True, False)
    )
    var all_source = cut_capacity_of(
        _classic_src(),
        _classic_dst(),
        _classic_cap(),
        4,
        _bools(True, True, True, True),
    )
    if (
        short_side.status == FLOW_ERR_LENGTH_MISMATCH
        and not short_side.has_value
        and all_source.status == FLOW_OK
        and all_source.value == 0.0
        and all_source.index == 0
    ):
        passed += 1
        print("  ✅ a wrong-length partition is refused; the trivial one crosses nothing")
    else:
        failed += 1
        print(
            "  ❌ partition pricing:",
            short_side.status,
            all_source.status,
            all_source.value,
            all_source.index,
        )

    # ── one name per status code, and they are all distinct ──────────────────
    # A duplicated name would make two different defects indistinguishable in a log, which
    # is the same failure as a duplicated code.
    var names = List[String]()
    for code in range(22):
        names.append(flow_status_name(code))
    var distinct = True
    for i in range(len(names)):
        if names[i] == "unknown_status":
            distinct = False
        for j in range(i + 1, len(names)):
            if names[i] == names[j]:
                distinct = False
    if distinct and flow_status_name(22) == "unknown_status":
        passed += 1
        print("  ✅ all 22 status codes have distinct names; 22 is unknown")
    else:
        failed += 1
        print("  ❌ status names are not distinct")

    print("  [optimization.flow] Passed:", passed, "Failed:", failed)
