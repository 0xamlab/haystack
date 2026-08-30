---
icon: circle-nodes
description: Scalar formulas for compiling an execution graph, scoring decisions walked over a graph under real constraints, and blending ML, simulation and symbolic rules into one reasoning step.
---

# Graph-based reasoning kernels

Three modules for the arithmetic underneath three different kinds of graph-shaped decision: how a
compiler should lower a computation graph into an executable form (fuse these two ops or keep them
separate, eliminate that dead node, pick this kernel over that one), how a router or planner should
score one edge of a graph it is walking (under cost and risk together, under a flow capacity, under
a time window, under a resource budget), and how an agent should decide *how to reason at all* at a
given step (trust the model's own output, fall back to a slower simulation, blend the two, gate on
a symbolic rule, switch reasoning mode under a time budget). All three modules share the same shape:
every function is a pure scalar formula — a handful of `Float64` arguments in, one `Float64` out —
with zero Python imports and no graph object, adjacency list, or neural network anywhere in the
implementation. The caller supplies whatever graph, plan, or model output is being scored; these
modules only compute the number that scoring produces.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# Should the compiler fuse op_a -> op_b? benefit = shared_intermediate_bytes - fusion_overhead
runtime.execute("graph_compiler", "fusion_benefit_score",
                [1000000.0, 2000000.0, 500000.0, 50000.0])["result"]
# 450000.0 — positive: fusing eliminates 500 KB of intermediate tensor for 50 KB of overhead

# Is there enough time budget to run full simulation on a hard problem?
runtime.execute("hybrid_reasoning", "meta_reasoning_switch", [0.9, 300.0, 10.0, 200.0])["result"]
# 2.0 — 300ms covers ml_latency + sim_latency (210ms) and complexity (0.9) is past the 0.7 cutoff
```

## The modules

| Module | What it does |
| --- | --- |
| `graph_compiler` | Op-fusion benefit, dead-op elimination, constant folding, cache-locality op-reorder priority, a common-subexpression hash, graph-partition cut cost, broadcast shape inference, dtype-promotion width, kernel-selection score, and tensor memory-layout transform cost. |
| `graph_decision` | Multi-objective (cost/risk) edge relaxation, max-flow residual capacity and augmenting-path bottleneck, time-decayed edge weight, probabilistic route scoring, resource-budget-penalized path cost, time-window edge validity, edge criticality, supply-chain slack, and discounted decision-node utility. |
| `hybrid_reasoning` | ML/simulation blending and the cost-benefit of running simulation at all, feasibility-gated optimization objectives, quadratic rule-violation penalty, rollout-value blending, counterfactual scoring, symbolic constraint satisfaction, reasoning-chain coherence, combined epistemic+aleatoric uncertainty, and a three-way fast-ML/hybrid/full-simulation mode switch. |

## Scalar formulas, not graph algorithms

`graph_decision` sits next to [`graph_analytics`](sparse-and-graph.md) in the runtime's library
list, and the names invite confusion, but the two are not overlapping implementations of the same
thing. `graph_analytics.adjacency`, `.centrality`, `.community`, and `.temporal` — documented in
[Sparse systems & graph analytics](sparse-and-graph.md) — take an actual compressed adjacency
(`row_ptr`, `targets`, `weights`) and *run* a traversal: Dijkstra, Brandes betweenness, Louvain
community detection, time-respecting reachability. They own the loop, and they return arrays
(`distance`, `reached`, community labels) describing the whole graph.

`graph_decision` never takes a graph as an argument. Each function computes one edge's or one
node's contribution to a score that some caller-owned traversal is accumulating —
`multi_constraint_relax` is the per-edge relaxation step a Pareto-weighted Dijkstra variant would
call once per edge it examines, not a shortest-path search in its own right; `flow_augment_amount`
is the bottleneck-update step inside an augmenting-path max-flow loop, not the max-flow algorithm.
If you need an actual shortest path or a max-flow value from a stored graph, that traversal lives in
`graph_analytics` (or `graph.weighted.bellman_ford` for negative edge weights); if you need to score
one edge of a graph you are walking with your own logic — because the edge weight itself depends on
elapsed time, a resource budget, or two competing objectives — that is what `graph_decision`
computes. The same separation holds for `graph_compiler` (formulas a compiler's pass would apply to
one node or one op-pair, not a compiler) and `hybrid_reasoning` (formulas one reasoning step would
apply, not a reasoning engine).

## `graph_compiler`: worked examples

Every example below follows directly from the formula in the function's docstring in
`mojo/engine/graph_compiler.mojo` — see [Verification](#verification) for why these are hand-traced
rather than lifted from the test file.

```python
# fusion_benefit_score: shared_intermediate_bytes - fusion_overhead (op sizes are unused)
runtime.execute("graph_compiler", "fusion_benefit_score",
                [1000000.0, 2000000.0, 500000.0, 50000.0])["result"]
