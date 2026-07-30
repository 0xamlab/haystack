"""test_columnar_validity.mojo — known-value tests for validity bitmaps and dtypes.

Hand-written. The bitmap is the piece that makes "missing" representable without
stealing a value from the domain, so these assertions pin the bit layout, the
polarity, and the counting — a drift in any of them silently changes which rows an
aggregation sees.
"""
from columnar.dtype import (
    DTYPE_BOOL,
    DTYPE_FLOAT64,
    DTYPE_INT64,
    DTYPE_INVALID,
    DTYPE_NULL,
    DTYPE_STRING,
    byte_width,
    can_promote,
    dtype_from_name,
    dtype_name,
    is_fixed_width,
    is_numeric,
    promote,
    promotion_loses_precision,
)
from columnar.validity import (
    all_valid,
    any_null,
    bitmap_and,
    bitmap_or,
    bytes_for_bits,
    count_null,
    count_valid,
    is_valid,
    new_all_null,
    new_all_valid,
    set_null,
    set_valid,
    slice_bitmap,
)


fn main() raises:
    var passed = 0
    var failed = 0

    # ── byte sizing rounds up ────────────────────────────────────────────────
    if (
        bytes_for_bits(0) == 0
        and bytes_for_bits(1) == 1
        and bytes_for_bits(8) == 1
        and bytes_for_bits(9) == 2
        and bytes_for_bits(64) == 8
    ):
        passed += 1
        print("  ✅ bytes_for_bits rounds up at byte boundaries")
    else:
        failed += 1
        print("  ❌ sizing wrong:", bytes_for_bits(9))

    # ── a zeroed bitmap reads as all-null, not all-valid ─────────────────────
    # Polarity matters: allocate-and-forget must yield "no data", never "every zero
    # is a real value".
    var fresh = new_all_null(10)
    if not is_valid(fresh, 0) and count_valid(fresh, 10) == 0 and count_null(fresh, 10) == 10:
        passed += 1
        print("  ✅ a fresh bitmap is all-null (set == present)")
    else:
        failed += 1
        print("  ❌ polarity wrong")

    var full = new_all_valid(10)
    if is_valid(full, 0) and is_valid(full, 9) and count_valid(full, 10) == 10:
        passed += 1
        print("  ✅ new_all_valid marks every slot present")
    else:
        failed += 1
        print("  ❌ all-valid wrong:", count_valid(full, 10))

    # ── trailing bits past the logical length are never counted ──────────────
    # new_all_valid(10) sets 16 bits; only 10 are real.
    if count_valid(new_all_valid(10), 10) == 10 and count_valid(new_all_valid(3), 3) == 3:
        passed += 1
        print("  ✅ trailing bits in the final byte do not inflate the count")
    else:
        failed += 1
        print("  ❌ trailing bits counted:", count_valid(new_all_valid(3), 3))

    # ── individual set/clear, at a byte boundary and across one ──────────────
    var bm = new_all_null(20)
    set_valid(bm, 0)
    set_valid(bm, 7)
    set_valid(bm, 8)
    set_valid(bm, 19)
    if (
        is_valid(bm, 0)
        and is_valid(bm, 7)
        and is_valid(bm, 8)
        and is_valid(bm, 19)
        and not is_valid(bm, 1)
        and count_valid(bm, 20) == 4
    ):
        passed += 1
        print("  ✅ set_valid works across byte boundaries (7, 8) ")
    else:
        failed += 1
        print("  ❌ set/get wrong:", count_valid(bm, 20))

    set_null(bm, 7)
    if not is_valid(bm, 7) and is_valid(bm, 8) and count_valid(bm, 20) == 3:
        passed += 1
        print("  ✅ set_null clears one bit without disturbing its neighbour")
    else:
        failed += 1
        print("  ❌ set_null wrong")

    # ── out-of-range reads are absent, not a crash ──────────────────────────
    if not is_valid(bm, -1) and not is_valid(bm, 10_000):
        passed += 1
        print("  ✅ out-of-range indices read as absent")
    else:
        failed += 1
        print("  ❌ out-of-range not handled")

    # ── all_valid / any_null agree with the counts ──────────────────────────
    if (
        all_valid(new_all_valid(5), 5)
        and not all_valid(bm, 20)
        and any_null(bm, 20)
        and not any_null(new_all_valid(5), 5)
    ):
        passed += 1
        print("  ✅ all_valid / any_null match the counts")
    else:
        failed += 1
        print("  ❌ predicates disagree with counts")

    # ── slicing re-aligns so bit 0 is the slice's first slot ─────────────────
    var src = new_all_null(16)
    set_valid(src, 4)
    set_valid(src, 5)
    set_valid(src, 12)
    var sliced = slice_bitmap(src, 4, 4)  # slots 4..7 -> 0..3
    if (
        is_valid(sliced, 0)
        and is_valid(sliced, 1)
        and not is_valid(sliced, 2)
        and count_valid(sliced, 4) == 2
    ):
        passed += 1
        print("  ✅ slice_bitmap re-aligns to bit 0")
    else:
        failed += 1
        print("  ❌ slice wrong:", count_valid(sliced, 4))

    # ── a slice crossing a byte boundary stays correct ───────────────────────
    var crossing = slice_bitmap(src, 5, 8)  # slots 5..12
    if is_valid(crossing, 0) and is_valid(crossing, 7) and count_valid(crossing, 8) == 2:
        passed += 1
        print("  ✅ a slice spanning a byte boundary keeps its bits")
    else:
        failed += 1
        print("  ❌ crossing slice wrong:", count_valid(crossing, 8))

    # ── AND is the validity of a binary op; OR the union ────────────────────
    var a = new_all_null(4)
    set_valid(a, 0)
    set_valid(a, 1)
    var b = new_all_null(4)
    set_valid(b, 1)
    set_valid(b, 2)
    var both = bitmap_and(a, b, 4)
    var either = bitmap_or(a, b, 4)
    if (
        count_valid(both, 4) == 1
        and is_valid(both, 1)
        and count_valid(either, 4) == 3
    ):
        passed += 1
        print("  ✅ bitmap_and gives the intersection, bitmap_or the union")
    else:
        failed += 1
        print("  ❌ combinators wrong:", count_valid(both, 4), count_valid(either, 4))

    # ── dtype names round-trip ──────────────────────────────────────────────
    if (
        dtype_from_name(dtype_name(DTYPE_FLOAT64)) == DTYPE_FLOAT64
        and dtype_from_name("int64") == DTYPE_INT64
        and dtype_from_name("nonsense") == DTYPE_INVALID
    ):
        passed += 1
        print("  ✅ dtype names round-trip; an unknown name is invalid")
    else:
        failed += 1
        print("  ❌ dtype naming wrong")

    # ── bool is NOT numeric, so it cannot be averaged by accident ────────────
    if (
        is_numeric(DTYPE_INT64)
        and is_numeric(DTYPE_FLOAT64)
        and not is_numeric(DTYPE_BOOL)
        and not is_numeric(DTYPE_STRING)
    ):
        passed += 1
        print("  ✅ bool is not numeric — averaging it requires an explicit cast")
    else:
        failed += 1
        print("  ❌ numeric classification wrong")

    # ── widths, and which types are fixed-width ─────────────────────────────
    if (
        byte_width(DTYPE_INT64) == 8
        and byte_width(DTYPE_FLOAT64) == 8
        and byte_width(DTYPE_BOOL) == 1
        and byte_width(DTYPE_STRING) == 0
        and is_fixed_width(DTYPE_INT64)
        and not is_fixed_width(DTYPE_STRING)
    ):
        passed += 1
        print("  ✅ fixed widths reported; string is variable-width")
    else:
        failed += 1
        print("  ❌ widths wrong")

    # ── promotion: null takes its counterpart, int+float widens ─────────────
    if (
        promote(DTYPE_NULL, DTYPE_INT64) == DTYPE_INT64
        and promote(DTYPE_FLOAT64, DTYPE_NULL) == DTYPE_FLOAT64
        and promote(DTYPE_INT64, DTYPE_FLOAT64) == DTYPE_FLOAT64
        and promote(DTYPE_INT64, DTYPE_INT64) == DTYPE_INT64
    ):
        passed += 1
        print("  ✅ null promotes to its counterpart; int64+float64 -> float64")
    else:
        failed += 1
        print("  ❌ promotion wrong")

    # ── nothing promotes across the string boundary ─────────────────────────
    if (
        promote(DTYPE_STRING, DTYPE_INT64) == DTYPE_INVALID
        and not can_promote(DTYPE_STRING, DTYPE_FLOAT64)
        and not can_promote(DTYPE_BOOL, DTYPE_INT64)
    ):
        passed += 1
        print("  ✅ string/bool do not silently promote to a number")
    else:
        failed += 1
        print("  ❌ an unsafe promotion was allowed")

    # ── precision loss is reported, not hidden ──────────────────────────────
    if (
        promotion_loses_precision(DTYPE_INT64, DTYPE_FLOAT64)
        and not promotion_loses_precision(DTYPE_INT64, DTYPE_INT64)
        and not promotion_loses_precision(DTYPE_NULL, DTYPE_INT64)
    ):
        passed += 1
        print("  ✅ int64->float64 is flagged as lossy so a caller can warn")
    else:
        failed += 1
        print("  ❌ precision-loss reporting wrong")

    print("  [columnar.validity] Passed:", passed, "Failed:", failed)
