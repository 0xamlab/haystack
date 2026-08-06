"""
sparse_numerics.diagnostics — structural and numerical health of a sparse matrix.
Zero Python.

Why this module exists
----------------------
Every frozen kernel that answers a question about a sparse matrix answers it with a
number, and spends one of the numbers it can return on "I could not answer". A caller
holding the return value cannot tell the two apart. Each of these was re-read from
source before being wrapped:

* `sparse.sparse_density` returns `0.0` when `nrows * ncols == 0` — "perfectly sparse"
  for a matrix that has no elements at all. It also divides `len(entries)` by
  `nrows * ncols`, and COO permits duplicate coordinates, so the density of a
  `sparse_add` result routinely exceeds 1.0: that function concatenates both entry
  lists and nothing on the path coalesces. Density is reported here only when the
  matrix has at least one element, and only for the coalesced image, so it lands in
  [0, 1] or is absent.

* `sparse_vector.sv_max` scans the STORED values only. An all-negative sparse matrix
  therefore reports its largest *negative* value while the matrix's true maximum is the
  implicit zero sitting in every unstored position. Both numbers are reported here,
  under different names, plus the boolean saying whether they coincide.

* `sparse_vector.sv_max` on an empty list returns `0.0` — "the maximum of nothing is
  zero". The maximum of nothing does not exist; `max_abs_present` is how that is said.

* `sparse_vector.sv_nnz` counts anything with `|v| > 1e-30`, while `sparse_from_dense`
  and `sparse_vector.dense_to_sparse` refuse to *store* anything with `|v| < 1e-15`.
  The band [1e-30, 1e-15) is "nonzero" to the counter and "not worth storing" to the
  builders. Both thresholds are named as constants below; `numeric_nnz` is sv_nnz's
  answer and is documented as sv_nnz's answer. Re-thresholding at 1e-15 would invent a
  third convention, which is worse than reporting an inconsistency that exists.

* `linalg_ext.mat_condition_number` returns exactly `1e18` for a non-square matrix AND
  for a singular one — it detects singularity by `linalg.mat_inv` handing back an
  all-zero matrix, which is itself `mat_inv`'s sentinel. `1e18` is not a condition
  number; it is two unrelated failures wearing one costume. A third case hides in
  there: on a 0x0 matrix the "inverse is all zeros" scan is vacuously true, so the
  empty matrix is reported singular. All three are separate statuses here and none of
  them is a number.

* Every max/min loop in the tree compares with `>` or `<`, and every comparison against
  a NaN is False, so a NaN never wins a maximum: it is *invisible* rather than
  poisonous. `sv_nnz` counts a NaN as a zero for the same reason (`fabs(nan) > 1e-30`
  is False). `matrix_ops.matrix_norm_inf` is worse than invisible — `row_sum` becomes
  NaN, `NaN > max_sum` is False, so the row is silently skipped and the function
  returns the norm of the *other* rows, which looks entirely plausible. Non-finite
  values are counted and located here, excluded from every extremum, and the `finite`
  flag says the norms describe the finite part only.

Storage conventions that do NOT match, and are therefore not used
-----------------------------------------------------------------
`matrix_ops.matrix_norm_1`, `matrix_ops.matrix_norm_inf` and
`matrix_decomp.is_symmetric` all take `List[List[Float64]]` — a dense, nested,
row-of-rows matrix. Reaching them from a CSR means materialising `nrows * ncols`
Float64s, which is the one thing this layout exists to avoid, and (for the norms)
inheriting the silent NaN-row skip described above. The row and column sums here are
accumulated over the stored values instead, in O(nnz); the hand-written suite pins them
against `matrix_norm_inf`/`matrix_norm_1`/`is_symmetric` on the dense image of a small
finite matrix, so the two definitions are proved equal where both are honest rather
than assumed equal.

`linalg_ext.mat_norm_inf` and `mat_condition_number` take `linalg.Matrix`, which *is*
row-major dense — the same convention `csr_to_dense` produces. Those two are called
directly, on the dense image, in the condition-number path only, where an O(n^3)
inverse already dominates the O(n^2) densification.

What is reused rather than rebuilt
----------------------------------
`sparse.sparse_density` and `sparse.sparse_trace` are the density and the trace; there
is no fourth density and no second trace here. `sparse_vector.sv_max` is the stored
maximum and `sparse_vector.sv_nnz` is the numeric nonzero count. `csr.csr_coalesce`,
`csr_transpose`, `csr_row_counts`, `csr_to_coo`, `csr_to_dense` and `csr_validate` do
all the structural work; column counts are the row counts of the transpose rather than
a second counting loop.

Out-of-range indices are diagnosed, not rejected
------------------------------------------------
`csr_validate_flat` checks index range *last*, after everything that bounds the
iteration (shape, paired lengths, indptr length, zero head, monotonicity, tail == nnz).
That ordering is documented as load-bearing in `csr.mojo` and this module depends on
it: a status of `CSR_ERR_INDEX_OUT_OF_RANGE` proves the pointer structure is sound, so
the offending entries can be dropped and the rest of the matrix diagnosed. A report is
most valuable for a matrix that is *not* sound, so rejecting one outright would defeat
the purpose. `status` still names the defect, `out_of_range` counts the dropped
entries, and `diagnosed` says whether the numbers describe a matrix at all. When the
pointer structure itself is broken there is nothing safe to iterate, so no numbers are
produced — indexing on a bad `indptr` is an uncatchable process crash, not an
exception.
"""
from std.math import abs as fabs, isinf, isnan

