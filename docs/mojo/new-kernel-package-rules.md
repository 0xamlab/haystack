# Rules for new additive kernel packages

Empirically established, not stylistic. Each rule below was verified against this
repo's actual Mojo toolchain and harnesses; the verification command is given so a
future change can re-check rather than trust this file.

## 1. Bounds-check every dimension argument. A read past the end is UNCATCHABLE.

The frozen kernels take an explicit element count and trust it: `compute_mean(v, n)`
reads `v[0..n)` without checking `n <= len(v)`. Reading past the end does not raise —
it crashes the process, and `try`/`except` around the call does not help.

Verified:

```mojo
fn read_past_end(v: List[Float64], n: Int) -> Float64:
    var total = 0.0
    for i in range(n):
        total += v[i]
    return total
# read_past_end(five_elements, 25)  ->  "error: execution crashed"
```

Inside the worker this takes down every resident dataset and open cursor with it, and
presents to a client as a hang rather than an error.

**This is not hypothetical for new code.** A function in the runtime contract is called
by the generated A–Z suite with fixed sample arguments: `List[Float64]` becomes a
**5-element** list and every `Int` becomes **5** (see `_SCALAR_VALUES` and the `_lf5`
preamble in `tests/generate_mojo_tests.py`). So an exported
`solve(c, A, b, m: Int, n: Int)` is called as `solve(_lf5, _lf5, _lf5, 5, 5)` and will
index `A[24]` on a 5-element list. Without a guard, adding the kernel breaks the whole
A–Z run.

Every exported function must therefore validate its dimensions against the real lengths
first and return a safe sentinel — an empty list, or a result whose status field says
`invalid_dimensions` — rather than indexing.

## 1b. `mojo run` cannot prove memory soundness. Only the compiled binary can.

Every hand-written suite in `mojo/tests/libs/` runs under the JIT. The JIT is more
forgiving about freed memory than the optimized worker binary, so a whole class of bug
passes 46/46 there and then misbehaves in production.

This is not a hypothetical either. `query/plan.mojo` built a return value with

```mojo
return String(StringSlice(unsafe_from_utf8=Span(data)))   # `data` is a local
```

which leaves the String pointing at a buffer that dies on return. Under `mojo run` it
worked, including a probe that deliberately churned the allocator between calls. In the
compiled worker:

- a `filter` op **crashed the process**
- a `project` op read a garbage op name and was rejected as `unknown op ''` for a plan
  that plainly said `"project"`
- `select` and `sort` worked fine

Working sometimes, on some inputs, is the signature of use-after-free — and the two that
worked are why it was not obvious.

Two consequences:

1. Never hand a `Span` over a local to a constructor and return the result. Copy into an
   owned value first — `var out = String(""); out += slice; return out`. `+=` on an
   owned String must copy into that String's own buffer, so no aliasing survives. Treat
   every API with `unsafe` in its name as needing this.
2. **A JIT suite is not sufficient evidence.** Anything reachable over the wire needs an
   end-to-end test through the compiled binary
   (`tests/integration/test_query_plane_e2e.py` is the model). That suite is what caught
   this; the 46-assertion kernel suite could not have.

## 1c. A per-item ceiling is not a bound on total allocation.

`sparse_numerics.csr.MAX_CSR_DIM` (`1 << 26`) is the one shared dimension ceiling, and
`csr.mojo` justifies that number precisely: the worst-case row-pointer array is ~512 MB,
which is what the 512 MiB resident-dataset budget already treats as the outer limit **for
one object**. One object — not seven.

A driver that allocates *k* arrays of length `n_nodes` is therefore bounded at `k × 512 MB`,
not 512 MB. Measured on `optimization/flow.mojo`: `max_flow_dinic`, `flow_audit_flat` and
`min_cost_max_flow` each allocate three to seven independent `n_nodes`-length arrays, so an
**empty edge list** with `n_nodes` at the ceiling allocated several times the ceiling's own
budget.

Worse, a dimension can be bounded by the ceiling and still be tied to nothing in the
payload. `optimization/linear.lp_from_arenas` took `n_vars` as a bare `Int`, then
materialised five `n_vars`-length columns, one `OptVar` per variable each carrying a
`String` name, and two more vectors in the linearity extractor — about 200 bytes per
variable **regardless of how many variables the expression arena actually references**.
Measured: `n_vars = 2^22` peaked at 1.29 GB RSS and `2^24` at 3.50 GB, from a request
payload of a one-node arena plus one integer (~60 bytes).

