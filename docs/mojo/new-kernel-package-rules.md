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
  | grep -v -E 'algenta_runtime/|columnar/|query/|determinism/|canonical/|numeric/|sparse_numerics/|optimization/|dispatch_generated|main\.mojo'
git diff eea8e045 -- mojo/tests/libs/ | grep '^-' | grep -v '^---'
```

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