from linalg import Matrix, mat_from_list
from linalg_ext import mat_condition_number, mat_norm_inf
from sparse import sparse_density, sparse_trace
from sparse_numerics.csr import (
    dims_fit,
    CSRMatrix,
    CSR_ERR_INDEX_OUT_OF_RANGE,
    CSR_ERR_INVALID_DIMENSIONS,
    CSR_OK,
    csr_coalesce,
    csr_empty,
    csr_from_arrays,
    csr_from_dense,
    csr_row_counts,
    csr_status_name,
    csr_to_coo,
    csr_to_dense,
    csr_transpose,
    csr_validate,
)
from sparse_vector import sv_max, sv_nnz

# ── thresholds the tree already disagrees about, named so a caller can see them ──
# Constants rather than comments: a caller comparing `numeric_nnz` against its own
# notion of "nonzero" needs the number that produced it, and a caller round-tripping
# through a dense matrix needs the number that decided what got stored.

comptime DIAG_SV_NNZ_THRESHOLD: Float64 = 1e-30
comptime DIAG_DENSE_STORE_THRESHOLD: Float64 = 1e-15

# Matches the tolerance of the frozen `matrix_decomp.is_symmetric` and
# `linalg_ext.mat_is_symmetric`, so "symmetric" means the same thing here as there.
comptime DIAG_SYMMETRY_TOL: Float64 = 1e-10

# The value `linalg_ext.mat_condition_number` returns for a failure. Anything at or
# above it is treated as "no estimate", never as a number.
comptime DIAG_CONDITION_SENTINEL: Float64 = 1e18

# ── status codes ──────────────────────────────────────────────────────────────
# Codes 0-8 belong to `csr.mojo` and are reused verbatim; this module's own codes start
# at 20 so the two spaces can never be confused by a caller that only knows one of
# them.

comptime DIAG_ERR_NOT_SQUARE: Int = 20
comptime DIAG_ERR_TOO_LARGE: Int = 21
comptime DIAG_ERR_SINGULAR: Int = 22
comptime DIAG_ERR_NON_FINITE: Int = 23
comptime DIAG_ERR_EMPTY: Int = 24


def diag_status_name(code: Int) -> String:
    """Name for a diagnostics status, delegating to `csr_status_name` below 20."""
    if code == DIAG_ERR_NOT_SQUARE:
        return "not_square"
    if code == DIAG_ERR_TOO_LARGE:
        return "larger_than_max_n"
    if code == DIAG_ERR_SINGULAR:
        return "singular"
    if code == DIAG_ERR_NON_FINITE:
        return "non_finite_values"
    if code == DIAG_ERR_EMPTY:
        return "empty_matrix"
    return csr_status_name(code)


# ── result structs ────────────────────────────────────────────────────────────


