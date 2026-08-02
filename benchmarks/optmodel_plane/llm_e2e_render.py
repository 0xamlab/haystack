"""Natural-language renderers for the LLM end-to-end pass@1 harness.

MM-OptBench (arXiv:2605.12154) hands candidates a natural-language word problem and
keeps the machine-readable `instance_data` (the flat formulation + verified optimum)
hidden. Our proxy corpus (`make_mirror_instances.py`) only carries the machine-readable
half — a one-line `description` label, not a word problem. To exercise the real
benchmark SHAPE end to end (text in, formulation out), this module renders each
sampled instance's OWN flat data (variable bounds, objective coefficients, constraint
rows) into a genuine natural-language scenario, using the known naming convention of
the generator that produced it (`make_mirror_instances.py`, read directly, one
renderer per subcategory).

Honest caveat, stated wherever this module's output is used: this is a MECHANICALLY
GENERATED rendering of our own proxy instance's data, not an independently authored
word problem like the withheld benchmark's. It is built from the SAME numbers the
ground-truth formulation encodes (so solving the rendered scenario correctly must
reach the same verified optimum), but the prose itself is templated, not human-written.
That is a weaker test of free-form language understanding than the real benchmark,
though it still requires the model to read a scenario, recover the entities and
numbers, and produce a correct mathematical formulation — the skill MM-OptBench itself
scores.
"""

from __future__ import annotations

import re
from collections import defaultdict

SCHEMA_BLURB = """
Produce your answer as a formulation in this JSON schema (no extra prose, no markdown
fences — the field named `formulation` in your structured response IS the schema):

  maximize: bool — true to maximize the objective, false to minimize.
  variables: list of {name: string, kind: "continuous"|"integer"|"binary",
    lower: number or null (null = no lower bound), upper: number or null (null = no
    upper bound)}. Every variable used anywhere below MUST be declared here exactly
    once. Binary variables are implicitly in [0, 1] even if you leave lower/upper null.
  objective: {terms: list of {var: string, coeff: number}, constant: number}.
  constraints: list of {name: string, terms: list of {var: string, coeff: number},
    sense: "<="|"=="|">=", rhs: number}. Every `var` referenced in `terms` (objective or
    constraints) must be one of the declared `variables` names, spelled identically.

This is a linear/mixed-integer program: the objective and every constraint are linear
(sum of coeff * var), nothing nonlinear. Use exactly the entities/indices named in the
problem text for your variable names so the model is auditable (e.g. `x_2_5` for a
decision tied to items 2 and 5).
""".strip()


def _vmap(inst: dict) -> dict:
    return {v["name"]: v for v in inst["variables"]}


def _obj(inst: dict) -> dict:
    return dict(inst["objective"].get("coeffs", {}))


def _cons_by_prefix(inst: dict, prefix: str) -> list:
    return [c for c in inst["constraints"] if c["name"].startswith(prefix)]


def _vars_by_regex(inst: dict, pattern: str) -> list[tuple]:
    rx = re.compile(pattern)
    out = []
    for v in inst["variables"]:
        m = rx.match(v["name"])
        if m:
            out.append((v, m.groups()))
    return out


def _money(x: float) -> str:
    if float(x) == int(x):
        return str(int(x))
    return f"{x:g}"


# ── network ──────────────────────────────────────────────────────────────────────

def render_min_cost_flow(inst: dict) -> str:
    arcs = _vars_by_regex(inst, r"^x_(\d+)_(\d+)$")
    obj = _obj(inst)
    lines = []
    for v, (u, w) in sorted(arcs, key=lambda t: (int(t[1][0]), int(t[1][1]))):
        cost = obj.get(v["name"], 0.0)
        cap = v.get("upper")
        lines.append(f"  node {u} -> node {w}: ${_money(cost)}/unit, capacity {_money(cap)} units")
    bal = []
    for c in sorted(_cons_by_prefix(inst, "balance_"), key=lambda c: int(c["name"].split("_")[1])):
        node = c["name"].split("_")[1]
        rhs = c["rhs"]
        if rhs > 0:
            bal.append(f"  node {node} has net supply {_money(rhs)} units (must ship out this much more than it receives)")
        elif rhs < 0:
            bal.append(f"  node {node} has net demand {_money(-rhs)} units (must receive this much more than it ships)")
        else:
            bal.append(f"  node {node} is pure transshipment (inflow must equal outflow)")
    return (
        "A logistics network ships goods over the following directed arcs, each with a "
        "per-unit shipping cost and a maximum capacity:\n" + "\n".join(lines) +
        "\n\nEach node has a fixed net requirement:\n" + "\n".join(bal) +
        "\n\nDecide the shipment quantity on every arc (0 <= flow <= that arc's capacity) "
        "so every node's requirement is met exactly, minimizing total shipping cost."
    )


def render_max_flow(inst: dict) -> str:
    arcs = _vars_by_regex(inst, r"^x_(\d+)_(\d+)$")
    nodes = sorted({int(g) for _, gr in arcs for g in gr})
    source, sink = nodes[0], nodes[-1]
    lines = []
    for v, (u, w) in sorted(arcs, key=lambda t: (int(t[1][0]), int(t[1][1]))):
        lines.append(f"  node {u} -> node {w}: capacity {_money(v.get('upper'))} units")
    return (
        "A pipe network has directed arcs, each with a maximum throughput capacity:\n" +
        "\n".join(lines) +
        f"\n\nFind the flow on every arc (0 <= flow <= capacity) that maximizes the total "
        f"flow shipped from source node {source} to sink node {sink}, subject to flow "
        f"conservation (inflow = outflow) at every other node."
    )


