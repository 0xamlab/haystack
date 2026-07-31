---
icon: bullseye
description: Solve linear, integer, assignment and network-flow programs with compiled kernels on your own machine — and be told when no answer exists.
---

# Optimization & decision programs

Six kernel families for problems where you are choosing, not measuring: linear programs,
mixed-integer programs, assignment, network flow, and the surfaces that explain what came
back. All run as compiled kernels inside the runtime that ships with the SDK — there is
nothing to start and nothing to install separately.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

LE, EQ, GE = 0, 1, 2

# maximise 3x + 5y  subject to  x <= 4,  2y <= 12,  3x + 2y <= 18,  x, y >= 0
out = runtime.execute("optimization.linear", "lp_solve_default", [
    [3.0, 5.0],                        # objective coefficients
    [1.0, 0.0, 0.0, 2.0, 3.0, 2.0],    # constraint matrix, row-major
    3, 2,                              # rows, columns
    [LE, LE, LE],
    [4.0, 12.0, 18.0],                 # right-hand sides
    True,                              # maximise
])
r = out["result"]
r["status"]      # 0 — optimal
r["objective"]   # 36.0
r["x"]           # [2.0, 6.0]
r["duals"]       # one shadow price per row
```

A matrix crosses as a flat row-major list plus its `rows` and `cols`, the same convention
the rest of the engine uses. Constraint senses are `0` for `<=`, `1` for `==`, `2` for `>=`.

## The modules

| Module | What it does |
| --- | --- |
| `optimization.model` | variables with bounds, kinds and warm starts; objectives and constraints as expressions; whole-model validation; projection of a point onto the box and the integer grid |
| `optimization.linear` | linear programs — optimum, duals, reduced costs, activity, slack, the final basis, right-hand-side ranges, and recovery of a linear form from an expression |
| `optimization.integer` | mixed-integer programs by branch and bound — incumbent, best bound, gap, node census, branching choice, and a knapsack entry point |
| `optimization.assignment` | optimal agent-to-task assignment with dual potentials, forbidden pairings as a mask, cost scoring, and outside verification of a matching you were handed |
| `optimization.flow` | maximum flow with the minimum cut as data, min-cost flow to a target or at maximum flow, network validation, residuals, bottlenecks, and auditing a flow you were handed |
| `optimization.explain` | why the answer is what it is — binding rows and their prices, an infeasibility core, objective decomposition, complementary-slackness audit |

## An answer that does not exist is reported absent

This is the difference between these kernels and a solver that returns numbers. A program
can fail to have an optimum in several ways, and every one of them leaves a plausible
vector lying around inside the algorithm. None of them is returned.

An infeasible program comes back with **no solution vector at all**, and says how far from
feasible it is:

```python
# x + y <= 1 and x + y >= 3 cannot both hold
out = runtime.execute("optimization.linear", "lp_solve_default", [
    [1.0, 1.0], [1.0, 1.0, 1.0, 1.0], 2, 2, [LE, GE], [1.0, 3.0], True,
])
r = out["result"]
r["has_objective"]    # False
r["x"]                # [] — not "the closest point"
r["infeasibility"]    # 2.0 — the gap between the two right-hand sides
runtime.execute("optimization.linear", "lp_status_name", [r["status"]])["result"]
# "infeasible"
```

An unbounded program does not return the last vertex it visited, which has a perfectly
finite objective value and is not an optimum:

```python
# maximise x + y subject only to x - y <= 1: y can grow forever
r = runtime.execute("optimization.linear", "lp_solve_default", [
    [1.0, 1.0], [1.0, -1.0], 1, 2, [LE], [1.0], True,
])["result"]
r["has_objective"]         # False
r["x"]                     # []
r["unbounded_variable"]    # 1 — the direction that runs away
```

A solver that ran out of iterations has not solved anything, so it reports
`iteration_limit` with nothing attached rather than handing back the iterate it happened to
be sitting on. `has_objective` is the authority throughout; `objective` is `0.0` padding
when it is `False`, never a claim.

Why this matters more than it sounds: a wrong answer here does not look wrong. It is a
vector of plausible numbers under a success status, and everything downstream will branch on
it. **A solver that returns a confident wrong answer is worse than one that declines**,
because declining is actionable and a fabricated optimum is not.

### A truncated search reports its gap instead of claiming optimality

Branch and bound takes a node budget, and hitting it is a normal outcome rather than an
error. The result then carries the incumbent it did find, the bound on everything it did not
explore, and the distance between them:

```python
INTEGER = 1

