"""
exactnum.lstsq — compensated Householder QR least squares. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_exactnum_lstsq.mojo
benchmark: benchmarks/mojo_benchmarks/measure_exactnum_strd.mojo
docs: gitbook/benchmarks/least-squares-accuracy.md
version_introduced: 0.1.0
deprecation_state: active
@endcapability

Inputs are float64 and the return is float64. Everything between — the reflector norms, the
reflector applications, `R`, `Q^T b` and the back substitution — is carried in double-double
(~106 significand bits). On an ill-conditioned design that is exactly where the digits are
lost, and it is a place a float64 LAPACK is structurally unable to go.

Status range
------------
`lstsq` owns **810-819** of `exactnum`'s 800-819. `eft` owns 800-809 (rule 4e). A status
from `eft` is returned unchanged when it is the real cause — `EFT_ERR_NO_FUSED_MULTIPLY_ADD`
means the arithmetic assumption broke and no answer exists, which is not a least-squares
condition and must not be renamed as one.

Why Householder and not the frozen routes
-----------------------------------------
`sparse_numerics.factor.csr_least_squares` forms `X^T X` and Choleskys it, which squares
the condition number: a design with `kappa(X) = 1.8e15` (StRD Filip) presents
`kappa(X^T X) = 3.1e30` to the factorisation. `linalg_ext.mat_qr` is modified Gram-Schmidt,
whose loss of orthogonality is `O(eps * kappa)` rather than Householder's `O(eps)`. Neither
is modified and both stay reachable; this is a third, complete driver (rule 3).

Three things that are easy to get wrong here, and what this does instead
-----------------------------------------------------------------------
1. **The reflector sign.** `alpha = -sign(A[k,k]) * ||A[k:,k]||` so that `v[k] = A[k,k] -
   alpha` has magnitude `|A[k,k]| + ||.||`. Choosing the other sign subtracts two nearly equal
   numbers and destroys the reflector.

   How much it matters was MEASURED by flipping the sign in both arms and re-running the whole
   StRD suite, because the prose version of this claim ("double-double loses just as much, 53
   bits further down") turned out to be wrong. What actually happens on all 11 datasets:

       float64 arms        EVERY coefficient changes  (11/11 Filip, 7/7 Longley, 6/6 Wampler5)
       double-double arms  NOT ONE coefficient changes; only the tails move

   So the sign rule is load-bearing in float64 and double-double absorbs it completely at this
   suite's conditioning. It is kept because it is correct and free, not because it is what is
   buying the digits here — and a reader should not be told otherwise.
2. **`v^T v` by identity vs by summation.** `v^T v == -2 * alpha * v[k]` holds only if
   `alpha^2 == sigma` exactly, which it is not once `alpha` came out of a rounded square
   root. This sums `v_i^2` directly: `O(m)` extra double-double multiply-adds, all terms
   positive, no cancellation to reason about.
3. **A dependent column and a merely ill-conditioned one need different answers.** The pivot
   `R[k,k]` is the part of column k orthogonal to columns 0..k-1, so its own natural scale is
   `||A[:,k]||` — that column's norm and nothing else. A pivot below `2^-100 * ||A[:,k]||` is
   indistinguishable from zero *in the arithmetic this driver carries*, so the column is
   dependent, the minimiser is not unique, and there is no answer to return (rule 4). An
   Both ends are measured, not estimated. An exactly duplicated column lands at `2.4e-33`
   (`2^-108`) of its column norm and is caught. The suite's worst-conditioned real case, StRD
   Filip at degree 10, has `pivot_ratio_min = 5.2e-8` (`2^-24`) — seventy-six octaves above the
   floor — and is solved normally. `pivot_ratio_min` for all 11 datasets is in
   `benchmarks/external_baselines/strd_lstsq/scores.json`.

   The scale is deliberately per-column and NOT `max_k |R[k,k]|` or `||A||`. An aggregate over
   columns is rule 4b spelling 2: it transfers one column's units onto another column's
   comparison. `numpy.linalg.lstsq`'s default `rcond` is that aggregate, applied as a rank
   cut, and it is why that arm scores 0.00 correct digits on StRD Filip — it truncates a rank
   nobody asked it to truncate. `pivot_ratio_min` is published so a caller can apply its own
   cut with full information; this driver does not apply one.

The float64 control is the same algorithm, not a different one
--------------------------------------------------------------
`f64_lstsq_flat` runs the identical pivot order, the identical sign rule and the identical
`v^T v`-by-summation, in plain float64. It exists so a difference between the two is
attributable to the arithmetic and to nothing else — which is what makes "the compensation
is load-bearing" a measurement rather than a claim.

Public API:
  lstsq_status_name(code)                     — the status vocabulary
  lstsq_cells_fit(rows, cols, ceiling)        — division-based rows*cols bound, no wrapping
  lstsq_work_fits(rows, cols, ceiling)        — division-based rows*cols*cols bound
  lstsq_pivot_floor(colnorm)                  — the per-column dependent-column floor
  dd_lstsq_flat(a, rows, cols, b)             — compensated QR on a row-major design matrix
  f64_lstsq_flat(a, rows, cols, b)            — the float64 control, same algorithm
  dd_poly_lstsq(x, y, n, lo_deg, hi_deg, dd_powers)      — polynomial basis, raw domain
  dd_poly_lstsq_scaled(x, y, n, hi_deg, dd_powers, dd_mapback)  — centred/scaled domain
"""