# 450000.0

# op_reorder_priority: compute_intensity / ((cache_miss_cost + 1) * (dependency_depth + 1))
runtime.execute("graph_compiler", "op_reorder_priority", [3.0, 8.0, 1.0])["result"]
# 1.0 — 8.0 / ((3+1) * (1+1)) = 8.0 / 8.0

# common_subexpr_hash: op_type * 31^2 + input_hash_a * 31 + input_hash_b
runtime.execute("graph_compiler", "common_subexpr_hash", [2.0, 5.0, 7.0])["result"]
# 2084.0 — 2*961 + 5*31 + 7 = 1922 + 155 + 7

# shape_inference_broadcast: NumPy-style, one dim of 1 wins, mismatch is -1.0
runtime.execute("graph_compiler", "shape_inference_broadcast", [1.0, 8.0])["result"]  # 8.0
runtime.execute("graph_compiler", "shape_inference_broadcast", [3.0, 4.0])["result"]  # -1.0

# memory_layout_transform_cost: n_elements * max(src_stride, dst_stride) * dtype_bytes
runtime.execute("graph_compiler", "memory_layout_transform_cost", [1024.0, 1.0, 4.0, 4.0])["result"]
# 16384.0 — 1024 * max(1, 4) * 4
```

`fusion_benefit_score` takes `op_a_memory_bytes` and `op_b_memory_bytes` as declared parameters but
the source (`return shared_intermediate_bytes - fusion_overhead`) never reads either one — the
per-op memory totals are there for a caller who wants to log them alongside the score, not because
the formula uses them. `dead_op_elimination_check(output_consumer_count, grad_flow)` returns `1.0`
(eliminate) only when both are `<= 0.0` — `(0.0, 0.0) -> 1.0`, but `(0.0, 0.001) -> 0.0`, because a
consumerless op with any residual gradient flow is still live for backward-pass purposes.
`constant_folding_value(is_constant, computed_value)` treats `is_constant` as a probability-style
gate at `0.5`, not a strict boolean check (`is_constant > 0.5`), so a caller passing `1` or `0`
directly works, but a caller passing a soft confidence score below `0.5` gets `0.0` folded — the
non-constant sentinel — rather than the computed value.

## `graph_decision`: worked examples

```python
# multi_constraint_relax: dist_u + alpha*edge_cost + (1-alpha)*edge_risk
runtime.execute("graph_decision", "multi_constraint_relax",
                [10.0, 5.0, 2.0, 0.0, 0.0, 0.7])["result"]
# 14.1 — 10 + 0.7*5 + 0.3*2 (dist_v_cost, dist_v_risk are accepted but not used in the return)

# dynamic_edge_weight_decay: base_weight * exp(-decay_rate * time_elapsed)
runtime.execute("graph_decision", "dynamic_edge_weight_decay", [100.0, 2.0, 0.1])["result"]
# 81.87307530779819