# maximise 5x + 8y  s.t.  x + y <= 6,  5x + 9y <= 45,  x, y integer >= 0
args = [[5.0, 8.0], [1.0, 1.0, 5.0, 9.0], 2, 2, [LE, LE], [6.0, 45.0], True,
        [INTEGER, INTEGER]]

full = runtime.execute("optimization.integer", "milp_solve_default", [*args, 500])["result"]
full["objective"]                # 40.0 at x = [0.0, 5.0]
full["proven_optimal"]           # True
full["gap"]                      # 0.0
full["relaxation_objective"]     # 41.25 — what the LP alone would have told you

capped = runtime.execute("optimization.integer", "milp_solve_default", [*args, 3])["result"]
capped["objective"]              # 39.0 — a real feasible point
capped["proven_optimal"]         # False
capped["gap"]                    # 2.111... — what is still unaccounted for
capped["nodes_open"]             # 2 — regions never looked at
```

`feasible`, `proven_optimal` and `search_complete` are three separate facts and a solver
that ships one of them in place of the others is exactly the problem. A budget can be hit
after the surviving bounds already closed the gap, in which case the answer *is* optimal
and says so; a budget can also be hit before any integer point was found at all, in which
case there is a real bound, no answer, and `has_gap` is `False` — because a gap of `0.0`
claims proven optimality and an unknown gap must not be padded with it.

The relaxation value travels out alongside, because "the continuous relaxation said 41.25
and the integer answer is 40" is the first thing anyone checks — and rounding the relaxation
is the classic way to produce an integral point that is not optimal, or not even feasible.

## Duals, reduced costs and right-hand-side ranges

An optimum answers "what should I do". The duals answer "what is each constraint costing
me", and a dual without its range of validity invites a caller to extrapolate a linear
prediction that stops being true at a vertex they cannot see. So the range comes with it:

```python
r = runtime.execute("optimization.linear", "lp_rhs_ranges", [
    [5.0, 4.0, 3.0],                                    # objective
    0.0,                                                # objective constant
    [2.0, 3.0, 1.0, 4.0, 1.0, 2.0, 3.0, 4.0, 2.0],      # 3x3, row-major
    3, 3,
    [LE, LE, LE],
    [5.0, 11.0, 8.0],
    True,
    1000, 1e-9, 1e-9,                                   # iterations, tolerances
])["result"]

r["objective"]        # 13.0
r["duals"]            # [1.0, -0.0, 1.0] — row 1 has room, so it is worth nothing
r["binding"]          # [True, False, True]
r["lower"][0]         # 4.0
r["upper"][0]         # 5.333... — beyond this the shadow price is a different number
r["has_upper"][1]     # False — row 1's right-hand side can grow without limit
```

An unbounded end is a **flag, not an infinity**: `has_upper[i] == False` means "no limit",
and `upper[i]` then holds the current right-hand side as padding. An infinite bound would go
on to do arithmetic in a caller's range check, and `inf - inf` is not a number.

A zero dual may print as `-0.0`. That is IEEE signed zero, not a negative price — it compares
equal to `0.0` — and it is left as the arithmetic produced it rather than normalised, so the
number you see is the number the solver computed.

`lp_solve` additionally reports `reduced_costs` — what each variable would have to improve
by before it becomes worth using — plus `activity`, `slack` and the final `basis`, so a
caller can re-derive the duals independently.

### A range that cannot move is reported PINNED, not open

Some models are rank-deficient by construction: a balanced transportation problem, or any
block of flow-conservation equalities, has one redundant row. For such a row, moving the
right-hand side by any amount at all makes the program infeasible — the range has **zero
width**. That is reported as two present ends that coincide (`has_lower` and `has_upper`
both `True`, `lower[i] == upper[i]`), and deliberately not as a cleared flag:

```python
# minimise 4a + 6b + 9c + 5d  subject to a balanced 2x2 transportation block
r = runtime.execute("optimization.linear", "lp_rhs_ranges", [
    [4.0, 6.0, 9.0, 5.0], 0.0,
    [1.0, 1.0, 0.0, 0.0,
     0.0, 0.0, 1.0, 1.0,
     1.0, 0.0, 1.0, 0.0,
     0.0, 1.0, 0.0, 1.0],
    4, 4,
    [EQ, EQ, EQ, EQ],
    [10.0, 5.0, 8.0, 7.0],
    False,
    1000, 1e-9, 1e-9,
])["result"]