from std.math import abs as fabs, isinf, isnan, sqrt

from exactnum.eft import (
    DD,
    EFT_ERR_NEGATIVE_RADICAND,
    EFT_OK,
    dd_add,
    dd_add_d,
    dd_div,
    dd_from,
    dd_mul,
    dd_mul_d,
    dd_neg,
    dd_sqrt,
    dd_sub,
    eft_selfcheck_code,
)

# ── status codes: lstsq owns 810-819 ──────────────────────────────────────────

comptime LSTSQ_OK: Int = 810
comptime LSTSQ_ERR_EMPTY_DIM: Int = 811
comptime LSTSQ_ERR_A_LENGTH: Int = 812
comptime LSTSQ_ERR_B_LENGTH: Int = 813
comptime LSTSQ_ERR_UNDERDETERMINED: Int = 814
comptime LSTSQ_ERR_CELLS_TOO_LARGE: Int = 815
comptime LSTSQ_ERR_WORK_TOO_LARGE: Int = 816
comptime LSTSQ_ERR_NON_FINITE_INPUT: Int = 817
comptime LSTSQ_ERR_RANK_DEFICIENT: Int = 818
comptime LSTSQ_ERR_BASIS_NOT_APPLICABLE: Int = 819

comptime LSTSQ_MAX_CELLS: Int = 1 << 22
"""Bound on `rows * cols`.

Rule 1c arithmetic, stated because the ceiling was scaled for it: the solver holds four
`rows * cols` double-double arrays live at once — the working matrix, an untouched copy of
it for the residual, and the reflector store — at 16 bytes per cell each. 2^22 cells is
therefore ~200 MB of resident double-double, inside the 512 MB per-object budget. The tree's
shared `sparse_numerics.csr.MAX_CSR_DIM` of 2^26 is a *single float64 buffer's* ceiling and
would be 3.2 GB here; it is not raised or lowered, it is simply not the applicable bound."""

comptime LSTSQ_MAX_COLS: Int = 1 << 12
"""Bound on `cols` alone. Back substitution is O(cols^2) double-double divisions and the
reflector sweep is O(rows * cols^2); `LSTSQ_MAX_WORK` charges the product, but a caller who
passes `cols` far larger than any real design also hits a `cols^2` allocation in nothing —
so this exists mainly so the work bound below cannot be reached with a degenerate `rows`."""

comptime LSTSQ_MAX_WORK: Int = 1 << 28
"""Bound on `rows * cols * cols`, the reflector-sweep work.

Rule 1c: bounding memory is not bounding work. A 2^22-cell matrix that is 4096 columns wide
sits inside `LSTSQ_MAX_CELLS` while `rows * cols^2` is 2^34 double-double multiply-adds —
each ~15 float64 flops — which is minutes, and a hang is indistinguishable from rule 1's
uncatchable abort from the caller's side. 2^28 is ~4e9 float64 flops, a few seconds."""

comptime LSTSQ_MAX_DEGREE: Int = 64
"""Bound on a polynomial-basis degree.

Separate from `LSTSQ_MAX_COLS` because the Vandermonde construction raises `x` to this power:
`x = 10` at degree 309 overflows to `inf`, and degree 64 keeps `|x| <= 100` finite. A caller
wanting more columns than this can build the design matrix itself and use `dd_lstsq_flat`."""


fn lstsq_status_name(code: Int) -> String:
    """The `exactnum.lstsq` status vocabulary. One integer, one meaning (rule 4e)."""
    if code == LSTSQ_OK:
        return String("ok")
    if code == LSTSQ_ERR_EMPTY_DIM:
        return String("empty_dimension")
    if code == LSTSQ_ERR_A_LENGTH:
        return String("design_matrix_length_mismatch")
    if code == LSTSQ_ERR_B_LENGTH:
        return String("response_length_mismatch")
    if code == LSTSQ_ERR_UNDERDETERMINED:
        return String("fewer_rows_than_columns")
    if code == LSTSQ_ERR_CELLS_TOO_LARGE:
        return String("cells_too_large")
    if code == LSTSQ_ERR_WORK_TOO_LARGE:
        return String("work_too_large")
    if code == LSTSQ_ERR_NON_FINITE_INPUT:
        return String("non_finite_input")
    if code == LSTSQ_ERR_RANK_DEFICIENT:
        return String("rank_deficient_no_unique_solution")
    if code == LSTSQ_ERR_BASIS_NOT_APPLICABLE:
        return String("basis_transform_not_applicable")
    return String("unknown_status")


fn lstsq_cells_fit(rows: Int, cols: Int, ceiling: Int) -> Bool:
    """`rows * cols <= ceiling`, by division so the product cannot wrap.

    `3 * 6148914691236517206 == 2` in wrapping 64-bit arithmetic, which is how a product
    guard was walked past in `sparse_numerics` and aborted the worker.

    @capability lstsq_cells_fit
    complexity: O(1)
    @endcapability
    """
    if rows <= 0 or cols <= 0 or ceiling <= 0:
        return False
    if rows > ceiling:
        return False
    return cols <= ceiling // rows