def render_rc_shortest_path(inst: dict) -> str:
    arcs = _vars_by_regex(inst, r"^e_(\d+)_(\d+)$")
    obj = _obj(inst)
    nodes = sorted({int(g) for _, gr in arcs for g in gr})
    source, sink = nodes[0], nodes[-1]
    lines = []
    for v, (u, w) in sorted(arcs, key=lambda t: (int(t[1][0]), int(t[1][1]))):
        lines.append(f"  node {u} -> node {w}: travel cost {_money(obj.get(v['name'], 0.0))}")
    res_rows = sorted(_cons_by_prefix(inst, "resource_"), key=lambda c: c["name"])
    res_lines = []
    for c in res_rows:
        arc_usage = []
        for name, coeff in c["coeffs"].items():
            m = re.match(r"^e_(\d+)_(\d+)$", name)
            if m:
                arc_usage.append(f"{m.group(1)}->{m.group(2)}: {_money(coeff)}")
        res_lines.append(
            f"  resource budget {_money(c['rhs'])} total along the path; per-arc usage: "
            + ", ".join(arc_usage)
        )
    return (
        f"A courier must travel from node {source} to node {sink} along a directed "
        f"network. Each arc has a travel cost:\n" + "\n".join(lines) +
        "\n\nEach arc also consumes one or more scarce resources (e.g. fuel, time) at a "
        "fixed amount, and the path's total resource consumption may not exceed a fixed "
        "budget:\n" + "\n".join(res_lines) +
        "\n\nChoose a set of arcs forming a single path from source to sink (each "
        "intermediate node used has equal in- and out-degree, exactly one arc leaves the "
        "source and exactly one enters the sink) that minimizes total travel cost while "
        "respecting every resource budget."
    )


def render_cap_network_design(inst: dict) -> str:
    xs = _vars_by_regex(inst, r"^x_(\d+)_(\d+)$")
    obj = _obj(inst)
    install_rows = {c["name"]: c for c in _cons_by_prefix(inst, "install_")}
    lines = []
    for v, (u, w) in sorted(xs, key=lambda t: (int(t[1][0]), int(t[1][1]))):
        row = install_rows.get(f"install_{u}_{w}")
        cap = None
        if row:
            for name, coeff in row["coeffs"].items():
                if name.startswith("y_") and coeff < 0:
                    cap = -coeff
        fixed = obj.get(f"y_{u}_{w}", 0.0)
        usecost = obj.get(v["name"], 0.0)
        lines.append(
            f"  node {u} -> node {w}: install cost ${_money(fixed)} (one-time), then "
            f"${_money(usecost)}/unit shipped, capacity {_money(cap)} units IF installed"
        )
    bal = []
    for c in sorted(_cons_by_prefix(inst, "balance_"), key=lambda c: int(c["name"].split("_")[1])):
        node = c["name"].split("_")[1]
        rhs = c["rhs"]
        if rhs > 0:
            bal.append(f"  node {node}: net supply {_money(rhs)} units")
        elif rhs < 0:
            bal.append(f"  node {node}: net demand {_money(-rhs)} units")
        else:
            bal.append(f"  node {node}: pure transshipment")
    return (
        "A network operator may build any subset of the following candidate directed "
        "arcs. Building an arc costs a one-time installation fee and unlocks a fixed "
        "shipping capacity on it; every unit shipped over a built arc also costs a "
        "per-unit usage fee. Arcs that are not built carry zero flow.\n" + "\n".join(lines) +
        "\n\nEach node has a fixed net supply/demand requirement:\n" + "\n".join(bal) +
        "\n\nDecide which arcs to build and how much to ship on each, meeting every "
        "node's requirement exactly, minimizing total installation + shipping cost."
    )


def render_time_expanded_flow(inst: dict) -> str:
    obj = _obj(inst)
    qs = _vars_by_regex(inst, r"^q_(\d+)_(\d+)$")
    ss = _vars_by_regex(inst, r"^s_(\d+)_(\d+)_(\d+)$")
    n_plants = len({int(g[0]) for _, g in qs})
    n_periods = len({int(g[1]) for _, g in qs})
    n_markets = len({int(g[1]) for _, g in ss})
    prod_lines = []
    for v, (p, t) in sorted(qs, key=lambda x: (int(x[1][0]), int(x[1][1]))):
        prod_lines.append(
            f"  plant {p}, period {t}: cost ${_money(obj.get(v['name'], 0.0))}/unit produced, "
            f"capacity {_money(v.get('upper'))} units"
        )
    ship_costs = sorted({(g[0], g[1]): obj.get(f"s_{g[0]}_{g[1]}_{g[2]}", 0.0) for _, g in ss}.items())
    demand_lines = []
    for c in sorted(_cons_by_prefix(inst, "market_"), key=lambda c: (c["name"])):
        _, m, t = c["name"].split("_")
        demand_lines.append(f"  market {m}, period {t}: demand {_money(c['rhs'])} units")
    return (
        f"A company has {n_plants} plant(s) supplying {n_markets} market(s) over "
        f"{n_periods} time periods. Each plant's production cost and capacity per "
        f"period:\n" + "\n".join(prod_lines) +
        "\n\nShipping cost per unit from plant to market (flat across periods): " +
        ", ".join(f"plant {p}->market {m}: ${_money(c)}" for (p, m), c in ship_costs) +
        "\n\nMarkets may hold inventory between periods at $1/unit/period, capacity 20 "
        "units, starting and ending empty. Demand each period must be met exactly from "
        "shipments received plus inventory carried in:\n" + "\n".join(demand_lines) +
        "\n\nDecide production, shipments and inventory in every period, meeting all "
        "demand exactly, minimizing total production + shipping + holding cost. Each "
        "plant's production in a period must equal what it ships out that period "
        "(no plant-side inventory)."
    )


# ── location_cover_assign ────────────────────────────────────────────────────────