struct SparseHealthReport(Copyable, Movable):
    """Everything one O(nnz) pass can honestly say about a sparse matrix.

    Flat fields only, so the dispatch generator can serialise it. Every quantity that
    can fail to exist has a `_present` companion; a quantity whose value is a real
    answer for the degenerate case (a count of nothing is 0, the norm of the zero
    matrix is 0) does not, and says so in its own comment.

    `nnz` is the number of values SUPPLIED, matching CSR's convention that nnz counts
    what is stored — duplicates and explicit zeros included. `nnz_canonical` is what
    remains after out-of-range entries are dropped and duplicate coordinates are
    summed, so `nnz == nnz_canonical + duplicates + out_of_range` always holds.
    """

    var status: Int
    var diagnosed: Bool  # False => every number below is a placeholder, not a measurement
    var nrows: Int
    var ncols: Int
    var nnz: Int
    var nnz_canonical: Int
    var duplicates: Int
    var out_of_range: Int
    var numeric_nnz: Int  # frozen sv_nnz over the finite values: |v| > 1e-30
    var stored_zeros: Int  # finite stored values sv_nnz does not count
    var nonfinite: Int
    var first_nonfinite_row: Int  # -1 when every stored value is finite
    var first_nonfinite_col: Int
    var finite: Bool
    var has_elements: Bool  # nrows * ncols > 0; gates `density` and `max_element`
    var density: Float64
    var max_abs: Float64
    var max_stored: Float64  # what sv_max reports over the stored values
    var max_abs_present: Bool  # gates `max_abs` and `max_stored` together
    var max_element: Float64  # true maximum, implicit zeros included
    var max_element_present: Bool
    var max_stored_is_matrix_max: Bool
    var norm_inf: Float64  # max absolute row sum; 0.0 for an empty matrix is an answer
    var norm_1: Float64  # max absolute column sum; likewise
    var trace: Float64
    var trace_present: Bool
    var min_abs_diag: Float64
    var min_abs_diag_present: Bool
    var missing_diagonal: Int
    var symmetry_defect: Float64
    var symmetry_defect_present: Bool
    var symmetric: Bool
    var empty_rows: Int
    var empty_cols: Int
    var structurally_singular: Bool

    def __init__(out self, status: Int, diagnosed: Bool, nrows: Int, ncols: Int):
        """The absent report: a status, a shape, and no measurements.

        Constructed this way rather than memberwise because a 34-argument positional
        constructor is a transposition waiting to happen — every field is assigned by
        name in `sparse_health` instead.
        """
        self.status = status
        self.diagnosed = diagnosed
        self.nrows = nrows
        self.ncols = ncols
        self.nnz = 0
        self.nnz_canonical = 0
        self.duplicates = 0
        self.out_of_range = 0
        self.numeric_nnz = 0
        self.stored_zeros = 0
        self.nonfinite = 0
        self.first_nonfinite_row = -1
        self.first_nonfinite_col = -1
        self.finite = True
        self.has_elements = False
        self.density = 0.0
        self.max_abs = 0.0
        self.max_stored = 0.0
        self.max_abs_present = False
        self.max_element = 0.0
        self.max_element_present = False
        self.max_stored_is_matrix_max = False
        self.norm_inf = 0.0
        self.norm_1 = 0.0
        self.trace = 0.0
        self.trace_present = False
        self.min_abs_diag = 0.0
        self.min_abs_diag_present = False
        self.missing_diagonal = 0
        self.symmetry_defect = 0.0
        self.symmetry_defect_present = False
        self.symmetric = False
        self.empty_rows = 0
        self.empty_cols = 0
        self.structurally_singular = False


struct SparseMetric(Copyable, Movable):
    """One scalar health figure, its status, and whether it exists at all.

    Shared by the focused predicates so that "absent" has one representation across
    them. A bare `Float64` cannot carry the distinction this module is about.
    """

    var status: Int
    var present: Bool
    var value: Float64

    def __init__(out self, status: Int, present: Bool, value: Float64):
        self.status = status
        self.present = present
        self.value = value