fn lstsq_work_fits(rows: Int, cols: Int, ceiling: Int) -> Bool:
    """`rows * cols * cols <= ceiling`, by division so the product cannot wrap.

    @capability lstsq_work_fits
    complexity: O(1)
    @endcapability
    """
    if rows <= 0 or cols <= 0 or ceiling <= 0:
        return False
    if rows > ceiling:
        return False
    var q = ceiling // rows
    if cols > q:
        return False
    return cols <= q // cols


@fieldwise_init
struct DDLstsq(Copyable, Movable):
    """A least-squares solution, or the absence of one.

    `coefficients` is the double-double solution rounded once, at the very end, to float64.
    `coefficients_lo` is the double-double tail that was discarded by that rounding — it is
    published because it is the only way a caller can see how much internal precision was
    actually carried, and because a tail that is identically zero is the signature of the
    compensation having degraded to plain float64.

    `status != LSTSQ_OK` means both lists are empty. Not "zeros of the right length": the
    frozen `linalg.mat_solve` returns an all-zeros vector of length n for a singular matrix,
    so "the solution is the zero vector" and "there is no solution" are the same return
    value there. That is the confusion rule 4 exists to prevent.

    `residual_norm` is the 2-norm of the least-squares residual, read off the tail of
    `Q^T b` rather than recomputed from `b - A x`, so it costs nothing and is not subject to
    the cancellation a recomputation would suffer.

    `r_diag_min` is `min_i |R[i,i]|` and `pivot_ratio_min` is `min_i |R[i,i]| / ||A[:,i]||` —
    the scale-free version, and the one a caller can actually threshold. A raw `r_diag_min`
    carries the data's units, so 1e-9 means nothing without the column norms; the ratio is
    dimensionless and per-column, which is the only form of that number that is comparable
    across problems. Both are reported rather than acted on, except for the dependent-column
    refusal described in the module docstring."""

    var coefficients: List[Float64]
    var coefficients_lo: List[Float64]
    var status: Int
    var rank: Int
    var r_diag_min: Float64
    var pivot_ratio_min: Float64
    var residual_norm: Float64
    var refine_steps: Int


fn _empty_result(status: Int) -> DDLstsq:
    return DDLstsq(List[Float64](), List[Float64](), status, 0, 0.0, 0.0, 0.0, 0)


fn _dims_check(rows: Int, cols: Int, len_a: Int, len_b: Int) -> Int:
    """Every dimension against the real buffer lengths, before anything is indexed (rule 1)."""
    if rows <= 0 or cols <= 0:
        return LSTSQ_ERR_EMPTY_DIM
    if cols > LSTSQ_MAX_COLS:
        return LSTSQ_ERR_CELLS_TOO_LARGE
    if not lstsq_cells_fit(rows, cols, LSTSQ_MAX_CELLS):
        return LSTSQ_ERR_CELLS_TOO_LARGE
    if not lstsq_work_fits(rows, cols, LSTSQ_MAX_WORK):
        return LSTSQ_ERR_WORK_TOO_LARGE
    if rows < cols:
        return LSTSQ_ERR_UNDERDETERMINED
    if len_a != rows * cols:
        return LSTSQ_ERR_A_LENGTH
    if len_b != rows:
        return LSTSQ_ERR_B_LENGTH
    return LSTSQ_OK


# ── the compensated factorisation ─────────────────────────────────────────────