def render_facility_location(inst: dict) -> str:
    obj = _obj(inst)
    open_vars = [v for v in inst["variables"] if re.match(r"^y\d+$", v["name"])]
    n_fac = len(open_vars)
    assign_rows = defaultdict(dict)
    for c in inst["constraints"]:
        m = re.match(r"^serve_(\d+)$", c["name"])
        if m:
            assign_rows[int(m.group(1))] = c
    cap_rows = {c["name"]: c for c in _cons_by_prefix(inst, "cap_")}
    capacitated = bool(cap_rows)
    open_cost = ", ".join(f"site {i}: ${_money(obj.get(f'y{i}', 0.0))}" for i in range(n_fac))
    dist_lines = []
    for j, row in sorted(assign_rows.items()):
        parts = []
        for name in row["coeffs"]:
            m = re.match(r"^a_(\d+)_(\d+)$", name)
            if m:
                parts.append(f"site {m.group(1)}: ${_money(obj.get(name, 0.0))}")
        dist_lines.append(f"  customer {j} can be served by -> " + ", ".join(parts))
    cap_lines = []
    if capacitated:
        for name, c in sorted(cap_rows.items()):
            i = name.split("_")[1]
            cap_lines.append(f"  site {i} capacity {_money(-c['rhs']) if c['rhs'] < 0 else _money(c['rhs'])} units (in the units of customer demand below)")
    return (
        f"A company must choose which of {n_fac} candidate sites to open as service "
        "facilities and which open facility serves each customer. Opening cost per "
        f"site: {open_cost}.\n\nEach customer may only be served by facilities within "
        "its service radius, at the listed per-customer service cost if that site is "
        "open:\n" + "\n".join(dist_lines) +
        (("\n\nEach open facility has a maximum total demand it can serve:\n" + "\n".join(cap_lines))
         if capacitated else "\n\nFacilities have no capacity limit once opened.") +
        "\n\nDecide which sites to open and which open site serves each customer "
        "(every customer served by exactly one open site within its radius), "
        "minimizing total opening + service cost."
    )


def render_p_median_center(inst: dict) -> str:
    is_center = any(v["name"] == "dmax" for v in inst["variables"])
    open_vars = [v for v in inst["variables"] if re.match(r"^y\d+$", v["name"])]
    n_sites = len(open_vars)
    p_row = next(c for c in inst["constraints"] if c["name"] == "choose_p")
    p = int(p_row["rhs"])
    serve_rows = [c for c in inst["constraints"] if c["name"].startswith("serve_")]
    n_cust = len(serve_rows)
    obj = _obj(inst)
    if is_center:
        dist_lines = []
        for c in inst["constraints"]:
            m = re.match(r"^center_(\d+)$", c["name"])
            if m:
                j = m.group(1)
                parts = [f"site {re.match(r'x_(\d+)_', name).group(1)}: {_money(coeff)}"
                         for name, coeff in c["coeffs"].items() if name.startswith("x_")]
                dist_lines.append(f"  customer {j} distance to each site -> " + ", ".join(parts))
        return (
            f"Choose exactly {p} of {n_sites} candidate sites to open, and assign each of "
            f"{n_cust} customers to one open site, minimizing the WORST (maximum) "
            "distance any customer travels to its assigned open site (a p-center "
            "problem). Distances from each customer to each candidate site:\n" +
            "\n".join(dist_lines) +
            "\n\nEvery customer must be assigned to a site that is actually open."
        )
    else:
        weight_lines = []
        for j in range(n_cust):
            parts = []
            for i in range(n_sites):
                key = f"x_{i}_{j}"
                if key in obj:
                    parts.append(f"site {i}: {_money(obj[key])}")
            weight_lines.append(f"  customer {j} weighted distance to each site -> " + ", ".join(parts))
        return (
            f"Choose exactly {p} of {n_sites} candidate sites to open, and assign each of "
            f"{n_cust} customers to one open site, minimizing the TOTAL of each "
            "customer's demand-weighted distance to its assigned open site (a p-median "
            "problem; the numbers below already include each customer's demand weight "
            "multiplied into the distance):\n" + "\n".join(weight_lines) +
            "\n\nEvery customer must be assigned to a site that is actually open, and a "
            "customer's assignment fraction to any non-open site must be zero."
        )


def render_set_cover_partition(inst: dict) -> str:
    obj = _obj(inst)
    sets = sorted(v["name"] for v in inst["variables"])
    elements = sorted({int(c["name"].split("_")[1]) for c in inst["constraints"]})
    sense = inst["constraints"][0]["sense"] if inst["constraints"] else "=="
    membership = defaultdict(list)
    for c in inst["constraints"]:
        e = c["name"].split("_")[1]
        for name in c["coeffs"]:
            membership[name].append(e)
    set_lines = [f"  {s}: cost {_money(obj.get(s, 0.0))}, covers elements {{{', '.join(membership.get(s, []))}}}"
                 for s in sets]
    verb = "exactly once (a partition)" if sense == "==" else "at least once (a cover)"
    return (
        f"There are {len(elements)} elements that must each be covered {verb} by the "
        f"sets chosen from the following {len(sets)} candidate sets, each with a fixed "
        "selection cost:\n" + "\n".join(set_lines) +
        "\n\nChoose a subset of the candidate sets, minimizing total selection cost, "
        f"such that every element 0..{max(elements)} is covered {verb}."
    )


def render_assignment_matching(inst: dict) -> str:
    obj = _obj(inst)
    pairs = _vars_by_regex(inst, r"^m_(\d+)_(\d+)$")
    n_agents = len({int(g[0]) for _, g in pairs})
    lines = []
    for v, (i, j) in sorted(pairs, key=lambda t: (int(t[1][0]), int(t[1][1]))):
        lines.append(f"  agent {i} <-> task {j}: cost {_money(obj.get(v['name'], 0.0))}")
    return (
        f"There are {n_agents} agents and {n_agents} tasks. Only the pairs listed below "
        "are allowed (an agent may NOT be assigned to a task not listed); each allowed "
        "pair has an assignment cost:\n" + "\n".join(lines) +
        "\n\nAssign every agent to exactly one allowed task and every task to exactly "
        "one agent (a perfect matching), minimizing total assignment cost."
    )