struct SparseConditionEstimate(Copyable, Movable):
    """`||A||_inf * ||A^-1||_inf` from the frozen estimator, with its failure split out.

    `present` is False for every case in which `mat_condition_number` would have
    returned its 1e18 sentinel, and `status` says which case it was: non-square,
    singular, empty, non-finite, or larger than the caller's `max_n` budget.
    """

    var status: Int
    var present: Bool
    var n: Int
    var condition_number: Float64
    var norm_inf: Float64  # ||A||_inf via the frozen mat_norm_inf; 0.0 when absent
    var singular: Bool

    def __init__(out self, status: Int, n: Int):
        self.status = status
        self.present = False
        self.n = n
        self.condition_number = 0.0
        self.norm_inf = 0.0
        self.singular = status == DIAG_ERR_SINGULAR


# ── internals ─────────────────────────────────────────────────────────────────


def _is_finite(v: Float64) -> Bool:
    return not (isnan(v) or isinf(v))


def _drop_out_of_range(m: CSRMatrix) -> CSRMatrix:
    """`m` without the column indices outside `[0, ncols)`, `indptr` rebuilt.

    Only safe once the caller has established that the pointer structure is sound —
    the row loop below trusts `indptr` completely. Flags come back False from
    `csr_from_arrays`, which is what makes the subsequent coalesce actually run.
    """
    var indptr = List[Int]()
    indptr.append(0)
    var indices = List[Int]()
    var values = List[Float64]()
    for i in range(m.nrows):
        for k in range(m.indptr[i], m.indptr[i + 1]):
            var j = m.indices[k]
            if j >= 0 and j < m.ncols:
                indices.append(j)
                values.append(m.values[k])
        indptr.append(len(values))
    return csr_from_arrays(indptr, indices, values, m.nrows, m.ncols)


def _max_abs_row_sum(m: CSRMatrix) -> Float64:
    """Max absolute row sum over the FINITE stored values. `m` must be valid.

    Unstored positions contribute nothing, which is exactly right: their value is zero.
    Non-finite values are skipped explicitly rather than being left to lose the `>`
    comparison — an implicit skip is how `matrix_norm_inf` ends up reporting the norm of
    a different matrix than the one it was given.
    """
    var best = 0.0
    for i in range(m.nrows):
        var row_sum = 0.0
        for k in range(m.indptr[i], m.indptr[i + 1]):
            var v = m.values[k]
            if _is_finite(v):
                row_sum += fabs(v)
        if row_sum > best:
            best = row_sum
    return best


def _count_zeros(counts: List[Int]) -> Int:
    var empty = 0
    for i in range(len(counts)):
        if counts[i] == 0:
            empty += 1
    return empty


def _symmetry_defect(a: CSRMatrix, t: CSRMatrix) -> Float64:
    """`max |A_ij - A_ji|` over the finite entries. Both inputs must be canonical.

    A sorted two-pointer merge of row `i` of `A` with row `i` of `A^T`, so a coordinate
    present on one side only is compared against the implicit zero on the other rather
    than being skipped — skipping it is how a wildly asymmetric pattern passes a
    symmetry test. O(nnz) with no dense image.
    """
    var worst = 0.0
    for i in range(a.nrows):
        var p = a.indptr[i]
        var p_end = a.indptr[i + 1]
        var q = t.indptr[i]
        var q_end = t.indptr[i + 1]
        while p < p_end or q < q_end:
            var take_a = False
            var take_t = False
            if p < p_end and q < q_end:
                if a.indices[p] == t.indices[q]:
                    take_a = True
                    take_t = True
                elif a.indices[p] < t.indices[q]:
                    take_a = True
                else:
                    take_t = True
            elif p < p_end:
                take_a = True
            else:
                take_t = True
            var a_val = 0.0
            var t_val = 0.0
            if take_a:
                a_val = a.values[p]
            if take_t:
                t_val = t.values[q]
            if _is_finite(a_val) and _is_finite(t_val):
                var defect = fabs(a_val - t_val)
                if defect > worst:
                    worst = defect
            if take_a:
                p += 1
            if take_t:
                q += 1
    return worst


