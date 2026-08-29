---
icon: scale-balanced
description: A flat typed LP/MIP formulation container, its refusal-first validator and x>=0 lowering, a solve bridge that re-audits every answer in the caller's own coordinates, and a judge that scores a solved objective against a stated ground truth at two tolerances.
---

# Optimization benchmark plane

`optimization/` (see [Optimization & decision programs](optimization.md)) already holds the
solving half of the picture: `lp_solve`, `milp_solve`, and the `explain` surfaces that say why an
answer is what it is. What it does not hold is the shape an optimization *benchmark* actually
hands over — a formulation (variables with bounds and kinds, one objective, coefficient rows)
paired with a ground-truth optimum the candidate's answer has to be checked against. `optmodel` is
that layer, built on top of `optimization` rather than inside it: **`optmodel.formulation`** is the
flat, typed wire container plus its validator, its lowering onto the solvers' `x >= 0` convention,
and a solver-free point audit; **`optmodel.solve`** is the bridge that dispatches a formulation to
the right solver, certifies the answer, and maps it back into the caller's own variable space;
**`optmodel.judge`** is the scoring half — one solved objective against one stated truth, at a
strict tolerance and at the published OptMATH-lineage tolerance, landing every instance in exactly
one of three buckets: VERIFIED, REFUSED, or WRONG. This is grading infrastructure in the same
spirit as [FinQA exact execution](../benchmarks/finqa-exact-execution.md)'s `progexec` — a
domain-specific harness for checking a candidate's answer against ground truth — not a fourth
solver; every actual solve underneath is `optimization`'s own, called and never reimplemented.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

LE, CONTINUOUS, HAS_LOWER = 0, 0, 1

# max 3x + 2y,  x + y <= 4,  x + 3y <= 6  — solved, then judged against a stated truth of 12
verdict = runtime.execute("optmodel.judge", "formulation_verdict_default", [
    2, 2, True, [3.0, 2.0], 0.0, [1.0, 1.0, 1.0, 3.0],
    [LE, LE], [4.0, 6.0], [CONTINUOUS, CONTINUOUS], [0.0, 0.0], [0.0, 0.0],
    [HAS_LOWER, HAS_LOWER],
    12.0, 100,          # ground_truth, max_nodes
])["result"]

verdict["objective"]         # 12.0
verdict["verdict_strict"]    # 0 — VERIFIED
verdict["verdict_lineage"]   # 0 — VERIFIED
verdict["message"]           # "optimal"
```

## The modules

| Module | What it does |
| --- | --- |
| `optmodel.formulation` | the flat, typed formulation container — dense rows, senses, rhs, per-variable kind/bounds — plus `formulation_check_flat` (refusal-first validation with a WHERE beside every WHAT), `formulation_lower_flat` (compiles onto the solvers' `x >= 0` convention), and `formulation_point_audit_flat` (re-checks a candidate point against every original declaration, independent of any solver) |
| `optmodel.solve` | the bridge: dispatches all-continuous formulations to `lp_solve` and discrete ones to `milp_solve`, certifies the answer (complementary slackness, or a verified incumbent), maps it back to the caller's variable space, re-audits it there, and converts every non-answer into a typed refusal with its evidence attached |
| `optmodel.judge` | the scoring half — `judge_objective` compares one objective to one ground truth under a strict and a lineage tolerance regime, and `formulation_verdict_flat`/`formulation_verdict_default` solve, certify and classify a whole formulation into VERIFIED / REFUSED / WRONG in one call |

## The container: dense, typed, and validated before any index is used

A formulation is `n_vars` and `n_cons` declared up front, an objective (`c`, `c0`), dense
constraint rows (`a`, `senses`, `rhs`), and per-variable kind and bounds (`var_kind`,
`var_lower`, `var_upper`, `var_flags` — the same column format `optimization.model` already
defines, validated by `variables_validate_flat` rather than a second spelling of the same rules).
`formulation_check_flat` guards the dense shape by division (`dims_fit`, never a wrapping
multiply — the test file's `wrap` case declares `n_cons = 6148914691236517206` so that
`3 * n_cons` overflows back to `2` under a naive 64-bit multiply, and asserts the guard still
refuses `dense_shape` instead of reading past the array), then every parallel array length, then
every coefficient, rhs, and objective term for non-finite values. Nine hand-corrupted single-field
mutations of the production LP `max 3x + 2y, x+y<=4, x+3y<=6` are each asserted to refuse with
**its own** status and a WHERE index — a short `c` is `parallel_arrays_length_mismatch`, an
unknown sense at row 1 is `MODEL_ERR_SENSE` with `constraint_index == 1`, `NaN` in `A[1][0]` is
`MODEL_ERR_NON_FINITE_COEFFICIENT` with `constraint_index == 1, var_index == 0` — never one shared
"invalid" verdict that cannot say which array was wrong.

What is deliberately **not** representable: a variable with no declared lower bound. The solver
plane underneath every lowering is `x >= 0`; a free variable would need a two-column split that
changes the variable count the caller sees, so it is refused as a typed, countable status
(`free_variable_unsupported_declare_a_lower_bound`) rather than silently worked around. The same
policy holds for a discrete variable whose lower bound is fractional
(`discrete_variable_lower_bound_not_integral`) — shifting an integer variable by `0.5` would move
the integer grid itself, not just relabel it.

## The lowering's arithmetic, exact

`formulation_lower_flat` substitutes `x_j = y_j + shift_j` with `shift_j` the declared lower
bound, folds the shift into the objective constant and every row's right-hand side, and emits one
explicit `y_j <= upper_j - shift_j` row per declared upper bound. `row_kind[i]`/`row_ref[i]` map
every lowered row back to the caller's own constraint or variable index — kind 0 with the
constraint's index, kind 1 with the bounded variable's index — which is what lets an
infeasibility core (below) name the caller's rows instead of internal ones.

The test file asserts the arithmetic exactly, because every quantity here is exact in binary
floating point. Lowering `min 2x + 3y, x+y>=1` with `x ∈ [-2, 5], y ∈ [0, 5]`:

```python
lowered = runtime.execute("optmodel.formulation", "formulation_lower_flat", [
    2, 1, [2.0, 3.0], 0.0, [1.0, 1.0], [2],       # SENSE_GE
    [1.0], [CONTINUOUS, CONTINUOUS], [-2.0, 0.0], [5.0, 5.0], [3, 3],  # both VAR_FLAG_BOXED
])["result"]