def render_generalized_assignment(inst: dict) -> str:
    obj = _obj(inst)
    gs = _vars_by_regex(inst, r"^g_(\d+)_(\d+)$")
    n_agents = len({int(g[0]) for _, g in gs})
    n_tasks = len({int(g[1]) for _, g in gs})
    cost_lines = []
    for a in range(n_agents):
        parts = [f"task {j}: cost {_money(obj.get(f'g_{a}_{j}', 0.0))}" for j in range(n_tasks)]
        cost_lines.append(f"  agent {a} -> " + ", ".join(parts))
    cap_lines = []
    for c in _cons_by_prefix(inst, "capacity_"):
        a = c["name"].split("_")[1]
        loads = [f"task {re.match(r'g_(\d+)_(\d+)', n).group(2)}: {_money(v)} units"
                 for n, v in c["coeffs"].items()]
        cap_lines.append(f"  agent {a}: capacity {_money(c['rhs'])} units; each task's load if assigned to this agent -> " + ", ".join(loads))
    return (
        f"There are {n_agents} agents and {n_tasks} tasks. Each task must be assigned to "
        "exactly one agent. The cost of assigning each task to each agent:\n" +
        "\n".join(cost_lines) +
        "\n\nEach agent has a capacity, and assigning a task to an agent consumes some "
        "of that agent's capacity (the amount depends on both agent and task):\n" +
        "\n".join(cap_lines) +
        "\n\nAssign every task to exactly one agent without exceeding any agent's "
        "capacity, minimizing total assignment cost."
    )


# ── scheduling ───────────────────────────────────────────────────────────────────

def render_job_shop(inst: dict) -> str:
    starts = _vars_by_regex(inst, r"^s_(\d+)_(\d+)$")
    n_jobs = len({int(g[0]) for _, g in starts})
    n_mach = len({int(g[1]) for _, g in starts})
    route_rows = sorted(_cons_by_prefix(inst, "route_"), key=lambda c: c["name"])
    job_routes = defaultdict(list)
    for c in route_rows:
        _, j, o = c["name"].split("_")
        dur = c["rhs"]
        job_routes[j].append((o, dur))
    cmax_rows = {c["name"]: c for c in _cons_by_prefix(inst, "cmax_")}
    # The machine each (job, operation-index) pair runs on is only recoverable from
    # the disjunctive "m{machine}_{jobA}b{jobB}" rows' own variable references
    # (s_{jobA}_{opA}, s_{jobB}_{opB}) — NOT from the route_/cmax_ rows above, which
    # only carry durations in per-job operation order. Recover it here so the
    # rendered problem actually names which operations conflict, exactly like a real
    # job-shop instance would.
    op_machine: dict[tuple[str, str], str] = {}
    for c in inst["constraints"]:
        m = re.match(r"^m(\d+)_(\d+)b(\d+)$", c["name"])
        if not m:
            continue
        mach = m.group(1)
        for name in c["coeffs"]:
            sm = re.match(r"^s_(\d+)_(\d+)$", name)
            if sm:
                op_machine[(sm.group(1), sm.group(2))] = mach
    lines = []
    for j, ops in sorted(job_routes.items()):
        seq = sorted(ops, key=lambda x: int(x[0]))
        parts = []
        for o, dur in seq:
            mach = op_machine.get((j, o), "?")
            parts.append(f"(machine {mach}, duration {_money(dur)})")
        last = cmax_rows.get(f"cmax_{j}")
        if last:
            o_last = str(n_mach - 1)
            mach = op_machine.get((j, o_last), "?")
            parts.append(f"(machine {mach}, duration {_money(last['rhs'])})")
        lines.append(f"  job {j}, operations in required order -> " + ", ".join(parts))
    return (
        f"A workshop has {n_jobs} jobs and {n_mach} machines. Each job consists of "
        f"{n_mach} operations that MUST run in the listed order (each operation starts "
        "only after the previous operation of the SAME job finishes); each operation "
        "runs on the stated machine for its stated duration. A machine can process "
        "only one operation at a time across ALL jobs (no two operations on the same "
        "machine may overlap, regardless of which jobs they belong to); operations "
        "cannot be interrupted once started:\n" + "\n".join(lines) +
        "\n\nSchedule every operation's start time to minimize the makespan (the "
        "completion time of the last operation to finish across all jobs), respecting "
        "both each job's fixed operation order and machine exclusivity."
    )


def render_parallel_machine(inst: dict) -> str:
    xs = _vars_by_regex(inst, r"^x_(\d+)_(\d+)$")
    n_jobs = len({int(g[0]) for _, g in xs})
    n_mach = len({int(g[1]) for _, g in xs})
    load_rows = {c["name"]: c for c in _cons_by_prefix(inst, "load_")}
    durs = {}
    for c in load_rows.values():
        for name, coeff in c["coeffs"].items():
            m = re.match(r"^x_(\d+)_\d+$", name)
            if m:
                durs[int(m.group(1))] = coeff
    dur_line = ", ".join(f"job {j}: {_money(durs[j])}" for j in sorted(durs))
    return (
        f"There are {n_jobs} jobs and {n_mach} identical parallel machines. Each job "
        f"has a fixed processing time (independent of which machine runs it): {dur_line}."
        f"\n\nAssign every job to exactly one of the {n_mach} machines (a machine "
        "processes its assigned jobs one at a time, total time = sum of their "
        "durations) to minimize the makespan (the maximum total processing time loaded "
        "onto any one machine)."
    )