r["objective"]                                  # 69.0
r["lower"][3] == r["upper"][3] == 7.0           # pinned: no movement at all
```

"No limit" and "no movement" are opposites, so they must not share a representation.
Reporting a free end that is not free is precisely how a caller ends up extrapolating a
prediction that was never true — and unlike a wrong number, nothing in the answer would
have said so.

## Assignment, and knowing the matching is optimal

Rows are agents, columns are tasks, `cost[i * cols + j]` is the cost of agent `i` doing task
`j`, and a complete answer assigns every task to a distinct agent. Agents may be idle;
`col_of_row[i] == -1` is an idle agent, which is a real answer when there are more agents
than tasks.

```python
# c[i][j] = (i + 1)(j + 1) — the greedy answer and the optimal one differ
r = runtime.execute("optimization.assignment", "assignment_solve", [
    [1.0, 2.0, 3.0,
     2.0, 4.0, 6.0,
     3.0, 6.0, 9.0],
    3, 3,
])["result"]

r["total_cost"]        # 10.0 — the unique minimum over all six permutations
r["col_of_row"]        # [2, 1, 0]
r["perfect"]           # True — every task is assigned
r["greedy_cost"]       # 14.0 — what a per-row cheapest-available rule costs here
r["improvement"]       # 4.0
r["dual_certified"]    # True
r["u"], r["v"]         # the potentials that prove it
```

A forbidden pairing is a **boolean, never a big number**. `assignment_solve_masked` takes an
`allowed` list parallel to `cost`. Encoding "this agent cannot do this task" as a cost of
`1e9` is the standard trick and it fails two ways: the big number enters the duals, the
reduced costs and the total, and it silently becomes *choosable* the moment the alternative
is bigger — so an impossible problem returns a plausible assignment.

When no complete matching exists, that is what you get told:

```python
ones = [1.0] * 9
# agents 0 and 1 can only do task 0; tasks 1 and 2 both need agent 2
allowed = [True, False, False,
           True, False, False,
           True, True, True]
r = runtime.execute("optimization.assignment", "assignment_solve_masked",
                    [ones, 3, 3, allowed])["result"]

r["col_of_row"]    # [] — not a partial matching dressed up as an assignment
runtime.execute("optimization.assignment", "assign_status_name",
                [r["status"]])["result"]        # "no_perfect_matching"
```

`assignment_dual_check` verifies a matching and its potentials from the outside, so you can
audit an assignment that some other system produced.

## Network flow

```python
# a 4-node network: s=0, t=3
src = [0, 0, 1, 1, 2]
dst = [1, 2, 2, 3, 3]
cap = [3.0, 2.0, 5.0, 2.0, 3.0]

r = runtime.execute("optimization.flow", "max_flow_dinic", [src, dst, cap, 4, 0, 3])["result"]
r["value"]               # 5.0
r["cut_capacity"]        # 5.0 — computed from different data, and it must agree
r["cut_edges"]           # [0, 1] — the bottleneck, as data
r["source_side"]         # per node: which side of the minimum cut it is on
r["edge_flow"]           # [3.0, 2.0, 1.0, 2.0, 3.0] — one entry per input edge, in order
```

Maximum flow equals minimum cut capacity exactly, and the two are computed here from
different data — the value from the augmentations, the cut from a residual sweep over the
original capacities. So the identity is a **self-check inside the driver**, not just an
assertion in a test: if the two disagree, the result is `flow_does_not_equal_cut` with no
numbers attached. An answer that fails a checkable identity should not be returned.

Min-cost flow prices each additional unit on the cheapest route still open, and a target
above the maximum flow has neither a value nor a cost:

```python
src, dst = [0, 1, 1, 2], [1, 2, 3, 3]
cap, cost = [2.0, 2.0, 2.0, 1.0], [0.0, 1.0, 6.0, 0.0]

two = runtime.execute("optimization.flow", "min_cost_flow",
                      [src, dst, cap, cost, 4, 0, 3, 2.0])["result"]
two["value"], two["cost"]   # 2.0, 7.0 — the cheap route holds one unit, the second pays 6

too_much = runtime.execute("optimization.flow", "min_cost_flow",
                           [src, dst, cap, cost, 4, 0, 3, 3.0])["result"]