def _summarize(r: SparseHealthReport) -> String:
    """One line naming the shape, the status and every defect found.

    Concatenation only — `String` has no slice operator here and none is needed.
    """
    if not r.diagnosed:
        return "sparse matrix not diagnosable: " + diag_status_name(r.status)
    var out = String("sparse ")
    out += String(r.nrows) + "x" + String(r.ncols)
    out += " nnz=" + String(r.nnz)
    out += " canonical=" + String(r.nnz_canonical)
    if r.has_elements:
        out += " density=" + String(r.density)
    else:
        out += " density=absent"
    if r.max_abs_present:
        out += " max_abs=" + String(r.max_abs)
    else:
        out += " max_abs=absent"
    out += " norm_inf=" + String(r.norm_inf)
    if r.duplicates > 0:
        out += " duplicates=" + String(r.duplicates)
    if r.out_of_range > 0:
        out += " out_of_range=" + String(r.out_of_range)
    if r.nonfinite > 0:
        out += " nonfinite=" + String(r.nonfinite)
        out += " first_at=" + String(r.first_nonfinite_row)
        out += "," + String(r.first_nonfinite_col)
    if r.empty_rows > 0:
        out += " empty_rows=" + String(r.empty_rows)
    if r.empty_cols > 0:
        out += " empty_cols=" + String(r.empty_cols)
    if r.missing_diagonal > 0:
        out += " missing_diagonal=" + String(r.missing_diagonal)
    if r.structurally_singular:
        out += " structurally_singular"
    if r.symmetric:
        out += " symmetric"
    out += " status=" + diag_status_name(r.status)
    return out


# ── the report ────────────────────────────────────────────────────────────────


