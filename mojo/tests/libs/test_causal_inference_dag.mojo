"""test_causal_inference_dag.mojo — known-value tests for identification.

Hand-written. Every d-separation answer below is enumerable by hand on a graph of three to five
nodes, which is the point: the three blocking rules have exactly three canonical shapes and each
one is tested in isolation before anything composite is.

    chain     0 -> 1 -> 2      0 and 2 dependent; BLOCKED by {1}
    fork      0 <- 1 -> 2      0 and 2 dependent; BLOCKED by {1}
    collider  0 -> 1 <- 2      0 and 2 INDEPENDENT; conditioning on {1} OPENS the path
    collider  0 -> 1 <- 2,     0 and 2 INDEPENDENT; conditioning on a DESCENDANT {3} of the
      + child   1 -> 3         collider also OPENS it

The fourth is the one a naive implementation gets wrong — a routine that only tests `node in Z`
reports separation for `Z = {3}` — and it is why Bayes-Ball needs its Phase I ancestor pass at
all. It is asserted separately from the third.

The composite cases are the two textbook adjustment problems, both with answers that are argued
in every causal-inference text:

  * CONFOUNDING. `T <- U -> Y`, `T -> Y`. Not identified with `Z = {}` (the backdoor path
    `T <- U -> Y` is open), identified with `Z = {U}`, and NOT identified with `Z = {M}` where
    `T -> M` — because M is a descendant of the treatment, which is the half of the backdoor
    criterion an incomplete implementation omits (rule 4d).
  * M-BIAS. `U1 -> T`, `U1 -> M`, `U2 -> M`, `U2 -> Y`. Identified with `Z = {}` because the
    collider at M blocks the only backdoor path, and NOT identified with `Z = {M}` because
    conditioning on the collider opens it. Adjusting for more covariates is not safer, and this
    is the case that proves the implementation knows it.

The witness path is asserted as a NODE SEQUENCE, not as "non-empty": a refusal that cannot name
the open path is not actionable, so the path itself is a tested output.

Cycle reporting is checked the same way. `graph.algorithms.topological_sort` is the acyclicity
oracle and is called directly here so the suite's verdict does not come from the code under test;
what the code adds is an EDGE on the cycle, and the suite verifies that the named pair really is
one of the caller's edges and that both endpoints lie on a cycle (each reaches the other).
"""
from graph.algorithms import Graph, graph_add_edge, graph_new, topological_sort

from causal_inference.base import (
    CI_ERR_DUPLICATE,
    CI_ERR_INDEX,
    CI_ERR_LENGTH_MISMATCH,
    CI_ERR_NOT_A_DAG,
    CI_ERR_NOT_IDENTIFIED,
    CI_ERR_SHAPE,
    CI_OK,
)
from causal_inference.dag import (
    DAG_NO_NODE,
    backdoor_check,
    backdoor_minimal_set,
    d_separated,
    dag_ancestors,
    dag_descendants,
    dag_validate,
)


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