So, for every declared dimension:

1. Bound it against the ceiling — necessary, not sufficient.
2. Bound it against **what the payload actually contains**. A variable no expression
   mentions cannot change any answer; a node no edge mentions cannot carry flow. Derive
   the dimension from the data, or reject a mismatch — do not trust the caller's integer.
3. Count the arrays your entry point allocates per unit of that dimension, and state the
   arithmetic in a comment. If the product exceeds the budget, scale the local ceiling
   down. Never raise or lower `MAX_CSR_DIM` itself; other packages depend on it.

Neither of the above was reachable past a length guard — both requests were *structurally
valid*. Shape validation and resource bounding are two separate checks.

## 2. Export flat-list functions, and the package is reachable for free.

`_SKIP_RUNTIME_DIRS` in `apps/runtime/mojo_inventory.py` excludes a package from the
runtime contract. `columnar/` and `query/` are in it because their entry points take
`RecordBatch` and `List[ExprNode]`, which cannot cross a JSON frame — which is why they
needed a new `query_execute` message type, a daemon RPC and SDK code to become
reachable.

A package whose **public** functions take and return only `List[Float64]`,
`List[Int]`, `List[Bool]`, `Float64`, `Int`, `Bool` and `String` needs none of that.
It lands in the contract automatically and is callable as
`execute(module, function, args)` from **both** local SDKs with no new message type, no
proto change and no SDK code.

There are already 502 contract functions with `List` parameters and a `List` return, so
this is the established shape, not a new idea:

```bash
python3 -c "
import json
c = json.load(open('packages/algenta/algenta/runtime_library_contract.json'))
print(sum(1 for m in c['modules'] for f in m['functions']
          if any('List[' in p['type'] for p in f.get('params', []))
          and 'List[' in f.get('return_type','')))"
# 502
```

So: keep structs for internals, export flat-list drivers. Do **not** add the package to
`_SKIP_RUNTIME_DIRS`. Register the hand-written suite filename in `HANDWRITTEN_TESTS`
(a separate mechanism) so the generator protects it instead of overwriting it — the
module still gets contract coverage.

A 2D matrix crosses as a flat row-major `List[Float64]` plus its `rows`/`cols`, which is
what the existing kernels already do.

### A returned struct must be defined in the SAME FILE, or the function vanishes

`apps/runtime/mojo_inventory.py` calls `parse_runtime_struct_specs(target.path)` — one
file at a time. So the marshalling spec for a returned struct is only found if that struct
is declared in the same module. Return a struct from elsewhere and
`is_runtime_supported_return_type` says `False`, and the function is **silently dropped**
from the contract and the dispatch. No error, no warning; it simply is not there.

Verified:

```python
from apps.runtime import mojo_inventory as mi
specs = mi.parse_runtime_struct_specs(Path("mojo/engine/numeric/reduce.mojo"))
mi.is_runtime_supported_return_type("Reduction")                      # False
mi.is_runtime_supported_return_type("Reduction", struct_specs=specs,
                                    allow_struct_types={"Reduction"})  # True
```

Two consequences:

- Do not return `numeric.reduce.Reduction`, `columnar.batch.RecordBatch` or any other
  struct owned by a different module from a public driver. Declare a local result struct
  with the fields you need.
- Do not put a struct with a non-marshalable field in a public signature at all.
  `columnar.array.Float64Array` holds an `ArcPointer`, which cannot cross the wire, so any
  function mentioning it is dropped the same silent way. Use plain
  `List[Float64]` / `List[Int]` in public signatures and keep the richer types internal.

### A driver may RETURN a struct, and should

91 distinct struct return types are already in the contract, and a struct field may
itself be a `List[Float64]`. The dispatch generator emits a serializer per struct —
`arima.ar_fit_yule_walker` returns `ARFit{phi: List[Float64], sigma2: Float64}` and the
generated table calls `_to_json_arfit(result)`:

```mojo
var result = _arima__ar_fit_yule_walker(arg_0, arg_1)
var result_json = _to_json_arfit(result)
```

So the right export shape is **flat lists in, a typed struct out**. The input side stays
JSON-friendly; the output side carries a status field alongside its numbers, which rule
4 requires. Encoding a status into a flat list would lose exactly the distinction that
matters.