def sparse_health(
    m: CSRMatrix, tol: Float64 = DIAG_SYMMETRY_TOL
) -> SparseHealthReport:
    """Structural and numerical health of `m` in one O(nnz + nrows + ncols) pass.

    `tol` is the symmetry tolerance only. A negative `tol` is clamped to zero: it would
    otherwise declare an exactly symmetric matrix asymmetric, which is a wrong answer
    dressed as a strict one.

    Measurements are taken on the COALESCED matrix, because every quantity here is a
    property of the linear map and not of its storage: a duplicate coordinate would
    otherwise inflate the density above 1, hide the true value at that coordinate from
    `max_abs`, and make the diagonal disagree with the dense image.
    """
    var status = csr_validate(m)
    if status != CSR_OK and status != CSR_ERR_INDEX_OUT_OF_RANGE:
        # The pointer structure is what bounds every loop below. Without it there is
        # nothing safe to read, so the report carries a status and a 0x0 shape — never
        # a plausible-looking measurement of a matrix that does not exist.
        return SparseHealthReport(status, False, 0, 0)

    var supplied = m.nnz()
    # The rebuild happens only when there is something to drop. Doing it unconditionally
    # would also strip the canonical flags off an already-canonical input and force
    # csr_coalesce to redo a merge it is entitled to skip.
    var in_range_nnz = supplied
    var canon = csr_empty(0, 0)
    if status == CSR_OK:
        canon = csr_coalesce(m)
    else:
        var in_range = _drop_out_of_range(m)
        in_range_nnz = in_range.nnz()
        canon = csr_coalesce(in_range)
    var out_of_range = supplied - in_range_nnz

    var nrows = canon.nrows
    var ncols = canon.ncols
    var report = SparseHealthReport(status, True, nrows, ncols)
    report.nnz = supplied
    report.out_of_range = out_of_range
    report.nnz_canonical = canon.nnz()
    report.duplicates = in_range_nnz - canon.nnz()
    report.has_elements = nrows > 0 and ncols > 0

    # ── stored values: extrema, non-finite positions, and the nonzero count ──
    var finite_values = List[Float64]()
    var max_abs = 0.0
    for i in range(nrows):
        for k in range(canon.indptr[i], canon.indptr[i + 1]):
            var v = canon.values[k]
            if _is_finite(v):
                finite_values.append(v)
                if fabs(v) > max_abs:
                    max_abs = fabs(v)
            else:
                report.nonfinite += 1
                if report.first_nonfinite_row < 0:
                    # "First" is row-major in the canonical ordering, which is a
                    # property of the matrix; the caller's array order is not.
                    report.first_nonfinite_row = i
                    report.first_nonfinite_col = canon.indices[k]
    report.finite = report.nonfinite == 0
    report.numeric_nnz = sv_nnz(finite_values)
    report.stored_zeros = len(finite_values) - report.numeric_nnz

    var have_finite = len(finite_values) > 0
    report.max_abs_present = have_finite
    if have_finite:
        report.max_abs = max_abs
        # sv_max is the frozen definition of "largest stored value"; it is handed only
        # the finite ones because a NaN loses every comparison and would silently
        # become the answer if it were the first element.
        report.max_stored = sv_max(finite_values)

    # An unstored position holds a real zero, so it is a candidate for the maximum. An
    # all-negative matrix with any unstored position has maximum 0.0, which is the
    # number sv_max cannot produce.
    var implicit_zeros = nrows * ncols - canon.nnz()
    if have_finite:
        report.max_element = report.max_stored
        report.max_element_present = True
    if implicit_zeros > 0:
        if not report.max_element_present or report.max_element < 0.0:
            report.max_element = 0.0
        report.max_element_present = True
    report.max_stored_is_matrix_max = have_finite and (
        implicit_zeros == 0 or report.max_stored >= 0.0
    )

    # ── density and trace, from the frozen kernels ──
    var coo = csr_to_coo(canon)
    if report.has_elements:
        report.density = sparse_density(coo)
    report.trace_present = nrows == ncols
    if report.trace_present:
        report.trace = sparse_trace(coo)

    # ── norms and empty rows/columns; the transpose serves both ──
    var t = csr_transpose(canon)
    report.norm_inf = _max_abs_row_sum(canon)
    report.norm_1 = _max_abs_row_sum(t)
    report.empty_rows = _count_zeros(csr_row_counts(canon))
    # Column counts are the row counts of the transpose. A second counting loop over
    # `indices` would cost the same and be a second place for the definition to live.
    report.empty_cols = _count_zeros(csr_row_counts(t))

    # ── the diagonal, counting absent entries as the zeros they are ──
    var diag_len = nrows
    if ncols < diag_len:
        diag_len = ncols
    var have_diag = False
    var min_abs_diag = 0.0
    for i in range(diag_len):
        var found = False
        var value = 0.0
        for k in range(canon.indptr[i], canon.indptr[i + 1]):
            if canon.indices[k] == i:
                found = True
                value = canon.values[k]
                break
        if not found:
            report.missing_diagonal += 1
        if _is_finite(value):
            var magnitude = fabs(value)
            if not have_diag or magnitude < min_abs_diag:
                min_abs_diag = magnitude
                have_diag = True
    report.min_abs_diag_present = have_diag
    if have_diag:
        report.min_abs_diag = min_abs_diag

    # ── symmetry ──
    report.symmetry_defect_present = nrows == ncols
    if report.symmetry_defect_present:
        report.symmetry_defect = _symmetry_defect(canon, t)
        var symmetry_tol = tol
        if symmetry_tol < 0.0:
            symmetry_tol = 0.0
        # A matrix carrying a NaN is not symmetric: NaN != NaN, and the defect above
        # only measured the finite part.
        report.symmetric = report.finite and report.symmetry_defect <= symmetry_tol

    # A missing perfect matching is what "structurally singular" means, and an empty row
    # or column proves one is missing. The converse does not hold: this flag being False
    # means "not proved singular by this test", NOT "invertible" — [[1,1],[1,1]] has no
    # empty row or column and is singular. Proving the general case needs a maximum
    # bipartite matching, which is a different driver with a different cost.
    report.structurally_singular = (
        nrows != ncols or report.empty_rows > 0 or report.empty_cols > 0
    )
    return report^


# ── focused predicates ────────────────────────────────────────────────────────
# Each one delegates to `sparse_health` and picks a field. The extra work is one O(nnz)
# pass; the alternative — a bespoke loop per metric — would put "an absent diagonal
# entry is a zero" and "a NaN is excluded from extrema" in five places, where four of
# them can drift.


def sparse_density_checked(m: CSRMatrix) -> SparseMetric:
    """Density in [0, 1], absent for a matrix with no elements.

    The frozen `sparse_density` returns 0.0 for a 0x0 — indistinguishable from a
    genuinely empty 5x5 — and can exceed 1.0 on a duplicate-bearing COO. Neither can
    escape through here.
    """
    var report = sparse_health(m)
    if not report.diagnosed:
        return SparseMetric(report.status, False, 0.0)
    return SparseMetric(report.status, report.has_elements, report.density)