def _same_ints(a: List[Int], b: List[Int]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


def _li5() -> List[Int]:
    return _ints(1, 2, 3, 4, 5)


def _empty_int() -> List[Int]:
    return List[Int]()


def _reaches(ef: List[Int], et: List[Int], n: Int, src: Int, dst: Int) -> Bool:
    """Forward reachability computed HERE, so the cycle assertion does not use the code under
    test as its own oracle."""
    var seen = List[Bool]()
    for _ in range(n):
        seen.append(False)
    var stack = List[Int]()
    stack.append(src)
    seen[src] = True
    while len(stack) > 0:
        var u = stack[len(stack) - 1]
        _ = stack.pop()
        for k in range(len(ef)):
            if ef[k] == u and not seen[et[k]]:
                seen[et[k]] = True
                stack.append(et[k])
    return seen[dst]


def _edge_exists(ef: List[Int], et: List[Int], u: Int, v: Int) -> Bool:
    for k in range(len(ef)):
        if ef[k] == u and et[k] == v:
            return True
    return False


def _order_respects_edges(order: List[Int], ef: List[Int], et: List[Int], n: Int) -> Bool:
    """Every edge must go forward in the reported order. Computed here rather than trusted."""
    if len(order) != n:
        return False
    var pos = List[Int]()
    for _ in range(n):
        pos.append(-1)
    for i in range(len(order)):
        var v = order[i]
        if v < 0 or v >= n or pos[v] >= 0:
            return False
        pos[v] = i
    for k in range(len(ef)):
        if pos[ef[k]] >= pos[et[k]]:
            return False
    return True


def main() raises:
    var passed = 0
    var failed = 0

    # ── shape 1: the CHAIN 0 -> 1 -> 2 ───────────────────────────────────────
    var chain_f = _ints(0, 1)
    var chain_t = _ints(1, 2)
    var chain_open = d_separated(chain_f, chain_t, 3, _ints(0), _ints(2), _empty_int())
    var chain_blocked = d_separated(chain_f, chain_t, 3, _ints(0), _ints(2), _ints(1))
    if (
        chain_open.status == CI_OK
        and chain_open.has_answer
        and not chain_open.separated
        and _same_ints(chain_open.path_nodes, _ints(0, 1, 2))
        and chain_blocked.status == CI_OK
        and chain_blocked.separated
        and len(chain_blocked.path_nodes) == 0
    ):
        passed += 1
        print("  ✅ chain 0->1->2: open with Z={}, witness [0,1,2]; blocked by Z={1}")
    else:
        failed += 1
        print("  ❌ chain wrong:", chain_open.separated, chain_blocked.separated)

    # ── shape 2: the FORK 0 <- 1 -> 2 ────────────────────────────────────────
    var fork_f = _ints(1, 1)
    var fork_t = _ints(0, 2)
    var fork_open = d_separated(fork_f, fork_t, 3, _ints(0), _ints(2), _empty_int())
    var fork_blocked = d_separated(fork_f, fork_t, 3, _ints(0), _ints(2), _ints(1))
    if (
        not fork_open.separated
        and _same_ints(fork_open.path_nodes, _ints(0, 1, 2))
        and fork_blocked.separated
    ):
        passed += 1
        print("  ✅ fork 0<-1->2: open with Z={}, witness [0,1,2]; blocked by Z={1}")
    else:
        failed += 1
        print("  ❌ fork wrong:", fork_open.separated, fork_blocked.separated)

    # ── shape 3: the COLLIDER 0 -> 1 <- 2 (the sign flips) ───────────────────
    var col_f = _ints(0, 2)
    var col_t = _ints(1, 1)
    var col_closed = d_separated(col_f, col_t, 3, _ints(0), _ints(2), _empty_int())
    var col_opened = d_separated(col_f, col_t, 3, _ints(0), _ints(2), _ints(1))
    if (
        col_closed.separated
        and len(col_closed.path_nodes) == 0
        and not col_opened.separated
        and _same_ints(col_opened.path_nodes, _ints(0, 1, 2))
    ):
        passed += 1
        print("  ✅ collider 0->1<-2: SEPARATED with Z={}; conditioning on {1} OPENS it")
    else:
        failed += 1
        print("  ❌ collider wrong:", col_closed.separated, col_opened.separated)

    # ── shape 4: conditioning on a DESCENDANT of the collider also opens it ──
    # 0 -> 1 <- 2, plus 1 -> 3. Z = {3} touches no node on the path, and a routine that only
    # tests `node in Z` reports separation here. This is why Phase I exists.
    var desc_f = _ints(0, 2, 1)
    var desc_t = _ints(1, 1, 3)
    var via_desc = d_separated(desc_f, desc_t, 4, _ints(0), _ints(2), _ints(3))
    var no_cond = d_separated(desc_f, desc_t, 4, _ints(0), _ints(2), _empty_int())
    if (
        no_cond.separated
        and not via_desc.separated
        and _same_ints(via_desc.path_nodes, _ints(0, 1, 2))
    ):
        passed += 1
        print("  ✅ a collider's DESCENDANT in Z opens the path — the Phase I ancestor pass")
    else:
        failed += 1
        print("  ❌ collider-descendant case wrong:", no_cond.separated, via_desc.separated)

    # ── an empty side is separated, and that is a real answer ────────────────
    var empty_x = d_separated(chain_f, chain_t, 3, _empty_int(), _ints(2), _empty_int())
    if empty_x.status == CI_OK and empty_x.has_answer and empty_x.separated:
        passed += 1
        print("  ✅ X empty is separated with has_answer=True — an answer, not an absence")
    else:
        failed += 1
        print("  ❌ empty X mishandled")

    # ── overlapping or duplicated node sets are refused, not guessed ──────────
    if (
        d_separated(chain_f, chain_t, 3, _ints(0), _ints(0), _empty_int()).status
        == CI_ERR_DUPLICATE
        and d_separated(chain_f, chain_t, 3, _ints(0), _ints(2), _ints(0)).status
        == CI_ERR_DUPLICATE
        and d_separated(chain_f, chain_t, 3, _ints(0, 0), _ints(2), _empty_int()).status
        == CI_ERR_DUPLICATE
        and d_separated(chain_f, chain_t, 3, _ints(3), _ints(2), _empty_int()).status
        == CI_ERR_INDEX
    ):
        passed += 1
        print("  ✅ overlapping / duplicated / out-of-range node sets are refused")
    else:
        failed += 1
        print("  ❌ degenerate node sets were answered")

    # ── a cycle is not a DAG, and d-separation refuses over one ──────────────
    var cyc_f = _ints(0, 1, 2)
    var cyc_t = _ints(1, 2, 0)
    var cyc = dag_validate(cyc_f, cyc_t, 3)
    var oracle = graph_new(3)
    for k in range(3):
        graph_add_edge(oracle, cyc_f[k], cyc_t[k], 1.0)
    var oracle_partial = len(topological_sort(oracle)) != 3
    if (
        cyc.status == CI_ERR_NOT_A_DAG
        and not cyc.is_dag
        and not cyc.has_order
        and len(cyc.topo_order) == 0
        and oracle_partial
        and _edge_exists(cyc_f, cyc_t, cyc.cycle_from, cyc.cycle_to)
        and _reaches(cyc_f, cyc_t, 3, cyc.cycle_to, cyc.cycle_from)
    ):
        passed += 1
        print("  ✅ cycle: refused, no partial order, and the named edge IS on a cycle")
    else:
        failed += 1
        print("  ❌ cycle reporting wrong:", cyc.status, cyc.cycle_from, cyc.cycle_to)

    var loop = dag_validate(_ints(0), _ints(0), 2)
    if (
        loop.status == CI_ERR_NOT_A_DAG
        and loop.n_self_loops == 1
        and loop.cycle_from == 0
        and loop.cycle_to == 0
    ):
        passed += 1
        print("  ✅ a self loop is a cycle and is named as the edge 0 -> 0")
    else:
        failed += 1
        print("  ❌ self loop wrong:", loop.status, loop.cycle_from, loop.cycle_to)

    # ── the cycle is named whatever ORDER the edges arrive in ─────────────────
    # A node merely DOWNSTREAM of a cycle is left in Kahn's residual set (nothing ever settles
    # it) and can be a sink, so a walk that follows residual CHILDREN strands itself there and
    # names nothing. Measured on exactly this graph — 2-cycle 0<->1 with a pendant 1 -> 2 — the
    # verdict depended on which residual child the walk happened to see first: edge list
    # [(0,1),(1,2),(1,0)] reported `not a DAG` with cycle_from == cycle_to == -1, while the SAME
    # graph as [(0,1),(1,0),(1,2)] named an edge. Walking residual PARENTS instead cannot
    # strand: Kahn leaves every residual node with at least one residual parent, always.
    #
    # Every ordering of every graph below must name an edge that (a) really exists and (b) lies
    # on a cycle, both checked by this file's own reachability oracle and not by the code under
    # test. The exact pair is asserted too, because the walk is deterministic.
    var pend_f = _ints(0, 1, 1)
    var pend_t = _ints(1, 2, 0)
    var pend_a = dag_validate(pend_f, pend_t, 3)
    var perm_f = _ints(0, 1, 1)
    var perm_t = _ints(1, 0, 2)
    var pend_b = dag_validate(perm_f, perm_t, 3)
    # The residual set's LOWEST-indexed node is the pendant here, which is the sharpest form:
    # the walk starts on a sink. 1 <-> 2 is the cycle, 1 -> 0 the pendant, node 3 isolated.
    var sink_f = _ints(1, 2, 1)
    var sink_t = _ints(2, 1, 0)
    var sink = dag_validate(sink_f, sink_t, 4)
    if (
        pend_a.status == CI_ERR_NOT_A_DAG
        and not pend_a.is_dag
        and pend_a.cycle_from != DAG_NO_NODE
        and pend_a.cycle_to != DAG_NO_NODE
        and _edge_exists(pend_f, pend_t, pend_a.cycle_from, pend_a.cycle_to)
        and _reaches(pend_f, pend_t, 3, pend_a.cycle_to, pend_a.cycle_from)
        and pend_a.cycle_from == 0
        and pend_a.cycle_to == 1
        # the permuted edge list is the same graph and must give the same answer
        and pend_b.status == CI_ERR_NOT_A_DAG
        and _edge_exists(perm_f, perm_t, pend_b.cycle_from, pend_b.cycle_to)
        and _reaches(perm_f, perm_t, 3, pend_b.cycle_to, pend_b.cycle_from)
        and pend_b.cycle_from == pend_a.cycle_from
        and pend_b.cycle_to == pend_a.cycle_to
        # the walk STARTS on a sink here and still names an edge on the cycle
        and sink.status == CI_ERR_NOT_A_DAG
        and sink.cycle_from != DAG_NO_NODE
        and _edge_exists(sink_f, sink_t, sink.cycle_from, sink.cycle_to)
        and _reaches(sink_f, sink_t, 4, sink.cycle_to, sink.cycle_from)
        and sink.cycle_from == 1
        and sink.cycle_to == 2
    ):
        passed += 1
        print("  ✅ a cycle with a downstream pendant is named in EVERY edge order")
    else:
        failed += 1
        print(
            "  ❌ cycle went unnamed:",
            pend_a.cycle_from, "->", pend_a.cycle_to,
            "|", pend_b.cycle_from, "->", pend_b.cycle_to,
            "|", sink.cycle_from, "->", sink.cycle_to,
        )

    if d_separated(cyc_f, cyc_t, 3, _ints(0), _ints(1), _empty_int()).status == CI_ERR_NOT_A_DAG:
        passed += 1
        print("  ✅ d-separation over a cyclic graph refuses rather than answering")
    else:
        failed += 1
        print("  ❌ d-separation answered over a cycle")

    # ── a real DAG: order verified against the edges, degrees, duplicates ─────
    var dagf = _ints(0, 1, 0, 0)
    var dagt = _ints(1, 2, 2, 1)
    var ok = dag_validate(dagf, dagt, 3)
    if (
        ok.status == CI_OK
        and ok.is_dag
        and ok.has_order
        and _order_respects_edges(ok.topo_order, dagf, dagt, 3)
        and ok.n_duplicate_edges == 1
        and ok.n_self_loops == 0
        and ok.n_edges == 4
        and _same_ints(ok.in_degree, _ints(0, 2, 2))
        and _same_ints(ok.out_degree, _ints(3, 1, 0))
        and ok.cycle_from == DAG_NO_NODE
    ):
        passed += 1
        print("  ✅ DAG: every edge goes forward in the order; duplicate counted, not an error")
    else:
        failed += 1
        print("  ❌ DAG report wrong:", ok.status, ok.n_duplicate_edges)

    # ── ancestors and descendants, inclusive of the root ─────────────────────
    if (
        _same_ints(dag_descendants(chain_f, chain_t, 3, 0), _ints(0, 1, 2))
        and _same_ints(dag_descendants(chain_f, chain_t, 3, 2), _ints(2))
        and _same_ints(dag_ancestors(chain_f, chain_t, 3, 2), _ints(0, 1, 2))
        and _same_ints(dag_ancestors(chain_f, chain_t, 3, 0), _ints(0))
        and len(dag_descendants(chain_f, chain_t, 3, 7)) == 0
    ):
        passed += 1
        print("  ✅ descendants / ancestors are inclusive and exact; a bad root is empty")
    else:
        failed += 1
        print("  ❌ reachability helpers wrong")

    # ── CONFOUNDING: T=0, Y=1, U=2 with 2->0, 2->1, 0->1 ────────────────────
    var cf_f = _ints(2, 2, 0)
    var cf_t = _ints(0, 1, 1)
    var unadjusted = backdoor_check(cf_f, cf_t, 3, 0, 1, _empty_int())
    if (
        unadjusted.status == CI_ERR_NOT_IDENTIFIED
        and unadjusted.has_verdict
        and not unadjusted.identified
        and not unadjusted.blocks_backdoor_paths
        and unadjusted.n_descendant_violations == 0
        and unadjusted.n_open_backdoor_paths_found == 1
        and _same_ints(unadjusted.unblocked_path, _ints(0, 2, 1))
    ):
        passed += 1
        print("  ✅ confounded, Z={}: REFUSED with the open path named as [0,2,1] (T<-U->Y)")
    else:
        failed += 1
        print(
            "  ❌ unadjusted case wrong:",
            unadjusted.status,
            unadjusted.identified,
            len(unadjusted.unblocked_path),
        )

    var adjusted = backdoor_check(cf_f, cf_t, 3, 0, 1, _ints(2))
    if (
        adjusted.status == CI_OK
        and adjusted.identified
        and adjusted.blocks_backdoor_paths
        and adjusted.n_adjustment == 1
        and len(adjusted.unblocked_path) == 0
    ):
        passed += 1
        print("  ✅ confounded, Z={U}: identified, no open path")
    else:
        failed += 1
        print("  ❌ adjusted case wrong:", adjusted.status, adjusted.identified)

    # ── the half an incomplete implementation omits: Z may not be downstream ──
    # Add M = 3 with T -> M. Adjusting for M does not open a backdoor path here, so the ONLY
    # thing that can refuse it is condition (i). A check that tested only d-separation would
    # certify this.
    var md_f = _ints(2, 2, 0, 0)
    var md_t = _ints(0, 1, 1, 3)
    var post_treatment = backdoor_check(md_f, md_t, 4, 0, 1, _ints(2, 3))
    if (
        post_treatment.status == CI_ERR_NOT_IDENTIFIED
        and not post_treatment.identified
        and post_treatment.blocks_backdoor_paths
        and post_treatment.n_descendant_violations == 1
        and post_treatment.first_descendant == 3
    ):
        passed += 1
        print("  ✅ a DESCENDANT of the treatment in Z refuses even though every path is blocked")
    else:
        failed += 1
        print(
            "  ❌ descendant condition not enforced:",
            post_treatment.status,
            post_treatment.n_descendant_violations,
        )

    # ── M-BIAS: adjusting for more is not safer ──────────────────────────────
    # T=0, Y=1, U1=2, U2=3, M=4.  2->0, 2->4, 3->4, 3->1.
    var m_f = _ints(2, 2, 3, 3)
    var m_t = _ints(0, 4, 4, 1)
    var m_empty = backdoor_check(m_f, m_t, 5, 0, 1, _empty_int())
    var m_adjust = backdoor_check(m_f, m_t, 5, 0, 1, _ints(4))
    if (
        m_empty.status == CI_OK
        and m_empty.identified
        and m_adjust.status == CI_ERR_NOT_IDENTIFIED
        and not m_adjust.identified
        and m_adjust.n_descendant_violations == 0
        and _same_ints(m_adjust.unblocked_path, _ints(0, 2, 4, 3, 1))
    ):
        passed += 1
        print("  ✅ M-bias: identified with Z={}, REFUSED with Z={M}, path [0,2,4,3,1]")
    else:
        failed += 1
        print(
            "  ❌ M-bias wrong:",
            m_empty.identified,
            m_adjust.identified,
            len(m_adjust.unblocked_path),
        )

    # ── treatment == outcome, and Z containing either, are refusals ──────────
    if (
        backdoor_check(cf_f, cf_t, 3, 0, 0, _empty_int()).status == CI_ERR_DUPLICATE
        and backdoor_check(cf_f, cf_t, 3, 0, 1, _ints(0)).status == CI_ERR_DUPLICATE
        and backdoor_check(cf_f, cf_t, 3, 0, 1, _ints(1)).status == CI_ERR_DUPLICATE
        and backdoor_check(cf_f, cf_t, 3, 0, 5, _empty_int()).status == CI_ERR_INDEX
    ):
        passed += 1
        print("  ✅ T==Y, and Z containing T or Y, are refused")
    else:
        failed += 1
        print("  ❌ degenerate backdoor queries were answered")

    # ── the minimal adjustment set, with minimality MEASURED ─────────────────
    # Candidates {U=2, I=3} where I is an isolated node: U is necessary, I is redundant.
    var iso_f = _ints(2, 2, 0)
    var iso_t = _ints(0, 1, 1)
    var minimal = backdoor_minimal_set(iso_f, iso_t, 4, 0, 1, _ints(2, 3))
    if (
        minimal.status == CI_OK
        and minimal.identified
        and minimal.has_set
        and _same_ints(minimal.chosen, _ints(2))
        and minimal.n_candidates == 2
        and minimal.n_dropped_non_ancestral == 1
        and minimal.n_dropped_descendant == 0
        and minimal.minimality_measured
        and minimal.n_checks == 2
    ):
        passed += 1
        print("  ✅ minimal set = {U}: the isolated candidate is dropped as non-ancestral")
    else:
        failed += 1
        print(
            "  ❌ minimal set wrong:",
            minimal.status,
            len(minimal.chosen),
            minimal.n_checks,
            minimal.n_dropped_redundant,
        )

    # Descendants of T are filtered out BEFORE the sufficiency test, and are counted separately.
    var with_desc = backdoor_minimal_set(md_f, md_t, 4, 0, 1, _ints(2, 3))
    if (
        with_desc.status == CI_OK
        and with_desc.identified
        and _same_ints(with_desc.chosen, _ints(2))
        and with_desc.n_dropped_descendant == 1
    ):
        passed += 1
        print("  ✅ a descendant candidate is dropped and counted, not left in the set")
    else:
        failed += 1
        print("  ❌ descendant filtering wrong:", len(with_desc.chosen))

    # A pool that cannot block is a refusal with the open path, and NO set.
    var hopeless = backdoor_minimal_set(cf_f, cf_t, 3, 0, 1, _empty_int())
    if (
        hopeless.status == CI_ERR_NOT_IDENTIFIED
        and not hopeless.identified
        and not hopeless.has_set
        and len(hopeless.chosen) == 0
        and not hopeless.minimality_measured
    ):
        passed += 1
        print("  ✅ a candidate pool that cannot block yields NO set, not a partial one")
    else:
        failed += 1
        print("  ❌ hopeless pool wrong:", hopeless.status, len(hopeless.chosen))

    # M-bias again, through the minimiser: the right answer is the EMPTY set, and the minimiser
    # must be willing to return it.
    var m_min = backdoor_minimal_set(m_f, m_t, 5, 0, 1, _ints(4))
    if (
        m_min.status == CI_OK
        and m_min.identified
        and m_min.has_set
        and len(m_min.chosen) == 0
        and m_min.n_dropped_non_ancestral == 1
        and m_min.n_dropped_descendant == 0
    ):
        passed += 1
        print("  ✅ M-bias: the collider is dropped as non-ancestral; the EMPTY set is returned")
    else:
        failed += 1
        print("  ❌ M-bias minimiser wrong:", m_min.status, len(m_min.chosen))

    # ── structural refusals ──────────────────────────────────────────────────
    if (
        dag_validate(_ints(0, 1), _ints(1), 2).status == CI_ERR_LENGTH_MISMATCH
        and dag_validate(_ints(0), _ints(5), 2).status == CI_ERR_INDEX
        and dag_validate(_ints(0), _ints(-1), 2).status == CI_ERR_INDEX
        and dag_validate(_empty_int(), _empty_int(), -1).status == CI_ERR_SHAPE
        and dag_validate(_empty_int(), _empty_int(), 0).status == CI_OK
    ):
        passed += 1
        print("  ✅ mismatched, out-of-range and negative shapes refused; empty graph is a DAG")
    else:
        failed += 1
        print("  ❌ structural refusals wrong")

    # ── the A-Z harness pattern: 5-element lists and 5 for every Int ─────────
    if (
        dag_validate(_li5(), _li5(), 5).status == CI_ERR_INDEX
        and d_separated(_li5(), _li5(), 5, _li5(), _li5(), _li5()).status == CI_ERR_INDEX
        and backdoor_check(_li5(), _li5(), 5, 5, 5, _li5()).status == CI_ERR_INDEX
        and backdoor_minimal_set(_li5(), _li5(), 5, 5, 5, _li5()).status == CI_ERR_INDEX
        and len(dag_descendants(_li5(), _li5(), 5, 5)) == 0
        and len(dag_ancestors(_li5(), _li5(), 5, 5)) == 0
    ):
        passed += 1
        print("  ✅ the fixed harness arguments are refused before any endpoint is indexed")
    else:
        failed += 1
        print("  ❌ the A-Z argument pattern reached an index")

    print("  [causal_inference.dag] Passed:", passed, "Failed:", failed)
