"""test_columnar_array.mojo — known-value tests for typed nullable columns.

Hand-written. The load-bearing properties: a null and a real zero stay
distinguishable, a slice shares values without copying them, and reductions over a
column agree with the same data passed directly to numeric.reduce.
"""
from columnar.array import (
    BoolArray,
    Float64Array,
    Int64Array,
    bool_from_list,
    describe,
    float64_from_list,
    float64_with_nulls,
    int64_from_list,
    string_from_list,
)
from columnar.dtype import DTYPE_FLOAT64, DTYPE_INT64, DTYPE_STRING
from numeric.reduce import reduce_mean, reduce_sum


fn _floats(a: Float64, b: Float64, c: Float64, d: Float64) -> List[Float64]:
    var out = List[Float64]()
    out.append(a)
    out.append(b)
    out.append(c)
    out.append(d)
    return out^


fn main() raises:
    var passed = 0
    var failed = 0

    # ── a no-nulls column reads back exactly ─────────────────────────────────
    var col = float64_from_list(_floats(1.0, 2.0, 3.0, 4.0))
    if (
        col.length == 4
        and col.get(0) == 1.0
        and col.get(3) == 4.0
        and col.null_count() == 0
        and col.dtype() == DTYPE_FLOAT64
    ):
        passed += 1
        print("  ✅ a dense Float64 column reads back exactly")
    else:
        failed += 1
        print("  ❌ dense column wrong")

    # ── a real 0.0 is present; a null is not — the whole point of validity ───
    var mask = List[Bool]()
    mask.append(True)   # 0.0, genuinely zero
    mask.append(False)  # null, stored as 0.0 too
    mask.append(True)
    mask.append(True)
    var mixed = float64_with_nulls(_floats(0.0, 0.0, 5.0, 7.0), mask)
    if (
        mixed.is_valid_at(0)
        and mixed.get(0) == 0.0
        and not mixed.is_valid_at(1)
        and mixed.get(1) == 0.0
        and mixed.null_count() == 1
        and mixed.valid_count() == 3
    ):
        passed += 1
        print("  ✅ a real 0.0 and a null both read 0.0 but differ in validity")
    else:
        failed += 1
        print("  ❌ null/zero conflated:", mixed.null_count())

    # ── out-of-range is absent, not a crash ─────────────────────────────────
    if not col.is_valid_at(-1) and not col.is_valid_at(99) and col.get(99) == 0.0:
        passed += 1
        print("  ✅ out-of-range reads are absent")
    else:
        failed += 1
        print("  ❌ bounds handling wrong")

    # ── slicing is a window, and it does not copy the values ─────────────────
    var window = col.slice(1, 2)
    if (
        window.length == 2
        and window.get(0) == 2.0
        and window.get(1) == 3.0
        and window.offset == 1
        # The slice's backing buffer is the FULL column's buffer, not a 2-element
        # copy — that is what makes a window O(1) in rows rather than O(window).
        and len(window.values[]) == 4
        and len(col.values[]) == 4
    ):
        passed += 1
        print("  ✅ slice(1,2) is a window over the shared values, offset 1")
    else:
        failed += 1
        print("  ❌ slice wrong:", window.length, window.offset)

    # ── slice bounds clamp instead of raising ────────────────────────────────
    if (
        col.slice(3, 99).length == 1
        and col.slice(99, 1).length == 0
        and col.slice(-5, 2).length == 2
        and col.slice(0, -1).length == 0
    ):
        passed += 1
        print("  ✅ out-of-range slices clamp to an empty or partial window")
    else:
        failed += 1
        print("  ❌ slice clamping wrong:", col.slice(3, 99).length, col.slice(99, 1).length)

    # ── a slice carries its own validity, re-aligned ─────────────────────────
    var null_window = mixed.slice(1, 2)  # slots 1 (null) and 2 (valid)
    if (
        not null_window.is_valid_at(0)
        and null_window.is_valid_at(1)
        and null_window.get(1) == 5.0
        and null_window.null_count() == 1
    ):
        passed += 1
        print("  ✅ a slice's validity is re-aligned to its own index 0")
    else:
        failed += 1
        print("  ❌ sliced validity wrong")

    # ── a column reduces the same as the raw data via numeric.reduce ──────────
    var vals = mixed.values_list()
    var msk = mixed.mask_list()
    var summed = reduce_sum(vals, msk)
    var averaged = reduce_mean(vals, msk)
    # Live values are 0.0, 5.0, 7.0 -> sum 12, mean 4.
    if summed.value == 12.0 and averaged.present and averaged.value == 4.0 and averaged.n == 3:
        passed += 1
        print("  ✅ column reduces to sum 12 / mean 4 over its three live values")
    else:
        failed += 1
        print("  ❌ reduction over a column wrong:", summed.value, averaged.value)

    # ── an all-null column has no mean ──────────────────────────────────────
    var none_mask = List[Bool]()
    for _ in range(4):
        none_mask.append(False)
    var all_null = float64_with_nulls(_floats(1.0, 2.0, 3.0, 4.0), none_mask)
    if all_null.valid_count() == 0 and not reduce_mean(
        all_null.values_list(), all_null.mask_list()
    ).present:
        passed += 1
        print("  ✅ an all-null column has no mean, rather than 0.0")
    else:
        failed += 1
        print("  ❌ all-null column wrong")

    # ── Int64 stays exact where Float64 would not ───────────────────────────
    var big = List[Int]()
    big.append(9007199254740993)  # 2^53 + 1: not representable as Float64
    var ints = int64_from_list(big^)
    if ints.dtype() == DTYPE_INT64 and ints.get(0) == 9007199254740993:
        passed += 1
        print("  ✅ Int64 keeps 2^53+1 exactly (a Float64 column could not)")
    else:
        failed += 1
        print("  ❌ Int64 precision lost:", ints.get(0))

    # ── widening is available but explicit ──────────────────────────────────
    var small = List[Int]()
    small.append(3)
    small.append(4)
    var widened = int64_from_list(small^).to_float64()
    if widened.dtype() == DTYPE_FLOAT64 and widened.get(0) == 3.0 and widened.length == 2:
        passed += 1
        print("  ✅ to_float64 widens explicitly, preserving values and length")
    else:
        failed += 1
        print("  ❌ widening wrong")

    # ── int64-columnar-fidelity: the documented floor, proven at the exact pair ──
    # `to_float64`'s own docstring already says this is lossy above 2^53; this proves
    # it AT the specific pair the bug report named, so the floor is not merely
    # asserted, it is measured. Two DISTINCT Int64 values collapse to ONE Float64 bit
    # pattern: `9007199254740992` (2^53) and `9007199254740993` (2^53+1) both round to
    # the same double, because a double's mantissa holds only 53 bits of integer
    # precision. This is inherent to Float64 and not something `to_float64` can fix —
    # it is exactly the reason `group_by_int64` (query.aggregate) exists: a caller
    # that needs both of these to stay distinct through a group-by must never route
    # them through this function.
    var pair = List[Int]()
    pair.append(9007199254740992)  # 2^53
    pair.append(9007199254740993)  # 2^53 + 1
    var pair_widened = int64_from_list(pair^).to_float64()
    if (
        pair_widened.get(0) == pair_widened.get(1)
        and pair_widened.get(0) == 9007199254740992.0
    ):
        passed += 1
        print("  ✅ to_float64(2^53) and to_float64(2^53+1) collide — the documented floor, measured")
    else:
        failed += 1
        print("  ❌ 2^53 and 2^53+1 did not collide under to_float64 — floor claim is stale:", pair_widened.get(0), pair_widened.get(1))

    # ── ...and Int64Array itself never loses that distinction ────────────────────
    # The corruption is strictly downstream of the WIDEN, not the storage: read back
    # from the Int64Array directly (no to_float64 in the path) and the two values are
    # still exact and still distinct.
    var pair2 = List[Int]()
    pair2.append(9007199254740992)
    pair2.append(9007199254740993)
    var pair_ints = int64_from_list(pair2^)
    if (
        pair_ints.get(0) == 9007199254740992
        and pair_ints.get(1) == 9007199254740993
        and pair_ints.get(0) != pair_ints.get(1)
    ):
        passed += 1
        print("  ✅ Int64Array keeps 2^53 and 2^53+1 exact and distinct — the fidelity to preserve downstream")
    else:
        failed += 1
        print("  ❌ Int64Array itself lost the distinction:", pair_ints.get(0), pair_ints.get(1))

    # ── a bool column distinguishes false from unknown ──────────────────────
    var flags = List[Bool]()
    flags.append(True)
    flags.append(False)
    flags.append(True)
    var bools = bool_from_list(flags^)
    if bools.true_count() == 2 and bools.get(1) == False and bools.is_valid_at(1):
        passed += 1
        print("  ✅ present-false counts as known-false, not unknown")
    else:
        failed += 1
        print("  ❌ bool column wrong:", bools.true_count())

    # ── an empty string is a value, not an absence ──────────────────────────
    var names = List[String]()
    names.append("")
    names.append("beta")
    var strings = string_from_list(names^)
    if (
        strings.dtype() == DTYPE_STRING
        and strings.is_valid_at(0)
        and strings.get(0) == ""
        and strings.get(1) == "beta"
        and strings.null_count() == 0
    ):
        passed += 1
        print("  ✅ an empty string is present, distinct from a null")
    else:
        failed += 1
        print("  ❌ string column wrong")

    # ── describe is usable in an error message ──────────────────────────────
    if describe(DTYPE_FLOAT64, 4, 1) == "float64[4] nulls=1" and describe(
        DTYPE_INT64, 2, 0
    ) == "int64[2]":
        passed += 1
        print("  ✅ describe reads cleanly, omitting a zero null count")
    else:
        failed += 1
        print("  ❌ describe wrong:", describe(DTYPE_FLOAT64, 4, 1))

    print("  [columnar.array] Passed:", passed, "Failed:", failed)
