"""Author the seed instance set for the optmodel plane harness.

Writes ``instances/*.json`` — one ground-truth FORMULATION per file, in the shape the
MM-OptBench reference side keeps hidden (`instance_data.json` + verified optimum), so
the harness can measure the solver-side ceiling: given the formulation, does the
Algenta plane solve AND verify it, refuse it with a type, or (the bug bucket) return a
plausible wrong number?

Six families mirror the benchmark's taxonomy; every solvable instance carries a
hand-derived optimum where one fits on paper (``ground_truth.source: "hand"``) and is
ALWAYS re-proved by the harness's independent referee (SciPy/HiGHS) before it is
admitted — a hand slip fails the run rather than poisoning the measurement. Instances
whose optimum is not hand-friendly are stamped by ``harness.py --fill-gt``
(``source: "referee:scipy-highs"``) and re-proved on every subsequent run all the same.

Refusal instances are the honest half of the ceiling: two are refused because the
MODEL has no answer (infeasible, unbounded — the referee agrees), two because the
PLANE declines (a free variable, a starved node budget — the referee can solve these,
and the harness counts them as coverage gaps rather than hiding them).

Deterministic: no randomness, no network, no LLM. Re-running overwrites the same files
byte-for-byte (dict order is authoring order, floats are plain literals).
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "instances"


def var(name: str, kind: str = "continuous", lower: float | None = 0.0,
        upper: float | None = None) -> dict:
    v: dict = {"name": name, "kind": kind, "lower": lower}
    if upper is not None:
        v["upper"] = upper
    return v


def con(name: str, coeffs: dict, sense: str, rhs: float) -> dict:
    return {"name": name, "coeffs": coeffs, "sense": sense, "rhs": rhs}


def instance(id: str, family: str, description: str, maximize: bool,
             objective: dict, variables: list, constraints: list,
             expect: str = "verified", gt: float | None = None,
             gt_source: str = "hand", max_nodes: int = 10000,
             coverage_gap: str | None = None,
             referee_expectation: str = "optimal") -> dict:
    out = {
        "id": id,
        "family": family,
        "description": description,
        "maximize": maximize,
        "objective": objective,
        "variables": variables,
        "constraints": constraints,
        "expect": expect,
        "max_nodes": max_nodes,
        "referee_expectation": referee_expectation,
    }
    if gt is not None:
        out["ground_truth"] = {"objective": gt, "source": gt_source}
    if coverage_gap is not None:
        out["coverage_gap"] = coverage_gap
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    instances: list[dict] = []

    # ── family: network ────────────────────────────────────────────────────────
    # Transportation LP, 2 plants x 3 markets. Costs row-major [[2,3,1],[5,4,8]],
    # supplies <= [20, 30], demands >= [10, 25, 15].
    tvars = [var(f"x{i}{j}") for i in range(1, 3) for j in range(1, 4)]
    instances.append(instance(
        "net_transport_2x3", "network",
        "Ship from 2 plants to 3 markets at minimum freight cost.",
        False,
        {"coeffs": {"x11": 2, "x12": 3, "x13": 1, "x21": 5, "x22": 4, "x23": 8},
         "constant": 0.0},
        tvars,
        [
            con("supply_1", {"x11": 1, "x12": 1, "x13": 1}, "<=", 20),
            con("supply_2", {"x21": 1, "x22": 1, "x23": 1}, "<=", 30),
            con("demand_1", {"x11": 1, "x21": 1}, ">=", 10),
            con("demand_2", {"x12": 1, "x22": 1}, ">=", 25),
            con("demand_3", {"x13": 1, "x23": 1}, ">=", 15),
        ],
        gt=None, gt_source="referee:scipy-highs",
    ))

    # Max-flow s->t over 5 directed edges; conservation at a and b; cut value 5 by hand
    # (sa=3 splits at=2, ab=1; b receives 2+1 and sends bt=3; 2+3=5).
    instances.append(instance(
        "net_maxflow_4node", "network",
        "Maximum s-t flow on a 4-node network with edge capacities.",
        True,
        {"coeffs": {"at": 1, "bt": 1}, "constant": 0.0},
        [var("sa", upper=3), var("sb", upper=2), var("ab", upper=1),
         var("at", upper=2), var("bt", upper=3)],
        [
            con("conserve_a", {"sa": 1, "ab": -1, "at": -1}, "==", 0),
            con("conserve_b", {"sb": 1, "ab": 1, "bt": -1}, "==", 0),
        ],
        gt=5.0,
    ))

    # Shortest path 1->4 as a min-cost unit flow. Paths: 1-2-4 = 4, 1-3-4 = 3,
    # 1-2-3-4 = 3. Optimum 3 (two optimal paths; the VALUE is unique).
    instances.append(instance(
        "net_shortestpath_4node", "network",
        "Shortest 1->4 path as a unit min-cost flow.",
        False,
        {"coeffs": {"e12": 1, "e24": 3, "e13": 2, "e34": 1, "e23": 1},
         "constant": 0.0},
        [var("e12", upper=1), var("e24", upper=1), var("e13", upper=1),
         var("e34", upper=1), var("e23", upper=1)],
        [
            con("out_of_source", {"e12": 1, "e13": 1}, "==", 1),
            con("into_sink", {"e24": 1, "e34": 1}, "==", 1),
            con("conserve_2", {"e12": 1, "e24": -1, "e23": -1}, "==", 0),
            con("conserve_3", {"e13": 1, "e23": 1, "e34": -1}, "==", 0),
        ],
        gt=3.0,
    ))

    # ── family: location_cover_assign ──────────────────────────────────────────
    # Uncapacitated facility location, 2 sites x 3 customers. Open-both 12, site 1
    # alone 11, site 2 alone 4+3+1+1 = 9. Optimum 9.
    fvars = ([var(f"y{i}", "binary", 0, 1) for i in range(1, 3)]
             + [var(f"a{i}{j}", "binary", 0, 1)
                for i in range(1, 3) for j in range(1, 4)])
    fcons = [con(f"serve_{j}", {f"a1{j}": 1, f"a2{j}": 1}, "==", 1)
             for j in range(1, 4)]
    fcons += [con(f"open_{i}{j}", {f"a{i}{j}": 1, f"y{i}": -1}, "<=", 0)
              for i in range(1, 3) for j in range(1, 4)]
    instances.append(instance(
        "loc_facility_2x3", "location_cover_assign",
        "Open facilities (fixed costs 5 and 4) and assign 3 customers.",
        False,
        {"coeffs": {"y1": 5, "y2": 4, "a11": 1, "a12": 2, "a13": 3,
                    "a21": 3, "a22": 1, "a23": 1}, "constant": 0.0},
        fvars, fcons, gt=9.0,
    ))

    # Set cover over 5 elements: A{1,2,3}/3, B{2,4}/2, C{3,5}/2, D{4,5}/3, E{1}/1.
    # E+B+C = 5 covers everything; A+D = 6; A+B+C = 7. Optimum 5.
    instances.append(instance(
        "loc_setcover_5x5", "location_cover_assign",
        "Cover 5 elements with weighted sets.",
        False,
        {"coeffs": {"A": 3, "B": 2, "C": 2, "D": 3, "E": 1}, "constant": 0.0},
        [var(s, "binary", 0, 1) for s in "ABCDE"],
        [
            con("cover_1", {"A": 1, "E": 1}, ">=", 1),
            con("cover_2", {"A": 1, "B": 1}, ">=", 1),
            con("cover_3", {"A": 1, "C": 1}, ">=", 1),
            con("cover_4", {"B": 1, "D": 1}, ">=", 1),
            con("cover_5", {"C": 1, "D": 1}, ">=", 1),
        ],
        gt=5.0,
    ))

    # 3x3 assignment, costs [[4,2,8],[4,3,7],[3,1,6]]. All six permutations by hand:
    # 4+3+6=13, 4+7+1=12, 2+4+6=12, 2+7+3=12, 8+4+1=13, 8+3+3=14. Optimum 12.
    avars = [var(f"m{i}{j}", "binary", 0, 1)
             for i in range(1, 4) for j in range(1, 4)]
    acons = [con(f"agent_{i}", {f"m{i}{j}": 1 for j in range(1, 4)}, "==", 1)
             for i in range(1, 4)]
    acons += [con(f"task_{j}", {f"m{i}{j}": 1 for i in range(1, 4)}, "==", 1)
              for j in range(1, 4)]
    instances.append(instance(
        "loc_assignment_3x3", "location_cover_assign",
        "Assign 3 agents to 3 tasks at minimum cost.",
        False,
        {"coeffs": {"m11": 4, "m12": 2, "m13": 8, "m21": 4, "m22": 3, "m23": 7,
                    "m31": 3, "m32": 1, "m33": 6}, "constant": 0.0},
        avars, acons, gt=12.0,
    ))

    # ── family: scheduling ─────────────────────────────────────────────────────
    # 4 jobs (3,3,2,2) on 2 identical machines, min makespan. Total work 10, so 5 is
    # a lower bound and {3,2}/{3,2} achieves it. Optimum 5.
    pvars = ([var(f"x{j}{m}", "binary", 0, 1)
              for j in range(1, 5) for m in range(1, 3)] + [var("cmax")])
    p = {1: 3, 2: 3, 3: 2, 4: 2}
    pcons = [con(f"assign_{j}", {f"x{j}1": 1, f"x{j}2": 1}, "==", 1)
             for j in range(1, 5)]
    for m in range(1, 3):
        coeffs = {f"x{j}{m}": float(p[j]) for j in range(1, 5)}
        coeffs["cmax"] = -1.0
        pcons.append(con(f"load_{m}", coeffs, "<=", 0))
    instances.append(instance(
        "sched_parallel_2m", "scheduling",
        "Schedule 4 jobs on 2 parallel machines to minimise makespan.",
        False,
        {"coeffs": {"cmax": 1}, "constant": 0.0},
        pvars, pcons, gt=5.0,
    ))

    # Job shop 2x2, disjunctive big-M (M = 20). J1: M1(3) -> M2(2); J2: M2(1) -> M1(4).
    # Optimal makespan 7 (J1 first on M1; J2's M2 op fits before J1 arrives there).
    instances.append(instance(
        "sched_jobshop_2x2", "scheduling",
        "Two-job two-machine job shop with disjunctive big-M sequencing.",
        False,
        {"coeffs": {"cmax": 1}, "constant": 0.0},
        [var("s11"), var("s12"), var("s22"), var("s21"), var("cmax"),
         var("z_m1", "binary", 0, 1), var("z_m2", "binary", 0, 1)],
        [
            con("j1_route", {"s12": 1, "s11": -1}, ">=", 3),
            con("j2_route", {"s21": 1, "s22": -1}, ">=", 1),
            # M1 disjunction, z_m1 = 1 means J1 first: s21 >= s11 + 3 - 20(1 - z)
            # and s11 >= s21 + 4 - 20 z, in >= row form.
            con("m1_j1_first", {"s21": 1, "s11": -1, "z_m1": -20}, ">=", 3 - 20),
            con("m1_j2_first", {"s11": 1, "s21": -1, "z_m1": 20}, ">=", 4),
            # M2 disjunction, z_m2 = 1 means J1 first, durations 2 and 1.
            con("m2_j1_first", {"s22": 1, "s12": -1, "z_m2": -20}, ">=", 2 - 20),
            con("m2_j2_first", {"s12": 1, "s22": -1, "z_m2": 20}, ">=", 1),
            con("cmax_j1", {"cmax": 1, "s12": -1}, ">=", 2),
            con("cmax_j2", {"cmax": 1, "s21": -1}, ">=", 4),
        ],
        gt=7.0,
    ))

    # ── family: planning ───────────────────────────────────────────────────────
    # The two-variable production LP: max 3x + 2y, x + y <= 4, x + 3y <= 6 -> 12 at (4,0).
    instances.append(instance(
        "plan_production_2var", "planning",
        "Two products, two shared resources, maximise profit.",
        True,
        {"coeffs": {"x": 3, "y": 2}, "constant": 0.0},
        [var("x"), var("y")],
        [
            con("resource_a", {"x": 1, "y": 1}, "<=", 4),
            con("resource_b", {"x": 1, "y": 3}, "<=", 6),
        ],
        gt=12.0,
    ))

    # Capacitated lot sizing, 3 periods: demand (4,5,3), capacity 8, setup 6,
    # unit cost 1, holding 0.5. Referee stamps the optimum.
    lvars = ([var(f"q{t}", upper=8.0) for t in range(1, 4)]
             + [var(f"inv{t}") for t in range(1, 4)]
             + [var(f"u{t}", "binary", 0, 1) for t in range(1, 4)])
    d = {1: 4.0, 2: 5.0, 3: 3.0}
    lcons = []
    for t in range(1, 4):
        balance = {f"q{t}": 1.0, f"inv{t}": -1.0}
        if t > 1:
            balance[f"inv{t-1}"] = 1.0
        lcons.append(con(f"balance_{t}", balance, "==", d[t]))
        lcons.append(con(f"setup_{t}", {f"q{t}": 1.0, f"u{t}": -8.0}, "<=", 0))
    lcons.append(con("end_empty", {"inv3": 1.0}, "==", 0))
    instances.append(instance(
        "plan_lotsizing_3p", "planning",
        "Three-period capacitated lot sizing with setup and holding costs.",
        False,
        {"coeffs": {"q1": 1, "q2": 1, "q3": 1, "inv1": 0.5, "inv2": 0.5,
                    "inv3": 0.5, "u1": 6, "u2": 6, "u3": 6}, "constant": 0.0},
        lvars, lcons, gt=None, gt_source="referee:scipy-highs",
    ))

    # Toy unit commitment, 2 units 2 periods: output box [2, 5] when on (big-M rows),
    # demand (3, 6), unit 1 at 1/MW, unit 2 at 2/MW plus a fixed on-cost of 1.
    uvars = ([var(f"p{u}{t}") for u in range(1, 3) for t in range(1, 3)]
             + [var(f"on{u}{t}", "binary", 0, 1)
                for u in range(1, 3) for t in range(1, 3)])
    ucons = []
    for t in range(1, 3):
        ucons.append(con(f"demand_{t}", {f"p1{t}": 1.0, f"p2{t}": 1.0}, ">=",
                         {1: 3.0, 2: 6.0}[t]))
    for u in range(1, 3):
        for t in range(1, 3):
            ucons.append(con(f"cap_{u}{t}", {f"p{u}{t}": 1.0, f"on{u}{t}": -5.0},
                             "<=", 0))
            ucons.append(con(f"min_{u}{t}", {f"p{u}{t}": 1.0, f"on{u}{t}": -2.0},
                             ">=", 0))
    instances.append(instance(
        "plan_unitcommit_2u2t", "planning",
        "Two generating units, two periods, minimum-output big-M commitment.",
        False,
        {"coeffs": {"p11": 1, "p12": 1, "p21": 2, "p22": 2,
                    "on21": 1, "on22": 1}, "constant": 0.0},
        uvars, ucons, gt=None, gt_source="referee:scipy-highs",
    ))

    # ── family: routing ────────────────────────────────────────────────────────
    # 4-city TSP, the classic symmetric matrix; optimal tour 0-1-3-2-0 = 10+25+30+15
    # = 80. MTZ subtour elimination with u_i integer in [1, 3].
    dist4 = [[0, 10, 15, 20], [10, 0, 35, 25], [15, 35, 0, 30], [20, 25, 30, 0]]
    instances.append(_tsp_mtz("route_tsp4_mtz", dist4, gt=80.0))

    # 5-city TSP; the referee stamps the optimum. The node budget is raised because
    # most-fractional branch and bound over 20 edge binaries can legitimately need
    # more than the 10k default — a starved budget would be a REFUSAL, and this
    # instance exists to measure the solve, not the budget.
    dist5 = [[0, 3, 4, 2, 7], [3, 0, 4, 6, 3], [4, 4, 0, 5, 8],
             [2, 6, 5, 0, 6], [7, 3, 8, 6, 0]]
    instances.append(_tsp_mtz("route_tsp5_mtz", dist5, gt=None, max_nodes=200000))

    # ── family: combinatorial ──────────────────────────────────────────────────
    # Multi-dimensional knapsack: 4 items, two budgets. Referee stamps.
    instances.append(instance(
        "comb_knapsack_2d", "combinatorial",
        "Choose items under two independent budgets.",
        True,
        {"coeffs": {"i1": 10, "i2": 13, "i3": 7, "i4": 11}, "constant": 0.0},
        [var(f"i{k}", "binary", 0, 1) for k in range(1, 5)],
        [
            con("budget_a", {"i1": 6, "i2": 8, "i3": 5, "i4": 4}, "<=", 10),
            con("budget_b", {"i1": 3, "i2": 1, "i3": 4, "i4": 2}, "<=", 5),
        ],
        gt=None, gt_source="referee:scipy-highs",
    ))

    # Graph colouring of the 5-cycle: chromatic number 3 (an odd cycle is not
    # 2-colourable). Colour-use variables y_c; assignment x_vc; adjacency conflicts.
    cvars = ([var(f"y{c}", "binary", 0, 1) for c in range(1, 4)]
             + [var(f"x{v}{c}", "binary", 0, 1)
                for v in range(1, 6) for c in range(1, 4)])
    ccons = [con(f"colour_{v}", {f"x{v}{c}": 1 for c in range(1, 4)}, "==", 1)
             for v in range(1, 6)]
    edges = [(1, 2), (2, 3), (3, 4), (4, 5), (5, 1)]
    for (u, w) in edges:
        for c in range(1, 4):
            ccons.append(con(f"edge_{u}{w}_c{c}",
                             {f"x{u}{c}": 1, f"x{w}{c}": 1, f"y{c}": -1}, "<=", 0))
    instances.append(instance(
        "comb_coloring_c5", "combinatorial",
        "Colour the 5-cycle with the fewest colours (chromatic number 3).",
        False,
        {"coeffs": {"y1": 1, "y2": 1, "y3": 1}, "constant": 0.0},
        cvars, ccons, gt=3.0,
    ))

    # Logical selection: max 3a + 2b + 4c with a -> b and (b, c) mutually exclusive.
    # {a, b} = 5, {c} = 4, {b} alone = 2. Optimum 5.
    instances.append(instance(
        "comb_logical_implication", "combinatorial",
        "Weighted selection under an implication and a mutual exclusion.",
        True,
        {"coeffs": {"a": 3, "b": 2, "c": 4}, "constant": 0.0},
        [var(s, "binary", 0, 1) for s in "abc"],
        [
            con("a_implies_b", {"a": 1, "b": -1}, "<=", 0),
            con("b_xor_c", {"b": 1, "c": 1}, "<=", 1),
        ],
        gt=5.0,
    ))

    # ── refusals: the honest half of the ceiling ───────────────────────────────
    # A model with NO answer: two contradictory rows. The referee agrees (infeasible),
    # and the plane must name both rows in its core.
    instances.append(instance(
        "refuse_infeasible_rows", "refusals",
        "x <= 2 against x >= 5: proven infeasible, core names both rows.",
        True,
        {"coeffs": {"x": 1}, "constant": 0.0},
        [var("x")],
        [con("ceiling", {"x": 1}, "<=", 2), con("floor", {"x": 1}, ">=", 5)],
        expect="refused", referee_expectation="infeasible",
    ))

    # A model with no finite optimum. The referee agrees (unbounded).
    instances.append(instance(
        "refuse_unbounded", "refusals",
        "Maximise x with no ceiling anywhere: unbounded, refused.",
        True,
        {"coeffs": {"x": 1, "y": 1}, "constant": 0.0},
        [var("x"), var("y")],
        [con("gap", {"x": 1, "y": -1}, "<=", 1)],
        expect="refused", referee_expectation="unbounded",
    ))

    # A PLANE limitation, counted, not hidden: the referee solves this (optimum 2),
    # the x >= 0 plane refuses the free variable by type.
    instances.append(instance(
        "refuse_free_variable", "refusals",
        "min x + y with x free: solvable in general, refused by the x >= 0 plane.",
        False,
        {"coeffs": {"x": 1, "y": 1}, "constant": 0.0},
        [var("x", lower=None), var("y")],
        [con("floor", {"x": 1, "y": 1}, ">=", 2)],
        expect="refused", coverage_gap="free_variable",
        referee_expectation="optimal",
    ))

    # A BUDGET refusal, counted, not hidden: the Wolsey MILP under max_nodes = 3 stops
    # with incumbent 39 and bound 370/9 — the plane must refuse, not report 39.
    instances.append(instance(
        "refuse_node_budget", "refusals",
        "Wolsey MILP at max_nodes 3: truncated search refuses, incumbent stays a diagnostic.",
        True,
        {"coeffs": {"x": 5, "y": 8}, "constant": 0.0},
        [var("x", "integer"), var("y", "integer")],
        [con("row_a", {"x": 1, "y": 1}, "<=", 6),
         con("row_b", {"x": 5, "y": 9}, "<=", 45)],
        expect="refused", max_nodes=3, coverage_gap="node_budget",
        referee_expectation="optimal",
    ))

    for inst in instances:
        path = OUT / f"{inst['id']}.json"
        path.write_text(json.dumps(inst, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(instances)} instances to {OUT}")


def _tsp_mtz(id: str, dist: list, gt: float | None, max_nodes: int = 10000) -> dict:
    """Asymmetric-form MTZ TSP over a symmetric distance matrix."""
    n = len(dist)
    variables = [var(f"e{i}_{j}", "binary", 0, 1)
                 for i in range(n) for j in range(n) if i != j]
    variables += [var(f"u{i}", "integer", 1, n - 1) for i in range(1, n)]
    cons = []
    for i in range(n):
        cons.append(con(f"leave_{i}",
                        {f"e{i}_{j}": 1 for j in range(n) if j != i}, "==", 1))
        cons.append(con(f"enter_{i}",
                        {f"e{j}_{i}": 1 for j in range(n) if j != i}, "==", 1))
    for i in range(1, n):
        for j in range(1, n):
            if i == j:
                continue
            cons.append(con(f"mtz_{i}_{j}",
                            {f"u{i}": 1, f"u{j}": -1, f"e{i}_{j}": n}, "<=", n - 1))
    coeffs = {f"e{i}_{j}": float(dist[i][j])
              for i in range(n) for j in range(n) if i != j}
    return instance(
        id, "routing", f"{n}-city TSP with MTZ subtour elimination.",
        False, {"coeffs": coeffs, "constant": 0.0}, variables, cons,
        gt=gt, gt_source="hand" if gt is not None else "referee:scipy-highs",
        max_nodes=max_nodes,
    )


if __name__ == "__main__":
    main()