lowered["rows"], lowered["n_upper_rows"]   # 3, 2
lowered["constant"]                        # -4.0  =  c·shift  =  2*(-2) + 3*0
lowered["rhs"]                             # [3.0, 7.0, 5.0]
# row 0: x+y>=1 folded to  1 - (1*(-2) + 1*0) = 3, same sense (GE)
# row 1: y_0 <= 5 - (-2) = 7   (kind 1, ref 0 — the caller's variable 0)
# row 2: y_1 <= 5 - 0 = 5      (kind 1, ref 1 — the caller's variable 1)
lowered["shift"]                           # [-2.0, 0.0]
```

`shift = (-2, 0)` recovers the caller's own point later: `formulation_solve_flat` (below) solves
this exact program to `2` at caller-space `(1, 0)`, not at the shifted `y = (3, 0)`.

A binary variable's own upper-bound row is skipped when it is **redundant** with
`milp_solve`'s unconditional root-node box (`y_j <= 1`, added once at every node for every binary
column): the test's three-variable mixed case (one real row to keep `n_cons >= 1`) has a binary
at its standard `[0, 1]` box omit its row entirely (`rows == 3`, not 4), while a binary **fixed at
1** (`lower == upper == 1.0`, shift 1, so its row would say `y_j <= 0`) keeps its own row — the
root box only ever says `<= 1`, unaware of any shift, so testing `upper == 1.0` alone (forgetting
`lower == 0.0`) would silently widen the variable back to `{0, 1}`. An all-continuous formulation
of the identical shape keeps all three upper rows, because no root box exists for a continuous
kind at all — the redundancy check is `kind == VAR_BINARY`, never merely `upper == 1.0`.

The rule-1c cell ceiling (`OPTM_MAX_LOWERED_CELLS = 2^26`, checked by division, never by a
multiply that can wrap) is demonstrated from a small payload: 65,536 upper-bounded variables with
zero constraint rows would materialize a `65536 × 65536` (`2^32`-cell, ~32 GB) dense block from a
payload of a few hundred kilobytes, and is refused `dimension_too_large`; the same shape at 1,024
variables (`2^20` cells) lowers cleanly.

## The point audit: solver-free, against every original declaration

`formulation_point_audit_flat` re-checks a candidate point against the *original* formulation —
never the lowering — so a lowering bug and a solver bug are both catchable by the same
independent check. It reuses `model.sense_violation` as the one definition of "this row fails,"
under a three-term tolerance budget (the caller's absolute tolerance, an ulp allowance scaled to
the row's own magnitude, and an integrality-snap term over discrete columns only) — the same
`integer._verify_row_budget` shape, deliberately not the simpler `tol * (1 + |b|)` forms the test
file demonstrates failing: a **full-unit** violation of `x <= 1e9` (point `1e9 + 1.0`) is caught,
while a `1e-5` gap at the same magnitude is honest floating-point rounding and passes.

At the production LP's optimum `(4, 0)`, the audit reports `feasible = True`, `objective = 12.0`,
zero violations of any kind. Each of the three violation categories has its own mutated point and
its own counter in the test file:

| Mutated point | What's wrong | Caught as |
| --- | --- | --- |
| `(4.1, 0)` | row 0 (`x+y<=4`) overshoots by 0.1 | `n_row_violations = 1`, `worst_row = 0`, `row_violation ≈ 0.1`, `objective ≈ 12.3` |
| `(4, -0.5)` | `y`'s lower bound (0) undershoots by 0.5 | `n_bound_violations = 1`, `worst_bound_var = 1`, `bound_violation ≈ 0.5` |
| `(3.5, 0)`, both vars declared integer | `x` is 0.5 off the integer grid | `n_integrality_violations = 1`, `worst_integrality_var = 0`, `integrality_violation ≈ 0.5` |

A defect in the audit's own inputs — a point of the wrong length, a `NaN` coordinate, a negative
tolerance — comes back as a status (`parallel_arrays_length_mismatch`,
`MODEL_ERR_NON_FINITE_POINT`, `MODEL_ERR_POLICY`), never folded into `feasible = False` as if it
were a real violation.

## The solve bridge: certified twice before a number is ever reported

`formulation_solve_flat` lowers, dispatches by the variable census (all-continuous to `lp_solve`,
anything discrete to `milp_solve`), and requires **two** independent passes before reporting an
objective: the solver's own certificate (complementary slackness via `explain.slackness_check`
for an LP; a re-verified incumbent, `proven_optimal`, for a MILP), and then this package's own
`formulation_point_audit_flat` run in the **original** variable space — which never sees the
lowering, so a lowering bug and a solver bug both land in the same bucket
(`refused_self_check_failed`), never in a reported number. `OptModelSolve.solved` is the sole
authority: `True` means `x` is the caller-space point and every certificate passed; `False` means
`x` is empty and `has_objective` is `False`, no matter what diagnostics ride along.

Six real solves from the test file, each with its refusal or answer:

| Program | Result |
| --- | --- |
| `max 3x+2y, x+y<=4, x+3y<=6` | solved, `12.0` at `(4, 0)` |
| `min 2x+3y, x+y>=1, x∈[-2,5], y∈[0,5]` | solved, `2.0` at caller-space `(1, 0)` — 3 lowered rows |
| Wolsey MILP `max 5x+8y, x+y<=6, 5x+9y<=45, integer` | solved, `40.0` at `(0, 5)`, `max_nodes=500` |
| the same Wolsey MILP at `max_nodes=3` | `refused_search_limit` — incumbent `39.0` and bound `370/9` ride along as diagnostics, `has_objective` stays `False` |
| binary knapsack `max 10a+13b+7c, 6a+8b+5c<=10` | solved, `13.0` — item `b` alone (every pair overweight: 11/14/13 all exceed 10) |
| `x<=2` against `x>=5` (with an innocent `y<=100`) | `refused_infeasible`, core names rows `{0, 1}` exactly, excluding row 2 |

A node/iteration limit is refused, never relayed as if it were an optimum — the incumbent found
so far survives only as a labeled diagnostic (`has_incumbent`/`incumbent_objective`,
`has_bound`/`best_bound`), exactly the distinction [Optimization & decision
programs](optimization.md) draws for `milp_solve` itself. Infeasibility is explained rather than
shrugged at: `formulation_solve_flat` runs `explain.infeasibility_core` over the lowered rows and
maps the result back through `row_kind`/`row_ref`, so a conflict written as two constraint rows
names `core_constraints = [0, 1]`, while the identical conflict written with `x`'s upper bound
declared instead of a row names `core_bound_vars = [0]` and `core_constraints = [0]` — the same
mathematical conflict, reported in whichever vocabulary the caller actually used. An
integer-infeasible model with a *feasible* LP relaxation (`2x == 1` over an integer `x`) refuses
`refused_infeasible` with an **empty** core — inventing a conflicting subset when the relaxation
itself is innocent would misname where the infeasibility actually lives.

A formulation with zero rows at all (no constraints, no upper bounds) never reaches a simplex: it
is answered analytically, because each shifted variable can only grow from `y=0`, so the model is
unbounded the instant any objective coefficient rewards growth, and `y=0` (the caller's own lower
bound) is optimal otherwise. The test file's `min x` over `x ∈ [-2, ∞)` with no rows confirms this
returns the **caller's** corner (`-2.0`), not the internal `0`.

## The judge: two tolerance regimes that are asserted to disagree

`judge_objective` compares one solved objective to one ground truth under two regimes that the
test file deliberately proves disagree on the cases they're built to disagree on — a judge whose
regimes always agreed would be one regime wearing two names:

- **Strict** — relative error `|objective - truth| / max(1, |truth|)` at `1e-4` (the `max(1, ·)`
  floor keeps the test absolute near zero, where plain relative error divides by nothing).
- **Lineage** — the published OptMATH executor's rule, reproduced exactly for comparability: round
  both values to the nearest integer, then require the rounded difference within 5% of the rounded
  truth. When rounded truth is `0`, that quotient doesn't exist, so the coded rule requires
  `round(objective) == 0` exactly rather than laundering a division by zero into `inf`/`nan`.

Asserted cases from the test file: objective `103` against truth `100` is a 3% gap — lineage
accepts, strict rejects (`3e-2 > 1e-4`). Objective `106` against the same truth is a 6% gap —
**both** reject. Objective `100.0` against truth `99.6` rounds both to `100` — lineage accepts
while strict still sees `4e-3` and rejects, isolating the rounding half of the lineage rule from
its 5% half. Near zero, `5e-5` against a truth of `0` passes both regimes, while `0.6` against the
same truth rounds to `1` and fails both. A `NaN` truth or a negative tolerance comes back
`comparable = False` with **both** match flags `False` — not comparable must never score as a
pass.

`formulation_verdict_flat` is the end-to-end driver: solve, certify, judge, and land in exactly
one of `OPTM_VERDICT_VERIFIED` / `_REFUSED` / `_WRONG` per regime. WRONG requires `solved` —a
refusal can never be classified WRONG, only REFUSED — and the test file proves a refusal is never
upgraded by a lucky stated truth: the Wolsey MILP capped at `max_nodes=3` refuses
`refused_search_limit` under **both** regimes even when the stated truth (`39.0`) equals its own
incumbent exactly. Run to completion (`max_nodes=500`) against a stated truth of `40.0`, the same
program is VERIFIED under both. Against a stated truth of `12.3` on the production LP, the plane's
own answer never changes (`12.0` every time) — lineage rounds `12.3` to `12` and still VERIFIES,
strict sees the `2.5%` gap and calls it WRONG; against a stated truth of `11.0`, both regimes call
it WRONG (`9.1%` off after rounding). Only the stated truth moves between these three cases, which
is exactly the point: the judge is being tested, not the solver.

## Verification

`mojo/tests/libs/test_optmodel_formulation.mojo`, `test_optmodel_solve.mojo`, and
`test_optmodel_judge.mojo` are the golden vectors cited throughout this page — every numeric
example above is lifted directly from an assertion in one of those three files, worked out on
paper before being asserted, never invented for this page. Every certifying check in the suite
carries a mutated twin: the same formulation with one field corrupted, one bound removed, one
node budget cut, asserted to land in its own distinct refusal rather than a shared "invalid"
bucket — anti-vacuity by construction, so a check that would pass anything cannot survive review.
Status codes for this package start at 200, clear of every vocabulary `optimization` already
occupies (model 0–30, linear 40–63, explain 80–86, integer 100–105, quadratic 110–117, routing
120–129, scheduling 130–139, multiobjective 140–149, robust 150–170) — verified pairwise distinct,
by both code and name, in the test file's status-vocabulary check.

**Next:** [Optimization & decision programs](optimization.md) for the solvers this plane calls, or
[FinQA exact execution](../benchmarks/finqa-exact-execution.md) for the same
verify-against-ground-truth spirit applied to arithmetic programs instead of LP/MIP formulations.