def render_rcpsp(inst: dict) -> str:
    starts = _vars_by_regex(inst, r"^x_(\d+)_(\d+)$")
    n_act = len({int(g[0]) for _, g in starts})
    horizon = max(int(g[1]) for _, g in starts) + 1
    prec_rows = _cons_by_prefix(inst, "prec_")
    prec = [tuple(c["name"].split("_")[1:3]) for c in prec_rows]
    cmax_rows = {c["name"]: c["rhs"] for c in _cons_by_prefix(inst, "cmax_")}
    dur = {name.split("_")[1]: rhs for name, rhs in cmax_rows.items()}
    res_rows = _cons_by_prefix(inst, "resource_")
    cap = res_rows[0]["rhs"] if res_rows else None
    req = {}
    for c in res_rows:
        for name, coeff in c["coeffs"].items():
            m = re.match(r"^x_(\d+)_\d+$", name)
            if m:
                req[int(m.group(1))] = max(req.get(int(m.group(1)), 0), coeff)
    act_lines = [f"  activity {a}: duration {_money(dur.get(str(a), 0))}, uses {_money(req.get(a, 0))} units of the shared resource while running"
                 for a in range(n_act)]
    prec_line = ", ".join(f"{i} before {j}" for i, j in prec) or "(none)"
    return (
        f"A project has {n_act} activities to schedule within a horizon of {horizon} "
        "time units (integer start times). Activities:\n" + "\n".join(act_lines) +
        f"\n\nPrecedence requirements (predecessor must FINISH before successor STARTS): "
        f"{prec_line}.\n\nAt most {_money(cap)} units of a single shared renewable "
        "resource are available at any instant; the total resource usage of all "
        "activities running simultaneously may never exceed that. Every activity runs "
        "without interruption once started. Choose integer start times for every "
        "activity minimizing the makespan (completion time of the last activity), "
        "respecting precedence and the resource limit at every instant."
    )


def render_hybrid_flow_shop(inst: dict) -> str:
    ts = _vars_by_regex(inst, r"^t_(\d+)_(\d+)$")
    n_jobs = len({int(g[0]) for _, g in ts})
    n_stages = len({int(g[1]) for _, g in ts})
    machines_per_stage = {}
    for v in inst["variables"]:
        m = re.match(r"^x_\d+_(\d+)_(\d+)$", v["name"])
        if m:
            s, mm = int(m.group(1)), int(m.group(2))
            machines_per_stage[s] = max(machines_per_stage.get(s, 0), mm + 1)
    stageprec = {c["name"].split("_")[1]: c["rhs"] for c in _cons_by_prefix(inst, "stageprec_")}
    cmax = {c["name"].split("_")[1]: c["rhs"] for c in _cons_by_prefix(inst, "cmax_")}
    lines = []
    for j in range(n_jobs):
        lines.append(f"  job {j}: stage 0 duration {_money(stageprec.get(str(j), 0))}, stage 1 duration {_money(cmax.get(str(j), 0))}")
    stage_line = ", ".join(f"stage {s}: {n} parallel identical machines" for s, n in sorted(machines_per_stage.items()))
    return (
        f"A workshop has {n_stages} production stages in a fixed order; every job "
        f"passes through every stage in order 0, 1, .... Each stage has multiple "
        f"identical parallel machines: {stage_line}. A job may use any one machine at "
        "each stage (a machine processes one job at a time, no overlap), and cannot "
        "start a stage until it finished the previous stage. Per-job, per-stage "
        "processing time:\n" + "\n".join(lines) +
        "\n\nAssign each job's operation at each stage to one of that stage's machines "
        "and schedule all start times to minimize the makespan (completion time of the "
        "last job's last stage)."
    )


# ── planning ─────────────────────────────────────────────────────────────────────

def render_lot_sizing(inst: dict) -> str:
    obj = _obj(inst)
    qs = _vars_by_regex(inst, r"^q_(\d+)_(\d+)$")
    n_prod = len({int(g[0]) for _, g in qs})
    n_periods = len({int(g[1]) for _, g in qs})
    balance_rows = {c["name"]: c for c in _cons_by_prefix(inst, "balance_")}
    lines = []
    for p in range(n_prod):
        setup = obj.get(f"u_{p}_0", 0.0)
        unit = obj.get(f"q_{p}_0", 0.0)
        hold = obj.get(f"i_{p}_0", 0.0)
        demand = [_money(balance_rows[f"balance_{p}_{t}"]["rhs"]) for t in range(n_periods) if f"balance_{p}_{t}" in balance_rows]
        lines.append(
            f"  product {p}: setup cost ${_money(setup)} whenever it is produced in a "
            f"period, ${_money(unit)}/unit produced, ${_money(hold)}/unit held in "
            f"inventory to the next period, demand per period = {demand}"
        )
    cap_rows = _cons_by_prefix(inst, "capacity_")
    cap = cap_rows[0]["rhs"] if cap_rows else None
    return (
        f"A factory produces {n_prod} product(s) over {n_periods} time periods to meet "
        "known per-period demand exactly (no shortages, no backlog):\n" + "\n".join(lines) +
        f"\n\nTotal production across ALL products in any single period cannot exceed "
        f"{_money(cap)} units. Inventory starts and ends each product at zero. Decide "
        "production quantity per product per period (and whether that counts as a "
        "'setup' period incurring the setup cost) and resulting inventory, minimizing "
        "total setup + production + holding cost."
    )


def render_unit_commitment(inst: dict) -> str:
    obj = _obj(inst)
    ps = _vars_by_regex(inst, r"^p_(\d+)_(\d+)$")
    n_units = len({int(g[0]) for _, g in ps})
    n_periods = len({int(g[1]) for _, g in ps})
    cap_rows = {c["name"]: c for c in _cons_by_prefix(inst, "cap_")}
    min_rows = {c["name"]: c for c in _cons_by_prefix(inst, "min_")}
    lines = []
    for u in range(n_units):
        pmax = -cap_rows[f"cap_{u}_0"]["coeffs"][f"on_{u}_0"]
        pmin = -min_rows[f"min_{u}_0"]["coeffs"][f"on_{u}_0"]
        marginal = obj.get(f"p_{u}_0", 0.0)
        on_cost = obj.get(f"on_{u}_0", 0.0)
        start_cost = obj.get(f"su_{u}_0", 0.0)
        lines.append(
            f"  unit {u}: if ON in a period, must run between {_money(pmin)} and "
            f"{_money(pmax)} MW, cost ${_money(marginal)}/MW + ${_money(on_cost)} fixed "
            f"per period on; starting it up (OFF in the previous period, ON this one) "
            f"costs an extra ${_money(start_cost)}"
        )
    demand_rows = sorted(_cons_by_prefix(inst, "demand_"), key=lambda c: int(c["name"].split("_")[1]))
    demand_line = ", ".join(f"period {c['name'].split('_')[1]}: {_money(c['rhs'])} MW" for c in demand_rows)
    return (
        f"A power grid has {n_units} generating units over {n_periods} periods.\n"
        + "\n".join(lines) +
        f"\n\nDemand to meet or exceed in each period: {demand_line}."
        "\n\nDecide, for every unit and period, whether it is ON, its output level if "
        "ON, and whether it started up that period, minimizing total operating + "
        "startup cost while meeting demand every period. A unit produces nothing while "
        "OFF."
    )