One caveat from the `2d61f998` fix: a struct used as a *parameter* must be constructible
by the generated table — memberwise, `@fieldwise_init`, or a no-arg `__init__` plus
per-field assignment. A struct that is only ever *returned* needs no constructor beyond
whatever the kernel itself uses. Prefer return-only structs and keep parameters flat.

### A signature must close within NINE lines, or the function vanishes

`apps/runtime/mojo_inventory.py` matches a signature inside a **nine-line lookahead
window**. A signature whose closing paren lands on the tenth line or later is not parsed,
so the function never enters the contract and never enters dispatch — with no error
anywhere. `make inventory-refresh` succeeds, the counts simply come out one lower.

This is a live hazard, not a theoretical one. `optimization/model.mojo`'s
`expr_validate_flat` and `expr_evaluate_flat` both closed on **exactly** the ninth line.
Adding one parameter on its own line, or letting a formatter reflow either signature by a
single line, would have silently dropped two registered public functions.

So: pack several parameters per line to leave real headroom, and put a comment above any
signature near the limit saying the packing is load-bearing. After **any** signature
change, re-check the per-module function counts — a drop is the only symptom:

```bash
python3 -c "
import sys; sys.path.insert(0,'.')
from pathlib import Path
from apps.runtime import mojo_inventory as mi
for m in mi.discover_runtime_library_modules(Path('mojo/engine')):
    if m.import_path.startswith('<your_package>.'):
        print(m.import_path, len(m.functions))"
```

## 3. Never reimplement a frozen kernel. Call it.

From the project constraint: *"Existing Mojo kernels are frozen dependencies. Missing
capabilities must be implemented additively in new modules and new namespaces."*

A new driver's value is the composition, not the arithmetic. If a frozen kernel computes
an inner step — a Welford update, a residual capacity, a greedy assignment — call it,
even when inlining would be shorter. Where a frozen kernel has a limit (two variables
only, polynomial-coefficient objectives, an integer `func_id`), the new driver is a
separate complete driver and the old one stays reachable as a fast path.

Freeze verification, which must stay empty for existing kernel files:

```bash
git diff --stat eea8e045 -- mojo/engine/ \
  | grep -v -E 'algenta_runtime/|columnar/|query/|determinism/|canonical/|numeric/|sparse_numerics/|optimization/|graph_analytics/|retrieval/|hostio/|sheet/|tensorx/|gemm/|attnk/|normk/|mlpk/|lossk/|accel/|forecasting/|inference/|causal_inference/|survival_analysis/|streaming/|geospatial/|discrete_event/|evaluation/|data_quality/|strategy/|dispatch_generated|main\.mojo'
git diff eea8e045 -- mojo/tests/libs/ | grep '^-' | grep -v '^---'
```

**The gate is deceptively green for untracked namespaces.** `git diff` does not see untracked files,
so a brand-new package directory passes this check trivially until it is `git add`ed — at which point
it appears and the gate goes red unless its name was added to the alternation above. That is a
footgun in the wrong direction: it reads as "protected" during exactly the window when nothing is
being checked. `graph_analytics/`, `optimization/` and `retrieval/` were all untracked when this was
found on 2026-07-31.

So: **add the namespace to the alternation in the same commit that adds the package.**
`scripts/reliability_guards/guards/mojo_freeze_namespaces.py` enforces it — a directory under
`mojo/engine/` that is neither frozen nor listed above fails the build.

### Frozen kernels an optimization or numerics driver WILL be tempted to rewrite

Two adversarial reviews of a Phase 4 build plan found these already present. Each
signature below was re-verified against source. Call them.

| Need | Frozen kernel |
| --- | --- |
| CVaR / expected shortfall | `risk.mojo:116` `conditional_var(returns: List[Float64], confidence: Float64) -> Float64` |
| Value at risk | `risk.mojo:93` `value_at_risk(returns: List[Float64], confidence: Float64) -> Float64` |
| Binary min-heap, true O(log n) | `heap.mojo:122` `heap_push_min(mut heap: List[Float64], value: Float64)` |
| Worst-case / regret decision rule | `decision_analysis.mojo:235` `maximin(payoffs: List[List[Float64]]) -> Int`, `:126` `minimax_regret(...) -> Int` |
| Non-recursive sorts | `sorting.mojo:156` `insertion_sort(data: List[Float64]) -> List[Float64]`, `:213` `counting_sort_int(data: List[Int]) -> List[Int]` |
| Symmetry over list-of-rows | `matrix_decomp.mojo:62` `is_symmetric(A: List[List[Float64]], tol: Float64 = 1e-10) -> Bool` |
| Convexity / positive-definiteness | `linalg_ext.mojo:170` `mat_is_positive_definite(a: Matrix) -> Bool` |
| Dominant eigenvalue, no size cap | `linalg_ext.mojo:205` `mat_power_iteration(a: Matrix, max_iter: Int = 100) -> PowerIterResult` |
| Critical path through a dependency graph | `scheduler.mojo:181` `Scheduler.critical_path() -> CriticalPathResult` |