fn _dd_qr_solve(
    var a: List[DD], rows: Int, cols: Int, var b: List[DD], refine: Int
) -> DDLstsq:
    """Householder QR least squares in double-double. `a` is row-major `rows * cols`.

    Both buffers are taken by value and destroyed in place. Dimensions are already validated
    by the public caller — this is the inner driver and does not re-check per element.

    `refine` is the number of residual-refinement steps. Each one recomputes
    `r = b - A x` against untouched copies and re-solves for a correction using the *same*
    reflectors, which is what makes it cheap. It cannot buy more than the precision the
    residual is computed in: with a double-double residual and a double-double solve the
    fixed point is double-double, so refinement here corrects the O(rows * cols) accumulated
    factorisation rounding and nothing more. Whether that matters is a measurement, which is
    why the count is a parameter and is reported back in the result."""
    var self_check = eft_selfcheck_code()
    if self_check != EFT_OK:
        return _empty_result(self_check)

    var a0 = a.copy()
    var b0 = b.copy()

    # Each column's own 2-norm, before any reflector touches it. This is the scale the pivot
    # for that column is judged against — the quantity being judged, not an aggregate over
    # the matrix (rule 4b). Sum of squares, so no cancellation to reason about.
    var colnorm = List[Float64]()
    for j in range(cols):
        var cs = DD(0.0, 0.0)
        for i in range(rows):
            var e = a[i * cols + j]
            cs = dd_add(cs, dd_mul(e, e))
        colnorm.append(dd_sqrt(cs).hi)

    # Reflector store: column k's vector lives at vv[k * rows + i] for i in [k, rows).
    var vv = List[DD]()
    for _ in range(rows * cols):
        vv.append(DD(0.0, 0.0))

    for k in range(cols):
        var sigma = DD(0.0, 0.0)
        for i in range(k, rows):
            var e = a[i * cols + k]
            sigma = dd_add(sigma, dd_mul(e, e))
        if sigma.hi == 0.0:
            # The whole trailing column is zero: the column is a combination of the earlier
            # ones and there is no unique solution. Absent, not zero (rule 4).
            return _empty_result(LSTSQ_ERR_RANK_DEFICIENT)
        if sigma.hi < 0.0:
            # Unreachable for a sum of squares; kept because dd_sqrt returns NaN for a
            # negative radicand and a NaN must never be allowed to travel.
            return _empty_result(EFT_ERR_NEGATIVE_RADICAND)
        var nrm = dd_sqrt(sigma)
        # Below double-double's own noise floor for THIS column, the pivot is
        # indistinguishable from zero: column k is a combination of the earlier ones, the
        # minimiser is not unique, and there is no answer (rule 4).
        if nrm.hi <= lstsq_pivot_floor(colnorm[k]):
            return _empty_result(LSTSQ_ERR_RANK_DEFICIENT)
        var akk = a[k * cols + k]
        # Sign chosen so v[k] = akk - alpha ADDS magnitudes. The other sign subtracts two
        # nearly equal numbers, and double-double does not rescue a cancellation, it only
        # moves it 53 bits down.
        var alpha = nrm if akk.hi < 0.0 else dd_neg(nrm)
        vv[k * rows + k] = dd_sub(akk, alpha)
        for i in range(k + 1, rows):
            vv[k * rows + i] = a[i * cols + k]

        # v^T v by direct summation of positive terms, NOT by the -2*alpha*v[k] identity,
        # which is only true when alpha^2 == sigma exactly.
        var vtv = DD(0.0, 0.0)
        for i in range(k, rows):
            var e = vv[k * rows + i]
            vtv = dd_add(vtv, dd_mul(e, e))
        if vtv.hi == 0.0:
            return _empty_result(LSTSQ_ERR_RANK_DEFICIENT)

        for j in range(k + 1, cols):
            var w = DD(0.0, 0.0)
            for i in range(k, rows):
                w = dd_add(w, dd_mul(vv[k * rows + i], a[i * cols + j]))
            var f = dd_div(dd_mul_d(w, 2.0), vtv)
            for i in range(k, rows):
                a[i * cols + j] = dd_sub(
                    a[i * cols + j], dd_mul(f, vv[k * rows + i])
                )
        var wb = DD(0.0, 0.0)
        for i in range(k, rows):
            wb = dd_add(wb, dd_mul(vv[k * rows + i], b[i]))
        var fb = dd_div(dd_mul_d(wb, 2.0), vtv)
        for i in range(k, rows):
            b[i] = dd_sub(b[i], dd_mul(fb, vv[k * rows + i]))

        a[k * cols + k] = alpha
        for i in range(k + 1, rows):
            a[i * cols + k] = DD(0.0, 0.0)

    var r_diag_min = fabs(a[0].hi)
    var pivot_ratio_min = 1.0
    for i in range(cols):
        var d = fabs(a[i * cols + i].hi)
        if d < r_diag_min:
            r_diag_min = d
        if colnorm[i] > 0.0:
            var ratio = d / colnorm[i]
            if i == 0 or ratio < pivot_ratio_min:
                pivot_ratio_min = ratio

    var x = _dd_back_substitute(a, cols, b)
    if len(x) != cols:
        return _empty_result(LSTSQ_ERR_RANK_DEFICIENT)

    var steps_done = 0
    for _ in range(refine):
        var r = List[DD]()
        for i in range(rows):
            var acc = b0[i]
            for j in range(cols):
                acc = dd_sub(acc, dd_mul(a0[i * cols + j], x[j]))
            r.append(acc)
        _dd_apply_reflectors(vv, rows, cols, r)
        var dx = _dd_back_substitute(a, cols, r)
        if len(dx) != cols:
            break
        for j in range(cols):
            x[j] = dd_add(x[j], dx[j])
        steps_done += 1

    # Residual 2-norm from the tail of Q^T b: rows - cols terms, all squared, no cancellation.
    var rss = DD(0.0, 0.0)
    for i in range(cols, rows):
        rss = dd_add(rss, dd_mul(b[i], b[i]))
    var rnorm = dd_sqrt(rss)

    var out = List[Float64]()
    var out_lo = List[Float64]()
    for j in range(cols):
        out.append(x[j].hi)
        out_lo.append(x[j].lo)
    return DDLstsq(
        out^,
        out_lo^,
        LSTSQ_OK,
        cols,
        r_diag_min,
        pivot_ratio_min,
        rnorm.hi,
        steps_done,
    )


