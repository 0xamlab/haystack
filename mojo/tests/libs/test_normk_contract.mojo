"""test_normk_contract.mojo — the status vocabulary, the work budget and the epsilon rule.

Hand-written. Three things are worth asserting here and they are not obvious ones.

* THE STATUS RANGE DOES NOT COLLIDE. `normk` owns 380-389 and every neighbouring package owns its
  own block (rule 4e). A code that drifts into `attnk`'s 360-379 does not fail anywhere — it makes
  one package's error read as another's, which is worse than an unknown code because it looks
  answered.
* THE WORK GUARD DOES NOT WRAP. `norm_work_fits` grows the budget by division precisely so a product
  that overflows 64 bits cannot compare as small. The test passes dimensions whose product wraps.
* EPSILON ZERO IS ALLOWED, NEGATIVE IS NOT. Zero is mathematically correct for a known non-zero row
  and refusing it would force a caller to invent a value their checkpoint did not train with. A
  negative eps can drive `variance + eps` below zero and make `sqrt` return NaN for ordinary input,
  which surfaces far from its cause.
"""
from attnk.contract import ATTN_OK
from gemm.contract import GEMM_OK
from normk.contract import (
    NORM_ERR_BAD_EPS,
    NORM_ERR_DIM_TOO_LARGE,
    NORM_ERR_EMPTY_DIM,
    NORM_ERR_WORK_TOO_LARGE,
    NORM_MAX_COLS,
    NORM_MAX_ROWS,
    NORM_MAX_WORK_CELLS,
    NORM_OK,
    norm_dims_check,
    norm_eps_ok,
    norm_status_name,
    norm_tol_for,
    norm_work_fits,
)
from tensorx.contract import TX_OK


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── the range is exclusive ────────────────────────────────────────────────
    if NORM_OK == 380 and NORM_ERR_BAD_EPS == 386:
        passed += 1
        print("  ✅ normk owns 380-389 as declared")
    else:
        failed += 1
        print("  ❌ the status range moved:", NORM_OK)

    if NORM_OK != ATTN_OK and NORM_OK != GEMM_OK and NORM_OK != TX_OK:
        passed += 1
        print("  ✅ no collision with tensorx, gemm or attnk OK codes")
    else:
        failed += 1
        print("  ❌ NORM_OK collides with a neighbouring package")

    if norm_status_name(NORM_ERR_BAD_EPS) == String("bad_epsilon"):
        passed += 1
        print("  ✅ codes name themselves")
    else:
        failed += 1
        print("  ❌ a status code named itself wrongly")

    if norm_status_name(999) == String("unknown_status"):
        passed += 1
        print("  ✅ an unknown code says so rather than borrowing a neighbour's meaning")
    else:
        failed += 1
        print("  ❌ an unknown code was given a name")

    # ── the work guard cannot be walked past by a wrapping product ────────────
    # 2^40 x 2^40 overflows a signed 64-bit product to a small or negative number; growing the
    # budget by division never forms it.
    var huge = 1 << 40
    if not norm_work_fits(huge, huge, NORM_MAX_WORK_CELLS):
        passed += 1
        print("  ✅ a product that wraps 64 bits is still refused")
    else:
        failed += 1
        print("  ❌ a wrapping product was accepted as fitting")

    if norm_work_fits(1024, 4096, NORM_MAX_WORK_CELLS):
        passed += 1
        print("  ✅ a real layer shape fits: 1024 tokens x 4096 hidden")
    else:
        failed += 1
        print("  ❌ an ordinary layer shape was refused")

    if norm_dims_check(NORM_MAX_ROWS + 1, 8, 1.0e-6) == NORM_ERR_DIM_TOO_LARGE:
        passed += 1
        print("  ✅ a row count past the ceiling is refused")
    else:
        failed += 1
        print("  ❌ an oversized row count was accepted")

    if norm_dims_check(8, NORM_MAX_COLS + 1, 1.0e-6) == NORM_ERR_DIM_TOO_LARGE:
        passed += 1
        print("  ✅ a row width past the ceiling is refused")
    else:
        failed += 1
        print("  ❌ an oversized row width was accepted")

    if norm_dims_check(0, 8, 1.0e-6) == NORM_ERR_EMPTY_DIM:
        passed += 1
        print("  ✅ an empty dimension is refused")
    else:
        failed += 1
        print("  ❌ an empty dimension was accepted")

    # A shape inside both per-dimension ceilings whose PRODUCT is not: the budget is a third check,
    # not an implication of the first two.
    if norm_dims_check(NORM_MAX_ROWS, NORM_MAX_COLS, 1.0e-6) == NORM_ERR_WORK_TOO_LARGE:
        passed += 1
        print("  ✅ two legal dimensions with an illegal product are refused on the budget")
    else:
        failed += 1
        print("  ❌ the work budget did not fire on a legal-by-dimension shape")

    # ── the epsilon rule ──────────────────────────────────────────────────────
    if norm_eps_ok(0.0) and norm_eps_ok(1.0e-6):
        passed += 1
        print("  ✅ eps of exactly zero is allowed, as is a normal one")
    else:
        failed += 1
        print("  ❌ a valid epsilon was refused")

    if not norm_eps_ok(-1.0e-6):
        passed += 1
        print("  ✅ a negative eps is refused before it can make sqrt return NaN")
    else:
        failed += 1
        print("  ❌ a negative epsilon was accepted")

    # ── the tolerance scales with BOTH magnitude and reduction width ──────────
    var narrow = norm_tol_for(1.0, 128)
    var wide = norm_tol_for(1.0, 16384)
    if wide > narrow:
        passed += 1
        print("  ✅ tolerance grows with the row width the reduction ran over")
    else:
        failed += 1
        print("  ❌ tolerance ignores the reduction width")

    if norm_tol_for(0.0, 128) > 0.0:
        passed += 1
        print("  ✅ a value normalizing to zero still gets a usable tolerance")
    else:
        failed += 1
        print("  ❌ the tolerance floor is missing; a near-zero value is held to an impossible bound")

    print("  [normk.contract] Passed:", passed, "Failed:", failed)