### Frozen failure values that a new driver exists to make honest

Each of these reports failure as a value a caller cannot distinguish from an answer.
Wrapping them means turning that into a status, per rule 4.

- `linalg.mojo:318` `mat_solve` returns an **all-zeros vector of length n** for a singular
  matrix and an **empty list** for a non-square one. So "the solution is the zero vector"
  and "there is no solution" are the same return value.
- `eigen_full.mojo:113` `eigh_symmetric` silently returns an empty result when
  `n <= 0 or n > 200 or len(A) != n*n` — a hard size cap of 200 that reads as "no
  eigenvalues".
- `linear_programming.mojo:43` `is_feasible` hardcodes `x >= 0` and indexes `b[i]`
  unguarded, so it is not a general feasibility test and can crash on a short `b`.
- `sparse.mojo` `sparse_matvec` performs **no** dimension check and therefore crashes the
  process on a mismatch; `tensor2d.mojo` `m2_matvec` returns an empty list instead. Follow
  the second.

### The rule applies inside your own package too

A new package built by several agents in parallel duplicates helpers the same way, and the
copies then drift. Found in `optimization/` on its first review:

- `_finite` written **six times**, byte-identical, private in every file — so no file could
  import it even though five already import from `optimization.model`.
- `_round_f` / `_floor_f` / `_ceil_f` reimplementing `integer._nearest_int`, where **only
  the copy documenting the hazard actually avoided it** (rule 4c).
- One declared input invariant enforced at **three different strengths under three
  different status codes** in `linear`, `integer` and `explain`.
- Two contradictory definitions of a valid solver policy, so `model_validate` returned OK
  for a policy other code in the same package rejected.

A duplicated guard is worse than a missing one: it reads as defence-in-depth while
providing one arbitrary behaviour per call site. Make the helper public in the package's
base module — `model.mojo` here — and have the rest call it. When a check appears twice at
different strengths, the weaker one is a bug even if it never fires today.

## 4. An answer that does not exist must be absent, not zero.

`numeric/contract.mojo` is the policy for new surfaces: `count` and `sum` of nothing are
`0` — real answers — while a mean, min, max or spread of nothing does not exist and must
be reported absent.

The same rule generalises to solvers, and this is where a wrong answer looks most like a
right one:

- an unbounded LP has no optimal objective — do not return the last vertex value
- an infeasible LP has no solution — do not return the closest point
- an iterative solver that hit its iteration cap has not converged — do not return the
  current iterate as if it had
- a non-perfect matching is not an assignment — do not return a partial one silently

Every such driver returns a status alongside its numbers, and the status is asserted in
its test.

## 4b. A tolerance must scale with the thing it judges, never with the whole problem.

This is the single worst defect found in this work, and it hid behind 145 passing
assertions and a docstring that promised the opposite.

`optimization/linear.mojo` accepted a phase-1 simplex result when

```mojo
residual > feasibility_tol * scale     # scale = 1 + Σ_i |b_i|   over ALL rows
```

`Σ|b_i|` is a sum over every row in the model, so **any** unrelated row with a large
right-hand side inflates the infeasibility tolerance without limit. Executed:
200 rows of `x0 <= 1e7` — ordinary capacity scaling, nothing pathological — plus the
flatly contradictory pair `x1 >= 3`, `x1 <= 2` returned `LP_OPTIMAL` with a full solution
vector, duals, reduced costs and a basis, for a program with no feasible point. The
returned `x` violated a row by a full unit. It reproduced on a single row too:
`{x >= 5, x <= 4.5, x <= 1e9}` returned optimal with `x = [5.0]`.

The residual was measured correctly and stored in the result; only the *threshold* was
wrong, so nothing in the answer said so.