def sparse_trace_checked(m: CSRMatrix) -> SparseMetric:
    """Sum of the diagonal, absent for a non-square matrix.

    `sparse_trace` sums every entry with `row == col` whatever the shape, so on a
    non-square matrix it returns a number that is not a trace.
    """
    var report = sparse_health(m)
    if not report.diagnosed:
        return SparseMetric(report.status, False, 0.0)
    if not report.trace_present:
        return SparseMetric(DIAG_ERR_NOT_SQUARE, False, 0.0)
    return SparseMetric(report.status, True, report.trace)


def sparse_max_abs(m: CSRMatrix) -> SparseMetric:
    """Largest magnitude among the finite stored values; absent when there are none."""
    var report = sparse_health(m)
    if not report.diagnosed:
        return SparseMetric(report.status, False, 0.0)
    return SparseMetric(report.status, report.max_abs_present, report.max_abs)


def sparse_max_element(m: CSRMatrix) -> SparseMetric:
    """True maximum over ALL positions, implicit zeros included.

    Differs from `sv_max` exactly when every stored value is negative and some position
    is unstored, which is the common case for a sparse matrix of costs or losses.
    """
    var report = sparse_health(m)
    if not report.diagnosed:
        return SparseMetric(report.status, False, 0.0)
    return SparseMetric(
        report.status, report.max_element_present, report.max_element
    )


def sparse_row_norm_inf(m: CSRMatrix) -> SparseMetric:
    """Max absolute row sum. Absent when a non-finite value makes it meaningless."""
    var report = sparse_health(m)
    if not report.diagnosed:
        return SparseMetric(report.status, False, 0.0)
    if not report.finite:
        return SparseMetric(DIAG_ERR_NON_FINITE, False, 0.0)
    return SparseMetric(report.status, True, report.norm_inf)


def sparse_min_abs_diagonal(m: CSRMatrix) -> SparseMetric:
    """Smallest `|A_ii|` over the whole diagonal, absent entries counted as zeros.

    The tempting version — a minimum over the STORED diagonal entries — reports a
    comfortable pivot for a matrix whose diagonal is half absent, which is the same
    class of lie as `sv_max` ignoring implicit zeros.
    """
    var report = sparse_health(m)
    if not report.diagnosed:
        return SparseMetric(report.status, False, 0.0)
    return SparseMetric(
        report.status, report.min_abs_diag_present, report.min_abs_diag
    )


def sparse_symmetry_defect(
    m: CSRMatrix, tol: Float64 = DIAG_SYMMETRY_TOL
) -> SparseMetric:
    """`max |A_ij - A_ji|`, absent for a non-square or non-finite matrix."""
    var report = sparse_health(m, tol)
    if not report.diagnosed:
        return SparseMetric(report.status, False, 0.0)
    if not report.symmetry_defect_present:
        return SparseMetric(DIAG_ERR_NOT_SQUARE, False, 0.0)
    if not report.finite:
        return SparseMetric(DIAG_ERR_NON_FINITE, False, 0.0)
    return SparseMetric(report.status, True, report.symmetry_defect)


# ── condition number ──────────────────────────────────────────────────────────


