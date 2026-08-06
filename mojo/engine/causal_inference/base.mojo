"""
causal_inference.base — the package's shared vocabulary. Zero Python imports.

One status vocabulary, one finiteness test, one rounding-tolerance builder, one set of
dimension ceilings and one work-budget primitive, so that no two modules in this package
answer the same question two ways. That failure mode is documented in rule 3 of
`docs/mojo/new-kernel-package-rules.md` ("the rule applies inside your own package too"):
`optimization/` shipped `_finite` six times byte-identical and one input invariant enforced
at three different strengths under three different status codes. A duplicated guard reads as
defence in depth and provides one arbitrary behaviour per call site.

THE STATUS-CODE ALLOCATION (rule 4e)
------------------------------------
This package owns **340-359 inclusive** and uses no other code. All twenty are spent, they
are spent HERE rather than per file, and `ci_status_name` is the single vocabulary — so
`ci_status_name(347)` means one thing whichever module produced it. `optimization/` is the
cautionary case: `integer.mojo` and `explain.mojo` independently claimed 80-84, so
`milp_status_name(81)` was "node_limit" while `explain_status_name(81)` was
"feasible_so_there_is_no_infeasibility_core" — one integer, two meanings, one package.

ABSENCE IS NOT ZERO, AND IT IS NOT NaN EITHER
---------------------------------------------
Rule 4 is the whole point of this package: a causal estimate that is not identified is a
regression coefficient wearing a causal name. Every result struct here therefore carries a
`has_<quantity>` Bool beside its numbers, and a refusal returns empty lists with
`has_* = False`.

The obvious spelling for "no value" — `nan` — is unavailable, and not for style reasons: a
NON-FINITE Float64 crossing the result path ENDS THE WORKER PROCESS. That is measured and
recorded in `stats.compute_mean`'s own docstring (`compute_mean(five, 0)` returns `0.0/0.0`
and the serving pid vanishes). So every Float64 this package returns is finite, absence is a
Bool, and `CI_ABSENT` (-1.0) is used only for a diagnostic that is naturally NON-NEGATIVE
when it exists, where -1.0 cannot be confused with a real value.

WHAT THE CEILINGS ARE FOR, AND WHY THERE ARE TWO KINDS
------------------------------------------------------
Rule 1c and "bounding memory is not bounding work" are separate checks and both are needed:

* the MAX_CI_* ceilings bound ALLOCATION. Each one states the per-unit array count it was
  derived from, because a driver that allocates k arrays of length n is bounded at k x the
  budget, not at the budget;
* the *_WORK / *_CELLS budgets bound OPERATIONS. `optimization/scheduling` charged
  `n_machines` against allocation and never against work, and hung — which from a caller's
  side is indistinguishable from rule 1's uncatchable abort.

`ci_product_fits` / `ci_product3_fits` are how a budget is checked, and they never form the
product they are bounding: `rows * cols` is a WRAPPING 64-bit multiply, and
`3 * 6148914691236517206 == 2`. That is the defect `sparse_numerics.csr.dims_fit` exists to
prevent, and shape validation here is delegated to `dims_fit` rather than re-derived.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_causal_inference_base.mojo
benchmark: benchmarks/mojo_benchmarks/bench_causal_inference.mojo
docs: none
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs

from sparse_numerics.csr import dims_fit

# ── status codes: 340-359, the whole of this package's allocation ─────────────
# Every code in the range is assigned. A new outcome reuses an existing code or the package
# asks for a new range; it does not borrow from a neighbour.

comptime CI_OK: Int = 340
comptime CI_ERR_SHAPE: Int = 341
comptime CI_ERR_LENGTH_MISMATCH: Int = 342
comptime CI_ERR_NON_FINITE: Int = 343
comptime CI_ERR_DIMENSION_TOO_LARGE: Int = 344
comptime CI_ERR_NOT_A_DAG: Int = 345
comptime CI_ERR_INDEX: Int = 346
comptime CI_ERR_NOT_IDENTIFIED: Int = 347
comptime CI_ERR_NO_TREATED: Int = 348
comptime CI_ERR_NO_CONTROL: Int = 349
comptime CI_ERR_NO_OVERLAP: Int = 350
comptime CI_ERR_DEGENERATE_PROPENSITY: Int = 351
comptime CI_ERR_NOT_CONVERGED: Int = 352
comptime CI_ERR_SINGULAR: Int = 353
comptime CI_ERR_INSUFFICIENT_DATA: Int = 354
comptime CI_ERR_NO_MATCHES: Int = 355
comptime CI_ERR_TREATMENT_NOT_BINARY: Int = 356
comptime CI_ERR_WORK_BUDGET: Int = 357
comptime CI_ERR_DUPLICATE: Int = 358
comptime CI_ERR_INVALID_PARAMETER: Int = 359

# A non-negative diagnostic that does not exist. Never used for a quantity that can
# legitimately be negative (an ATE, a trend difference, a dual) — those carry a `has_*` Bool.
comptime CI_ABSENT: Float64 = -1.0

# 2^-52, the Float64 machine epsilon. A property of the format, not a policy choice, and the
# same number `optimization.linear.LP_DBL_EPSILON` names. Stated here rather than imported so
# that reading one machine constant does not drag a two-thousand-line simplex into every
# module of this package; rule 3 forbids reimplementing LOGIC and there is none here. The
# suite imports LP_DBL_EPSILON and asserts the two are equal, so they cannot drift.
comptime CI_DBL_EPSILON: Float64 = 2.220446049250313e-16

# How many ulps of the judged quantity's OWN magnitude an accumulation is allowed to have
# lost before a discrepancy counts as real. Same budget as the simplex uses
# (`optimization.linear.LP_FEAS_ULP_BUDGET`), and generous on purpose: it is a ROUNDING
# allowance, which is the only thing a relative term may legitimately absorb.
comptime CI_ULP_BUDGET: Float64 = 1024.0

# ── allocation ceilings ──────────────────────────────────────────────────────
# The heaviest per-unit entry point here is `propensity.propensity_fit`, which materialises
# the scores, the fitted probabilities, the arm masks and the caller's copies — call it eight
# `n_units`-length arrays at 8 bytes each. 2^20 units therefore peaks at ~64 MB, an eighth of
# the 512 MiB resident-dataset budget `algenta_runtime.session` treats as the outer limit for
# one object. Deliberately far below `sparse_numerics.csr.MAX_CSR_DIM` (2^26): that ceiling is
# justified for ONE row-pointer array, and this package allocates eight.
comptime MAX_CI_UNITS: Int = 1 << 20

# `linear_models.logistic_fit` builds a dense (p+1)x(p+1) observed-information matrix and
# inverts it, and `logistic_std_errors` builds a second. 2^7 features is (129)^2 x 8 bytes x 2
# = 266 KB of Hessian, and the p^3 elimination is 2.1M operations per Newton step. The real
# constraint on `p` is the WORK budget below, not this; the ceiling exists so that a declared
# `n_features` no expression references cannot allocate at all.
comptime MAX_CI_FEATURES: Int = 1 << 7

# A declared causal DAG is hand-drawn. The traversals allocate parent/child CSR row pointers
# (2 x (n+1) Ints), the 2n Bayes-Ball visit states, the 2n predecessor states used to
# reconstruct a witness path, and four n-length Bool masks (X, Y, Z, ancestors-of-Z) — about
# twelve n-length arrays, so 2^16 nodes is ~6 MB. Keeping it this low is what makes the
# payload tie in rule 1c a non-issue rather than a second guard: a node no edge and no query
# set mentions costs ~96 bytes here, against the ~200 bytes per unreferenced variable that
# took `optimization.linear.lp_from_arenas` to 3.50 GB from a 60-byte request.
comptime MAX_CI_NODES: Int = 1 << 16

# A design matrix is n_units x n_features cells and BOTH per-axis ceilings can hold while the
# product does not: 2^20 units x 2^7 features is 2^27 cells, a 1 GB payload, and a fit that
# copies it once needs 2 GB. The per-axis ceilings are necessary and not sufficient — rule 1c
# again — so the joint cell count has its own budget: 2^22 cells is 32 MB of design, which is
# what an estimator can copy per arm and still stay inside the resident-dataset budget.
comptime MAX_CI_DESIGN_CELLS: Int = 1 << 22

# Edges come from the payload (`n_edges == len(edge_from)`), so this bounds the CSR target
# arrays rather than a caller's integer: 2 arrays x 2^20 x 8 bytes = 16 MB.
comptime MAX_CI_EDGES: Int = 1 << 20

# ── work budgets ─────────────────────────────────────────────────────────────
# max_iter x n_units x ((n_features+1)^2 + CI_LOGISTIC_BACKTRACK_STEPS x (n_features+1)) for the
# Newton fit and its line search, plus max_iter x (n_features+1)^3 for the eliminations. 2^30 is
# order-of-seconds: MEASURED at 0.85-1.01 ns per charged unit in the worst regime the fit has
# (separable data, l2 = 0, every Newton step backtracking to its cap), i.e. 0.91-1.08 s at the
# ceiling. Charged with all factors, because a budget that counts one factor of a product is
# not a budget.
#
# NOT a budget for a resampling loop. A bootstrap replicate is not a Newton step and pricing one
# against the other undercharges by two orders of magnitude — see MAX_CI_BOOTSTRAP_WORK.
comptime MAX_CI_FIT_WORK: Int = 1 << 30

# The frozen `linear_models.logistic_fit` runs a backtracking line search INSIDE every Newton
# step — `for _ in range(20)` at linear_models.mojo:336 — and each trial is a full
# `_penalized_ll` pass, O(n x (p+1)). Charging only the Newton step's (p+1)^2 information
# accumulation leaves that loop unpriced: MEASURED at p = 1, where the omission is worst, the
# cost was 9.4-11.1 ns per Newton-only-charged unit against 0.19-0.24 ns in the converging
# regime, so the ceiling above bought ~10.1-11.9 s of work instead of ~1 s. The undercharge is
# a bounded constant factor, 20/(p+1) — ~10x at p = 1, negligible by p = 19 — so it is charged
# with this constant rather than by widening the ceiling, which would mis-price every other
# caller. The value tracks the frozen `range(20)` literal and the suite asserts it.
comptime CI_LOGISTIC_BACKTRACK_STEPS: Int = 20

# The bootstrap's own ceiling, in charged (replicate x unit) draws. It is NOT MAX_CI_FIT_WORK:
# that constant's order-of-seconds calibration is written for a ~1 ns multiply-accumulate inside
# a Newton loop, and a bootstrap draw is nothing of the kind — it allocates six n-length lists
# per replicate and runs a keyed counter-based RNG call per unit. MEASURED across four shapes
# (n = 200..2048, replicates = 4096..80000): 98-141 ns per charged unit, which at 2^30 is
# 118-151 SECONDS — minutes for a structurally valid request, against a constant whose comment
# promises seconds. Worse, the per-unit cost RISES with the replicate count (98 -> 122 -> 141 ns)
# from allocation pressure, so the extrapolation is a floor and not a ceiling.
#
# 2^24 was picked by MEASURING AT IT rather than by dividing: 1.84 s at n = 1024 x 16384
# replicates and 1.96-2.26 s at the same charge in two other shapes. That is the "seconds" the
# fit budget claims and this one now delivers. It refuses nothing a bootstrap actually asks for —
# 2,000 replicates on 8,192 units fits exactly, and 10,000 replicates on 1,677 units fits — while
# the old ceiling admitted 1,048,576 replicates on 1,024 units.
comptime MAX_CI_BOOTSTRAP_WORK: Int = 1 << 24

# Greedy caliper matching scans every (treated, control) pair once and allocates NOTHING per
# pair, so this is purely an operation count.
comptime MAX_CI_PAIR_CELLS: Int = 1 << 24

# Optimal matching is different in both directions: it MATERIALISES a Float64 cost and a Bool
# mask per pair (9 bytes) and the Hungarian solve is O(max(rows, cols)^3). 2^18 cells is
# 2.4 MB and, at the square shape 512x512, 1.3e8 solver operations.
comptime MAX_CI_MATCH_CELLS: Int = 1 << 18

# A panel is n_units x n_periods cells and the payload already carries all of them, so this
# bounds the caller's two integers against each other rather than against the payload alone.
comptime MAX_CI_PANEL_CELLS: Int = 1 << 22

# Synthetic control: max_iter Frank-Wolfe steps, each O(n_pre x n_controls).
comptime MAX_CI_SYNTH_WORK: Int = 1 << 28

# A HARD ceiling on any caller-supplied iteration or replicate count, and it is not redundant
# with the products above. A product budget bounds `max_iter x n x p^2`, so it admits
# `max_iter = 2^30` whenever `n` and `p` are 1 — and every iteration of every loop here carries
# constant overhead (a `List` allocation per Frank-Wolfe step, six per bootstrap replicate) that
# the product does not charge for. That is the shape of the confirmed hang rule 4b's "bounding
# memory is not bounding work" section describes: a budget that counts one factor of a product is
# not a budget, and neither is one that counts only the product. 2^20 iterations is far past what
# any convergent method here needs — the Newton fit converges in single digits and Frank-Wolfe in
# hundreds — so this refuses nothing a real caller asks for.
comptime MAX_CI_ITERATIONS: Int = 1 << 20


def ci_status_name(code: Int) -> String:
    """Name for a status code, so a failure surfaces the defect and not a bare number.

    One vocabulary for the whole package (rule 4e). An unrecognised code is reported as
    itself rather than mapped to "ok" or to the nearest known name.
    """
    if code == CI_OK:
        return String("ok")
    if code == CI_ERR_SHAPE:
        return String("invalid_shape")
    if code == CI_ERR_LENGTH_MISMATCH:
        return String("parallel_lists_length_mismatch")
    if code == CI_ERR_NON_FINITE:
        return String("non_finite_input")
    if code == CI_ERR_DIMENSION_TOO_LARGE:
        return String("dimension_too_large")
    if code == CI_ERR_NOT_A_DAG:
        return String("graph_is_not_acyclic")
    if code == CI_ERR_INDEX:
        return String("node_index_out_of_range")
    if code == CI_ERR_NOT_IDENTIFIED:
        return String("effect_not_identified")
    if code == CI_ERR_NO_TREATED:
        return String("no_treated_units")
    if code == CI_ERR_NO_CONTROL:
        return String("no_control_units")
    if code == CI_ERR_NO_OVERLAP:
        return String("no_common_support")
    if code == CI_ERR_DEGENERATE_PROPENSITY:
        return String("propensity_at_zero_or_one")
    if code == CI_ERR_NOT_CONVERGED:
        return String("fit_did_not_converge")
    if code == CI_ERR_SINGULAR:
        return String("singular_design")
    if code == CI_ERR_INSUFFICIENT_DATA:
        return String("insufficient_data")
    if code == CI_ERR_NO_MATCHES:
        return String("no_unit_matched_within_caliper")
    if code == CI_ERR_TREATMENT_NOT_BINARY:
        return String("treatment_not_binary")
    if code == CI_ERR_WORK_BUDGET:
        return String("work_budget_exceeded")
    if code == CI_ERR_DUPLICATE:
        return String("duplicate_or_overlapping_node")
    if code == CI_ERR_INVALID_PARAMETER:
        return String("invalid_parameter")
    return String("unknown_status_") + String(code)


# ── finiteness ───────────────────────────────────────────────────────────────


def ci_finite(v: Float64) -> Bool:
    """True when `v` is neither NaN nor +/-inf.

    NaN fails `v == v`; +/-inf fails `(v - v) == 0.0` because `inf - inf` is NaN. The same
    two-part test the frozen `stats.sort_values` uses, and the reason it matters twice over:
    a non-finite Float64 on the RESULT path ends the worker process, and a non-finite input
    silently defeats every threshold derived from it (rule 4d — with a NaN magnitude,
    `tol = SLOP * (1 + nan)` is NaN and every `fabs(d) > nan` is False, so an audit passes
    having counted zero violations).
    """
    return v == v and (v - v) == 0.0


def ci_all_finite(v: List[Float64]) -> Bool:
    """True when every element of the WHOLE list is finite.

    Deliberately not `(v, n)`: a count parameter here would be one more thing to bound, and
    every caller in this package validates its shape before it needs this.
    """
    for i in range(len(v)):
        if not ci_finite(v[i]):
            return False
    return True


# ── the one tolerance builder (rule 4b) ──────────────────────────────────────


def ci_tolerance(magnitude: Float64, abs_tol: Float64) -> Float64:
    """Rounding allowance for ONE comparison: `abs_tol + 1024 * DBL_EPSILON * magnitude`.

    `magnitude` must be the magnitude of THE QUANTITY BEING JUDGED — for a residual
    `a - b - c`, it is `|a| + |b| + |c|`, the terms of that single comparison. It must never
    be a sum, a max or a norm over other items, and `abs_tol` is the caller's ABSOLUTE
    tolerance, never the relative multiplier.

    All four spellings of rule 4b were measured elsewhere in this tree and every one of them
    is excluded by that sentence:

      1. a `Sigma` over all items — `feas_tol * (1 + Sum|b_i|)` let 200 ordinary capacity rows
         swallow a flat contradiction, and an infeasible LP returned OPTIMAL with duals;
      2. a `max` or norm over all items, which LOOKS per-item and is not — a pivot tolerance
         scaled by the largest diagonal of the whole matrix accepted an eigenvalue of -0.68
         as convex because another diagonal was 1e12;
      3. a `1 + |x|` whose 1.0 FLOOR dominates, i.e. a "relative" slop that is secretly an
         absolute allowance of one whole unit. There is no floor here: at magnitude 0 the
         allowance is exactly `abs_tol`, which is the number the caller chose;
      4. the caller's tolerance used as the RELATIVE multiplier instead of DBL_EPSILON — a
         measured gap of 400,000,000 reported `at_optimum = True`.

    A non-finite `magnitude` or `abs_tol` returns 0.0, making the comparison strict. That is
    the safe direction: a NaN tolerance would pass everything. Callers validate finiteness
    before they get here; this is the backstop, not the check.
    """
    if not ci_finite(magnitude) or not ci_finite(abs_tol):
        return 0.0
    var base = abs_tol if abs_tol > 0.0 else 0.0
    return base + CI_ULP_BUDGET * CI_DBL_EPSILON * fabs(magnitude)


# ── budgets ──────────────────────────────────────────────────────────────────


def ci_product_fits(a: Int, b: Int, budget: Int) -> Bool:
    """True when `a * b <= budget`, WITHOUT forming `a * b`.

    `a * b` is a wrapping 64-bit multiply, so a guard written on the product is not a bound
    at all: `3 * 6148914691236517206 == 2` walked straight past a `rows * cols != len(dense)`
    check and crashed the process. Same shape as `sparse_numerics.csr.dims_fit`, generalised
    to a budget instead of a length.

    A non-positive factor means no work and no allocation, so it fits. A non-positive budget
    admits nothing.
    """
    if budget < 0:
        return False
    if a <= 0 or b <= 0:
        return True
    if a > budget // b:
        return False
    return True


def ci_product3_fits(a: Int, b: Int, c: Int, budget: Int) -> Bool:
    """True when `a * b * c <= budget`, forming no product larger than `budget`.

    Grown factor by factor: once `a * b <= budget` is established the product is safe to
    form, so the second check is another `ci_product_fits`. This is how a work budget with
    several loop bounds is charged for ALL of them — `optimization/multiobjective` bounded
    memory and pair comparisons but not `generations x pop_size x rows x n_vars`.
    """
    if not ci_product_fits(a, b, budget):
        return False
    if a <= 0 or b <= 0:
        return ci_product_fits(c, 1, budget)
    return ci_product_fits(a * b, c, budget)


def ci_matrix_fits(n_rows: Int, n_cols: Int, length: Int) -> Bool:
    """True when `n_rows x n_cols` is exactly `length` cells AND both sit under this
    package's ceilings.

    Shape is delegated to the frozen `sparse_numerics.csr.dims_fit` — the one shared
    division-based shape check in the tree — and this adds only the local ceilings, which are
    tighter than its `MAX_CSR_DIM` because this package allocates several arrays per unit rather
    than one. Rule 1c: a ceiling is necessary and not sufficient, so THREE things are checked —
    each axis against its own ceiling, the JOINT cell count against `MAX_CI_DESIGN_CELLS`
    (because both axes can be legal while their product is a gigabyte), and the exact-cells
    relation against the payload.
    """
    if n_rows > MAX_CI_UNITS or n_cols > MAX_CI_FEATURES:
        return False
    if not ci_product_fits(n_rows, n_cols, MAX_CI_DESIGN_CELLS):
        return False
    return dims_fit(n_rows, n_cols, length)


def ci_panel_fits(n_units: Int, n_periods: Int, length: Int) -> Bool:
    """`ci_matrix_fits` for a panel, whose columns are PERIODS and not features.

    A separate function rather than a wider `ci_matrix_fits`, because `MAX_CI_FEATURES` (2^7)
    is sized by an inverted (p+1)x(p+1) information matrix and a panel has no such matrix. The
    joint cell budget is what binds here.
    """
    if n_units > MAX_CI_UNITS or n_periods < 0:
        return False
    if not ci_product_fits(n_units, n_periods, MAX_CI_PANEL_CELLS):
        return False
    return dims_fit(n_units, n_periods, length)


# ── treatment vectors ────────────────────────────────────────────────────────


def ci_treatment_defect(treatment: List[Int]) -> Int:
    """`CI_OK`, or the code naming why this is not a binary treatment vector.

    Every estimator here is defined for `T in {0, 1}`, and a value of 2 is not a treatment
    this package can interpret. The frozen `causal.ipw_estimate` reads `treatment[i] == 1`
    and silently pools EVERYTHING ELSE — 2, -1, 7 — into the control arm, so a three-arm trial
    returns a number that looks like an ATE and is not one. Refusing is the whole difference.

    Reports `CI_ERR_NO_TREATED` / `CI_ERR_NO_CONTROL` for a one-armed vector, because a
    contrast between two arms one of which is empty does not exist.
    """
    var n_t = 0
    var n_c = 0
    for i in range(len(treatment)):
        var t = treatment[i]
        if t == 1:
            n_t += 1
        elif t == 0:
            n_c += 1
        else:
            return CI_ERR_TREATMENT_NOT_BINARY
    if n_t == 0:
        return CI_ERR_NO_TREATED
    if n_c == 0:
        return CI_ERR_NO_CONTROL
    return CI_OK


def ci_count_treated(treatment: List[Int]) -> Int:
    """How many entries equal 1. Counts nothing else as treated; see `ci_treatment_defect`."""
    var n_t = 0
    for i in range(len(treatment)):
        if treatment[i] == 1:
            n_t += 1
    return n_t


# ── deterministic index orderings ────────────────────────────────────────────


def _argsort(keys: List[Float64], descending: Bool) -> List[Int]:
    """STABLE merge sort over indices. Iterative (bottom-up), never recursive.

    Stability is the determinism property that matters: ties break by original index, so the
    permutation is a pure function of the key VALUES and does not depend on the pivot choices
    a quicksort would make. `sorting.mojo` and `stats.fast_sort` sort VALUES and return no
    permutation, so there is no frozen kernel to call here — which the suite checks the only
    way it can, by asserting that the values gathered through this permutation are identical
    to the frozen `sorting.mergesort` of the same input.
    """
    var n = len(keys)
    var order = List[Int](capacity=n if n > 0 else 1)
    for i in range(n):
        order.append(i)
    if n < 2:
        return order^

    var buf = List[Int](capacity=n)
    for i in range(n):
        buf.append(0)

    var width = 1
    while width < n:
        var lo = 0
        while lo < n:
            var mid = lo + width
            if mid > n:
                mid = n
            var hi = lo + 2 * width
            if hi > n:
                hi = n
            var i = lo
            var j = mid
            var k = lo
            while i < mid and j < hi:
                var take_left: Bool
                if descending:
                    # `>=` keeps the earlier index first on a tie: stability.
                    take_left = keys[order[i]] >= keys[order[j]]
                else:
                    take_left = keys[order[i]] <= keys[order[j]]
                if take_left:
                    buf[k] = order[i]
                    i += 1
                else:
                    buf[k] = order[j]
                    j += 1
                k += 1
            while i < mid:
                buf[k] = order[i]
                i += 1
                k += 1
            while j < hi:
                buf[k] = order[j]
                j += 1
                k += 1
            for t in range(lo, hi):
                order[t] = buf[t]
            lo += 2 * width
        width *= 2
    return order^


def ci_argsort_asc(keys: List[Float64]) -> List[Int]:
    """Indices of `keys` in ascending order, ties by original index. Empty on a non-finite key.

    A NaN key makes every comparison False, so a sort would still terminate and would return
    an order that means nothing. An ordering that does not exist is absent (rule 4), so the
    answer is the empty list and the caller can tell.
    """
    if not ci_all_finite(keys):
        return List[Int]()
    return _argsort(keys, False)


def ci_argsort_desc(keys: List[Float64]) -> List[Int]:
    """Indices of `keys` in descending order, ties by original index. Empty on a non-finite key."""
    if not ci_all_finite(keys):
        return List[Int]()
    return _argsort(keys, True)


def ci_is_permutation(order: List[Int], n: Int) -> Bool:
    """True when `order` is exactly a permutation of `0..n-1`.

    Exists so a caller — and the suite — can CHECK a permutation instead of trusting one.
    `n` is required to EQUAL `len(order)`, so the seen-mask allocation is payload-bound and
    every read is `order[i]` for `i < len(order)`. `ci_is_permutation(five, 5)` is the A-Z
    harness's fixed call and it answers False without indexing anything.

    @capability ci_is_permutation
    complexity: O(n)
    counts:
    - n == len(order) [kernel_validated]
    @endcapability
    """
    if n < 0 or len(order) != n:
        return False
    var seen = List[Bool](capacity=n if n > 0 else 1)
    for _ in range(n):
        seen.append(False)
    for i in range(n):
        var v = order[i]
        if v < 0 or v >= n:
            return False
        if seen[v]:
            return False
        seen[v] = True
    return True
