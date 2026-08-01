"""
formulation — the flat, typed formulation container, its validation, its lowering.

The wire form of one optimisation formulation, the shape a benchmark's ground-truth
`instance_data` compiles into:

  * `n_vars`, `n_cons` — declared dimensions, both validated against every array they
    claim to describe before any index is used (a read past the end is UNCATCHABLE).
  * `c`, `c0` — objective coefficients and constant. Direction travels separately as a
    `maximize` flag on the solving drivers, never as a negated vector.
  * `a`, `senses`, `rhs` — dense row-major rows, `model.SENSE_LE/EQ/GE`, right-hand
    sides. Dense because benchmark instances are small and dense is the shape
    `lp_solve`/`milp_solve` already take; the cell budget below is the size guard.
  * `var_kind`, `var_lower`, `var_upper`, `var_flags` — per-variable kind and bounds in
    `optimization.model`'s own column format (`VAR_FLAG_HAS_LOWER`/`HAS_UPPER`, finite
    padding in unflagged slots), validated by `model.variables_validate_flat` rather
    than by a second spelling of the same rules.

Three drivers, one shared validator:

  * `formulation_check_flat` — refusal-first validation with a WHERE (`constraint_index`
    / `var_index`) beside every WHAT (`status`), plus the kind census dispatch needs.
  * `formulation_lower_flat` — compiles declared bounds onto the solvers' `x >= 0`
    convention: substitute `x = y + lower` (so `y >= 0`), fold the shift into the
    objective constant and every row's rhs, and emit one explicit `y_j <= upper - lower`
    row per declared upper bound. `row_kind`/`row_ref` map every lowered row back to the
    original constraint or variable it came from, which is what lets an infeasibility
    core name the caller's rows instead of internal ones.
  * `formulation_point_audit_flat` — re-checks a candidate point against EVERY original
    row, bound and integrality declaration, independently of any solver and of the
    lowering. `model.sense_violation` is the one definition of "this row fails"; the
    per-row budget mirrors `integer._verify_row_budget` (the caller's absolute
    tolerance, an ulp allowance at the row's own magnitude via `linear`'s imported
    constants, and an integrality-snap term over discrete columns only) — the two
    rejected forms documented there are rejected here for the same measured reasons.

What is NOT representable, on purpose: a variable with no lower bound. The solver plane
underneath is `x >= 0`; a free variable would need a split into two columns, which
changes the variable count the caller sees. It is a TYPED refusal (`OPTM_ERR_FREE_VARIABLE`)
at lowering time — counted, never silently dropped — and the same policy holds for a
discrete variable whose lower bound is fractional (`OPTM_ERR_DISCRETE_SHIFT`): shifting
an integer variable by 0.5 would move the integer grid itself.
@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_optmodel_formulation.mojo
benchmark: none
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability
"""

from std.math import abs as fabs

from optimization.integer import milp_status_name
from optimization.linear import LP_DBL_EPSILON, LP_FEAS_ULP_BUDGET
from optimization.model import (
    DEFAULT_FEASIBILITY_TOL,
    DEFAULT_INTEGRALITY_TOL,
    MODEL_ERR_DENSE_SHAPE,
    MODEL_ERR_DIMENSION_TOO_LARGE,
    MODEL_ERR_LENGTH_MISMATCH,
    MODEL_ERR_NON_FINITE_COEFFICIENT,
    MODEL_ERR_NON_FINITE_POINT,
    MODEL_ERR_NON_FINITE_RHS,
    MODEL_ERR_NON_FINITE_VALUE,
    MODEL_ERR_POLICY,
    MODEL_ERR_SENSE,
    MODEL_INT_GRID_MAX,
    MODEL_OK,
    SENSE_EQ,
    SENSE_GE,
    SENSE_LE,
    VAR_CONTINUOUS,
    _round_f as _nearest_int,
    has_lower_bound,
    has_upper_bound,
    model_finite as _finite,
    sense_violation,
    variables_validate_flat,
)
from sparse_numerics.csr import dims_fit

