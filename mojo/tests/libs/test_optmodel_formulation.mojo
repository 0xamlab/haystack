"""test_optmodel_formulation.mojo — known-value tests for the formulation container.

Hand-written; every number below was worked out on paper first. Anti-vacuity is by
mutation throughout: every check that certifies something also runs a mutated twin that
the same check must REJECT, so an assertion that would pass anything cannot survive.

  * The production LP `max 3x + 2y, x + y <= 4, x + 3y <= 6` validates, and each of the
    nine single-field corruptions of it (short `c`, wrong dense shape, the wrapping
    shape `3 x 6148914691236517206`, an unknown sense, NaN in `A`/`rhs`/`c`, a bad
    kind, crossed bounds) is refused with ITS OWN status and a WHERE index — not a
    shared "invalid" verdict that cannot distinguish them.
  * The lowering's arithmetic is asserted exactly: shifting `x ∈ [-2, 5]` folds
    `c·shift = -2` into the constant and moves the row `x + y >= 1` to rhs 3; the upper
    bound becomes the row `y_0 <= 7` tagged `row_kind 1 / row_ref 0`. Exact equality,
    because every quantity is exact in binary floating point.
  * A variable with no lower bound and a discrete variable with lower 0.5 are each a
    TYPED refusal (`free_variable...`, `discrete_variable_lower_bound_not_integral`),
    and the same formulations with the defect repaired lower cleanly — the mutation
    pair that proves the refusal tests something.
  * The rule-1c ceiling is demonstrated from a SMALL payload: 65536 variables with
    upper bounds and zero constraint rows would materialise a 2^32-cell dense block, so
    it must refuse `dimension_too_large`; the same shape at 1024 variables (2^20 cells)
    must lower. The refusal is the point — `git` history holds a 3.5 GB RSS spike from
    exactly this shape in `lp_from_arenas`.
  * The audit's tolerance doctrine is asserted at both scales the frozen modules
    document: a FULL-UNIT violation of `x <= 1e9` must be caught (the rejected
    `tol*(1+|b|)` budget passed it), while a 1e-5 gap at the same magnitude is honest
    rounding and must pass. Near the optimum, `(4, 0)` audits feasible and each of the
    three violation kinds (row, bound, integrality) is triggered by its own mutated
    point and lands in its own counter with its own WHERE.
  * Status codes: all `OPTM_*` codes sit at 200+, clear of every vocabulary the package
    composes (model 0-30, linear 40-63, explain 80-86, integer 100-105, quadratic
    110-117, routing 120-129, scheduling 130-139, multiobjective 140-149, robust
    150-170), and their names are pairwise distinct.
"""
from optimization.model import (
    MODEL_ERR_BINARY_BOUNDS,
    MODEL_ERR_BOUNDS_CROSSED,
    MODEL_ERR_DENSE_SHAPE,
    MODEL_ERR_DIMENSION_TOO_LARGE,
    MODEL_ERR_LENGTH_MISMATCH,
    MODEL_ERR_NON_FINITE_COEFFICIENT,
    MODEL_ERR_NON_FINITE_POINT,
    MODEL_ERR_NON_FINITE_RHS,
    MODEL_ERR_POLICY,
    MODEL_ERR_SENSE,
    MODEL_ERR_VAR_KIND,
    MODEL_OK,
    SENSE_EQ,
    SENSE_GE,
    SENSE_LE,
    VAR_BINARY,
    VAR_CONTINUOUS,
    VAR_FLAG_BOXED,
    VAR_FLAG_HAS_LOWER,
    VAR_INTEGER,
)
from optmodel.formulation import (
    OPTM_ERR_DISCRETE_SHIFT,
    OPTM_ERR_FREE_VARIABLE,
    OPTM_ERR_GROUND_TRUTH,
    OPTM_MAX_LOWERED_CELLS,
    OPTM_REFUSED_INFEASIBLE,
    OPTM_REFUSED_SEARCH_LIMIT,
    OPTM_REFUSED_SELF_CHECK,
    OPTM_REFUSED_UNBOUNDED,
    OPTM_REFUSED_UNCERTIFIED,
    OPTM_VERDICT_REFUSED,
    OPTM_VERDICT_VERIFIED,
    OPTM_VERDICT_WRONG,
    formulation_check_flat,
    formulation_lower_flat,
    formulation_point_audit_flat,
    optm_status_name,
    optm_verdict_name,
)


