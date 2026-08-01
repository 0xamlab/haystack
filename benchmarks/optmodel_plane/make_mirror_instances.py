"""Generate the MM-OptBench mirror: 780 ground-truth formulations, referee-proven.

MM-OptBench itself (arXiv:2605.12154) is withheld — "the dataset and benchmark code
are not publicly released at this stage and will be released upon acceptance". What
IS public is the paper's complete design: 6 families x 26 subcategories x 3
structural difficulty tiers x 10 instances = 780 solver-verified formulations, the
full subcategory taxonomy (Appendix Table 3), representative construction pipelines
per family (Appendix E), disclosed scale anchors (min-cost flow 6 nodes/7 arcs up to
20 nodes/52 arcs; facility location 4 facilities/5 customers up to 8/17 capacitated;
job-shop from 3 jobs/3 machines; a medium colouring instance with 15 vertices/51
edges and chromatic number 5), and the scoring rule (objective must match the
verified optimum; default tolerance 1e-6, absolute floor 1e-3 for the
continuous-objective location families).

This module mirrors that design deterministically: every subcategory gets a
generator that follows the family's published construction pipeline — structural
configuration first, parameters second, then REJECTION-REGENERATION until an
independent referee (SciPy/HiGHS, via `harness.referee`) certifies optimality and
the family-specific regime checks pass (e.g. a colouring instance is regenerated
until its verified chromatic number matches the target, exactly as the paper
describes). The verified optimum is stamped as the ground truth, and the harness
re-proves it on every run.

Honest deviations from the withheld original, all forced by the referee:
  - hard-tier scheduling/routing scales are trimmed to what HiGHS proves optimal in
    seconds (e.g. job-shop hard is 6 jobs x 4 machines, not 10 x 6-8; TSP hard is
    9 cities); difficulty here is structural, as in the paper, but the exact hidden
    scales are unknowable until release;
  - the inventory-routing subcategory uses an enumerated-route formulation (route
    subsets are instance data), the standard exact form at these scales;
  - visual carriers do not exist here at all: this is the SOLVER-SIDE mirror — the
    machine-readable `instance_data` half the benchmark keeps hidden.

Deterministic: every random draw is keyed by (subcategory, tier, index, attempt)
through `random.Random(str)`, which seeds by hashing the string with SHA-512 —
stable across processes and machines. Re-running writes the same file byte for byte.

Output: `build/optmodel_plane/mirror_instances.json` (a list; NOT committed — the
generator is the source of truth) plus a per-subcategory summary on stdout.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import BUILD, referee  # noqa: E402
from make_seed_instances import con, instance, var  # noqa: E402

OUT = BUILD / "mirror_instances.json"
TIERS = ("easy", "medium", "hard")
PER_TIER = 10
MAX_ATTEMPTS = 60

# Node budgets for the plane's exact branch-and-bound. Two forces, both stated:
# per tier, deeper search is allowed (routing/scheduling families get the DEEP
# ceilings because tour and disjunctive models dominate search depth), but the
# budget is also CELL-SCALED so one instance cannot burn unbounded wall time — the
# per-node cost of the dense-simplex B&B scales with rows x columns TIMES the LP
# iteration count, and degenerate big-M scheduling LPs run near the iteration cap
# (measured on this host: the 6x4 big-M job shop at ~12k cells runs ~20ms per
# node). NODE_COST_BUDGET caps every instance near ~75s of solo search at that
# measured 1.9us/cell-node. Raising any budget can only move instances from
# REFUSED to VERIFIED (never into WRONG — the audit is solver-independent), so
# the measured ceiling is a lower bound with respect to these numbers.
NODE_BUDGET = {"easy": 60_000, "medium": 120_000, "hard": 200_000}
NODE_BUDGET_DEEP = {"easy": 100_000, "medium": 250_000, "hard": 400_000}
DEEP_SUBCATS = {"tsp", "cvrp", "tsptw", "hf_vrp", "job_shop", "hybrid_flow_shop"}
NODE_COST_BUDGET = 4.0e7  # node-cells per instance ~= 75s at 1.9us/cell-node
NODE_BUDGET_FLOOR = 5_000


def _rng(sub: str, tier: str, k: int, attempt: int) -> random.Random:
    return random.Random(f"optmodel-mirror:{sub}:{tier}:{k}:{attempt}")


def _coords(rng: random.Random, n: int, span: int = 60) -> list[tuple[float, float]]:
    return [(rng.uniform(0, span), rng.uniform(0, span)) for _ in range(n)]


def _dist_int(a: tuple[float, float], b: tuple[float, float]) -> float:
    return float(max(1, round(math.hypot(a[0] - b[0], a[1] - b[1]))))


def _dist4(a: tuple[float, float], b: tuple[float, float]) -> float:
    return round(math.hypot(a[0] - b[0], a[1] - b[1]), 4)


def _mirror(sub: str, tier: str, k: int, family: str, description: str,
            maximize: bool, objective: dict, variables: list, constraints: list,
            paper_floor: float = 0.0) -> dict:
    tier_max = (NODE_BUDGET_DEEP if sub in DEEP_SUBCATS else NODE_BUDGET)[tier]
    cells = max(1, len(constraints) * len(variables))
    budget = max(NODE_BUDGET_FLOOR, min(tier_max, int(NODE_COST_BUDGET // cells)))
    out = instance(
        f"m_{sub}_{tier[0]}_{k:02d}", family, description, maximize, objective,
        variables, constraints, expect="measure", max_nodes=budget,
    )
    out["subcategory"] = sub
    out["difficulty"] = tier
    if paper_floor:
        out["paper_floor"] = paper_floor
    return out


# ── family: network ────────────────────────────────────────────────────────────

def _layered_arcs(rng: random.Random, layers: list[int], extra: int) -> tuple[list, int]:
    """Directed layered backbone + `extra` bypass arcs. Returns (arcs, n_nodes)."""
    offsets, total = [], 0
    for width in layers:
        offsets.append(total)
        total += width
    arcs: set[tuple[int, int]] = set()
    for li in range(len(layers) - 1):
        for a in range(layers[li]):
            u = offsets[li] + a
            v = offsets[li + 1] + rng.randrange(layers[li + 1])
            arcs.add((u, v))
        for b in range(layers[li + 1]):
            v = offsets[li + 1] + b
            u = offsets[li] + rng.randrange(layers[li])
            arcs.add((u, v))
    guard = 0
    while extra > 0 and guard < 200:
        guard += 1
        li = rng.randrange(len(layers) - 1)
        lj = rng.randrange(li + 1, len(layers))
        u = offsets[li] + rng.randrange(layers[li])
        v = offsets[lj] + rng.randrange(layers[lj])
        if (u, v) not in arcs:
            arcs.add((u, v))
            extra -= 1
    return sorted(arcs), total


def gen_min_cost_flow(rng: random.Random, tier: str, k: int) -> dict:
    layers = {"easy": [2, 2, 2], "medium": [3, 3, 3, 3],
              "hard": [4, 4, 4, 4, 4]}[tier]
    extra = {"easy": 2, "medium": 8, "hard": 24}[tier]
    arcs, n = _layered_arcs(rng, layers, extra)
    n_src, n_sink = layers[0], layers[-1]
    supplies = [rng.randint(4, 12) for _ in range(n_src)]
    total = sum(supplies)
    demands = [total // n_sink] * n_sink
    demands[-1] += total - sum(demands)
    balance = [0] * n
    for i, s in enumerate(supplies):
        balance[i] = s
    for i, d in enumerate(demands):
        balance[n - n_sink + i] = -d
    variables = [var(f"x_{u}_{v}", upper=float(rng.randint(6, 25)))
                 for (u, v) in arcs]
    coeffs = {f"x_{u}_{v}": float(rng.randint(1, 20)) for (u, v) in arcs}
    constraints = []
    for node in range(n):
        row = {}
        for (u, v) in arcs:
            if u == node:
                row[f"x_{u}_{v}"] = row.get(f"x_{u}_{v}", 0.0) + 1.0
            if v == node:
                row[f"x_{u}_{v}"] = row.get(f"x_{u}_{v}", 0.0) - 1.0
        constraints.append(con(f"balance_{node}", row, "==", float(balance[node])))
    return _mirror("min_cost_flow", tier, k, "network",
                   f"Min-cost flow, {n} nodes / {len(arcs)} arcs.", False,
                   {"coeffs": coeffs, "constant": 0.0}, variables, constraints)


def gen_max_flow(rng: random.Random, tier: str, k: int) -> dict:
    layers = {"easy": [1, 3, 1], "medium": [1, 3, 4, 1],
              "hard": [1, 4, 4, 4, 1]}[tier]
    extra = {"easy": 2, "medium": 6, "hard": 12}[tier]
    arcs, n = _layered_arcs(rng, layers, extra)
    sink = n - 1
    variables = [var(f"x_{u}_{v}", upper=float(rng.randint(2, 15)))
                 for (u, v) in arcs]
    coeffs = {f"x_{u}_{v}": 1.0 for (u, v) in arcs if v == sink}
    constraints = []
    for node in range(1, n - 1):
        row = {}
        for (u, v) in arcs:
            if v == node:
                row[f"x_{u}_{v}"] = row.get(f"x_{u}_{v}", 0.0) + 1.0
            if u == node:
                row[f"x_{u}_{v}"] = row.get(f"x_{u}_{v}", 0.0) - 1.0
        constraints.append(con(f"conserve_{node}", row, "==", 0.0))
    return _mirror("max_flow", tier, k, "network",
                   f"Max s-t flow, {n} nodes / {len(arcs)} arcs.", True,
                   {"coeffs": coeffs, "constant": 0.0}, variables, constraints)


def gen_rc_shortest_path(rng: random.Random, tier: str, k: int) -> dict:
    layers = {"easy": [1, 2, 2, 1], "medium": [1, 3, 3, 2, 1],
              "hard": [1, 3, 4, 3, 3, 1]}[tier]
    extra = {"easy": 2, "medium": 5, "hard": 10}[tier]
    n_resources = {"easy": 1, "medium": 1, "hard": 2}[tier]
    arcs, n = _layered_arcs(rng, layers, extra)
    sink = n - 1
    variables = [var(f"e_{u}_{v}", "binary", 0, 1) for (u, v) in arcs]
    cost = {f"e_{u}_{v}": float(rng.randint(1, 20)) for (u, v) in arcs}
    res = [{f"e_{u}_{v}": float(rng.randint(1, 9)) for (u, v) in arcs}
           for _ in range(n_resources)]
    constraints = [
        con("out_of_source",
            {f"e_{u}_{v}": 1.0 for (u, v) in arcs if u == 0}, "==", 1.0),
        con("into_sink",
            {f"e_{u}_{v}": 1.0 for (u, v) in arcs if v == sink}, "==", 1.0),
    ]
    for node in range(1, n - 1):
        row = {}
        for (u, v) in arcs:
            if v == node:
                row[f"e_{u}_{v}"] = row.get(f"e_{u}_{v}", 0.0) + 1.0
            if u == node:
                row[f"e_{u}_{v}"] = row.get(f"e_{u}_{v}", 0.0) - 1.0
        constraints.append(con(f"conserve_{node}", row, "==", 0.0))
    hops = len(layers) - 1
    for r in range(n_resources):
        budget = float(max(3, round(0.62 * 5.0 * hops)))
        constraints.append(con(f"resource_{r}", res[r], "<=", budget))
    return _mirror("rc_shortest_path", tier, k, "network",
                   f"Resource-constrained shortest path, {n} nodes.", False,
                   {"coeffs": cost, "constant": 0.0}, variables, constraints)


def gen_cap_network_design(rng: random.Random, tier: str, k: int) -> dict:
    layers = {"easy": [1, 2, 2, 1], "medium": [1, 3, 3, 1],
              "hard": [2, 4, 4, 2]}[tier]
    extra = {"easy": 2, "medium": 6, "hard": 10}[tier]
    arcs, n = _layered_arcs(rng, layers, extra)
    n_src, n_sink = layers[0], layers[-1]
    supplies = [rng.randint(6, 12) for _ in range(n_src)]
    total = sum(supplies)
    demands = [total // n_sink] * n_sink
    demands[-1] += total - sum(demands)
    balance = [0] * n
    for i, s in enumerate(supplies):
        balance[i] = s
    for i, d in enumerate(demands):
        balance[n - n_sink + i] = -d
    variables, coeffs, constraints = [], {}, []
    for (u, v) in arcs:
        cap = float(rng.randint(5, 14))
        variables.append(var(f"x_{u}_{v}"))
        variables.append(var(f"y_{u}_{v}", "binary", 0, 1))
        coeffs[f"x_{u}_{v}"] = float(rng.randint(1, 9))
        coeffs[f"y_{u}_{v}"] = float(rng.randint(10, 60))
        constraints.append(con(f"install_{u}_{v}",
                               {f"x_{u}_{v}": 1.0, f"y_{u}_{v}": -cap}, "<=", 0.0))
    for node in range(n):
        row = {}
        for (u, v) in arcs:
            if u == node:
                row[f"x_{u}_{v}"] = row.get(f"x_{u}_{v}", 0.0) + 1.0
            if v == node:
                row[f"x_{u}_{v}"] = row.get(f"x_{u}_{v}", 0.0) - 1.0
        constraints.append(con(f"balance_{node}", row, "==", float(balance[node])))
    return _mirror("cap_network_design", tier, k, "network",
                   f"Capacitated network design, {n} nodes / {len(arcs)} arcs.",
                   False, {"coeffs": coeffs, "constant": 0.0},
                   variables, constraints)


def gen_time_expanded_flow(rng: random.Random, tier: str, k: int) -> dict:
    T = {"easy": 3, "medium": 4, "hard": 6}[tier]
    n_plants = {"easy": 1, "medium": 2, "hard": 2}[tier]
    n_markets = {"easy": 1, "medium": 2, "hard": 3}[tier]
    prod_cost = [rng.randint(2, 6) for _ in range(n_plants)]
    prod_cap = [rng.randint(6, 12) for _ in range(n_plants)]
    demand = [[rng.randint(2, 7) for _ in range(n_markets)] for _ in range(T)]
    ship = [[rng.randint(1, 5) for _ in range(n_markets)] for _ in range(n_plants)]
    hold = 1.0
    variables, coeffs, constraints = [], {}, []
    for t in range(T):
        for p in range(n_plants):
            variables.append(var(f"q_{p}_{t}", upper=float(prod_cap[p])))
            coeffs[f"q_{p}_{t}"] = float(prod_cost[p])
            for m in range(n_markets):
                variables.append(var(f"s_{p}_{m}_{t}"))
                coeffs[f"s_{p}_{m}_{t}"] = float(ship[p][m])
        for m in range(n_markets):
            variables.append(var(f"inv_{m}_{t}", upper=20.0))
            coeffs[f"inv_{m}_{t}"] = hold
    for t in range(T):
        for p in range(n_plants):
            row = {f"q_{p}_{t}": 1.0}
            for m in range(n_markets):
                row[f"s_{p}_{m}_{t}"] = -1.0
            constraints.append(con(f"plant_{p}_{t}", row, "==", 0.0))
        for m in range(n_markets):
            row = {f"inv_{m}_{t}": -1.0}
            for p in range(n_plants):
                row[f"s_{p}_{m}_{t}"] = 1.0
            if t > 0:
                row[f"inv_{m}_{t-1}"] = 1.0
            constraints.append(con(f"market_{m}_{t}", row, "==",
                                   float(demand[t][m])))
    return _mirror("time_expanded_flow", tier, k, "network",
                   f"Time-expanded flow, {T} periods.", False,
                   {"coeffs": coeffs, "constant": 0.0}, variables, constraints)


# ── family: location_cover_assign ──────────────────────────────────────────────

def gen_facility_location(rng: random.Random, tier: str, k: int) -> dict:
    n_fac = {"easy": 4, "medium": 6, "hard": 8}[tier]
    n_cust = {"easy": 5, "medium": 10, "hard": 17}[tier]
    capacitated = tier != "easy"
    fac = _coords(rng, n_fac, 100)
    cust = _coords(rng, n_cust, 100)
    radius = {"easy": 75.0, "medium": 65.0, "hard": 60.0}[tier]
    open_cost = [rng.randint(20, 80) for _ in range(n_fac)]
    demand = [rng.randint(2, 6) for _ in range(n_cust)]
    feas = [[i for i in range(n_fac) if _dist4(fac[i], cust[j]) <= radius]
            for j in range(n_cust)]
    if any(not f for f in feas):
        raise ValueError("uncovered customer")
    cap_margin = {"medium": 1.6, "hard": 1.35}.get(tier, 0.0)
    total_demand = sum(demand)
    caps = [max(6, round(cap_margin * total_demand / n_fac)) for _ in range(n_fac)]
    variables = [var(f"y{i}", "binary", 0, 1) for i in range(n_fac)]
    coeffs = {f"y{i}": float(open_cost[i]) for i in range(n_fac)}
    constraints = []
    for j in range(n_cust):
        row = {}
        for i in feas[j]:
            variables.append(var(f"a_{i}_{j}", upper=1.0))
            coeffs[f"a_{i}_{j}"] = _dist4(fac[i], cust[j])
            row[f"a_{i}_{j}"] = 1.0
            constraints.append(con(f"open_{i}_{j}",
                                   {f"a_{i}_{j}": 1.0, f"y{i}": -1.0}, "<=", 0.0))
        constraints.append(con(f"serve_{j}", row, "==", 1.0))
    if capacitated:
        for i in range(n_fac):
            row = {f"a_{i}_{j}": float(demand[j])
                   for j in range(n_cust) if i in feas[j]}
            if row:
                row[f"y{i}"] = -float(caps[i])
                constraints.append(con(f"cap_{i}", row, "<=", 0.0))
    kind = "capacitated" if capacitated else "uncapacitated"
    return _mirror("facility_location", tier, k, "location_cover_assign",
                   f"{kind} facility location, {n_fac} sites / {n_cust} customers.",
                   False, {"coeffs": coeffs, "constant": 0.0},
                   variables, constraints, paper_floor=1e-3)


def gen_p_median_center(rng: random.Random, tier: str, k: int) -> dict:
    n_sites = {"easy": 5, "medium": 8, "hard": 10}[tier]
    n_cust = {"easy": 8, "medium": 14, "hard": 20}[tier]
    p = {"easy": 2, "medium": 3, "hard": 4}[tier]
    is_center = k % 2 == 1
    sites = _coords(rng, n_sites, 100)
    cust = _coords(rng, n_cust, 100)
    w = [rng.randint(1, 5) for _ in range(n_cust)]
    variables = [var(f"y{i}", "binary", 0, 1) for i in range(n_sites)]
    x_kind = "binary" if is_center else "continuous"
    variables += [var(f"x_{i}_{j}", x_kind, 0, 1)
                  for i in range(n_sites) for j in range(n_cust)]
    constraints = [con("choose_p", {f"y{i}": 1.0 for i in range(n_sites)},
                       "==", float(p))]
    for j in range(n_cust):
        constraints.append(con(
            f"serve_{j}", {f"x_{i}_{j}": 1.0 for i in range(n_sites)}, "==", 1.0))
        for i in range(n_sites):
            constraints.append(con(f"open_{i}_{j}",
                                   {f"x_{i}_{j}": 1.0, f"y{i}": -1.0}, "<=", 0.0))
    if is_center:
        variables.append(var("dmax"))
        coeffs = {"dmax": 1.0}
        for j in range(n_cust):
            row = {f"x_{i}_{j}": _dist4(sites[i], cust[j])
                   for i in range(n_sites)}
            row["dmax"] = -1.0
            constraints.append(con(f"center_{j}", row, "<=", 0.0))
        name = "p-center"
    else:
        coeffs = {f"x_{i}_{j}": round(w[j] * _dist4(sites[i], cust[j]), 4)
                  for i in range(n_sites) for j in range(n_cust)}
        name = "p-median"
    return _mirror("p_median_center", tier, k, "location_cover_assign",
                   f"{name}, {n_sites} sites / {n_cust} customers, p={p}.",
                   False, {"coeffs": coeffs, "constant": 0.0},
                   variables, constraints, paper_floor=1e-3)


def gen_set_cover_partition(rng: random.Random, tier: str, k: int) -> dict:
    n_el = {"easy": 6, "medium": 14, "hard": 25}[tier]
    n_sets = {"easy": 6, "medium": 12, "hard": 18}[tier]
    is_partition = k % 2 == 1
    members: list[set[int]] = [set() for _ in range(n_sets)]
    if is_partition:
        # Seed with a random partition so exact partitioning is feasible; the
        # noise below never touches the seed sets, so that witness stays intact.
        seed_sets = set(rng.sample(range(n_sets), max(2, n_sets // 3)))
        for e in range(n_el):
            members[rng.choice(sorted(seed_sets))].add(e)
    else:
        seed_sets = set()
    for s in range(n_sets):
        if s in seed_sets:
            continue
        for e in range(n_el):
            if rng.random() < 0.3:
                members[s].add(e)
    if not is_partition:
        for e in range(n_el):
            if not any(e in m for m in members):
                members[rng.randrange(n_sets)].add(e)
    members = [m for m in members if m]
    n_sets = len(members)
    if n_sets < 3:
        raise ValueError("degenerate set system")
    weights = [max(1, len(members[s]) * 2 + rng.randint(-2, 6))
               for s in range(n_sets)]
    sense = "==" if is_partition else ">="
    variables = [var(f"z{s}", "binary", 0, 1) for s in range(n_sets)]
    coeffs = {f"z{s}": float(weights[s]) for s in range(n_sets)}
    constraints = [
        con(f"element_{e}",
            {f"z{s}": 1.0 for s in range(n_sets) if e in members[s]}, sense, 1.0)
        for e in range(n_el)
    ]
    name = "set partitioning" if is_partition else "set covering"
    return _mirror("set_cover_partition", tier, k, "location_cover_assign",
                   f"{name}, {n_el} elements / {n_sets} sets.", False,
                   {"coeffs": coeffs, "constant": 0.0}, variables, constraints)


def gen_assignment_matching(rng: random.Random, tier: str, k: int) -> dict:
    n = {"easy": 3, "medium": 6, "hard": 9}[tier]
    perm = list(range(n))
    rng.shuffle(perm)  # kept feasible: this matching is never forbidden
    allowed = {(i, perm[i]) for i in range(n)}
    for i in range(n):
        for j in range(n):
            if (i, j) not in allowed and rng.random() > 0.25:
                allowed.add((i, j))
    variables = [var(f"m_{i}_{j}", "binary", 0, 1) for (i, j) in sorted(allowed)]
    coeffs = {f"m_{i}_{j}": float(rng.randint(1, 30)) for (i, j) in sorted(allowed)}
    constraints = []
    for i in range(n):
        constraints.append(con(
            f"agent_{i}", {f"m_{i}_{j}": 1.0 for j in range(n)
                           if (i, j) in allowed}, "==", 1.0))
    for j in range(n):
        constraints.append(con(
            f"task_{j}", {f"m_{i}_{j}": 1.0 for i in range(n)
                          if (i, j) in allowed}, "==", 1.0))
    return _mirror("assignment_matching", tier, k, "location_cover_assign",
                   f"Bipartite assignment with forbidden pairs, {n}x{n}.", False,
                   {"coeffs": coeffs, "constant": 0.0}, variables, constraints)


def gen_generalized_assignment(rng: random.Random, tier: str, k: int) -> dict:
    n_agents = {"easy": 2, "medium": 3, "hard": 5}[tier]
    n_tasks = {"easy": 4, "medium": 8, "hard": 15}[tier]
    r = [[rng.randint(1, 9) for _ in range(n_tasks)] for _ in range(n_agents)]
    c = [[rng.randint(1, 25) for _ in range(n_tasks)] for _ in range(n_agents)]
    avg_load = sum(sum(row) for row in r) / (n_agents * n_agents)
    caps = [max(6, round(1.25 * avg_load)) for _ in range(n_agents)]
    variables = [var(f"g_{i}_{j}", "binary", 0, 1)
                 for i in range(n_agents) for j in range(n_tasks)]
    coeffs = {f"g_{i}_{j}": float(c[i][j])
              for i in range(n_agents) for j in range(n_tasks)}
    constraints = [
        con(f"task_{j}", {f"g_{i}_{j}": 1.0 for i in range(n_agents)}, "==", 1.0)
        for j in range(n_tasks)
    ]
    for i in range(n_agents):
        constraints.append(con(
            f"capacity_{i}", {f"g_{i}_{j}": float(r[i][j])
                              for j in range(n_tasks)}, "<=", float(caps[i])))
    return _mirror("generalized_assignment", tier, k, "location_cover_assign",
                   f"GAP, {n_agents} agents / {n_tasks} tasks.", False,
                   {"coeffs": coeffs, "constant": 0.0}, variables, constraints)


# ── family: scheduling ─────────────────────────────────────────────────────────

def gen_job_shop(rng: random.Random, tier: str, k: int) -> dict:
    n_jobs = {"easy": 3, "medium": 4, "hard": 6}[tier]
    n_mach = {"easy": 3, "medium": 4, "hard": 4}[tier]
    routes = []
    for _ in range(n_jobs):
        route = list(range(n_mach))
        rng.shuffle(route)
        routes.append(route)
    dur = [[rng.randint(2, 9) for _ in range(n_mach)] for _ in range(n_jobs)]
    big_m = float(sum(sum(row) for row in dur))
    variables = [var(f"s_{j}_{o}") for j in range(n_jobs) for o in range(n_mach)]
    variables.append(var("cmax"))
    constraints = []
    for j in range(n_jobs):
        for o in range(n_mach - 1):
            constraints.append(con(
                f"route_{j}_{o}", {f"s_{j}_{o+1}": 1.0, f"s_{j}_{o}": -1.0},
                ">=", float(dur[j][routes[j][o]])))
        constraints.append(con(
            f"cmax_{j}", {"cmax": 1.0, f"s_{j}_{n_mach-1}": -1.0},
            ">=", float(dur[j][routes[j][n_mach - 1]])))
    for m in range(n_mach):
        ops = [(j, routes[j].index(m)) for j in range(n_jobs)]
        for a in range(len(ops)):
            for b in range(a + 1, len(ops)):
                (j1, o1), (j2, o2) = ops[a], ops[b]
                z = f"z_{m}_{j1}_{j2}"
                variables.append(var(z, "binary", 0, 1))
                constraints.append(con(
                    f"m{m}_{j1}b{j2}",
                    {f"s_{j2}_{o2}": 1.0, f"s_{j1}_{o1}": -1.0, z: -big_m},
                    ">=", float(dur[j1][m]) - big_m))
                constraints.append(con(
                    f"m{m}_{j2}b{j1}",
                    {f"s_{j1}_{o1}": 1.0, f"s_{j2}_{o2}": -1.0, z: big_m},
                    ">=", float(dur[j2][m])))
    return _mirror("job_shop", tier, k, "scheduling",
                   f"Job shop, {n_jobs} jobs x {n_mach} machines, big-M "
                   "disjunctions.", False,
                   {"coeffs": {"cmax": 1.0}, "constant": 0.0},
                   variables, constraints)


def gen_parallel_machine(rng: random.Random, tier: str, k: int) -> dict:
    n_jobs = {"easy": 4, "medium": 8, "hard": 12}[tier]
    n_mach = {"easy": 2, "medium": 3, "hard": 4}[tier]
    p = [rng.randint(1, 9) for _ in range(n_jobs)]
    variables = [var(f"x_{j}_{m}", "binary", 0, 1)
                 for j in range(n_jobs) for m in range(n_mach)]
    variables.append(var("cmax"))
    constraints = [
        con(f"assign_{j}", {f"x_{j}_{m}": 1.0 for m in range(n_mach)}, "==", 1.0)
        for j in range(n_jobs)
    ]
    for m in range(n_mach):
        row = {f"x_{j}_{m}": float(p[j]) for j in range(n_jobs)}
        row["cmax"] = -1.0
        constraints.append(con(f"load_{m}", row, "<=", 0.0))
    # Identical machines: break the machine-permutation symmetry with
    # non-increasing loads (any schedule can be relabelled into this order).
    for m in range(n_mach - 1):
        row = {f"x_{j}_{m}": float(p[j]) for j in range(n_jobs)}
        for j in range(n_jobs):
            row[f"x_{j}_{m+1}"] = row.get(f"x_{j}_{m+1}", 0.0) - float(p[j])
        constraints.append(con(f"symmetry_{m}", row, ">=", 0.0))
    return _mirror("parallel_machine", tier, k, "scheduling",
                   f"P||Cmax, {n_jobs} jobs / {n_mach} machines.", False,
                   {"coeffs": {"cmax": 1.0}, "constant": 0.0},
                   variables, constraints)


def gen_rcpsp(rng: random.Random, tier: str, k: int) -> dict:
    n_act = {"easy": 4, "medium": 6, "hard": 8}[tier]
    dur = [rng.randint(2, 6) for _ in range(n_act)]
    req = [rng.randint(1, 3) for _ in range(n_act)]
    cap = {"easy": 4, "medium": 4, "hard": 5}[tier]
    prec = [(i, j) for i in range(n_act) for j in range(i + 1, n_act)
            if rng.random() < 0.35]
    horizon = sum(dur)
    variables = [var(f"x_{j}_{t}", "binary", 0, 1)
                 for j in range(n_act) for t in range(horizon)]
    variables.append(var("cmax"))
    constraints = [
        con(f"start_{j}", {f"x_{j}_{t}": 1.0 for t in range(horizon)}, "==", 1.0)
        for j in range(n_act)
    ]
    for (i, j) in prec:
        row = {f"x_{j}_{t}": float(t) for t in range(1, horizon)}
        for t in range(1, horizon):
            row[f"x_{i}_{t}"] = row.get(f"x_{i}_{t}", 0.0) - float(t)
        constraints.append(con(f"prec_{i}_{j}", row, ">=", float(dur[i])))
    for t in range(horizon):
        row = {}
        for j in range(n_act):
            for tau in range(max(0, t - dur[j] + 1), t + 1):
                row[f"x_{j}_{tau}"] = row.get(f"x_{j}_{tau}", 0.0) + float(req[j])
        if row:
            constraints.append(con(f"resource_{t}", row, "<=", float(cap)))
    for j in range(n_act):
        row = {"cmax": 1.0}
        for t in range(1, horizon):
            row[f"x_{j}_{t}"] = -float(t)
        constraints.append(con(f"cmax_{j}", row, ">=", float(dur[j])))
    return _mirror("rcpsp", tier, k, "scheduling",
                   f"RCPSP time-indexed, {n_act} activities, horizon {horizon}.",
                   False, {"coeffs": {"cmax": 1.0}, "constant": 0.0},
                   variables, constraints)


def gen_hybrid_flow_shop(rng: random.Random, tier: str, k: int) -> dict:
    n_jobs = {"easy": 3, "medium": 4, "hard": 5}[tier]
    machines = {"easy": (1, 2), "medium": (2, 2), "hard": (2, 3)}[tier]
    p = [[rng.randint(2, 9) for _ in range(2)] for _ in range(n_jobs)]
    big_m = float(sum(sum(row) for row in p)) + 9.0
    variables, constraints = [], []
    for j in range(n_jobs):
        for s in range(2):
            variables.append(var(f"t_{j}_{s}"))
            for m in range(machines[s]):
                variables.append(var(f"x_{j}_{s}_{m}", "binary", 0, 1))
            constraints.append(con(
                f"assign_{j}_{s}",
                {f"x_{j}_{s}_{m}": 1.0 for m in range(machines[s])}, "==", 1.0))
        constraints.append(con(
            f"stageprec_{j}", {f"t_{j}_1": 1.0, f"t_{j}_0": -1.0},
            ">=", float(p[j][0])))
    variables.append(var("cmax"))
    for j in range(n_jobs):
        constraints.append(con(
            f"cmax_{j}", {"cmax": 1.0, f"t_{j}_1": -1.0}, ">=", float(p[j][1])))
    for s in range(2):
        for m in range(machines[s]):
            for j1 in range(n_jobs):
                for j2 in range(j1 + 1, n_jobs):
                    z = f"z_{s}_{m}_{j1}_{j2}"
                    variables.append(var(z, "binary", 0, 1))
                    constraints.append(con(
                        f"d_{s}_{m}_{j1}b{j2}",
                        {f"t_{j2}_{s}": 1.0, f"t_{j1}_{s}": -1.0, z: -big_m,
                         f"x_{j1}_{s}_{m}": -big_m, f"x_{j2}_{s}_{m}": -big_m},
                        ">=", float(p[j1][s]) - 3.0 * big_m))
                    constraints.append(con(
                        f"d_{s}_{m}_{j2}b{j1}",
                        {f"t_{j1}_{s}": 1.0, f"t_{j2}_{s}": -1.0, z: big_m,
                         f"x_{j1}_{s}_{m}": -big_m, f"x_{j2}_{s}_{m}": -big_m},
                        ">=", float(p[j2][s]) - 2.0 * big_m))
    return _mirror("hybrid_flow_shop", tier, k, "scheduling",
                   f"Hybrid flow shop, {n_jobs} jobs, machines {machines}.",
                   False, {"coeffs": {"cmax": 1.0}, "constant": 0.0},
                   variables, constraints)


# ── family: planning ───────────────────────────────────────────────────────────

def gen_lot_sizing(rng: random.Random, tier: str, k: int) -> dict:
    n_prod = {"easy": 1, "medium": 2, "hard": 3}[tier]
    T = {"easy": 3, "medium": 6, "hard": 8}[tier]
    demand = [[rng.randint(2, 9) for _ in range(T)] for _ in range(n_prod)]
    unit = [rng.randint(1, 4) for _ in range(n_prod)]
    setup = [rng.randint(5, 15) for _ in range(n_prod)]
    hold = [rng.choice([0.5, 1.0, 1.5]) for _ in range(n_prod)]
    peak = max(sum(demand[p][t] for p in range(n_prod)) for t in range(T))
    cap = float(max(peak + 2, round(1.3 * peak)))
    variables, coeffs, constraints = [], {}, []
    for pr in range(n_prod):
        total_rem = sum(demand[pr])
        for t in range(T):
            variables.append(var(f"q_{pr}_{t}", upper=cap))
            variables.append(var(f"i_{pr}_{t}"))
            variables.append(var(f"u_{pr}_{t}", "binary", 0, 1))
            coeffs[f"q_{pr}_{t}"] = float(unit[pr])
            coeffs[f"i_{pr}_{t}"] = hold[pr]
            coeffs[f"u_{pr}_{t}"] = float(setup[pr])
            row = {f"q_{pr}_{t}": 1.0, f"i_{pr}_{t}": -1.0}
            if t > 0:
                row[f"i_{pr}_{t-1}"] = 1.0
            constraints.append(con(f"balance_{pr}_{t}", row, "==",
                                   float(demand[pr][t])))
            constraints.append(con(
                f"setup_{pr}_{t}",
                {f"q_{pr}_{t}": 1.0, f"u_{pr}_{t}": -min(cap, float(total_rem))},
                "<=", 0.0))
        constraints.append(con(f"end_{pr}", {f"i_{pr}_{T-1}": 1.0}, "==", 0.0))
    for t in range(T):
        constraints.append(con(
            f"capacity_{t}", {f"q_{pr}_{t}": 1.0 for pr in range(n_prod)},
            "<=", cap))
    return _mirror("lot_sizing", tier, k, "planning",
                   f"Lot sizing, {n_prod} products x {T} periods.", False,
                   {"coeffs": coeffs, "constant": 0.0}, variables, constraints)


def gen_unit_commitment(rng: random.Random, tier: str, k: int) -> dict:
    n_units = {"easy": 2, "medium": 3, "hard": 5}[tier]
    T = {"easy": 2, "medium": 6, "hard": 8}[tier]
    pmin = [rng.randint(1, 3) for _ in range(n_units)]
    pmax = [pmin[u] + rng.randint(3, 6) for u in range(n_units)]
    marginal = [rng.randint(1, 6) for _ in range(n_units)]
    on_cost = [rng.randint(1, 4) for _ in range(n_units)]
    start_cost = [rng.randint(2, 8) for _ in range(n_units)]
    total_max = sum(pmax)
    demand = [rng.randint(max(2, total_max // 4), round(0.8 * total_max))
              for _ in range(T)]
    variables, coeffs, constraints = [], {}, []
    for u in range(n_units):
        for t in range(T):
            variables.append(var(f"p_{u}_{t}"))
            variables.append(var(f"on_{u}_{t}", "binary", 0, 1))
            variables.append(var(f"su_{u}_{t}", upper=1.0))
            coeffs[f"p_{u}_{t}"] = float(marginal[u])
            coeffs[f"on_{u}_{t}"] = float(on_cost[u])
            coeffs[f"su_{u}_{t}"] = float(start_cost[u])
            constraints.append(con(
                f"cap_{u}_{t}", {f"p_{u}_{t}": 1.0, f"on_{u}_{t}": -float(pmax[u])},
                "<=", 0.0))
            constraints.append(con(
                f"min_{u}_{t}", {f"p_{u}_{t}": 1.0, f"on_{u}_{t}": -float(pmin[u])},
                ">=", 0.0))
            row = {f"su_{u}_{t}": 1.0, f"on_{u}_{t}": -1.0}
            if t > 0:
                row[f"on_{u}_{t-1}"] = 1.0
            constraints.append(con(f"start_{u}_{t}", row, ">=", 0.0))
    for t in range(T):
        constraints.append(con(
            f"demand_{t}", {f"p_{u}_{t}": 1.0 for u in range(n_units)},
            ">=", float(demand[t])))
    return _mirror("unit_commitment", tier, k, "planning",
                   f"Unit commitment, {n_units} units x {T} periods.", False,
                   {"coeffs": coeffs, "constant": 0.0}, variables, constraints)


def gen_workforce_shift(rng: random.Random, tier: str, k: int) -> dict:
    days = {"easy": 5, "medium": 7, "hard": 14}[tier]
    n_pat = {"easy": 3, "medium": 5, "hard": 7}[tier]
    with_overtime = tier == "hard"
    demand = [rng.randint(3, 12) for _ in range(days)]
    patterns = []
    for s in range(n_pat):
        start = rng.randrange(days)
        length = rng.randint(2, min(5, days))
        patterns.append({(start + o) % days for o in range(length)})
    covered = set().union(*patterns)
    if covered != set(range(days)):
        raise ValueError("uncovered day")
    cost = [len(p) * rng.randint(2, 4) + rng.randint(0, 3) for p in patterns]
    variables = [var(f"n{s}", "integer", 0, 20) for s in range(n_pat)]
    coeffs = {f"n{s}": float(cost[s]) for s in range(n_pat)}
    constraints = []
    for d in range(days):
        row = {f"n{s}": 1.0 for s in range(n_pat) if d in patterns[s]}
        if with_overtime:
            variables.append(var(f"o{d}", upper=3.0))
            coeffs[f"o{d}"] = 9.0
            row[f"o{d}"] = 1.0
        constraints.append(con(f"cover_{d}", row, ">=", float(demand[d])))
    return _mirror("workforce_shift", tier, k, "planning",
                   f"Shift scheduling, {days} days / {n_pat} patterns.", False,
                   {"coeffs": coeffs, "constant": 0.0}, variables, constraints)


def gen_inventory_routing(rng: random.Random, tier: str, k: int) -> dict:
    n_cust = {"easy": 2, "medium": 3, "hard": 4}[tier]
    T = {"easy": 2, "medium": 3, "hard": 3}[tier]
    pts = _coords(rng, n_cust + 1, 40)  # index 0 = depot
    demand = [[rng.randint(2, 6) for _ in range(T)] for _ in range(n_cust)]
    peak = max(sum(demand[c][t] for c in range(n_cust)) for t in range(T))
    Q = float(peak + rng.randint(1, 4))
    routes = []
    for mask in range(1, 1 << n_cust):
        subset = [c for c in range(n_cust) if mask & (1 << c)]
        seq, cur, cost = list(subset), 0, 0.0
        while seq:
            nxt = min(seq, key=lambda c: _dist_int(pts[cur], pts[c + 1]))
            cost += _dist_int(pts[cur], pts[nxt + 1])
            cur = nxt + 1
            seq.remove(nxt)
        cost += _dist_int(pts[cur], pts[0])
        routes.append((subset, cost))
    hold = 0.5
    variables, coeffs, constraints = [], {}, []
    for t in range(T):
        for r, (subset, cost) in enumerate(routes):
            variables.append(var(f"z_{r}_{t}", "binary", 0, 1))
            coeffs[f"z_{r}_{t}"] = cost
        constraints.append(con(
            f"one_route_{t}", {f"z_{r}_{t}": 1.0 for r in range(len(routes))},
            "<=", 1.0))
        constraints.append(con(
            f"vehcap_{t}", {f"q_{c}_{t}": 1.0 for c in range(n_cust)}, "<=", Q))
        for c in range(n_cust):
            variables.append(var(f"q_{c}_{t}", upper=Q))
            variables.append(var(f"i_{c}_{t}", upper=25.0))
            coeffs[f"i_{c}_{t}"] = hold
            row = {f"q_{c}_{t}": 1.0, f"i_{c}_{t}": -1.0}
            if t > 0:
                row[f"i_{c}_{t-1}"] = 1.0
            constraints.append(con(f"balance_{c}_{t}", row, "==",
                                   float(demand[c][t])))
            visit = {f"q_{c}_{t}": 1.0}
            for r, (subset, _) in enumerate(routes):
                if c in subset:
                    visit[f"z_{r}_{t}"] = -Q
            constraints.append(con(f"visit_{c}_{t}", visit, "<=", 0.0))
    return _mirror("inventory_routing", tier, k, "planning",
                   f"Inventory routing (enumerated routes), {n_cust} customers x "
                   f"{T} periods.", False,
                   {"coeffs": coeffs, "constant": 0.0}, variables, constraints)


# ── family: routing ────────────────────────────────────────────────────────────

def _tour_edges(n: int) -> list[tuple[int, int]]:
    return [(i, j) for i in range(n) for j in range(n) if i != j]


def gen_tsp(rng: random.Random, tier: str, k: int) -> dict:
    n = {"easy": 5, "medium": 7, "hard": 9}[tier]
    pts = _coords(rng, n)
    d = {(i, j): _dist_int(pts[i], pts[j]) for (i, j) in _tour_edges(n)}
    variables = [var(f"e_{i}_{j}", "binary", 0, 1) for (i, j) in _tour_edges(n)]
    variables += [var(f"u{i}", "integer", 1, n - 1) for i in range(1, n)]
    constraints = []
    for i in range(n):
        constraints.append(con(
            f"leave_{i}", {f"e_{i}_{j}": 1.0 for j in range(n) if j != i},
            "==", 1.0))
        constraints.append(con(
            f"enter_{i}", {f"e_{j}_{i}": 1.0 for j in range(n) if j != i},
            "==", 1.0))
    for i in range(1, n):
        for j in range(1, n):
            if i != j:
                constraints.append(con(
                    f"mtz_{i}_{j}",
                    {f"u{i}": 1.0, f"u{j}": -1.0, f"e_{i}_{j}": float(n)},
                    "<=", float(n - 1)))
    coeffs = {f"e_{i}_{j}": d[(i, j)] for (i, j) in _tour_edges(n)}
    return _mirror("tsp", tier, k, "routing",
                   f"TSP with MTZ, {n} cities.", False,
                   {"coeffs": coeffs, "constant": 0.0}, variables, constraints)


def gen_cvrp(rng: random.Random, tier: str, k: int) -> dict:
    n_cust = {"easy": 4, "medium": 5, "hard": 7}[tier]
    n = n_cust + 1  # node 0 = depot
    pts = _coords(rng, n)
    demand = [0] + [rng.randint(1, 6) for _ in range(n_cust)]
    total = sum(demand)
    Q = float(max(max(demand) + 1, math.ceil(total / 2) + rng.randint(0, 2)))
    K = 2.0
    d = {(i, j): _dist_int(pts[i], pts[j]) for (i, j) in _tour_edges(n)}
    variables = [var(f"x_{i}_{j}", "binary", 0, 1) for (i, j) in _tour_edges(n)]
    variables += [var(f"f_{i}_{j}") for (i, j) in _tour_edges(n)]
    coeffs = {f"x_{i}_{j}": d[(i, j)] for (i, j) in _tour_edges(n)}
    constraints = [
        con("depot_out", {f"x_0_{j}": 1.0 for j in range(1, n)}, "==", K),
        con("depot_in", {f"x_{j}_0": 1.0 for j in range(1, n)}, "==", K),
        con("flow_out",
            {f"f_0_{j}": 1.0 for j in range(1, n)}, "==", float(total)),
    ]
    for c in range(1, n):
        constraints.append(con(
            f"leave_{c}", {f"x_{c}_{j}": 1.0 for j in range(n) if j != c},
            "==", 1.0))
        constraints.append(con(
            f"enter_{c}", {f"x_{j}_{c}": 1.0 for j in range(n) if j != c},
            "==", 1.0))
        row = {f"f_{j}_{c}": 1.0 for j in range(n) if j != c}
        for j in range(n):
            if j != c:
                row[f"f_{c}_{j}"] = -1.0
        constraints.append(con(f"drop_{c}", row, "==", float(demand[c])))
    for (i, j) in _tour_edges(n):
        constraints.append(con(
            f"link_{i}_{j}", {f"f_{i}_{j}": 1.0, f"x_{i}_{j}": -Q}, "<=", 0.0))
    return _mirror("cvrp", tier, k, "routing",
                   f"CVRP single-commodity flow, {n_cust} customers, 2 vehicles.",
                   False, {"coeffs": coeffs, "constant": 0.0},
                   variables, constraints)


def gen_tsptw(rng: random.Random, tier: str, k: int) -> dict:
    n = {"easy": 4, "medium": 5, "hard": 6}[tier] + 1  # node 0 = depot
    pts = _coords(rng, n)
    d = {(i, j): _dist_int(pts[i], pts[j]) for (i, j) in _tour_edges(n)}
    service = 2.0
    tour = list(range(1, n))
    rng.shuffle(tour)
    arrive, cur, t_cur = {}, 0, 0.0
    for c in tour:
        t_cur += (service if cur != 0 else 0.0) + d[(cur, c)]
        arrive[c] = t_cur
        cur = c
    horizon = t_cur + d[(cur, 0)] + service + 30.0
    windows = {c: (max(0.0, arrive[c] - rng.randint(3, 12)),
                   arrive[c] + rng.randint(3, 15)) for c in tour}
    big_m = horizon + max(d.values()) + service
    variables = [var(f"x_{i}_{j}", "binary", 0, 1) for (i, j) in _tour_edges(n)]
    variables.append(var("t_0", upper=0.0))
    for c in range(1, n):
        variables.append(var(f"t_{c}", lower=windows[c][0], upper=windows[c][1]))
    coeffs = {f"x_{i}_{j}": d[(i, j)] for (i, j) in _tour_edges(n)}
    constraints = []
    for i in range(n):
        constraints.append(con(
            f"leave_{i}", {f"x_{i}_{j}": 1.0 for j in range(n) if j != i},
            "==", 1.0))
        constraints.append(con(
            f"enter_{i}", {f"x_{j}_{i}": 1.0 for j in range(n) if j != i},
            "==", 1.0))
    for (i, j) in _tour_edges(n):
        if j == 0:
            continue  # the return leg has no time row
        constraints.append(con(
            f"time_{i}_{j}",
            {f"t_{j}": 1.0, f"t_{i}": -1.0, f"x_{i}_{j}": -big_m},
            ">=", d[(i, j)] + (service if i != 0 else 0.0) - big_m))
    return _mirror("tsptw", tier, k, "routing",
                   f"TSP with time windows, {n - 1} customers.", False,
                   {"coeffs": coeffs, "constant": 0.0}, variables, constraints)


def gen_hf_vrp(rng: random.Random, tier: str, k: int) -> dict:
    n_cust = {"easy": 3, "medium": 4, "hard": 5}[tier]
    n = n_cust + 1
    pts = _coords(rng, n)
    demand = [0] + [rng.randint(1, 5) for _ in range(n_cust)]
    total = sum(demand)
    q = {1: float(max(demand) + rng.randint(1, 3)), 2: float(total)}
    fixed = {1: 10.0, 2: 25.0}
    mult = {1: 1.0, 2: 1.25}
    d = {(i, j): _dist_int(pts[i], pts[j]) for (i, j) in _tour_edges(n)}
    variables, coeffs, constraints = [], {}, []
    for v in (1, 2):
        variables.append(var(f"use{v}", "binary", 0, 1))
        coeffs[f"use{v}"] = fixed[v]
        for (i, j) in _tour_edges(n):
            variables.append(var(f"x{v}_{i}_{j}", "binary", 0, 1))
            variables.append(var(f"f{v}_{i}_{j}"))
            coeffs[f"x{v}_{i}_{j}"] = round(mult[v] * d[(i, j)], 4)
            constraints.append(con(
                f"link{v}_{i}_{j}",
                {f"f{v}_{i}_{j}": 1.0, f"x{v}_{i}_{j}": -q[v]}, "<=", 0.0))
        constraints.append(con(
            f"depot_out{v}",
            {f"x{v}_0_{j}": 1.0 for j in range(1, n)} | {f"use{v}": -1.0},
            "==", 0.0))
        constraints.append(con(
            f"depot_in{v}",
            {f"x{v}_{j}_0": 1.0 for j in range(1, n)} | {f"use{v}": -1.0},
            "==", 0.0))
        constraints.append(con(
            f"fleetcap{v}", {f"f{v}_0_{j}": 1.0 for j in range(1, n)},
            "<=", q[v]))
    for c in range(1, n):
        constraints.append(con(
            f"leave_{c}",
            {f"x{v}_{c}_{j}": 1.0 for v in (1, 2) for j in range(n) if j != c},
            "==", 1.0))
        constraints.append(con(
            f"enter_{c}",
            {f"x{v}_{j}_{c}": 1.0 for v in (1, 2) for j in range(n) if j != c},
            "==", 1.0))
        for v in (1, 2):
            row = {f"x{v}_{j}_{c}": 1.0 for j in range(n) if j != c}
            for j in range(n):
                if j != c:
                    row[f"x{v}_{c}_{j}"] = row.get(f"x{v}_{c}_{j}", 0.0) - 1.0
            constraints.append(con(f"samev_{v}_{c}", row, "==", 0.0))
        drop = {}
        for v in (1, 2):
            for j in range(n):
                if j != c:
                    drop[f"f{v}_{j}_{c}"] = 1.0
                    drop[f"f{v}_{c}_{j}"] = drop.get(f"f{v}_{c}_{j}", 0.0) - 1.0
        constraints.append(con(f"drop_{c}", drop, "==", float(demand[c])))
    return _mirror("hf_vrp", tier, k, "routing",
                   f"Heterogeneous-fleet VRP, {n_cust} customers, 2 types.",
                   False, {"coeffs": coeffs, "constant": 0.0},
                   variables, constraints)


# ── family: combinatorial ──────────────────────────────────────────────────────

def gen_multidim_knapsack(rng: random.Random, tier: str, k: int) -> dict:
    n_items = {"easy": 4, "medium": 10, "hard": 20}[tier]
    n_dims = {"easy": 2, "medium": 3, "hard": 5}[tier]
    w = [[rng.randint(1, 15) for _ in range(n_items)] for _ in range(n_dims)]
    v = [rng.randint(5, 40) for _ in range(n_items)]
    variables = [var(f"i{j}", "binary", 0, 1) for j in range(n_items)]
    coeffs = {f"i{j}": float(v[j]) for j in range(n_items)}
    constraints = [
        con(f"budget_{r}", {f"i{j}": float(w[r][j]) for j in range(n_items)},
            "<=", float(math.floor(0.45 * sum(w[r]))))
        for r in range(n_dims)
    ]
    return _mirror("multidim_knapsack", tier, k, "combinatorial",
                   f"Multi-dimensional knapsack, {n_items} items / {n_dims} "
                   "budgets.", True,
                   {"coeffs": coeffs, "constant": 0.0}, variables, constraints)


def _coloring_target(tier: str) -> tuple[int, int]:
    return {"easy": (3, 5), "medium": (3, 9), "hard": (4, 12)}[tier]


def gen_graph_coloring(rng: random.Random, tier: str, k: int) -> dict:
    chi, n = _coloring_target(tier)
    if tier == "easy":
        n = rng.choice([5, 7])
        edges = {(i, (i + 1) % n) for i in range(n)}
        for _ in range(rng.randint(0, 2)):
            i, j = rng.randrange(n), rng.randrange(n)
            if abs(i - j) > 1 and {i, j} != {0, n - 1} and i != j:
                edges.add((min(i, j), max(i, j)))
    else:
        n += rng.randint(0, 1)
        groups = [i % chi for i in range(n)]
        rng.shuffle(groups)
        p = 0.5 if tier == "medium" else 0.45
        edges = set()
        for i in range(n):
            for j in range(i + 1, n):
                if groups[i] != groups[j] and rng.random() < p:
                    edges.add((i, j))
        for g in range(chi):
            member = [i for i in range(n) if groups[i] == g]
            nxt = [i for i in range(n) if groups[i] == (g + 1) % chi]
            if member and nxt:
                edges.add((min(member[0], nxt[0]), max(member[0], nxt[0])))
    n_colors = chi + 1
    variables = [var(f"y{c}", "binary", 0, 1) for c in range(n_colors)]
    variables += [var(f"x_{v}_{c}", "binary", 0, 1)
                  for v in range(n) for c in range(n_colors)]
    constraints = [
        con(f"colour_{v}", {f"x_{v}_{c}": 1.0 for c in range(n_colors)},
            "==", 1.0)
        for v in range(n)
    ]
    for (u, w) in sorted(edges):
        for c in range(n_colors):
            constraints.append(con(
                f"edge_{u}_{w}_c{c}",
                {f"x_{u}_{c}": 1.0, f"x_{w}_{c}": 1.0, f"y{c}": -1.0}, "<=", 0.0))
    # Standard symmetry breaking: colours used in order, vertex 0 takes colour 0.
    for c in range(n_colors - 1):
        constraints.append(con(f"order_{c}", {f"y{c}": 1.0, f"y{c+1}": -1.0},
                               ">=", 0.0))
    constraints.append(con("anchor", {"x_0_0": 1.0}, "==", 1.0))
    coeffs = {f"y{c}": 1.0 for c in range(n_colors)}
    inst = _mirror("graph_coloring", tier, k, "combinatorial",
                   f"Graph colouring, {n} vertices / {len(edges)} edges, "
                   f"target chi={chi}.", False,
                   {"coeffs": coeffs, "constant": 0.0}, variables, constraints)
    inst["chi_target"] = chi
    return inst


def gen_set_packing(rng: random.Random, tier: str, k: int) -> dict:
    n_el = {"easy": 6, "medium": 12, "hard": 20}[tier]
    n_sets = {"easy": 6, "medium": 12, "hard": 18}[tier]
    members = []
    for s in range(n_sets):
        m = {e for e in range(n_el) if rng.random() < 0.3}
        if not m:
            m = {rng.randrange(n_el)}
        members.append(m)
    weights = [rng.randint(3, 30) for _ in range(n_sets)]
    variables = [var(f"z{s}", "binary", 0, 1) for s in range(n_sets)]
    coeffs = {f"z{s}": float(weights[s]) for s in range(n_sets)}
    constraints = []
    for e in range(n_el):
        row = {f"z{s}": 1.0 for s in range(n_sets) if e in members[s]}
        if len(row) >= 2:
            constraints.append(con(f"conflict_{e}", row, "<=", 1.0))
    if not constraints:
        raise ValueError("no conflicts")
    return _mirror("set_packing", tier, k, "combinatorial",
                   f"Set packing, {n_el} elements / {n_sets} sets.", True,
                   {"coeffs": coeffs, "constant": 0.0}, variables, constraints)


def gen_logical_csp(rng: random.Random, tier: str, k: int) -> dict:
    n = {"easy": 5, "medium": 10, "hard": 15}[tier]
    weights = [rng.randint(-5, 20) for _ in range(n)]
    variables = [var(f"b{j}", "binary", 0, 1) for j in range(n)]
    coeffs = {f"b{j}": float(weights[j]) for j in range(n)}
    constraints = []
    for r in range(n):
        kind = rng.choice(["imply", "conflict", "amo", "clause"])
        picks = rng.sample(range(n), 3)
        if kind == "imply":
            constraints.append(con(
                f"imply_{r}", {f"b{picks[0]}": 1.0, f"b{picks[1]}": -1.0},
                "<=", 0.0))
        elif kind == "conflict":
            constraints.append(con(
                f"conflict_{r}", {f"b{picks[0]}": 1.0, f"b{picks[1]}": 1.0},
                "<=", 1.0))
        elif kind == "amo":
            constraints.append(con(
                f"amo_{r}", {f"b{p}": 1.0 for p in picks}, "<=", 1.0))
        else:
            constraints.append(con(
                f"clause_{r}", {f"b{p}": 1.0 for p in picks}, ">=", 1.0))
    return _mirror("logical_csp", tier, k, "combinatorial",
                   f"Logical selection, {n} binaries / {n} logic rows.", True,
                   {"coeffs": coeffs, "constant": 0.0}, variables, constraints)


GENERATORS = {
    "min_cost_flow": gen_min_cost_flow,
    "max_flow": gen_max_flow,
    "rc_shortest_path": gen_rc_shortest_path,
    "cap_network_design": gen_cap_network_design,
    "time_expanded_flow": gen_time_expanded_flow,
    "facility_location": gen_facility_location,
    "p_median_center": gen_p_median_center,
    "set_cover_partition": gen_set_cover_partition,
    "assignment_matching": gen_assignment_matching,
    "generalized_assignment": gen_generalized_assignment,
    "job_shop": gen_job_shop,
    "parallel_machine": gen_parallel_machine,
    "rcpsp": gen_rcpsp,
    "hybrid_flow_shop": gen_hybrid_flow_shop,
    "lot_sizing": gen_lot_sizing,
    "unit_commitment": gen_unit_commitment,
    "workforce_shift": gen_workforce_shift,
    "inventory_routing": gen_inventory_routing,
    "tsp": gen_tsp,
    "cvrp": gen_cvrp,
    "tsptw": gen_tsptw,
    "hf_vrp": gen_hf_vrp,
    "multidim_knapsack": gen_multidim_knapsack,
    "graph_coloring": gen_graph_coloring,
    "set_packing": gen_set_packing,
    "logical_csp": gen_logical_csp,
}


def build_one(task: tuple[str, str, int]) -> tuple[dict, int]:
    """Generate + referee-certify one instance under rejection-regeneration."""
    sub, tier, k = task
    gen = GENERATORS[sub]
    for attempt in range(MAX_ATTEMPTS):
        rng = _rng(sub, tier, k, attempt)
        try:
            inst = gen(rng, tier, k)
        except ValueError:
            continue
        status, optimum = referee(inst)
        if status != "optimal":
            continue
        chi_target = inst.pop("chi_target", None)
        if chi_target is not None and round(optimum) != chi_target:
            continue  # the paper's regime check: chromatic number must match
        if abs(optimum) > 1e12:
            continue
        inst["ground_truth"] = {
            "objective": round(optimum, 9),
            "source": "referee:scipy-highs",
        }
        return inst, attempt
    raise SystemExit(f"{sub}/{tier}/{k}: no admissible candidate "
                     f"in {MAX_ATTEMPTS} attempts")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-tier", type=int, default=PER_TIER)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    tasks = [(sub, tier, k)
             for sub in GENERATORS
             for tier in TIERS
             for k in range(args.per_tier)]
    started = time.monotonic()
    if args.workers > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            built = list(pool.map(build_one, tasks, chunksize=4))
    else:
        built = [build_one(t) for t in tasks]
    elapsed = time.monotonic() - started

    instances = [inst for inst, _ in built]
    retries = sum(attempt for _, attempt in built)
    BUILD.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(instances, indent=1) + "\n", encoding="utf-8")

    by_sub: dict[str, list[dict]] = {}
    for inst in instances:
        by_sub.setdefault(inst["subcategory"], []).append(inst)
    print(f"{'subcategory':<26}{'n':>4}{'vars(e/m/h)':>16}{'rows(e/m/h)':>16}")
    for sub in GENERATORS:
        group = by_sub[sub]
        vs, rs = [], []
        for tier in TIERS:
            tg = [i for i in group if i["difficulty"] == tier]
            vs.append(str(max(len(i["variables"]) for i in tg)))
            rs.append(str(max(len(i["constraints"]) for i in tg)))
        print(f"{sub:<26}{len(group):>4}{'/'.join(vs):>16}{'/'.join(rs):>16}")
    print(f"\nwrote {len(instances)} referee-certified instances to {OUT}")
    print(f"generation: {elapsed:.1f}s with {args.workers} workers, "
          f"{retries} rejection-regeneration retries")


if __name__ == "__main__":
    main()