# resource_constrained_cost: adds a penalty only once the resource budget is exceeded
runtime.execute("graph_decision", "resource_constrained_cost",
                [10.0, 5.0, 12.0, 10.0, 2.0])["result"]
# 19.0 — new_cost = 15.0, violation = 12-10 = 2.0, penalty = 2*2 = 4.0, 15+4 = 19.0
runtime.execute("graph_decision", "resource_constrained_cost",
                [10.0, 5.0, 8.0, 10.0, 2.0])["result"]
# 15.0 — resource_used (8.0) is under budget, no penalty added

# network_criticality: betweenness * utilisation, utilisation clamped to 1.0
runtime.execute("graph_decision", "network_criticality", [0.8, 15.0, 10.0])["result"]
# 0.8 — flow (15) exceeds capacity (10), utilisation clamps to 1.0 instead of 1.5

# decision_graph_utility: probability * outcome_value * discount_factor ** time_steps
runtime.execute("graph_decision", "decision_graph_utility", [1000.0, 0.6, 0.9, 3.0])["result"]
# 437.40000000000003 — 0.6 * 1000 * 0.9^3
```

`decision_graph_utility` computes `discount_factor ** time_steps` as
`exp(time_steps * log(discount_factor))` rather than calling a `pow`, with the `discount_factor`
floored at `1e-300` before the log if it is `<= 0.0` (a raw `log(0.0)` would be `-inf`, and
`-inf * time_steps` for `time_steps > 0` would poison the result to `-inf`/`nan` instead of
returning a well-defined, if degenerate, utility). One consequence worth knowing: at
`time_steps = 0.0`, the multiplication `time_steps * log(discount_factor)` is `0.0` regardless of
how invalid `discount_factor` is (`0.0 * -690.78 == -0.0`, not `nan`), so
`decision_graph_utility(1000.0, 0.6, 0.0, 0.0)` still returns `600.0` — the mathematically correct
`γ⁰ = 1` — rather than blowing up on a zero discount factor, as long as no time has actually elapsed.

## `hybrid_reasoning`: worked examples

`meta_reasoning_switch` is the mode dispatcher this family's opening example calls; its three return
values (`0.0` fast ML, `1.0` hybrid, `2.0` full simulation) come from three branches checked in a
fixed order — the time budget is checked before problem complexity, so a genuinely hard problem
still gets routed to fast-ML-only if the budget can't even cover one ML call:

```python
# Budget too tight for even one ML call: fast approximation is all that fits, complexity ignored
runtime.execute("hybrid_reasoning", "meta_reasoning_switch", [0.9, 5.0, 10.0, 200.0])["result"]
# 0.0

# Budget covers ML, problem is simple (complexity < 0.3): ML only
runtime.execute("hybrid_reasoning", "meta_reasoning_switch", [0.2, 300.0, 10.0, 200.0])["result"]
# 0.0

# Budget covers both stages, moderate complexity: neither fast-path condition fires
runtime.execute("hybrid_reasoning", "meta_reasoning_switch", [0.5, 300.0, 10.0, 200.0])["result"]
# 1.0 — hybrid
```

```python
# ml_confidence_simulation_cost: (1 - confidence) * expected_gain - simulation_cost
runtime.execute("hybrid_reasoning", "ml_confidence_simulation_cost", [0.3, 50.0, 100.0])["result"]
# 20.0 — low confidence, high potential gain: worth running the simulation
runtime.execute("hybrid_reasoning", "ml_confidence_simulation_cost", [0.9, 50.0, 100.0])["result"]
# -40.0 — high confidence: the simulation's expected gain doesn't cover its cost

# symbolic_constraint_score: 1.0 inside [lower, upper], exp(-distance) outside
runtime.execute("hybrid_reasoning", "symbolic_constraint_score", [5.0, 0.0, 10.0])["result"]
# 1.0 — inside the bound
runtime.execute("hybrid_reasoning", "symbolic_constraint_score", [15.0, 0.0, 10.0])["result"]
# 0.006737946999085467 — exp(-5), 5.0 past the upper bound