# ── status codes ──────────────────────────────────────────────────────────────
# This package composes `optimization`, whose numbering already occupies 0-30 (model),
# 40-42 / 60-63 (linear), 80-86 (explain), 100-105 (integer), 110-117 (quadratic),
# 120-129 (routing), 130-139 (scheduling), 140-149 (multiobjective) and 150-170 (robust).
# Underlying statuses are passed through in their own fields, so this block starts at 200
# to stay clear of every vocabulary it can carry. `optm_status_name` falls through to
# `integer.milp_status_name`, which falls through to linear's and model's tables — one
# name per integer across the whole composed surface.

# A variable with no declared lower bound. The plane underneath is `x >= 0`; refusing is
# the honest answer, and the code makes the refusal COUNTABLE by a harness.
comptime OPTM_ERR_FREE_VARIABLE: Int = 200

# An integer or binary variable whose lower bound is fractional: `x = y + 0.5` with `y`
# integral describes a DIFFERENT grid than the caller declared. Refused, never rounded —
# a bound that stops meaning what the caller wrote is the failure mode, not the bound.
comptime OPTM_ERR_DISCRETE_SHIFT: Int = 201

# The solver proved there is no feasible point. Carried with an `infeasibility_core`
# mapped back to the caller's own constraint/bound indices whenever the core solve
# produced one, so the refusal NAMES the conflict instead of shrugging.
comptime OPTM_REFUSED_INFEASIBLE: Int = 202

# The LP (or the MILP's root relaxation) is unbounded in the asked direction. For a pure
# LP this is a proof about the caller's model; for a MILP it is a proof that the search
# cannot even start — either way there is no number to report.
comptime OPTM_REFUSED_UNBOUNDED: Int = 203

# A node, depth or iteration limit stopped the search before optimality was proven. The
# incumbent (if any) and the surviving bound travel as diagnostics, but `has_objective`
# stays False: an incumbent reported as an optimum is the wrong answer this package
# exists to prevent.
comptime OPTM_REFUSED_SEARCH_LIMIT: Int = 204

# The solver returned something it could not certify (numerical breakdown, a failed
# relaxation, any status outside the enumerated outcomes). Refused rather than relayed.
comptime OPTM_REFUSED_UNCERTIFIED: Int = 205

# The solver CLAIMED optimal but the independent re-audit of its point against the
# ORIGINAL formulation failed — a lowering bug, a solver bug, or numerics past the ulp
# budget. The one bucket that must never degrade into a reported number.
comptime OPTM_REFUSED_SELF_CHECK: Int = 206

# The judge was handed a non-finite ground truth or tolerance: nothing can be compared.
comptime OPTM_ERR_GROUND_TRUTH: Int = 207

# ── verdict codes (a classification, not a status) ────────────────────────────
# Exactly the three buckets the ceiling measurement counts. WRONG is the bucket kept
# empty by construction: any instance landing there is a bug in the plane or in the
# ground truth, never an acceptable output.

comptime OPTM_VERDICT_VERIFIED: Int = 0
comptime OPTM_VERDICT_REFUSED: Int = 1
comptime OPTM_VERDICT_WRONG: Int = 2

# ── size budget ───────────────────────────────────────────────────────────────
# Rule 1c arithmetic for the lowered matrix, stated where the ceiling is set: the
# lowering allocates ONE dense `rows_out x n_vars` Float64 block plus five parallel
# `rows_out`-length columns and four `n_vars`-length columns. At the 2^26-cell ceiling
# the dense block is 512 MB — the same one-object budget `sparse_numerics.MAX_CSR_DIM`
# documents — and the parallel columns add at most a few percent on top. The input `a`
# already occupies `n_cons * n_vars` cells in the caller's memory, but `rows_out` also
# counts one row PER DECLARED UPPER BOUND, so a one-row model over 2^20 variables would
# otherwise materialise a ~2^40-cell block from a small payload. Checked by DIVISION,
# never by a wrapping multiply.
comptime OPTM_MAX_LOWERED_CELLS: Int = 1 << 26