too_much["has_value"]       # False
too_much["edge_flow"]       # []
runtime.execute("optimization.flow", "flow_status_name",
                [too_much["status"]])["result"]   # "target_flow_exceeds_max_flow"
```

Routing the largest flow it *could* manage, priced, would answer a question nobody asked.
Negative costs are refused (`negative_cost_needs_cycle_cancelling`) rather than answered
with a cheaper flow that is not the minimum-cost one — a wrong answer indistinguishable from
the right one without an independent oracle.

`flow_network_check` gives a one-call census of a network before you solve it — out-of-range
endpoints, self-loops, parallel edges, negative or non-finite capacities, zero-capacity
edges — and `flow_audit_flat` checks a flow vector you were handed against capacity and
conservation, reporting the first bad edge and the first bad node.

## Explaining the answer, and explaining the rejection

`optimization.explain` is the surface for the question after the answer.

**Which constraints are actually binding, and what is each worth:**

```python
r = runtime.execute("optimization.explain", "binding_constraints_default", [
    [1.0], [1.0, 1.0], 2, 1, [LE, LE], [4.0, 10.0], True,
])["result"]

r["objective"]         # 4.0
r["binding"]           # [True, False]
r["duals"]             # [1.0, -0.0] — the row with six units of room is worth exactly 0
r["binding_rows"]      # [0]
r["complementary"]     # True
r["strong_duality"]    # True
r["n_degenerate"]      # 0 — binding rows priced at zero, which is legal and common
```

**An infeasibility core** — the subset of constraints that is still contradictory on its
own, which is what you show a user instead of "infeasible":

```python
# x + y <= 10,  x >= 5,  y <= 4,  x <= 3   — rows 1 and 3 cannot both hold
r = runtime.execute("optimization.explain", "infeasibility_core_default", [
    [1.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0], 4, 2,
    [LE, GE, LE, LE], [10.0, 5.0, 4.0, 3.0],
])["result"]

r["is_infeasible"]           # True — the full model, proved
r["core"]                    # [1, 3] — exactly the contradictory pair
r["core_verified"]           # True — the subset was re-solved on its own
r["minimal"]                 # True — dropping either member makes it feasible
r["n_solves"]                # 8 — what the minimality claim cost
```

A feasible model returns an **empty** core and a status that says so, rather than inventing
a smallest-looking subset. And the three claims are three separate fields, because a caller
may get one without the others: whether the model is infeasible, whether the returned subset
is infeasible by itself, and whether it is minimal are proved by different solves.

**Where the objective came from**, itemised, with the residual that proves the parts add up
to the whole:

```python
r = runtime.execute("optimization.explain", "objective_contributions", [
    [3.0, 5.0], -2.0, [2.0, 6.0], True,
])["result"]

r["objective"]              # 34.0
r["contribution"]           # [6.0, 30.0]
r["share"]                  # each variable's fraction of the variable part
r["largest_index"]          # 1 — the term that dominates
r["residual"]               # objective - (constant + sum of parts)
r["sums_to_objective"]      # True
```

`share` is **absent** when the variable part of the objective is `0`, rather than a
zero-filled list: shares of a zero total do not exist, and a zero-filled list would claim
every variable contributed nothing to a total that several of them may have cancelled into
being.

`slackness_check` runs the same complementary-slackness audit over duals and slacks you
supply, so a solution produced elsewhere can be checked here.

## Certificates say which conditions they cover

A function that returns "verified" is making a stronger promise than one that returns a
number, and the promise is only as good as the weakest condition checked. **A certificate
that omits a condition is worse than no certificate, because the caller stops looking.** So
each one states its scope.

`binding_constraints` — `complementary` is *both* complementary-slackness conditions, not
one: no row the solver called loose carries a price, **and** no priced row has materially
positive measured slack. Those are two claims, and one does not imply the other over a
flag-and-vector pair. `strong_duality` compares the dual objective with the primal one. What
they do **not** certify: integrality, bounds handled outside the constraint rows, or that
the optimum is unique — a degenerate vertex has valid duals that another basis would report
differently.

`assignment_dual_check` — dual feasibility over every allowed pair, equality on every chosen
pair, a zero potential on every idle agent, **and** a non-positive potential on *every*
agent, which is what the "at most one task per agent" constraint implies. That last
condition only bites when there are more agents than tasks, and without it a suboptimal
matching can exhibit apparent strong duality: its dual objective matches its own cost while
the true optimum is lower.

`max_flow_dinic` — the returned value equals the returned cut's capacity, checked against
the original capacities.

`infeasibility_core` — infeasibility of the full model, infeasibility of the returned subset
on its own, and minimality of that subset, each reported separately with the number of
solves spent proving them.

`milp_solve` — `feasible` means the returned point was **verified** against every constraint
row after being snapped to the integer grid, not trusted from the relaxation. There are no
duals: linear-programming duality does not survive an integrality constraint, and the final
node's duals would be a number in the right units about a different program.

Non-finite inputs are rejected **before** any tolerance is computed from them, because a
tolerance derived from a `nan` is a `nan`, every comparison against it is false, and an
audit would pass having counted zero violations.

## Building and checking a model before you solve it

`optimization.model` holds the parts a solver needs and validates them as a whole. An
objective or constraint is an expression, built once and reusable:

```python
arena = runtime.execute("optimization.model", "linear_arena",
                        [[3.0, 5.0], -2.0])["result"]        # 3x + 5y - 2