fn _dd_apply_reflectors(
    vv: List[DD], rows: Int, cols: Int, mut r: List[DD]
) -> None:
    """`r <- Q^T r` using the stored reflectors, in double-double."""
    for k in range(cols):
        var vtv = DD(0.0, 0.0)
        for i in range(k, rows):
            var e = vv[k * rows + i]
            vtv = dd_add(vtv, dd_mul(e, e))
        if vtv.hi == 0.0:
            continue
        var w = DD(0.0, 0.0)
        for i in range(k, rows):
            w = dd_add(w, dd_mul(vv[k * rows + i], r[i]))
        var f = dd_div(dd_mul_d(w, 2.0), vtv)
        for i in range(k, rows):
            r[i] = dd_sub(r[i], dd_mul(f, vv[k * rows + i]))


fn _dd_back_substitute(a: List[DD], cols: Int, qtb: List[DD]) -> List[DD]:
    """Solve `R x = qtb[0:cols]` in double-double. Empty list iff a pivot is exactly zero."""
    var x = List[DD]()
    for _ in range(cols):
        x.append(DD(0.0, 0.0))
    for ii in range(cols):
        var i = cols - 1 - ii
        var rii = a[i * cols + i]
        if rii.hi == 0.0 and rii.lo == 0.0:
            return List[DD]()
        var s = qtb[i]
        for j in range(i + 1, cols):
            s = dd_sub(s, dd_mul(a[i * cols + j], x[j]))
        x[i] = dd_div(s, rii)
    return x^


# ── the float64 control: identical algorithm, plain arithmetic ────────────────


fn lstsq_pivot_floor(colnorm: Float64) -> Float64:
    """`2^-100 * colnorm` — double-double's own noise floor for a column of that magnitude.

    Written as 100 halvings rather than `colnorm * 2.0**-100` so it is exact for every finite
    input including subnormals, and so a `Float64(Int(...))` conversion never appears (rule 4c:
    `fptosi` past the integer grid is poison, not truncation).

    The exponent is the arithmetic's, not the caller's. `2^-100` is a few bits inside
    double-double's ~2^-106 representable resolution, which is what makes "indistinguishable
    from zero" a statement about the arithmetic rather than a guess about the data."""
    var t = colnorm if colnorm >= 0.0 else -colnorm
    for _ in range(100):
        t = t * 0.5
    return t


fn _f64_qr_solve(
    var a: List[Float64], rows: Int, cols: Int, var b: List[Float64]
) -> DDLstsq:
    """The same Householder QR least squares in plain float64.

    Deliberately a transcription of `_dd_qr_solve` and not an independent implementation:
    same pivot order, same sign rule, same `v^T v` by summation, same zero-pivot refusal. The
    only difference is the arithmetic, so any difference in the answer is attributable to the
    arithmetic. `coefficients_lo` comes back all zeros, which is the point — a float64 route
    has no tail to report.

    The dependent-column floor is the SAME `2^-100 * ||A[:,k]||` the compensated route uses,
    even though float64's own noise floor for a column is ~`2^-53` of it. Using each arm's own
    floor would make the two arms different algorithms and destroy the attribution this control
    exists for. The consequence is stated rather than hidden: this arm will return a
    meaningless answer for a column that is numerically — but not exactly — dependent, which is
    a real property of a float64 route and one of the things being demonstrated."""
    var colnorm = List[Float64]()
    for j in range(cols):
        var cs: Float64 = 0.0
        for i in range(rows):
            cs += a[i * cols + j] * a[i * cols + j]
        colnorm.append(sqrt(cs))
    for k in range(cols):
        var sigma: Float64 = 0.0
        for i in range(k, rows):
            var e = a[i * cols + k]
            sigma += e * e
        if sigma == 0.0:
            return _empty_result(LSTSQ_ERR_RANK_DEFICIENT)
        var nrm = sqrt(sigma)
        if nrm <= lstsq_pivot_floor(colnorm[k]):
            return _empty_result(LSTSQ_ERR_RANK_DEFICIENT)
        var akk = a[k * cols + k]
        var alpha = nrm if akk < 0.0 else -nrm
        var vk = List[Float64]()
        for _ in range(rows):
            vk.append(0.0)
        vk[k] = akk - alpha
        for i in range(k + 1, rows):
            vk[i] = a[i * cols + k]
        var vtv: Float64 = 0.0
        for i in range(k, rows):
            vtv += vk[i] * vk[i]
        if vtv == 0.0:
            return _empty_result(LSTSQ_ERR_RANK_DEFICIENT)
        for j in range(k + 1, cols):
            var w: Float64 = 0.0
            for i in range(k, rows):
                w += vk[i] * a[i * cols + j]
            var f = 2.0 * w / vtv
            for i in range(k, rows):
                a[i * cols + j] -= f * vk[i]
        var wb: Float64 = 0.0
        for i in range(k, rows):
            wb += vk[i] * b[i]
        var fb = 2.0 * wb / vtv
        for i in range(k, rows):
            b[i] -= fb * vk[i]
        a[k * cols + k] = alpha
        for i in range(k + 1, rows):
            a[i * cols + k] = 0.0

    var r_diag_min = fabs(a[0])
    var pivot_ratio_min = 1.0
    for i in range(cols):
        var d = fabs(a[i * cols + i])
        if d < r_diag_min:
            r_diag_min = d
        if colnorm[i] > 0.0:
            var ratio = d / colnorm[i]
            if i == 0 or ratio < pivot_ratio_min:
                pivot_ratio_min = ratio

    var x = List[Float64]()
    for _ in range(cols):
        x.append(0.0)
    for ii in range(cols):
        var i = cols - 1 - ii
        var rii = a[i * cols + i]
        if rii == 0.0:
            return _empty_result(LSTSQ_ERR_RANK_DEFICIENT)
        var s = b[i]
        for j in range(i + 1, cols):
            s -= a[i * cols + j] * x[j]
        x[i] = s / rii

    var rss: Float64 = 0.0
    for i in range(cols, rows):
        rss += b[i] * b[i]

    var lo = List[Float64]()
    for _ in range(cols):
        lo.append(0.0)
    return DDLstsq(
        x^, lo^, LSTSQ_OK, cols, r_diag_min, pivot_ratio_min, sqrt(rss), 0
    )