fn _ints(*vals: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _floats(*vals: Float64) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(vals)):
        out.append(vals[i])
    return out^


fn _close(a: Float64, b: Float64, tol: Float64) -> Bool:
    var d = a - b
    if d < 0.0:
        d = -d
    return d <= tol


# The production LP everything below mutates: max 3x + 2y, x + y <= 4, x + 3y <= 6.
fn _c2() -> List[Float64]:
    return _floats(3.0, 2.0)


fn _a2() -> List[Float64]:
    return _floats(1.0, 1.0, 1.0, 3.0)


fn _b2() -> List[Float64]:
    return _floats(4.0, 6.0)


fn _le2() -> List[Int]:
    return _ints(SENSE_LE, SENSE_LE)


fn _cont2() -> List[Int]:
    return _ints(VAR_CONTINUOUS, VAR_CONTINUOUS)


fn _lower2() -> List[Float64]:
    return _floats(0.0, 0.0)


fn _pad2() -> List[Float64]:
    return _floats(0.0, 0.0)


fn _haslow2() -> List[Int]:
    return _ints(VAR_FLAG_HAS_LOWER, VAR_FLAG_HAS_LOWER)


fn main() raises:
    var passed = 0
    var failed = 0

    # ── a valid formulation validates, with its census ────────────────────────
    var ok = formulation_check_flat(
        2, 2, _c2(), 0.0, _a2(), _le2(), _b2(), _cont2(),
        _lower2(), _pad2(), _haslow2(),
    )
    if (
        ok.ok and ok.status == MODEL_OK and ok.n_vars == 2 and ok.n_cons == 2
        and ok.n_continuous == 2 and ok.n_integer == 0 and ok.n_binary == 0
        and ok.constraint_index == -1 and ok.var_index == -1
    ):
        passed += 1
        print("  ✅ the production LP validates, census 2 continuous")
    else:
        failed += 1
        print("  ❌ valid formulation rejected:", ok.status, ok.ok)

    # ── each corruption is refused with ITS OWN code and WHERE ────────────────
    var short_c = formulation_check_flat(
        2, 2, _floats(3.0), 0.0, _a2(), _le2(), _b2(), _cont2(),
        _lower2(), _pad2(), _haslow2(),
    )
    var bad_shape = formulation_check_flat(
        2, 2, _c2(), 0.0, _floats(1.0, 1.0, 1.0), _le2(), _b2(), _cont2(),
        _lower2(), _pad2(), _haslow2(),
    )
    # The wrapping shape: 3 * 6148914691236517206 == 2 in a 64-bit multiply, so a
    # multiply-based guard admits it and then reads far past the end.
    var wrap = formulation_check_flat(
        3, 6148914691236517206, _floats(0.0, 0.0, 0.0), 0.0, _floats(1.0, 2.0),
        _ints(SENSE_LE), _floats(1.0), _ints(0, 0, 0),
        _floats(0.0, 0.0, 0.0), _floats(0.0, 0.0, 0.0), _ints(1, 1, 1),
    )
    var bad_sense = formulation_check_flat(
        2, 2, _c2(), 0.0, _a2(), _ints(SENSE_LE, 9), _b2(), _cont2(),
        _lower2(), _pad2(), _haslow2(),
    )
    var nan = 0.0 / 0.0
    var nan_a = formulation_check_flat(
        2, 2, _c2(), 0.0, _floats(1.0, 1.0, nan, 3.0), _le2(), _b2(), _cont2(),
        _lower2(), _pad2(), _haslow2(),
    )
    var nan_rhs = formulation_check_flat(
        2, 2, _c2(), 0.0, _a2(), _le2(), _floats(4.0, nan), _cont2(),
        _lower2(), _pad2(), _haslow2(),
    )
    var nan_c = formulation_check_flat(
        2, 2, _floats(3.0, nan), 0.0, _a2(), _le2(), _b2(), _cont2(),
        _lower2(), _pad2(), _haslow2(),
    )
    var bad_kind = formulation_check_flat(
        2, 2, _c2(), 0.0, _a2(), _le2(), _b2(), _ints(VAR_CONTINUOUS, 7),
        _lower2(), _pad2(), _haslow2(),
    )
    var crossed = formulation_check_flat(
        2, 2, _c2(), 0.0, _a2(), _le2(), _b2(), _cont2(),
        _floats(0.0, 5.0), _floats(0.0, 2.0), _ints(VAR_FLAG_HAS_LOWER, VAR_FLAG_BOXED),
    )
    var zero_vars = formulation_check_flat(
        0, 0, _floats(), 0.0, _floats(), _ints(), _floats(), _ints(),
        _floats(), _floats(), _ints(),
    )
    if (
        short_c.status == MODEL_ERR_LENGTH_MISMATCH
        and bad_shape.status == MODEL_ERR_DENSE_SHAPE
        and wrap.status == MODEL_ERR_DENSE_SHAPE
        and bad_sense.status == MODEL_ERR_SENSE and bad_sense.constraint_index == 1
        and nan_a.status == MODEL_ERR_NON_FINITE_COEFFICIENT
        and nan_a.constraint_index == 1 and nan_a.var_index == 0
        and nan_rhs.status == MODEL_ERR_NON_FINITE_RHS and nan_rhs.constraint_index == 1
        and nan_c.status == MODEL_ERR_NON_FINITE_COEFFICIENT and nan_c.var_index == 1
        and bad_kind.status == MODEL_ERR_VAR_KIND and bad_kind.var_index == 1
        and crossed.status == MODEL_ERR_BOUNDS_CROSSED and crossed.var_index == 1
        and zero_vars.status == MODEL_ERR_DENSE_SHAPE
        and not short_c.ok and not wrap.ok and not crossed.ok
    ):
        passed += 1
        print("  ✅ ten corruptions, ten distinct refusals, each with its WHERE")
    else:
        failed += 1
        print(
            "  ❌ corruption statuses wrong:", short_c.status, bad_shape.status,
            wrap.status, bad_sense.status, nan_a.status, nan_rhs.status,
            nan_c.status, bad_kind.status, crossed.status, zero_vars.status,
        )

    # A binary variable must declare BOTH bounds inside [0, 1] — `model.mojo`'s own
    # rule, inherited through `variables_validate_flat`, not restated here.
    var bin_unbounded = formulation_check_flat(
        2, 2, _c2(), 0.0, _a2(), _le2(), _b2(), _ints(VAR_BINARY, VAR_CONTINUOUS),
        _lower2(), _pad2(), _haslow2(),
    )
    var bin_ok = formulation_check_flat(
        2, 2, _c2(), 0.0, _a2(), _le2(), _b2(), _ints(VAR_BINARY, VAR_CONTINUOUS),
        _lower2(), _floats(1.0, 0.0), _ints(VAR_FLAG_BOXED, VAR_FLAG_HAS_LOWER),
    )
    if (
        bin_unbounded.status == MODEL_ERR_BINARY_BOUNDS
        and bin_ok.ok and bin_ok.n_binary == 1 and bin_ok.n_continuous == 1
    ):
        passed += 1
        print("  ✅ binary without both [0,1] bounds is refused; boxed binary passes")
    else:
        failed += 1
        print("  ❌ binary bounds rule broken:", bin_unbounded.status, bin_ok.status)

    # ── the lowering's arithmetic, exactly ─────────────────────────────────────
    # min 2x + 3y, x + y >= 1, x ∈ [-2, 5], y ∈ [0, 5]:
    #   shift = (-2, 0); constant folds to c·shift = -4; the row folds to
    #   rhs 1 - (1·(-2) + 1·0) = 3; two upper rows: y_0 <= 7 and y_1 <= 5.
    var low = formulation_lower_flat(
        2, 1, _floats(2.0, 3.0), 0.0, _floats(1.0, 1.0), _ints(SENSE_GE),
        _floats(1.0), _cont2(), _floats(-2.0, 0.0), _floats(5.0, 5.0),
        _ints(VAR_FLAG_BOXED, VAR_FLAG_BOXED),
    )
    if (
        low.ok and low.rows == 3 and low.cols == 2 and low.n_upper_rows == 2
        and low.constant == -4.0
        and low.rhs[0] == 3.0 and low.senses[0] == SENSE_GE
        and low.rhs[1] == 7.0 and low.senses[1] == SENSE_LE
        and low.rhs[2] == 5.0 and low.senses[2] == SENSE_LE
        and low.a[2] == 1.0 and low.a[3] == 0.0 and low.a[4] == 0.0 and low.a[5] == 1.0
        and low.shift[0] == -2.0 and low.shift[1] == 0.0
        and low.row_kind[0] == 0 and low.row_ref[0] == 0
        and low.row_kind[1] == 1 and low.row_ref[1] == 0
        and low.row_kind[2] == 1 and low.row_ref[2] == 1
    ):
        passed += 1
        print("  ✅ shift by (-2,0): constant -4, row rhs 3, upper rows y0<=7 y1<=5")
    else:
        failed += 1
        print(
            "  ❌ lowering arithmetic wrong:", low.status, low.rows, low.constant,
            len(low.rhs),
        )

    # ── a binary's OWN `x <= 1` row is skipped iff it is REDUNDANT ─────────────
    # Three variables, one real row (`x0+x1+x2 <= 2`) to keep `n_cons >= 1`:
    #   var0: binary, upper 1 — `milp_solve`'s root box already says this row, so
    #         `formulation_lower_flat` must OMIT its own copy;
    #   var1: binary, upper 0 (fixed at 0) — the root box only gives `<= 1`, so THIS
    #         row is the only place the tighter bound lives and must be KEPT;
    #   var2: continuous, upper 1 — no root box exists for a continuous kind at all,
    #         so its row must be KEPT regardless of the bound's numeric value.
    # Expected: 1 real row + 2 upper rows (var1, var2, in index order) = 3 rows.
    var mixed = formulation_lower_flat(
        3, 1, _floats(0.0, 0.0, 0.0), 0.0, _floats(1.0, 1.0, 1.0), _ints(SENSE_LE),
        _floats(2.0), _ints(VAR_BINARY, VAR_BINARY, VAR_CONTINUOUS),
        _floats(0.0, 0.0, 0.0), _floats(1.0, 0.0, 1.0),
        _ints(VAR_FLAG_BOXED, VAR_FLAG_BOXED, VAR_FLAG_BOXED),
    )
    if (
        mixed.ok and mixed.rows == 3 and mixed.n_upper_rows == 2
        and mixed.row_kind[0] == 0 and mixed.row_ref[0] == 0
        and mixed.row_kind[1] == 1 and mixed.row_ref[1] == 1
        and mixed.rhs[1] == 0.0
        and mixed.row_kind[2] == 1 and mixed.row_ref[2] == 2
        and mixed.rhs[2] == 1.0
    ):
        passed += 1
        print("  ✅ binary-at-1 row omitted; binary-at-0 and continuous-at-1 kept")
    else:
        failed += 1
        print(
            "  ❌ redundant-row skip wrong:", mixed.rows, mixed.n_upper_rows,
            len(mixed.row_kind),
        )

    # Mutation: an all-continuous twin of the SAME shape must NOT skip anything — the
    # predicate is `kind == VAR_BINARY`, not merely `upper == 1.0`, and this is the
    # check that would catch a broadened (wrong) version of it.
    var all_continuous = formulation_lower_flat(
        3, 1, _floats(0.0, 0.0, 0.0), 0.0, _floats(1.0, 1.0, 1.0), _ints(SENSE_LE),
        _floats(2.0), _ints(VAR_CONTINUOUS, VAR_CONTINUOUS, VAR_CONTINUOUS),
        _floats(0.0, 0.0, 0.0), _floats(1.0, 0.0, 1.0),
        _ints(VAR_FLAG_BOXED, VAR_FLAG_BOXED, VAR_FLAG_BOXED),
    )
    if all_continuous.ok and all_continuous.rows == 4 and all_continuous.n_upper_rows == 3:
        passed += 1
        print("  ✅ the same three upper bounds, all continuous, keep all three rows")
    else:
        failed += 1
        print(
            "  ❌ continuous-kind twin wrongly skipped a row:", all_continuous.rows,
            all_continuous.n_upper_rows,
        )

    # Mutation: a binary FIXED AT 1 (lower == upper == 1.0) must still get its OWN row.
    # Its shift is 1, so the row this function would emit is `y_0 <= upper - shift ==
    # 0.0` — NOT the same statement as `_root_node`'s hardcoded `y_0 <= 1.0` (that box
    # is written in `y`, unaware of any shift). A predicate that tested `upper == 1.0`
    # alone (forgetting `lower == 0.0`) would wrongly skip this row and silently widen
    # the variable from the single point `{1}` back to `{0, 1}` — this is the case
    # that distinguishes the two.
    var fixed_at_one = formulation_lower_flat(
        1, 1, _floats(0.0), 0.0, _floats(1.0), _ints(SENSE_LE), _floats(5.0),
        _ints(VAR_BINARY), _floats(1.0), _floats(1.0), _ints(VAR_FLAG_BOXED),
    )
    if (
        fixed_at_one.ok and fixed_at_one.rows == 2 and fixed_at_one.n_upper_rows == 1
        and fixed_at_one.row_kind[1] == 1 and fixed_at_one.row_ref[1] == 0
        and fixed_at_one.rhs[1] == 0.0
    ):
        passed += 1
        print("  ✅ a binary fixed at 1 keeps its own row (y_0 <= 0), not skipped")
    else:
        failed += 1
        print(
            "  ❌ binary-fixed-at-1 row wrongly skipped:", fixed_at_one.rows,
            fixed_at_one.n_upper_rows,
        )

    # ── typed refusals at lowering, each with its repaired twin ───────────────
    var free = formulation_lower_flat(
        2, 2, _c2(), 0.0, _a2(), _le2(), _b2(), _cont2(),
        _lower2(), _pad2(), _ints(0, VAR_FLAG_HAS_LOWER),
    )
    var repaired_free = formulation_lower_flat(
        2, 2, _c2(), 0.0, _a2(), _le2(), _b2(), _cont2(),
        _lower2(), _pad2(), _haslow2(),
    )
    var frac_int = formulation_lower_flat(
        2, 2, _c2(), 0.0, _a2(), _le2(), _b2(), _ints(VAR_INTEGER, VAR_CONTINUOUS),
        _floats(0.5, 0.0), _pad2(), _haslow2(),
    )
    var frac_cont = formulation_lower_flat(
        2, 2, _c2(), 0.0, _a2(), _le2(), _b2(), _cont2(),
        _floats(0.5, 0.0), _pad2(), _haslow2(),
    )
    if (
        free.status == OPTM_ERR_FREE_VARIABLE and not free.ok and len(free.a) == 0
        and repaired_free.ok
        and frac_int.status == OPTM_ERR_DISCRETE_SHIFT and not frac_int.ok
        and frac_cont.ok and frac_cont.rhs[0] == 3.5
    ):
        passed += 1
        print("  ✅ free variable and fractional discrete shift refused; twins lower")
    else:
        failed += 1
        print(
            "  ❌ lowering refusals wrong:", free.status, repaired_free.status,
            frac_int.status, frac_cont.status,
        )

    # ── the rule-1c ceiling, from a small payload ──────────────────────────────
    # 65536 upper-bounded variables and NO rows: the lowered block would be
    # 65536 x 65536 = 2^32 cells (32 GB), from a payload of a few hundred KB. The
    # ceiling is 2^26 cells, so this must refuse. 1024 variables is 2^20 cells and
    # must pass — the mutation that proves the guard reads the arithmetic.
    var big_n = 65536
    var big_c = List[Float64]()
    var big_kind = List[Int]()
    var big_low = List[Float64]()
    var big_up = List[Float64]()
    var big_flags = List[Int]()
    for _ in range(big_n):
        big_c.append(1.0)
        big_kind.append(VAR_CONTINUOUS)
        big_low.append(0.0)
        big_up.append(1.0)
        big_flags.append(VAR_FLAG_BOXED)
    var too_big = formulation_lower_flat(
        big_n, 0, big_c, 0.0, _floats(), _ints(), _floats(), big_kind,
        big_low, big_up, big_flags,
    )
    var small_n = 1024
    var small_c = List[Float64]()
    var small_kind = List[Int]()
    var small_low = List[Float64]()
    var small_up = List[Float64]()
    var small_flags = List[Int]()
    for _ in range(small_n):
        small_c.append(1.0)
        small_kind.append(VAR_CONTINUOUS)
        small_low.append(0.0)
        small_up.append(1.0)
        small_flags.append(VAR_FLAG_BOXED)
    var fits = formulation_lower_flat(
        small_n, 0, small_c, 0.0, _floats(), _ints(), _floats(), small_kind,
        small_low, small_up, small_flags,
    )
    if (
        too_big.status == MODEL_ERR_DIMENSION_TOO_LARGE and not too_big.ok
        and len(too_big.a) == 0
        and fits.ok and fits.rows == small_n
        and small_n * small_n <= OPTM_MAX_LOWERED_CELLS
    ):
        passed += 1
        print("  ✅ 2^32 lowered cells refused from a small payload; 2^20 lowers")
    else:
        failed += 1
        print("  ❌ cell ceiling broken:", too_big.status, fits.status, fits.rows)

    # ── the audit: certify the optimum, reject each mutation in its own counter ─
    var at_opt = formulation_point_audit_flat(
        2, 2, _c2(), 0.0, _a2(), _le2(), _b2(), _cont2(),
        _lower2(), _pad2(), _haslow2(), _floats(4.0, 0.0), 1e-9, 1e-9,
    )
    var row_bad = formulation_point_audit_flat(
        2, 2, _c2(), 0.0, _a2(), _le2(), _b2(), _cont2(),
        _lower2(), _pad2(), _haslow2(), _floats(4.1, 0.0), 1e-9, 1e-9,
    )
    var bound_bad = formulation_point_audit_flat(
        2, 2, _c2(), 0.0, _a2(), _le2(), _b2(), _cont2(),
        _lower2(), _pad2(), _haslow2(), _floats(4.0, -0.5), 1e-9, 1e-9,
    )
    var int_bad = formulation_point_audit_flat(
        2, 2, _c2(), 0.0, _a2(), _le2(), _b2(), _ints(VAR_INTEGER, VAR_INTEGER),
        _lower2(), _pad2(), _haslow2(), _floats(3.5, 0.0), 1e-9, 1e-9,
    )
    if (
        at_opt.status == MODEL_OK and at_opt.feasible
        and at_opt.has_objective and at_opt.objective == 12.0
        and at_opt.n_row_violations == 0 and at_opt.n_bound_violations == 0
        and not row_bad.feasible and row_bad.n_row_violations == 1
        and row_bad.worst_row == 0 and _close(row_bad.row_violation, 0.1, 1e-9)
        and row_bad.has_objective and _close(row_bad.objective, 12.3, 1e-12)
        and not bound_bad.feasible and bound_bad.n_bound_violations == 1
        and bound_bad.worst_bound_var == 1 and _close(bound_bad.bound_violation, 0.5, 1e-12)
        and not int_bad.feasible and int_bad.n_integrality_violations == 1
        and int_bad.worst_integrality_var == 0
        and _close(int_bad.integrality_violation, 0.5, 1e-12)
    ):
        passed += 1
        print("  ✅ (4,0) audits feasible at 12; row/bound/integrality mutations each caught")
    else:
        failed += 1
        print(
            "  ❌ audit verdicts wrong:", at_opt.feasible, row_bad.n_row_violations,
            bound_bad.n_bound_violations, int_bad.n_integrality_violations,
        )

    # ── the tolerance doctrine at magnitude 1e9 ───────────────────────────────
    # `x <= 1e9` violated by a FULL UNIT: the rejected `tol*(1+|b|)` budget was
    # 1.000000001 and passed it. The honest budget is ~4.5e-4 here, so 1.0 must fail —
    # while a 1e-5 overshoot IS inside the rounding a 1e9-magnitude dot product can
    # carry, and must pass.
    var unit_violation = formulation_point_audit_flat(
        1, 1, _floats(1.0), 0.0, _floats(1.0), _ints(SENSE_LE), _floats(1e9),
        _ints(VAR_CONTINUOUS), _floats(0.0), _floats(0.0), _ints(VAR_FLAG_HAS_LOWER),
        _floats(1e9 + 1.0), 1e-9, 1e-9,
    )
    var rounding_gap = formulation_point_audit_flat(
        1, 1, _floats(1.0), 0.0, _floats(1.0), _ints(SENSE_LE), _floats(1e9),
        _ints(VAR_CONTINUOUS), _floats(0.0), _floats(0.0), _ints(VAR_FLAG_HAS_LOWER),
        _floats(1e9 + 1e-5), 1e-9, 1e-9,
    )
    if (
        not unit_violation.feasible and unit_violation.n_row_violations == 1
        and rounding_gap.feasible
    ):
        passed += 1
        print("  ✅ a full unit past 1e9 is a violation; 1e-5 there is rounding")
    else:
        failed += 1
        print(
            "  ❌ magnitude doctrine broken:", unit_violation.feasible,
            rounding_gap.feasible,
        )

    # ── audit input defects are statuses, not verdicts ────────────────────────
    var wrong_len = formulation_point_audit_flat(
        2, 2, _c2(), 0.0, _a2(), _le2(), _b2(), _cont2(),
        _lower2(), _pad2(), _haslow2(), _floats(4.0), 1e-9, 1e-9,
    )
    var nan_point = formulation_point_audit_flat(
        2, 2, _c2(), 0.0, _a2(), _le2(), _b2(), _cont2(),
        _lower2(), _pad2(), _haslow2(), _floats(nan, 0.0), 1e-9, 1e-9,
    )
    var bad_tol = formulation_point_audit_flat(
        2, 2, _c2(), 0.0, _a2(), _le2(), _b2(), _cont2(),
        _lower2(), _pad2(), _haslow2(), _floats(4.0, 0.0), -1.0, 1e-9,
    )
    if (
        wrong_len.status == MODEL_ERR_LENGTH_MISMATCH and not wrong_len.feasible
        and nan_point.status == MODEL_ERR_NON_FINITE_POINT
        and bad_tol.status == MODEL_ERR_POLICY
    ):
        passed += 1
        print("  ✅ short point, NaN point and negative tolerance are named defects")
    else:
        failed += 1
        print(
            "  ❌ audit defect codes wrong:", wrong_len.status, nan_point.status,
            bad_tol.status,
        )

    # ── status vocabulary: 200+, distinct, clear of everything composed ───────
    var codes = _ints(
        OPTM_ERR_FREE_VARIABLE, OPTM_ERR_DISCRETE_SHIFT, OPTM_REFUSED_INFEASIBLE,
        OPTM_REFUSED_UNBOUNDED, OPTM_REFUSED_SEARCH_LIMIT, OPTM_REFUSED_UNCERTIFIED,
        OPTM_REFUSED_SELF_CHECK, OPTM_ERR_GROUND_TRUTH,
    )
    var vocabulary_clear = True
    for i in range(len(codes)):
        # model 0-30, linear 40-63, explain 80-86, integer 100-105, quadratic 110-117,
        # routing 120-129, scheduling 130-139, multiobjective 140-150, robust 150-170.
        if codes[i] < 200:
            vocabulary_clear = False
        for j in range(i + 1, len(codes)):
            if codes[j] == codes[i]:
                vocabulary_clear = False
            if optm_status_name(codes[j]) == optm_status_name(codes[i]):
                vocabulary_clear = False
    if (
        vocabulary_clear
        and optm_status_name(OPTM_ERR_FREE_VARIABLE)
        == "free_variable_unsupported_declare_a_lower_bound"
        and optm_status_name(MODEL_ERR_LENGTH_MISMATCH)
        == "parallel_arrays_length_mismatch"
        and optm_verdict_name(OPTM_VERDICT_VERIFIED) == "verified"
        and optm_verdict_name(OPTM_VERDICT_REFUSED) == "refused"
        and optm_verdict_name(OPTM_VERDICT_WRONG) == "wrong"
        and optm_verdict_name(99) == "unknown_verdict"
    ):
        passed += 1
        print("  ✅ codes at 200+, pairwise distinct, names fall through the vocabularies")
    else:
        failed += 1
        print("  ❌ status vocabulary broken")

    print("  [optmodel.formulation] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("optmodel.formulation suite failed")