fn optm_status_name(code: Int) -> String:
    """Name for a status, falling through the composed solver vocabularies."""
    if code == OPTM_ERR_FREE_VARIABLE:
        return "free_variable_unsupported_declare_a_lower_bound"
    if code == OPTM_ERR_DISCRETE_SHIFT:
        return "discrete_variable_lower_bound_not_integral"
    if code == OPTM_REFUSED_INFEASIBLE:
        return "refused_infeasible"
    if code == OPTM_REFUSED_UNBOUNDED:
        return "refused_unbounded"
    if code == OPTM_REFUSED_SEARCH_LIMIT:
        return "refused_search_limit"
    if code == OPTM_REFUSED_UNCERTIFIED:
        return "refused_uncertified"
    if code == OPTM_REFUSED_SELF_CHECK:
        return "refused_self_check_failed"
    if code == OPTM_ERR_GROUND_TRUTH:
        return "ground_truth_not_comparable"
    return milp_status_name(code)


fn optm_verdict_name(code: Int) -> String:
    """Name for a verdict bucket, so a table never prints a bare integer."""
    if code == OPTM_VERDICT_VERIFIED:
        return "verified"
    if code == OPTM_VERDICT_REFUSED:
        return "refused"
    if code == OPTM_VERDICT_WRONG:
        return "wrong"
    return "unknown_verdict"


# ── return-only result structs ────────────────────────────────────────────────
# Declared in this file because a returned struct's marshalling spec is parsed per FILE:
# returning a struct owned by another module drops the function from the runtime
# contract silently.


@fieldwise_init
struct FormulationCheck(Copyable, Movable):
    """Verdict on one formulation, with WHERE beside WHAT and the kind census.

    `ok` is the authority. `constraint_index` / `var_index` locate the defect (-1 when
    not applicable), and the census (`n_continuous` / `n_integer` / `n_binary`) is what
    the solving driver dispatches on, so it is computed once here and carried.
    """

    var status: Int
    var ok: Bool
    var n_vars: Int
    var n_cons: Int
    var constraint_index: Int
    var var_index: Int
    var n_continuous: Int
    var n_integer: Int
    var n_binary: Int


@fieldwise_init
struct LoweredForm(Copyable, Movable):
    """A formulation compiled onto `x >= 0`, with the map back to the caller's rows.

    On any status other than `MODEL_OK` every list is EMPTY and `ok` is False — a
    half-lowered program is not an input to anything. `shift[j]` is the amount added
    back to recover the caller's variable (`x_j = y_j + shift[j]`). `row_kind[i]` is 0
    for a caller constraint (`row_ref[i]` = its index) and 1 for an upper-bound row
    (`row_ref[i]` = the variable's index); `n_upper_rows` counts kind-1 rows, so
    `rows == n_cons + n_upper_rows` always.
    """

    var status: Int
    var ok: Bool
    var rows: Int
    var cols: Int
    var n_upper_rows: Int
    var constant: Float64
    var c: List[Float64]
    var a: List[Float64]
    var senses: List[Int]
    var rhs: List[Float64]
    var var_kind: List[Int]
    var shift: List[Float64]
    var row_kind: List[Int]
    var row_ref: List[Int]


@fieldwise_init
struct PointAudit(Copyable, Movable):
    """One candidate point against EVERY declaration of the original formulation.

    `status` says whether the audit RAN (`MODEL_OK`) or why it could not; `feasible` is
    the verdict and is False the moment any row, bound or integrality check fails.
    Worst offenders are reported per category with their violation magnitudes, so a
    failed audit names what failed instead of shrugging. `objective` is `c·x + c0`
    recomputed here, present whenever the arithmetic stayed finite — reported even for
    an infeasible point, because "what does the point claim" and "is the point real"
    are different questions and a judge needs both.
    """

    var status: Int
    var feasible: Bool
    var n_row_violations: Int
    var worst_row: Int
    var row_violation: Float64
    var n_bound_violations: Int
    var worst_bound_var: Int
    var bound_violation: Float64
    var n_integrality_violations: Int
    var worst_integrality_var: Int
    var integrality_violation: Float64
    var has_objective: Bool
    var objective: Float64