# ── public drivers ────────────────────────────────────────────────────────────


fn dd_lstsq_flat(
    a: List[Float64], rows: Int, cols: Int, b: List[Float64], refine: Int
) -> DDLstsq:
    """Compensated Householder QR least squares on a row-major float64 design matrix.

    `a` holds `rows * cols` values, row-major. `b` holds `rows`. Returns `cols`
    coefficients, or a status and no coefficients.

    @capability dd_lstsq_flat
    complexity: O(rows * cols^2)
    counts:
    - rows * cols == len(a) [kernel_validated]
    - rows == len(b) [kernel_validated]
    - dim rows <= LSTSQ_MAX_CELLS [kernel_validated]
    - dim cols <= LSTSQ_MAX_COLS [kernel_validated]
    @endcapability
    """
    var code = _dims_check(rows, cols, len(a), len(b))
    if code != LSTSQ_OK:
        return _empty_result(code)
    if refine < 0 or refine > 8:
        return _empty_result(LSTSQ_ERR_EMPTY_DIM)
    var da = List[DD]()
    for i in range(rows * cols):
        if isnan(a[i]) or isinf(a[i]):
            return _empty_result(LSTSQ_ERR_NON_FINITE_INPUT)
        da.append(dd_from(a[i]))
    var db = List[DD]()
    for i in range(rows):
        if isnan(b[i]) or isinf(b[i]):
            return _empty_result(LSTSQ_ERR_NON_FINITE_INPUT)
        db.append(dd_from(b[i]))
    return _dd_qr_solve(da^, rows, cols, db^, refine)


fn f64_lstsq_flat(
    a: List[Float64], rows: Int, cols: Int, b: List[Float64]
) -> DDLstsq:
    """The float64 control for `dd_lstsq_flat`: identical algorithm, plain arithmetic.

    @capability f64_lstsq_flat
    complexity: O(rows * cols^2)
    counts:
    - rows * cols == len(a) [kernel_validated]
    - rows == len(b) [kernel_validated]
    - dim rows <= LSTSQ_MAX_CELLS [kernel_validated]
    - dim cols <= LSTSQ_MAX_COLS [kernel_validated]
    @endcapability
    """
    var code = _dims_check(rows, cols, len(a), len(b))
    if code != LSTSQ_OK:
        return _empty_result(code)
    for i in range(rows * cols):
        if isnan(a[i]) or isinf(a[i]):
            return _empty_result(LSTSQ_ERR_NON_FINITE_INPUT)
    for i in range(rows):
        if isnan(b[i]) or isinf(b[i]):
            return _empty_result(LSTSQ_ERR_NON_FINITE_INPUT)
    var ca = List[Float64]()
    for i in range(rows * cols):
        ca.append(a[i])
    var cb = List[Float64]()
    for i in range(rows):
        cb.append(b[i])
    return _f64_qr_solve(ca^, rows, cols, cb^)


fn _poly_dims_check(n: Int, lo_deg: Int, hi_deg: Int, lx: Int, ly: Int) -> Int:
    if n <= 0:
        return LSTSQ_ERR_EMPTY_DIM
    if lo_deg < 0 or hi_deg < lo_deg or hi_deg > LSTSQ_MAX_DEGREE:
        return LSTSQ_ERR_EMPTY_DIM
    if n > lx or n > ly:
        return LSTSQ_ERR_A_LENGTH
    return _dims_check(n, hi_deg - lo_deg + 1, n * (hi_deg - lo_deg + 1), n)