# reasoning_chain_coherence: step_confidence ** n_steps * dependency_strength
runtime.execute("hybrid_reasoning", "reasoning_chain_coherence", [0.9, 5.0, 0.8])["result"]
# 0.47239200262439995 — 0.9^5 (~0.5905) * 0.8; confidence compounds multiplicatively over steps

# hybrid_uncertainty_estimate: sqrt(epistemic^2 + aleatoric^2) + model_disagreement
runtime.execute("hybrid_reasoning", "hybrid_uncertainty_estimate", [3.0, 4.0, 0.5])["result"]
# 5.5 — sqrt(9 + 16) = 5.0 (the classic 3-4-5 triangle again), + 0.5 disagreement
```

`reasoning_chain_coherence` clamps `step_confidence` to `1.0` before exponentiating (a confidence
above 1.0 would otherwise make coherence *increase* with chain length, the opposite of the intended
"errors compound" behavior) and adds `1e-9` inside the log to keep `step_confidence = 0.0` from
computing `log(0.0)`; the function has its own explicit early return of `0.0` for
`step_confidence <= 0.0`, so that epsilon only ever matters for the boundary case of exactly `0.0`
reaching the log call on the way to that early return being taken.

## Every function refuses to be silently wrong about a boundary, not just a bad input

None of these formulas validate their inputs the way `tensorx` or `sparse_numerics` do — there is no
shape or dtype to check, only floats — but several guard the specific arithmetic edge case that
would otherwise produce a wrong-but-plausible number:

- `flow_residual_capacity` clamps `capacity - current_flow` at `0.0` rather than returning a
  negative residual, which a caller feeding it into `flow_augment_amount`'s `min()` could otherwise
  select as a valid (negative) augmenting amount.
- `graph_partition_cost` and `op_reorder_priority` both guard their denominators
  (`n_devices <= 0.0`, and `cache_miss_cost`/`dependency_depth` combined `<= 0.0`) and fall back to
  the numerator alone rather than dividing by zero into `inf`/`nan`.
- `network_criticality` clamps `flow / capacity` at `1.0` — over-utilised is reported as fully
  utilised, not as a criticality index above the nominal 0–1 range the docstring promises.
- `hybrid_uncertainty_estimate` and `decision_graph_utility` both route their exponent/root through
  guarded intermediate math (a floored discount factor before `log`, `sqrt` of a sum of squares
  which is never negative) so a degenerate input produces a defined, if extreme, number rather than
  `nan`.

## Verification

`mojo/tests/libs/test_graph_compiler.mojo`, `test_graph_decision.mojo`, and
`test_hybrid_reasoning.mojo` are auto-generated coverage smoke tests: each calls every function in
its module exactly once with the same shared placeholder arguments (mostly `0.5`) and checks only
that the scalar result is finite — they assert no specific numeric output, so there is nothing in
these three test files to lift a worked example from. Every number in this page was instead computed
independently, either by hand from the formula documented in the function's docstring in
`mojo/engine/graph_compiler.mojo`, `graph_decision.mojo`, and `hybrid_reasoning.mojo`, or
cross-checked with a standalone Python calculation (`math.exp`, `math.log`, `math.sqrt`, no
library), matching the same approach used for the classical-ML worked examples in
[Classical ML algorithms](ml-classical-algorithms.md). Every number given can be reproduced by
re-running the same arithmetic.

**Next:** see [Sparse systems & graph analytics](sparse-and-graph.md) for the traversal algorithms
(Dijkstra, betweenness, Louvain, temporal reachability) these modules' formulas score edges and
nodes for but do not themselves run, or [Causal inference](causal-inference.md) for identification-
first counterfactual estimation on a declared DAG, a stricter relative of
`hybrid_reasoning.counterfactual_reasoning_score`'s plain what-if scalar.