fn _check_failure(
    status: Int, n_vars: Int, n_cons: Int, constraint_index: Int, var_index: Int
) -> FormulationCheck:
    return FormulationCheck(
        status, False, n_vars, n_cons, constraint_index, var_index, 0, 0, 0
    )


fn _audit_failure(status: Int) -> PointAudit:
    return PointAudit(
        status, False, 0, -1, 0.0, 0, -1, 0.0, 0, -1, 0.0, False, 0.0
    )


fn _empty_lowered(status: Int) -> LoweredForm:
    return LoweredForm(
        status, False, 0, 0, 0, 0.0,
        List[Float64](), List[Float64](), List[Int](), List[Float64](),
        List[Int](), List[Float64](), List[Int](), List[Int](),
    )


fn formulation_check_flat(
    n_vars: Int, n_cons: Int, c: List[Float64], c0: Float64,
    a: List[Float64], senses: List[Int], rhs: List[Float64], var_kind: List[Int],
    var_lower: List[Float64], var_upper: List[Float64], var_flags: List[Int],
) -> FormulationCheck:
    """Validate one formulation, refusal-first, and census its variable kinds.

    Every guard runs before any index is used: the dense shape by `dims_fit` (a division,
    never a wrapping multiply), every parallel length, then the variable block through
    `model.variables_validate_flat` — the package's ONE definition of a legal variable
    column, which is what rejects crossed bounds, non-finite padding, a binary outside
    `[0, 1]` and an integer box containing no integer. `n_vars >= 1` is required: a
    zero-variable formulation optimises nothing and a benchmark never states one, so it
    is a shape defect here rather than a degenerate accept.

    @capability formulation_check_flat
    complexity: O(n_cons * n_vars)
    counts:
    - n_cons * n_vars == len(a) [kernel_validated]
    - n_vars == len(c, var_kind, var_lower, var_upper, var_flags) [kernel_validated]
    - n_cons == len(senses, rhs) [kernel_validated]
    @endcapability
    """
    if n_vars < 1 or n_cons < 0 or not dims_fit(n_cons, n_vars, len(a)):
        return _check_failure(MODEL_ERR_DENSE_SHAPE, n_vars, n_cons, -1, -1)
    if (
        len(c) != n_vars or len(var_kind) != n_vars or len(var_lower) != n_vars
        or len(var_upper) != n_vars or len(var_flags) != n_vars
        or len(senses) != n_cons or len(rhs) != n_cons
    ):
        return _check_failure(MODEL_ERR_LENGTH_MISMATCH, n_vars, n_cons, -1, -1)

    # `var_start` is zeros: this format carries no warm start, and zero is finite, so the
    # start column can never be the defect the block is rejected for.
    var start = List[Float64]()
    for _ in range(n_vars):
        start.append(0.0)
    var vars_check = variables_validate_flat(
        var_lower, var_upper, var_kind, var_flags, start, DEFAULT_INTEGRALITY_TOL
    )
    if vars_check.status != MODEL_OK:
        return _check_failure(
            vars_check.status, n_vars, n_cons, -1, vars_check.var_index
        )

    if not _finite(c0):
        return _check_failure(MODEL_ERR_NON_FINITE_COEFFICIENT, n_vars, n_cons, -1, -1)
    for j in range(n_vars):
        if not _finite(c[j]):
            return _check_failure(
                MODEL_ERR_NON_FINITE_COEFFICIENT, n_vars, n_cons, -1, j
            )
    for i in range(n_cons):
        var sense = senses[i]
        if sense != SENSE_LE and sense != SENSE_EQ and sense != SENSE_GE:
            return _check_failure(MODEL_ERR_SENSE, n_vars, n_cons, i, -1)
        if not _finite(rhs[i]):
            return _check_failure(MODEL_ERR_NON_FINITE_RHS, n_vars, n_cons, i, -1)
        for j in range(n_vars):
            if not _finite(a[i * n_vars + j]):
                return _check_failure(
                    MODEL_ERR_NON_FINITE_COEFFICIENT, n_vars, n_cons, i, j
                )

    return FormulationCheck(
        MODEL_OK, True, n_vars, n_cons, -1, -1,
        vars_check.n_continuous, vars_check.n_integer, vars_check.n_binary,
    )