fn dd_poly_lstsq(
    x: List[Float64], y: List[Float64], n: Int,
    lo_deg: Int, hi_deg: Int, dd_powers: Bool, refine: Int
) -> DDLstsq:
    """Fit `sum_{k=lo_deg}^{hi_deg} beta_k x^k` to `y` by compensated Householder QR.

    `dd_powers` selects how the design matrix itself is built, and it is a *separate* lever
    from the precision of the solve:

    * `False` — powers by repeated **float64** multiplication, `p <- p * x`. This is the
      recipe every reference implementation uses and it is a real information loss: on StRD
      Filip (degree 10, `x` around -6.9) forming `x^2 .. x^10` this way perturbs the design
      matrix enough that the exact least-squares solution of the *perturbed* system already
      differs from the certified values in the 8th digit. No solver of any precision can
      recover that, so this arm is capped below the published bar and reported as such.
    * `True` — powers by repeated **double-double** multiplication from the same float64 `x`.
      The inputs are unchanged, only the construction is compensated. That lifts the same
      dataset's ceiling by ~6 digits, and on data whose powers are already exactly
      representable in float64 (integer `x`, StRD Wampler) it is bit-identical to `False` —
      so it is never worse.

    `lo_deg > 0` fits a model with no intercept (StRD NoInt1/NoInt2).

    @capability dd_poly_lstsq
    complexity: O(n * (hi_deg - lo_deg + 1)^2)
    counts:
    - n == len(x, y) [kernel_validated]
    - dim hi_deg <= LSTSQ_MAX_DEGREE [kernel_validated]
    @endcapability
    """
    var code = _poly_dims_check(n, lo_deg, hi_deg, len(x), len(y))
    if code != LSTSQ_OK:
        return _empty_result(code)
    if refine < 0 or refine > 8:
        return _empty_result(LSTSQ_ERR_EMPTY_DIM)
    var cols = hi_deg - lo_deg + 1
    for i in range(n):
        if isnan(x[i]) or isinf(x[i]) or isnan(y[i]) or isinf(y[i]):
            return _empty_result(LSTSQ_ERR_NON_FINITE_INPUT)
    var a = List[DD]()
    for _ in range(n * cols):
        a.append(DD(0.0, 0.0))
    for i in range(n):
        if dd_powers:
            var t = dd_from(1.0)
            for k in range(hi_deg + 1):
                if k >= lo_deg:
                    a[i * cols + (k - lo_deg)] = t
                t = dd_mul_d(t, x[i])
        else:
            var t: Float64 = 1.0
            for k in range(hi_deg + 1):
                if k >= lo_deg:
                    a[i * cols + (k - lo_deg)] = dd_from(t)
                t = t * x[i]
        for k in range(cols):
            var e = a[i * cols + k]
            if isnan(e.hi) or isinf(e.hi):
                return _empty_result(LSTSQ_ERR_NON_FINITE_INPUT)
    var b = List[DD]()
    for i in range(n):
        b.append(dd_from(y[i]))
    return _dd_qr_solve(a^, n, cols, b^, refine)


fn f64_poly_lstsq(
    x: List[Float64], y: List[Float64], n: Int,
    lo_deg: Int, hi_deg: Int, dd_powers: Bool
) -> DDLstsq:
    """The float64 control for `dd_poly_lstsq`, with the same `dd_powers` lever.

    Its existence is what turns "compensation is load-bearing" into a 2x2 measurement rather
    than a one-armed comparison. Construction and solve are independent levers:

        matrix in float64, solve in float64   f64_poly_lstsq(dd_powers=False)
        matrix in dd,      solve in float64   f64_poly_lstsq(dd_powers=True)
        matrix in float64, solve in dd        dd_poly_lstsq(dd_powers=False)
        matrix in dd,      solve in dd        dd_poly_lstsq(dd_powers=True)

    `dd_powers = True` here means the powers are formed in double-double and then rounded to
    float64 before the solve sees them, which is a strictly better design matrix handed to a
    strictly float64 solver. Without this cell a reader cannot tell which of the two changes
    bought the digits, and on this suite the answer is different per dataset.

    @capability f64_poly_lstsq
    complexity: O(n * (hi_deg - lo_deg + 1)^2)
    counts:
    - n == len(x, y) [kernel_validated]
    - dim hi_deg <= LSTSQ_MAX_DEGREE [kernel_validated]
    @endcapability
    """
    var code = _poly_dims_check(n, lo_deg, hi_deg, len(x), len(y))
    if code != LSTSQ_OK:
        return _empty_result(code)
    var cols = hi_deg - lo_deg + 1
    for i in range(n):
        if isnan(x[i]) or isinf(x[i]) or isnan(y[i]) or isinf(y[i]):
            return _empty_result(LSTSQ_ERR_NON_FINITE_INPUT)
    var a = List[Float64]()
    for _ in range(n * cols):
        a.append(0.0)
    for i in range(n):
        if dd_powers:
            var t = dd_from(1.0)
            for k in range(hi_deg + 1):
                if k >= lo_deg:
                    a[i * cols + (k - lo_deg)] = t.hi
                t = dd_mul_d(t, x[i])
        else:
            var t: Float64 = 1.0
            for k in range(hi_deg + 1):
                if k >= lo_deg:
                    a[i * cols + (k - lo_deg)] = t
                t = t * x[i]
        for k in range(cols):
            if isnan(a[i * cols + k]) or isinf(a[i * cols + k]):
                return _empty_result(LSTSQ_ERR_NON_FINITE_INPUT)
    var b = List[Float64]()
    for i in range(n):
        b.append(y[i])
    return _f64_qr_solve(a^, n, cols, b^)