def sparse_condition_estimate(
    m: CSRMatrix, max_n: Int
) -> SparseConditionEstimate:
    """`||A||_inf * ||A^-1||_inf` from `linalg_ext.mat_condition_number`, honestly.

    Kept out of `sparse_health` on purpose: the report is O(nnz), while this densifies
    to `n * n` and inverts in O(n^3). `max_n` is the caller's explicit budget for that,
    and exceeding it is a status rather than a silent slow path.

    Every way the frozen estimator can fail becomes a distinct status here:

    * non-square — it returns 1e18, indistinguishable from singular
    * 0x0 — its "the inverse came back all zeros" test is vacuously true on an empty
      matrix, so it returns 1e18 for a matrix that is trivially invertible
    * singular — 1e18 again
    * a genuine condition number at or above 1e18 — reported absent as well. At that
      magnitude the estimate carries no usable digits, and reporting it would make the
      sentinel ambiguous again in the one direction that matters.

    Non-finite values are rejected before `mat_inv` sees them: Gaussian elimination on
    a NaN produces a full matrix of NaNs, whose `fabs(...) > 1e-15` test is False, so
    the estimator would call a NaN-poisoned matrix singular.
    """
    var status = csr_validate(m)
    if status != CSR_OK:
        return SparseConditionEstimate(status, 0)
    if m.nrows != m.ncols:
        return SparseConditionEstimate(DIAG_ERR_NOT_SQUARE, m.nrows)
    var n = m.nrows
    if n == 0:
        return SparseConditionEstimate(DIAG_ERR_EMPTY, 0)
    if max_n < 0 or n > max_n:
        return SparseConditionEstimate(DIAG_ERR_TOO_LARGE, n)
    for k in range(len(m.values)):
        if not _is_finite(m.values[k]):
            return SparseConditionEstimate(DIAG_ERR_NON_FINITE, n)

    # `csr_to_dense` routes through the frozen `to_dense`, which sums duplicates, so no
    # coalesce is needed to get the right dense image here.
    var dense = csr_to_dense(m)
    var a = mat_from_list(dense, n, n)
    var cond = mat_condition_number(a)
    if cond >= DIAG_CONDITION_SENTINEL or not _is_finite(cond):
        return SparseConditionEstimate(DIAG_ERR_SINGULAR, n)
    var out = SparseConditionEstimate(CSR_OK, n)
    out.present = True
    out.condition_number = cond
    out.norm_inf = mat_norm_inf(a)
    return out^


# ── flat-list drivers ─────────────────────────────────────────────────────────
# Lists and scalars in, a status-bearing struct declared in this file out. No struct
# parameters anywhere in the public surface, matching `csr.mojo`: that is the shape the
# runtime contract and the dispatch generator are known to carry.


def sparse_health_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
    tol: Float64,
) -> SparseHealthReport:
    """Health report for the CSR described by these arrays."""
    return sparse_health(
        csr_from_arrays(indptr, indices, values, nrows, ncols), tol
    )


def sparse_health_from_dense_driver(
    dense: List[Float64], rows: Int, cols: Int, tol: Float64
) -> SparseHealthReport:
    """Health report for a flat row-major dense matrix.

    `rows * cols != len(dense)` yields an undiagnosable report rather than a matrix of
    the wrong shape: the declared shape and the data disagree and neither is authority.
    """
    if not dims_fit(rows, cols, len(dense)):
        return SparseHealthReport(CSR_ERR_INVALID_DIMENSIONS, False, 0, 0)
    return sparse_health(csr_from_dense(dense, rows, cols), tol)


def sparse_health_summary_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
    tol: Float64,
) -> String:
    """One-line human summary of the same report, for logs and error messages."""
    return _summarize(
        sparse_health_driver(indptr, indices, values, nrows, ncols, tol)
    )


def sparse_density_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
) -> SparseMetric:
    return sparse_density_checked(
        csr_from_arrays(indptr, indices, values, nrows, ncols)
    )


def sparse_trace_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
) -> SparseMetric:
    return sparse_trace_checked(
        csr_from_arrays(indptr, indices, values, nrows, ncols)
    )


def sparse_max_abs_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
) -> SparseMetric:
    return sparse_max_abs(
        csr_from_arrays(indptr, indices, values, nrows, ncols)
    )


def sparse_max_element_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
) -> SparseMetric:
    return sparse_max_element(
        csr_from_arrays(indptr, indices, values, nrows, ncols)
    )


def sparse_row_norm_inf_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
) -> SparseMetric:
    return sparse_row_norm_inf(
        csr_from_arrays(indptr, indices, values, nrows, ncols)
    )


def sparse_min_abs_diagonal_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
) -> SparseMetric:
    return sparse_min_abs_diagonal(
        csr_from_arrays(indptr, indices, values, nrows, ncols)
    )


def sparse_symmetry_defect_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
    tol: Float64,
) -> SparseMetric:
    return sparse_symmetry_defect(
        csr_from_arrays(indptr, indices, values, nrows, ncols), tol
    )


def sparse_condition_estimate_driver(
    indptr: List[Int],
    indices: List[Int],
    values: List[Float64],
    nrows: Int,
    ncols: Int,
    max_n: Int,
) -> SparseConditionEstimate:
    """Condition-number estimate, with `max_n` as the caller's O(n^3) budget."""
    return sparse_condition_estimate(
        csr_from_arrays(indptr, indices, values, nrows, ncols), max_n
    )