Feasibility is not a global property to be averaged. A row is satisfied or it is not, and
its tolerance must come from **its own** magnitude — a per-row relative test, or a maximum
violation against a per-row scale. Any aggregate over rows lets one row's units pay for
another row's contradiction.

The blast radius is the reason this rule is stated separately: `explain.infeasibility_core`
runs a zero-objective trial solve to decide whether a model is infeasible at all, so it
inherited the bug and reported `EXPLAIN_FEASIBLE_NO_CORE` with `is_infeasible = False` for
an infeasible model. **A wrong status propagates further than a wrong number, because
downstream code branches on it.**

### The rule as first written was not specific enough. Here are the four spellings.

This section was added after the `Σ|b_i|` defect above. Tier 2 was built by agents that had read
it, and reproduced the same family **four more ways**. So the principle alone does not transfer —
the spellings have to be named.

**The principle, stated to cover all of them:** a tolerance exists to absorb what floating point
cannot represent about *the one quantity being judged*. Build it from
`DBL_EPSILON × (that quantity's own magnitude)`, plus the caller's **absolute** tolerance if they
supplied one. Never from an aggregate over other items, never from a floor that dominates the real
scale, never by multiplying the caller's tolerance by a magnitude.

| # | Spelling | What it actually did |
| --- | --- | --- |
| 1 | `Σ` over all items | `feas_tol * (1 + Σᵢ\|bᵢ\|)` — 200 ordinary capacity rows swallowed a flat contradiction; an infeasible LP returned `LP_OPTIMAL` with duals and a basis |
| 2 | `max` / norm over all items | a pivot tolerance scaled by `max_diag` of the whole matrix accepted an eigenvalue of **−0.68** as convex because another diagonal was 1e12 |
| 3 | `1 + \|x\|` whose **1.0 floor dominates** | a "relative" slop floored at 1.0 is an *absolute* allowance of one unit — a resource limit that permits one whole unit of overload |
| 4 | `caller_tol × magnitude` | sizing the *relative* term by the caller's tolerance instead of `DBL_EPSILON` — a measured gap of **400,000,000** reported `at_optimum = True` |

Spelling 2 is the one to watch for, because `max` *looks* per-item. It is not: it is an aggregate
over every item, and it transfers one item's units onto another item's comparison. A pivot's
tolerance must come from that pivot's own magnitude and the elimination error accumulated at its
position. A direction's curvature tolerance must come from that direction's own curvature.

Spelling 3 hides because `1 + |x|` is the idiom for "relative, but don't divide by zero". That is
fine when `|x|` is O(1) or larger. It is a lie when `|x|` is 1e-13 and the floor is doing all the
work — the comparison has silently become absolute at a scale the caller never chose.

**Practical check before writing any `if error > tol`:** say out loud what quantity `error`
measures, then confirm `tol` is derived from *that quantity alone*. If the derivation mentions any
other item, it is one of the four above.

**When you fix a premise, re-examine everything downstream that trusted it.** Two of tier 2's
criticals were endorsed by the module's *own* cross-checks — a KKT certificate and an independent
linearisation bound both agreed the answer was optimal, because both inherited the same false
convexity verdict. Independent checks are only independent if they don't share the broken input.

**Self-consistency is a testable property, so test it.** `qp_convexity_flat` reported
`positive_definite = True` for a matrix the solver in the same run called unbounded, and one struct
carried `rank = 1` beside `positive_definite = True`. Two mutually exclusive claims in one returned
value means a caller can use neither. Assert that a package's own reports agree with each other —
that assertion catches a broken premise even when you cannot compute the right answer by hand.

### Bounding memory is not bounding work

A dimension can sit inside the allocation ceiling and still drive an unbounded number of
operations. Scheduling bounded `n_machines` against the allocation ceiling but never charged it
against the work budget, while `_mach_pred_of` and `_ranks_of` each looped over it on *every* tabu
trial — a confirmed hang, which from the caller's side is the same outcome as the uncatchable abort
in rule 1. Multiobjective bounded memory and pair comparisons but not
`generations × pop_size × rows × n_vars`.

So: for every work or iteration budget, walk each loop bound that multiplies into the cost and
confirm it is charged. A budget that only counts one factor of a product is not a budget.

## 4c. `Float64(Int(v))` past the integer grid is poison, not truncation.

`fptosi` on a double outside `Int`'s range is undefined, so it yields an arbitrary value
rather than a clamped or truncated one — and a `_finite()` guard does not catch it, because
`1e300` is perfectly finite.