fn dd_poly_lstsq_scaled(
    x: List[Float64], y: List[Float64], n: Int,
    hi_deg: Int, dd_powers: Bool, dd_mapback: Bool, refine: Int
) -> DDLstsq:
    """Fit in `numpy.polynomial.Polynomial.fit`'s conditioned basis, then map back.

    The domain map is byte-for-byte the one numpy uses: `t = off + scl * x` with
    `scl = 2 / (xmax - xmin)` and `off = -(xmax + xmin) / (xmax - xmin)`, both formed in
    float64 exactly as `numpy.polynomial.polyutils.mapparms` does. Fitting in `t` drops the
    Vandermonde condition number by orders of magnitude, which is the whole reason
    `Polynomial.fit` beats a plain float64 QR.

    **The map back is where this arm can lie, so it is a parameter.** The returned
    coefficients are in the *published* parameterisation, obtained from
    `beta_j = scl^j * sum_{k>=j} c_k * C(k,j) * off^(k-j)`. With `dd_mapback = False` that
    expansion runs in plain float64 and loses digits of its own; with `True` it runs in
    double-double. Reporting the digits measured in the `t` basis and implying they hold for
    `beta` would overstate the result by several digits, so this driver never returns `c`.

    Only defined for a full polynomial basis starting at degree 0: centring is a
    reparameterisation of the whole polynomial space, and a no-intercept model is not that
    space, so `lo_deg > 0` has no correct map back and is refused rather than approximated.

    @capability dd_poly_lstsq_scaled
    complexity: O(n * (hi_deg + 1)^2)
    counts:
    - n == len(x, y) [kernel_validated]
    - dim hi_deg <= LSTSQ_MAX_DEGREE [kernel_validated]
    @endcapability
    """
    var code = _poly_dims_check(n, 0, hi_deg, len(x), len(y))
    if code != LSTSQ_OK:
        return _empty_result(code)
    if refine < 0 or refine > 8:
        return _empty_result(LSTSQ_ERR_EMPTY_DIM)
    for i in range(n):
        if isnan(x[i]) or isinf(x[i]) or isnan(y[i]) or isinf(y[i]):
            return _empty_result(LSTSQ_ERR_NON_FINITE_INPUT)
    var xmin = x[0]
    var xmax = x[0]
    for i in range(1, n):
        if x[i] < xmin:
            xmin = x[i]
        if x[i] > xmax:
            xmax = x[i]
    var span = xmax - xmin
    if span == 0.0:
        # Every predictor value identical: the conditioned basis does not exist. Absent,
        # not silently un-scaled (rule 4).
        return _empty_result(LSTSQ_ERR_BASIS_NOT_APPLICABLE)
    var scl = 2.0 / span
    var off = -(xmax + xmin) / span
    if isnan(scl) or isinf(scl) or isnan(off) or isinf(off):
        return _empty_result(LSTSQ_ERR_NON_FINITE_INPUT)
    var t = List[Float64]()
    for i in range(n):
        var ti = off + scl * x[i]
        if isnan(ti) or isinf(ti):
            return _empty_result(LSTSQ_ERR_NON_FINITE_INPUT)
        t.append(ti)
    var fit = dd_poly_lstsq(t, y, n, 0, hi_deg, dd_powers, refine)
    if fit.status != LSTSQ_OK:
        return _empty_result(fit.status)
    var cols = hi_deg + 1

    # Pascal's triangle, exact in float64 for every degree this driver admits.
    var binom = List[Float64]()
    for _ in range(cols * cols):
        binom.append(0.0)
    for k in range(cols):
        binom[k * cols] = 1.0
        for j in range(1, k + 1):
            binom[k * cols + j] = binom[(k - 1) * cols + j - 1] + binom[
                (k - 1) * cols + j
            ]

    var out = List[Float64]()
    var out_lo = List[Float64]()
    if dd_mapback:
        var pow_off = List[DD]()
        var pow_scl = List[DD]()
        var po = dd_from(1.0)
        var ps = dd_from(1.0)
        for _ in range(cols):
            pow_off.append(po)
            pow_scl.append(ps)
            po = dd_mul_d(po, off)
            ps = dd_mul_d(ps, scl)
        for j in range(cols):
            var acc = DD(0.0, 0.0)
            for k in range(j, cols):
                var c = DD(fit.coefficients[k], fit.coefficients_lo[k])
                var term = dd_mul_d(c, binom[k * cols + j])
                acc = dd_add(acc, dd_mul(term, pow_off[k - j]))
            var beta = dd_mul(acc, pow_scl[j])
            out.append(beta.hi)
            out_lo.append(beta.lo)
    else:
        var pow_off_f = List[Float64]()
        var pow_scl_f = List[Float64]()
        var pof: Float64 = 1.0
        var psf: Float64 = 1.0
        for _ in range(cols):
            pow_off_f.append(pof)
            pow_scl_f.append(psf)
            pof = pof * off
            psf = psf * scl
        for j in range(cols):
            var accf: Float64 = 0.0
            for k in range(j, cols):
                accf += fit.coefficients[k] * binom[k * cols + j] * pow_off_f[k - j]
            out.append(accf * pow_scl_f[j])
            out_lo.append(0.0)
    return DDLstsq(
        out^,
        out_lo^,
        LSTSQ_OK,
        fit.rank,
        fit.r_diag_min,
        fit.pivot_ratio_min,
        fit.residual_norm,
        fit.refine_steps,
    )