value = runtime.execute("optimization.model", "expr_evaluate_flat", [
    arena["ops"], arena["values"], arena["var_idx"],
    arena["lefts"], arena["rights"], arena["extras"], arena["root"],
    [2.0, 6.0],
])["result"]
value["has_value"]    # True
value["value"]        # 34.0
```

Evaluation reports a domain failure rather than masking it into a plausible number, and
names the offending node in `node_index`. That matters for anything iterative: a line search
that walks into a logarithm of a negative number and receives a finite value keeps going,
and converges to nothing meaningful.

`linear_extract_flat` recovers `Σ c_j x_j + constant` from an expression, and **refuses**
what is not affine — a product of two variables, a division by a variable, a square root of
one — naming the node, the operator and the variable involved instead of linearising
something that is not linear.

Moving a point into its box and onto the integer grid is a single call, and it reports what
had to move:

```python
CONTINUOUS, INTEGER = 0, 1
BOXED = 3      # has a lower bound and an upper bound

r = runtime.execute("optimization.model", "project_point_flat", [
    [2.4, 7.0],                  # the point
    [0.0, 0.0], [5.0, 5.0],      # lower, upper
    [INTEGER, CONTINUOUS],       # kinds
    [BOXED, BOXED],              # which bounds are present
    [0.0, 0.0],                  # warm-start values
    1e-9,
])["result"]

r["x"]             # [2.0, 5.0]
r["n_rounded"]     # 1
r["n_clamped"]     # 1
```

Bounds are applied **after** rounding, and the grid then wins inwards, so the result is both
integral and inside the box — clamping first can leave a non-integral value, and rounding
without clamping can leave the box.

A free variable is a **flag**, not an infinite bound, for the same reason a forbidden
assignment is a boolean: an infinity that enters arithmetic produces `inf - inf`, and a
model that was merely unbounded in one direction becomes a model whose numbers cannot be
compared.

## Shapes and sizes are checked before anything is read

Every function validates its declared dimensions against the actual list lengths before
indexing, and returns a status rather than reading past the end of an array. `rows * cols`
is not treated as a bound on its own — that product can overflow and wrap, so it is checked
against the real length.

Declared sizes are also capped against what the request actually contains. A network that
claims a trillion nodes with an empty edge list is refused, because a level array and a
potential array are one slot per node however few edges exist; a program that declares more
variables than its expressions mention is bounded by the expressions rather than allocated
for the declaration. Search work is bounded too, and exceeding the bound is a status —
`iteration_limit`, `node_limit` — never a truncated answer presented as a complete one.

Each family has its own status vocabulary and a matching name function — `lp_status_name`,
`milp_status_name`, `assign_status_name`, `flow_status_name`, `explain_status_name`,
`model_status_name` — so a rejection tells you which of your arrays to look at instead of
saying "invalid input".

## See also

* [Routing, scheduling & trade-offs](optimization-heuristics.md) — searches that report the bound they have instead of claiming an optimum
* [Sparse systems & graph analytics](sparse-and-graph.md) — sparse solvers, shortest paths, centrality
* [Batched and chained execution](coarse-execution.md) — many kernel calls in one frame
* [Runtime library catalog](runtime-library-catalog.md) — every module and function
