"""test_gemm_contract.mojo — known-value tests for the gemm status vocabulary and budgets.

Hand-written. The interesting assertions are about the work budget, not the shape check: three
dimensions can each sit far inside the element ceiling while `m * n * k` is not reachable this
decade, and the caller-side symptom of missing that is a hang — indistinguishable from rule 1's
uncatchable abort from a client's point of view.
"""
from gemm.contract import (
    GEMM_BACKEND_CPU_SIMD,
    GEMM_BACKEND_METAL,
    GEMM_BACKEND_SCALAR,
    GEMM_ERR_A_LENGTH,
    GEMM_ERR_B_LENGTH,
    GEMM_ERR_DIM_TOO_LARGE,
    GEMM_ERR_EMPTY_DIM,
    GEMM_ERR_WORK_TOO_LARGE,
    GEMM_MAX_DIM_ELEMS,
    GEMM_MAX_FLOP_CELLS,
    GEMM_OK,
    gemm_backend_name,
    gemm_dims_check,
    gemm_scalars_ok,
    gemm_status_name,
    gemm_work_fits,
)
from tensorx.contract import TX_MAX_ELEMS


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── status vocabulary is distinct and in range ────────────────────────────
    var codes = List[Int]()
    codes.append(GEMM_OK)
    codes.append(GEMM_ERR_EMPTY_DIM)
    codes.append(GEMM_ERR_A_LENGTH)
    codes.append(GEMM_ERR_B_LENGTH)
    codes.append(GEMM_ERR_DIM_TOO_LARGE)
    codes.append(GEMM_ERR_WORK_TOO_LARGE)

    var distinct = True
    var in_range = True
    for i in range(len(codes)):
        if codes[i] < 320 or codes[i] > 339:
            in_range = False
        for j in range(len(codes)):
            if i != j and gemm_status_name(codes[i]) == gemm_status_name(codes[j]):
                distinct = False
    if distinct and in_range and gemm_status_name(1) == String("unknown_status"):
        passed += 1
        print("  ✅ gemm statuses are distinct and inside its own 320-339 range (rule 4e)")
    else:
        failed += 1
        print("  ❌ gemm status codes collide, escaped their range, or mislabel an unknown")

    # tensorx owns 300-319; a shared integer meaning two things across packages is the defect.
    var no_overlap = True
    for i in range(len(codes)):
        if codes[i] >= 300 and codes[i] <= 319:
            no_overlap = False
    if no_overlap:
        passed += 1
        print("  ✅ no gemm code overlaps the tensorx 300-319 range")
    else:
        failed += 1
        print("  ❌ a gemm status collides with a tensorx status")

    if (
        gemm_backend_name(GEMM_BACKEND_SCALAR) == String("cpu_scalar")
        and gemm_backend_name(GEMM_BACKEND_CPU_SIMD) == String("cpu_simd")
        and gemm_backend_name(GEMM_BACKEND_METAL) == String("metal")
        and gemm_backend_name(77) == String("unknown_backend")
    ):
        passed += 1
        print("  ✅ backend tags name themselves, so a result can say which kernel ran")
    else:
        failed += 1
        print("  ❌ backend tag naming is wrong")

    # ── the work budget: three legal dimensions, one illegal product ──────────
    # This is the case a per-buffer ceiling cannot catch. 2^20 cubed is 2^60 multiply-accumulates.
    if not gemm_work_fits(1 << 20, 1 << 20, 1 << 20, GEMM_MAX_FLOP_CELLS):
        passed += 1
        print("  ✅ m=n=k=2^20 is refused on work even though each dimension is modest")
    else:
        failed += 1
        print("  ❌ the work budget accepted 2^60 multiply-accumulates")

    if gemm_work_fits(64, 64, 64, GEMM_MAX_FLOP_CELLS):
        passed += 1
        print("  ✅ an ordinary 64^3 shape fits the work budget")
    else:
        failed += 1
        print("  ❌ the work budget rejected an ordinary shape")

    # The wrapping-multiply trap, in three factors this time.
    if not gemm_work_fits(3, 6148914691236517206, 3, GEMM_MAX_FLOP_CELLS):
        passed += 1
        print("  ✅ a wrapping three-factor product is refused, not formed")
    else:
        failed += 1
        print("  ❌ gemm_work_fits formed a wrapping product")

    if (
        not gemm_work_fits(0, 5, 5, GEMM_MAX_FLOP_CELLS)
        and not gemm_work_fits(5, -1, 5, GEMM_MAX_FLOP_CELLS)
        and not gemm_work_fits(5, 5, 5, 0)
    ):
        passed += 1
        print("  ✅ non-positive dimensions and a zero ceiling do not 'fit' vacuously")
    else:
        failed += 1
        print("  ❌ gemm_work_fits accepted a non-positive input")

    # ── the element ceiling is divided by three, not applied three times ──────
    # A, B and C are all live at once, so the per-object budget is shared (rule 1c).
    # GEMM_MAX_DIM_ELEMS is written as a literal because the capability parser cannot evaluate a
    # division, so this is the assertion that keeps the literal tied to its derivation. Without it the
    # two live in separate files and drift in separate commits.
    if GEMM_MAX_DIM_ELEMS == TX_MAX_ELEMS // 3:
        passed += 1
        print("  ✅ the per-buffer ceiling is exactly TX_MAX_ELEMS // 3 (A, B and C all live)")
    else:
        failed += 1
        print("  ❌ GEMM_MAX_DIM_ELEMS drifted from TX_MAX_ELEMS // 3")

    if GEMM_MAX_FLOP_CELLS == 68719476736:
        passed += 1
        print("  ✅ the work ceiling is 2^36 multiply-accumulates")
    else:
        failed += 1
        print("  ❌ GEMM_MAX_FLOP_CELLS drifted")

    # ── shape checking is exact on both operands ──────────────────────────────
    if gemm_dims_check(2, 2, 3, 6, 6) == GEMM_OK:
        passed += 1
        print("  ✅ a 2x3 by 3x2 shape with exact buffers is accepted")
    else:
        failed += 1
        print("  ❌ an exact shape was rejected")

    # Longer is as wrong as shorter: it means the caller and the kernel disagree about the data.
    if (
        gemm_dims_check(2, 2, 3, 7, 6) == GEMM_ERR_A_LENGTH
        and gemm_dims_check(2, 2, 3, 5, 6) == GEMM_ERR_A_LENGTH
        and gemm_dims_check(2, 2, 3, 6, 7) == GEMM_ERR_B_LENGTH
    ):
        passed += 1
        print("  ✅ A and B length mismatches are distinct, and 'too long' is rejected too")
    else:
        failed += 1
        print("  ❌ shape checking accepted a buffer that disagreed with its declared shape")

    if (
        gemm_dims_check(0, 2, 3, 0, 6) == GEMM_ERR_EMPTY_DIM
        and gemm_dims_check(-1, 2, 3, 6, 6) == GEMM_ERR_EMPTY_DIM
    ):
        passed += 1
        print("  ✅ an empty or negative dimension is refused before any length is considered")
    else:
        failed += 1
        print("  ❌ an empty dimension was not refused")

    # ── NaN scalars are caught before anything is built from them ─────────────
    var nan_v = 0.0 / 0.0
    var inf_v = 1.0 / 0.0
    if gemm_scalars_ok(1.0, 0.0) and not gemm_scalars_ok(nan_v, 0.0) and not gemm_scalars_ok(1.0, inf_v):
        passed += 1
        print("  ✅ a NaN or infinite alpha/beta is refused (rule 4d: validate before you compare)")
    else:
        failed += 1
        print("  ❌ a non-finite scaling factor was accepted")

    print("  [gemm.contract] Passed:", passed, "Failed:", failed)