def render_workforce_shift(inst: dict) -> str:
    obj = _obj(inst)
    pat_vars = [v for v in inst["variables"] if re.match(r"^n\d+$", v["name"])]
    n_pat = len(pat_vars)
    cover_rows = sorted(_cons_by_prefix(inst, "cover_"), key=lambda c: int(c["name"].split("_")[1]))
    days = len(cover_rows)
    pattern_days = defaultdict(list)
    for c in cover_rows:
        d = c["name"].split("_")[1]
        for name in c["coeffs"]:
            if name.startswith("n"):
                pattern_days[name].append(d)
    lines = [f"  pattern {p['name']}: covers days {{{', '.join(pattern_days.get(p['name'], []))}}}, cost ${_money(obj.get(p['name'], 0.0))} per worker assigned to it"
             for p in pat_vars]
    demand_line = ", ".join(f"day {c['name'].split('_')[1]}: >= {_money(c['rhs'])} workers" for c in cover_rows)
    has_overtime = any(v["name"].startswith("o") and re.match(r"^o\d+$", v["name"]) for v in inst["variables"])
    ot_note = (
        " Overtime workers may also be used on any day at a fixed cost per day, "
        "counted toward that day's coverage."
        if has_overtime else ""
    )
    return (
        f"A staffing manager must cover {days} days of demand using {n_pat} available "
        "shift patterns, each covering a fixed subset of days. Assign a non-negative "
        "integer number of workers to each pattern (cost is per worker assigned, paid "
        "once regardless of how many days that pattern covers):\n" + "\n".join(lines) +
        f"\n\nMinimum workers required each day: {demand_line}." + ot_note +
        "\n\nMinimize total cost while covering every day's minimum requirement."
    )


def render_inventory_routing(inst: dict) -> str:
    obj = _obj(inst)
    q_vars = _vars_by_regex(inst, r"^q_(\d+)_(\d+)$")
    n_cust = len({int(g[0]) for _, g in q_vars})
    n_periods = len({int(g[1]) for _, g in q_vars})
    balance_rows = {c["name"]: c for c in _cons_by_prefix(inst, "balance_")}
    demand_lines = []
    dem = defaultdict(list)
    for name, c in balance_rows.items():
        _, cu, t = name.split("_")
        dem[cu].append((t, c["rhs"]))
    for cu, vals in sorted(dem.items()):
        demand_lines.append(f"  customer {cu}: demand per period = {[_money(r) for _, r in sorted(vals, key=lambda x: int(x[0]))]}")
    route_costs = sorted({name: coeff for name, coeff in obj.items() if name.startswith("z_")}.items())
    route_lines = [f"  {name}: round-trip cost {_money(c)}" for name, c in route_costs]
    more = ""
    Q_rows = _cons_by_prefix(inst, "vehcap_")
    Q = Q_rows[0]["rhs"] if Q_rows else None
    return (
        f"A depot delivers to {n_cust} customers over {n_periods} periods using a "
        f"single vehicle of capacity {_money(Q)} units per trip. Every possible subset "
        "of customers a single trip could visit has a precomputed round-trip cost "
        "(distance-based); at most one such route may be used per period:\n" +
        "\n".join(route_lines) + more +
        "\n\nEach customer's known demand per period (must be met exactly via a "
        "delivery quantity that period, tracked through carried inventory, capacity 25 "
        "units, starting and implicitly available to carry forward):\n" +
        "\n".join(demand_lines) +
        "\n\nA customer can only receive a delivery in a period if the route chosen "
        "that period visits it. Choose, for each period, at most one route and each "
        "visited customer's delivery quantity (bounded by vehicle capacity), and each "
        "customer's inventory carried forward, meeting all demand exactly while "
        "minimizing total routing + inventory-holding cost."
    )


# ── routing ──────────────────────────────────────────────────────────────────────

def render_tsp(inst: dict) -> str:
    obj = _obj(inst)
    edges = _vars_by_regex(inst, r"^e_(\d+)_(\d+)$")
    n = len({int(g) for _, gr in edges for g in gr})
    lines = []
    seen = set()
    for v, (i, j) in edges:
        key = tuple(sorted((int(i), int(j))))
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"  city {i} <-> city {j}: distance {_money(obj.get(v['name'], 0.0))}")
    return (
        f"A salesperson must visit all {n} cities (numbered 0..{n - 1}), returning to "
        "the start, visiting each city exactly once. Distances between city pairs:\n" +
        "\n".join(sorted(lines)) +
        "\n\nFind the tour (a single cycle through all cities) minimizing total "
        "distance traveled."
    )