fn formulation_lower_flat(
    n_vars: Int, n_cons: Int, c: List[Float64], c0: Float64,
    a: List[Float64], senses: List[Int], rhs: List[Float64], var_kind: List[Int],
    var_lower: List[Float64], var_upper: List[Float64], var_flags: List[Int],
) -> LoweredForm:
    """Compile declared bounds onto the solvers' `x >= 0` convention.

    The substitution is `x_j = y_j + shift_j` with `shift_j` the declared lower bound,
    exact for the caller because it is added back verbatim: the objective constant
    becomes `c0 + Σ c_j shift_j`, every caller row's rhs drops `Σ a_ij shift_j`, and
    each declared upper bound becomes the explicit row `y_j <= upper_j - shift_j`.
    Refusals are typed, never silent: a variable with no lower bound is
    `OPTM_ERR_FREE_VARIABLE` (the WHERE is in the check driver; re-run it), a discrete
    variable with a fractional lower bound is `OPTM_ERR_DISCRETE_SHIFT`, and a lowered
    block past `OPTM_MAX_LOWERED_CELLS` is `MODEL_ERR_DIMENSION_TOO_LARGE` — the rule-1c
    arithmetic is at the constant's declaration.

    Binary variables keep their kind: `variables_validate_flat` already forced their
    declared box inside `[0, 1]`, `OPTM_ERR_DISCRETE_SHIFT` forces the shift onto the
    grid, so the shift is 0 or 1 and the shifted domain stays inside `{0, 1}` — the
    `y_j <= 1` row `milp_solve` adds for the kind is therefore valid (if loose) and the
    explicit upper row emitted here is what binds.

    @capability formulation_lower_flat
    complexity: O(n_cons * n_vars + n_vars * n_vars)
    counts:
    - n_cons * n_vars == len(a) [kernel_validated]
    - n_vars == len(c, var_kind, var_lower, var_upper, var_flags) [kernel_validated]
    - n_cons == len(senses, rhs) [kernel_validated]
    @endcapability
    """
    var check = formulation_check_flat(
        n_vars, n_cons, c, c0, a, senses, rhs, var_kind,
        var_lower, var_upper, var_flags,
    )
    if not check.ok:
        return _empty_lowered(check.status)

    var n_upper = 0
    for j in range(n_vars):
        if not has_lower_bound(var_flags[j]):
            return _empty_lowered(OPTM_ERR_FREE_VARIABLE)
        if var_kind[j] != VAR_CONTINUOUS:
            if _nearest_int(var_lower[j]) != var_lower[j]:
                return _empty_lowered(OPTM_ERR_DISCRETE_SHIFT)
        if has_upper_bound(var_flags[j]):
            n_upper += 1

    var rows_out = n_cons + n_upper
    # Division, not multiplication: `rows_out * n_vars` can wrap, `//` cannot.
    if rows_out > 0 and rows_out > OPTM_MAX_LOWERED_CELLS // n_vars:
        return _empty_lowered(MODEL_ERR_DIMENSION_TOO_LARGE)

    var shift = List[Float64]()
    for j in range(n_vars):
        shift.append(var_lower[j])

    # Objective: fold the shift into the constant. Any overflow to non-finite is refused
    # here rather than handed to a solver whose own finiteness guard would name the
    # wrong culprit (a coefficient, when the defect is the fold).
    var constant = c0
    for j in range(n_vars):
        constant += c[j] * shift[j]
    if not _finite(constant):
        return _empty_lowered(MODEL_ERR_NON_FINITE_VALUE)

    var out_c = List[Float64]()
    for j in range(n_vars):
        out_c.append(c[j])
    var out_kind = List[Int]()
    for j in range(n_vars):
        out_kind.append(var_kind[j])

    var out_a = List[Float64]()
    var out_senses = List[Int]()
    var out_rhs = List[Float64]()
    var row_kind = List[Int]()
    var row_ref = List[Int]()

    for i in range(n_cons):
        var base = i * n_vars
        var folded = rhs[i]
        for j in range(n_vars):
            var coefficient = a[base + j]
            out_a.append(coefficient)
            folded -= coefficient * shift[j]
        if not _finite(folded):
            return _empty_lowered(MODEL_ERR_NON_FINITE_VALUE)
        out_senses.append(senses[i])
        out_rhs.append(folded)
        row_kind.append(0)
        row_ref.append(i)

    for j in range(n_vars):
        if not has_upper_bound(var_flags[j]):
            continue
        for k in range(n_vars):
            if k == j:
                out_a.append(1.0)
            else:
                out_a.append(0.0)
        out_senses.append(SENSE_LE)
        # Non-negative because `variables_validate_flat` rejected crossed bounds; finite
        # because both endpoints are.
        out_rhs.append(var_upper[j] - shift[j])
        row_kind.append(1)
        row_ref.append(j)

    return LoweredForm(
        MODEL_OK, True, rows_out, n_vars, n_upper, constant,
        out_c^, out_a^, out_senses^, out_rhs^, out_kind^, shift^, row_kind^, row_ref^,
    )