`optimization/model.mojo` rounded with `Float64(Int(v + 0.5))`, reachable from three
registered public functions. Executed: `project_point_flat(x=[1e300],
var_kind=[VAR_INTEGER])` passed every validation and returned an **arbitrary coordinate**
with status `MODEL_OK` and `rounded` counting 1 — a number returned where none exists,
which is exactly what rule 4 exists to prevent.

Build rounding, flooring and ceiling from `std.math.floor` / `ceil`, which are total over
every finite `Float64`, and guard the conversion separately. `integer.mojo`'s
`_nearest_int` already documented this hazard in its own comments — 700 lines from a second
implementation that still had the bug. See rule 3: the duplicate is how it survived.

## 4d. A certificate must check every condition it claims, not only the ones the current answer exercises.

A driver that returns "verified" is making a stronger promise than one that returns a
number, and the promise is only as good as the weakest condition checked.

`optimization/assignment.mojo` exported `assignment_dual_check` so a caller could validate
a matching **somebody else produced**. Its `certified` flag required dual feasibility,
tightness on the chosen pairs, and zero duals on agents idle *in the matching being
checked* — but not `u[i] <= 0` for every agent, which is what the capacity constraint
`Σ_j x_ij <= 1` actually implies. Executed: `assignment_dual_check(cost=[5.0, 1.0],
rows=2, cols=1, col_of_row=[0, -1], u=[4.0, 0.0], v=[1.0])` returned `certified = True`
with a dual objective of 5.0 matching a total cost of 5.0 — apparent strong duality — while
the true optimum was 1.0.

The omitted condition was invisible because no test exercised the shape that needs it
(`rows > cols`), and the test helper written to prove the duals had the same gap as the
code. Two related traps:

- **Complementary slackness is two conditions**, not one. Positive slack implies a zero
  dual, *and* a nonzero dual implies a tight row. `explain.binding_constraints` audited one
  direction and presented the result as justifying its shadow prices.
- **A `nan` defeats an unvalidated threshold silently.** With a `nan` dual,
  `dual_tol = SLOP * (1 + nan)` is `nan`, every `fabs(d) > nan` is `False`, and the audit
  passes having counted zero violations. Validate finiteness before computing any tolerance
  from the inputs, and route internal paths through the same validation as the public one.

State in the docstring which conditions the certificate covers. A certificate that omits
one is worse than no certificate, because a caller stops looking.

## 4e. Allocate status-code ranges per package, not per file.

`optimization/integer.mojo` and `optimization/explain.mojo` independently claimed codes
80–84, so `milp_status_name(81)` was `"node_limit"` while `explain_status_name(81)` was
`"feasible_so_there_is_no_infeasibility_core"` — one integer, two meanings, one package. A
caller that logs a status code cannot tell which vocabulary produced it, and neither can a
test.

Record the ranges a package has handed out in a comment beside each block, and pick from
what is left.

## 5. Mojo dialect, as actually used here

- `comptime NAME: T = value` for module constants; `alias` for types and function
  types.
- `fn`, not `def`, for new code (the deprecation warning is repo-wide and expected).
- Structs stored in a `List` declare `struct T(Copyable, Movable)`.
- Transfer ownership out of a function with `return values^`; take an owned parameter as
  `var values: List[Float64]`.
- `ref x = items[i]` binds without copying; plain `var x = items[i]` copies.
- `String` has **no** slice operator. Read bytes with `value.as_bytes()` and rebuild with
  `chr(Int(bytes[i]))`, or use `query.plan.substring`.
- Shifting or masking a `UInt8` by an `Int` warns; write `UInt8(index % 8)`.
- `perf_counter_ns()` returns `UInt`, so convert with `Float64(Int(t1 - t0))`.
- Prefer iteration with an explicit stack over recursion, matching `stats.fast_sort` and
  `graph/algorithms.mojo`.
- `List` element access on an out-of-range index crashes — see rule 1.

## 6. Definition of done, per module

1. Compiled Mojo kernel under `mojo/engine/`, zero Python imports.
2. Reachable from both local SDKs — free via rule 2.
3. Declared capability block + golden vectors.
4. Hand-written known-value suite in `mojo/tests/libs/`, registered in
   `HANDWRITTEN_TESTS`.
5. Benchmark under `benchmarks/`.
6. GitBook page, `make docs-check` green, artifacts regenerated via
   `make inventory-refresh`.