def render_cvrp(inst: dict) -> str:
    obj = _obj(inst)
    xs = _vars_by_regex(inst, r"^x_(\d+)_(\d+)$")
    n = len({int(g) for _, gr in xs for g in gr})
    n_cust = n - 1
    depot_out = next(c for c in inst["constraints"] if c["name"] == "depot_out")
    K = depot_out["rhs"]
    drop_rows = {c["name"]: c for c in _cons_by_prefix(inst, "drop_")}
    demand = {name.split("_")[1]: c["rhs"] for name, c in drop_rows.items()}
    link_rows = _cons_by_prefix(inst, "link_")
    Q = None
    for c in link_rows:
        for name, coeff in c["coeffs"].items():
            if name.startswith("x_") and coeff != 0:
                Q = -c["coeffs"].get(name.replace("x_", "x_"), 0)
        break
    # Q is the negative coefficient on the matching x_ var in the same link row.
    Q = None
    for c in link_rows:
        xname = next(n_ for n_ in c["coeffs"] if n_.startswith("x_"))
        Q = -c["coeffs"][xname]
        break
    dist_lines = []
    seen = set()
    for v, (i, j) in xs:
        key = tuple(sorted((int(i), int(j))))
        if key in seen:
            continue
        seen.add(key)
        dist_lines.append(f"  node {i} <-> node {j}: distance {_money(obj.get(v['name'], 0.0))}")
    demand_line = ", ".join(f"customer {c}: {_money(d)} units" for c, d in sorted(demand.items(), key=lambda x: int(x[0])))
    return (
        f"A depot (node 0) dispatches exactly {int(K)} vehicles, each of capacity "
        f"{_money(Q)} units, to serve {n_cust} customers (nodes 1..{n_cust}). Distances "
        "between every pair of nodes:\n" + "\n".join(sorted(dist_lines)) +
        f"\n\nCustomer demands: {demand_line}."
        "\n\nEvery vehicle starts and ends at the depot; every customer is visited by "
        "exactly one vehicle exactly once; a vehicle's total delivered demand may not "
        "exceed its capacity. Minimize the combined distance traveled by all vehicles."
    )


def render_tsptw(inst: dict) -> str:
    obj = _obj(inst)
    xs = _vars_by_regex(inst, r"^x_(\d+)_(\d+)$")
    n = len({int(g) for _, gr in xs for g in gr})
    n_cust = n - 1
    windows = {}
    for v in inst["variables"]:
        m = re.match(r"^t_(\d+)$", v["name"])
        if m and m.group(1) != "0":
            windows[m.group(1)] = (v.get("lower"), v.get("upper"))
    dist_lines = []
    for v, (i, j) in xs:
        dist_lines.append(f"  node {i} -> node {j}: distance {_money(obj.get(v['name'], 0.0))}")
    win_line = ", ".join(f"customer {c}: arrive within [{_money(lo)}, {_money(hi)}]" for c, (lo, hi) in sorted(windows.items(), key=lambda x: int(x[0])))
    return (
        f"A single vehicle starts and ends at the depot (node 0), visiting {n_cust} "
        f"customers (nodes 1..{n_cust}) exactly once each, in some order. Travel "
        "distances/times (also used as time advance) between every ordered pair of "
        "nodes:\n" + "\n".join(dist_lines) +
        f"\n\nEach customer requires the vehicle to arrive within a fixed time window "
        f"(the vehicle may wait if it arrives early, and a 2-unit service time is spent "
        f"at each customer before departing): {win_line}."
        "\n\nFind the visiting order (a single tour through all customers and back to "
        "the depot) and arrival times satisfying every time window, minimizing total "
        "travel distance."
    )


def render_hf_vrp(inst: dict) -> str:
    obj = _obj(inst)
    xs = _vars_by_regex(inst, r"^x1_(\d+)_(\d+)$")
    n = len({int(g) for _, gr in xs for g in gr})
    n_cust = n - 1
    drop_rows = {c["name"]: c for c in _cons_by_prefix(inst, "drop_")}
    demand = {name.split("_")[1]: c["rhs"] for name, c in drop_rows.items()}
    demand_line = ", ".join(f"customer {c}: {_money(d)} units" for c, d in sorted(demand.items(), key=lambda x: int(x[0])))
    dist1 = {}
    dist2 = {}
    for v in inst["variables"]:
        m = re.match(r"^x1_(\d+)_(\d+)$", v["name"])
        if m:
            dist1[(m.group(1), m.group(2))] = obj.get(v["name"], 0.0)
        m = re.match(r"^x2_(\d+)_(\d+)$", v["name"])
        if m:
            dist2[(m.group(1), m.group(2))] = obj.get(v["name"], 0.0)
    fixed1 = obj.get("use1", 0.0)
    fixed2 = obj.get("use2", 0.0)
    q1_row = next((c for c in inst["constraints"] if c["name"] == "fleetcap1"), None)
    q2_row = next((c for c in inst["constraints"] if c["name"] == "fleetcap2"), None)
    q1 = q1_row["rhs"] if q1_row else None
    q2 = q2_row["rhs"] if q2_row else None
    return (
        f"A depot (node 0) may dispatch up to one vehicle of each of TWO available "
        f"types to serve {n_cust} customers (nodes 1..{n_cust}), each demand:\n"
        f"  {demand_line}\n\n"
        f"Type 1: capacity {_money(q1)} units, fixed dispatch cost ${_money(fixed1)}, "
        f"per-unit-distance cost multiplier 1.0. Type 2: capacity {_money(q2)} units, "
        f"fixed dispatch cost ${_money(fixed2)}, per-unit-distance cost multiplier "
        "1.25 (both use the same underlying distances between nodes; type 2's arc cost "
        "is 1.25x type 1's for the same arc)."
        f"\n\nAll type-1 arc costs (distance x 1.0; every ordered pair of nodes, since "
        "the network need not be symmetric): " +
        ", ".join(f"{i}->{j}: {_money(c)}" for (i, j), c in sorted(dist1.items(), key=lambda t: (int(t[0][0]), int(t[0][1])))) +
        "\n\nEach dispatched vehicle starts and ends at the depot; every customer is "
        "visited exactly once by exactly one of the (at most two) dispatched vehicles; "
        "a vehicle's delivered demand may not exceed its capacity. Decide which "
        "vehicle type(s) to dispatch and each dispatched vehicle's route, minimizing "
        "total fixed dispatch cost + distance cost."
    )