fn _audit_row_budget(
    absolute_tol: Float64, integrality_tol: Float64,
    activity_scale: Float64, snap_scale: Float64,
) -> Float64:
    """The `integer._verify_row_budget` shape over precomputed scales.

    Three terms with three meanings: the caller's ABSOLUTE allowance used absolutely, an
    ulp rounding allowance AT the judged quantity's own magnitude
    (`LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * activity_scale`), and the integrality snap
    over discrete columns only (`integrality_tol * snap_scale`). A non-finite relative
    term contributes 0.0 rather than `inf` — an infinite budget switches its own test
    off. The two rejected forms (`tol * (1 + Σ|b|)` aggregate, `tol * (1 + |b|)`
    per-row) are documented with their measured failures in `linear._lp_row_gap_budget`.
    """
    var budget = absolute_tol
    if budget < 0.0:
        budget = 0.0
    var rounding = LP_FEAS_ULP_BUDGET * LP_DBL_EPSILON * activity_scale
    if _finite(rounding) and rounding > 0.0:
        budget += rounding
    var snap = integrality_tol * snap_scale
    if _finite(snap) and snap > 0.0:
        budget += snap
    if not _finite(budget) or budget < 0.0:
        return 0.0
    return budget


fn formulation_point_audit_flat(
    n_vars: Int, n_cons: Int, c: List[Float64], c0: Float64,
    a: List[Float64], senses: List[Int], rhs: List[Float64], var_kind: List[Int],
    var_lower: List[Float64], var_upper: List[Float64], var_flags: List[Int],
    x: List[Float64], feasibility_tol: Float64, integrality_tol: Float64,
) -> PointAudit:
    """Audit `x` against EVERY row, bound and integrality declaration, solver-free.

    This is the independent half of the plane's honesty: it reads the ORIGINAL
    formulation, never the lowering, so a lowering bug and a solver bug are both
    catchable by the same check. Rows are judged by `model.sense_violation` under the
    `_audit_row_budget` allowance; bounds get the same three-term budget at the bound's
    own magnitude; a discrete coordinate past `MODEL_INT_GRID_MAX` is structurally
    integral (every representable Float64 there is an integer). A free-of-upper or
    free-of-lower slot simply skips that side — the audit checks what was DECLARED.

    @capability formulation_point_audit_flat
    complexity: O(n_cons * n_vars)
    counts:
    - n_cons * n_vars == len(a) [kernel_validated]
    - n_vars == len(c, var_kind, var_lower, var_upper, var_flags, x) [kernel_validated]
    - n_cons == len(senses, rhs) [kernel_validated]
    @endcapability
    """
    var check = formulation_check_flat(
        n_vars, n_cons, c, c0, a, senses, rhs, var_kind,
        var_lower, var_upper, var_flags,
    )
    if not check.ok:
        return _audit_failure(check.status)
    if len(x) != n_vars:
        return _audit_failure(MODEL_ERR_LENGTH_MISMATCH)
    if not (_finite(feasibility_tol) and _finite(integrality_tol)):
        return _audit_failure(MODEL_ERR_POLICY)
    if feasibility_tol < 0.0 or integrality_tol < 0.0:
        return _audit_failure(MODEL_ERR_POLICY)
    for j in range(n_vars):
        if not _finite(x[j]):
            return _audit_failure(MODEL_ERR_NON_FINITE_POINT)

    var n_row_bad = 0
    var worst_row = -1
    var worst_row_violation: Float64 = 0.0
    for i in range(n_cons):
        var base = i * n_vars
        var activity: Float64 = 0.0
        var activity_scale = fabs(rhs[i])
        var snap_scale: Float64 = 0.0
        for j in range(n_vars):
            var coefficient = a[base + j]
            activity += coefficient * x[j]
            activity_scale += fabs(coefficient) * fabs(x[j])
            if var_kind[j] != VAR_CONTINUOUS:
                snap_scale += fabs(coefficient)
        var budget = _audit_row_budget(
            feasibility_tol, integrality_tol, activity_scale, snap_scale
        )
        var violation = sense_violation(activity, senses[i], rhs[i], budget)
        if violation != 0.0:
            # `MODEL_VIOLATION_ABSENT` (-1.0) can only mean a non-finite activity here —
            # finite cells times a finite point can still overflow — and an activity the
            # audit cannot measure is a row it must not certify.
            n_row_bad += 1
            var magnitude = violation
            if magnitude < 0.0:
                magnitude = fabs(activity)
            if magnitude >= worst_row_violation:
                worst_row_violation = magnitude
                worst_row = i

    var n_bound_bad = 0
    var worst_bound_var = -1
    var worst_bound_violation: Float64 = 0.0
    var n_int_bad = 0
    var worst_int_var = -1
    var worst_int_violation: Float64 = 0.0
    for j in range(n_vars):
        var discrete_snap: Float64 = 0.0
        if var_kind[j] != VAR_CONTINUOUS:
            discrete_snap = 1.0
        if has_lower_bound(var_flags[j]):
            var budget = _audit_row_budget(
                feasibility_tol, integrality_tol,
                fabs(var_lower[j]) + fabs(x[j]), discrete_snap,
            )
            var under = sense_violation(x[j], SENSE_GE, var_lower[j], budget)
            if under != 0.0:
                n_bound_bad += 1
                if under >= worst_bound_violation:
                    worst_bound_violation = under
                    worst_bound_var = j
        if has_upper_bound(var_flags[j]):
            var budget = _audit_row_budget(
                feasibility_tol, integrality_tol,
                fabs(var_upper[j]) + fabs(x[j]), discrete_snap,
            )
            var over = sense_violation(x[j], SENSE_LE, var_upper[j], budget)
            if over != 0.0:
                n_bound_bad += 1
                if over >= worst_bound_violation:
                    worst_bound_violation = over
                    worst_bound_var = j
        if var_kind[j] != VAR_CONTINUOUS and fabs(x[j]) <= MODEL_INT_GRID_MAX:
            var gap = fabs(x[j] - _nearest_int(x[j]))
            if gap > integrality_tol:
                n_int_bad += 1
                if gap >= worst_int_violation:
                    worst_int_violation = gap
                    worst_int_var = j

    var objective = c0
    for j in range(n_vars):
        objective += c[j] * x[j]
    var has_objective = _finite(objective)
    if not has_objective:
        objective = 0.0

    var feasible = n_row_bad == 0 and n_bound_bad == 0 and n_int_bad == 0
    return PointAudit(
        MODEL_OK, feasible,
        n_row_bad, worst_row, worst_row_violation,
        n_bound_bad, worst_bound_var, worst_bound_violation,
        n_int_bad, worst_int_var, worst_int_violation,
        has_objective, objective,
    )