# ── combinatorial ────────────────────────────────────────────────────────────────

def render_multidim_knapsack(inst: dict) -> str:
    obj = _obj(inst)
    items = sorted(v["name"] for v in inst["variables"])
    budgets = _cons_by_prefix(inst, "budget_")
    item_lines = []
    for it in items:
        weights = [f"budget {c['name'].split('_')[1]}: {_money(c['coeffs'].get(it, 0.0))}" for c in budgets]
        item_lines.append(f"  {it}: value {_money(obj.get(it, 0.0))}, uses -> " + ", ".join(weights))
    budget_line = ", ".join(f"budget {c['name'].split('_')[1]}: capacity {_money(c['rhs'])}" for c in budgets)
    return (
        f"There are {len(items)} items to choose from, each usable at most once, and "
        f"{len(budgets)} independent resource budgets. Per item, its value and its "
        "consumption of each budget:\n" + "\n".join(item_lines) +
        f"\n\nBudget capacities: {budget_line}."
        "\n\nChoose a subset of items maximizing total value without exceeding any "
        "budget's capacity."
    )


def render_graph_coloring(inst: dict) -> str:
    n_colors_row = [v for v in inst["variables"] if re.match(r"^y\d+$", v["name"])]
    n_colors = len(n_colors_row)
    edges = set()
    for c in inst["constraints"]:
        m = re.match(r"^edge_(\d+)_(\d+)_c\d+$", c["name"])
        if m:
            edges.add((int(m.group(1)), int(m.group(2))))
    verts = sorted({int(m.group(1)) for c in inst["constraints"] for m in [re.match(r"^colour_(\d+)$", c["name"])] if m})
    edge_line = ", ".join(f"{u}-{w}" for u, w in sorted(edges))
    return (
        f"A graph has vertices {{{', '.join(str(v) for v in verts)}}} and the following "
        f"undirected edges: {edge_line}.\n\nAssign each vertex one of up to {n_colors} "
        "available colours such that no edge connects two same-coloured vertices, "
        "using as FEW distinct colours as possible (minimize the number of colours "
        "actually used, i.e. the chromatic number)."
    )


def render_set_packing(inst: dict) -> str:
    obj = _obj(inst)
    sets = sorted(v["name"] for v in inst["variables"])
    membership = defaultdict(list)
    for c in inst["constraints"]:
        m = re.match(r"^conflict_(\d+)$", c["name"])
        if not m:
            continue
        e = m.group(1)
        for name in c["coeffs"]:
            membership[name].append(e)
    set_lines = [f"  {s}: value {_money(obj.get(s, 0.0))}, conflicts on elements {{{', '.join(membership.get(s, []))}}}"
                 for s in sets]
    return (
        f"There are {len(sets)} candidate sets to choose from, each with a value, and "
        "some pairs (or groups) of sets 'conflict' by sharing an element — at most one "
        "set from each conflicting group may be selected. Sets and the elements "
        "driving their conflicts:\n" + "\n".join(set_lines) +
        "\n\nChoose a subset of the sets, maximizing total value, such that for every "
        "shared element, at most one selected set contains it."
    )


def render_logical_csp(inst: dict) -> str:
    obj = _obj(inst)
    binaries = sorted(v["name"] for v in inst["variables"])
    rule_lines = []
    for c in inst["constraints"]:
        vs = list(c["coeffs"].keys())
        if c["name"].startswith("imply_"):
            rule_lines.append(f"  if {vs[0]}=1 then {vs[1]}=1 (implication)")
        elif c["name"].startswith("conflict_"):
            rule_lines.append(f"  not both {vs[0]}=1 and {vs[1]}=1 (mutual exclusion)")
        elif c["name"].startswith("amo_"):
            rule_lines.append(f"  at most one of {{{', '.join(vs)}}} may be 1")
        elif c["name"].startswith("clause_"):
            rule_lines.append(f"  at least one of {{{', '.join(vs)}}} must be 1")
    value_line = ", ".join(f"{b}: {_money(obj.get(b, 0.0))}" for b in binaries)
    return (
        f"There are {len(binaries)} binary decisions to make ({', '.join(binaries)}), "
        f"each contributing a value if set to 1: {value_line}.\n\n"
        "The following logical rules constrain which combinations are allowed:\n" +
        "\n".join(rule_lines) +
        "\n\nChoose a 0/1 setting for every decision, satisfying every rule, "
        "maximizing the total value of decisions set to 1."
    )


RENDERERS = {
    "min_cost_flow": render_min_cost_flow,
    "max_flow": render_max_flow,
    "rc_shortest_path": render_rc_shortest_path,
    "cap_network_design": render_cap_network_design,
    "time_expanded_flow": render_time_expanded_flow,
    "facility_location": render_facility_location,
    "p_median_center": render_p_median_center,
    "set_cover_partition": render_set_cover_partition,
    "assignment_matching": render_assignment_matching,
    "generalized_assignment": render_generalized_assignment,
    "job_shop": render_job_shop,
    "parallel_machine": render_parallel_machine,
    "rcpsp": render_rcpsp,
    "hybrid_flow_shop": render_hybrid_flow_shop,
    "lot_sizing": render_lot_sizing,
    "unit_commitment": render_unit_commitment,
    "workforce_shift": render_workforce_shift,
    "inventory_routing": render_inventory_routing,
    "tsp": render_tsp,
    "cvrp": render_cvrp,
    "tsptw": render_tsptw,
    "hf_vrp": render_hf_vrp,
    "multidim_knapsack": render_multidim_knapsack,
    "graph_coloring": render_graph_coloring,
    "set_packing": render_set_packing,
    "logical_csp": render_logical_csp,
}


def render_instance(inst: dict) -> str:
    sub = inst["subcategory"]
    fn = RENDERERS.get(sub)
    if fn is None:
        raise KeyError(f"no NL renderer registered for subcategory {sub!r}")
    return fn(inst)
