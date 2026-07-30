"""test_columnar_hash_index.mojo — known-value tests for group-slot lookup.

Hand-written. The assertions concentrate on the failures that are silent: a key that
hashes to one slot but compares equal to another, two distinct composite keys merged
by a hash collision, and a resize that loses entries. All three produce a plausible
wrong aggregate rather than an error, so none of them would be caught by a test that
only checked that lookups mostly work.
"""
from std.math import isnan, sqrt
from std.memory import bitcast

from columnar.hash_index import (
    CANONICAL_NAN_BITS,
    CompositeKeyIndex,
    HashIndex,
    hash_bits,
    hash_float,
    hash_indices,
    hash_row,
    normalize_bits,
    row_indices,
)


fn _nan() -> Float64:
    """A NaN produced arithmetically, so it is not a literal the compiler folded."""
    return sqrt(-1.0)


fn main() raises:
    var passed = 0
    var failed = 0

    # ── -0.0 and +0.0 are the same group ──────────────────────────────────────
    # They compare equal under `==` but have different bit patterns. Hashing the raw
    # bits would file them separately while equality said they were the same, so which
    # group a zero landed in would depend on how the zero was produced.
    if normalize_bits(-0.0) == normalize_bits(0.0) and hash_float(-0.0) == hash_float(
        0.0
    ):
        passed += 1
        print("  ✅ -0.0 and +0.0 normalize to the same key")
    else:
        failed += 1
        print("  ❌ -0.0 and +0.0 hash differently")

    var zero_index = HashIndex(8)
    var slot_pos = zero_index.get_or_assign(0.0, 0)
    var slot_neg = zero_index.get_or_assign(-0.0, 1)
    if slot_pos == 0 and slot_neg == 0 and zero_index.size() == 1:
        passed += 1
        print("  ✅ -0.0 lands in the group +0.0 already opened, not a second one")
    else:
        failed += 1
        print("  ❌ -0.0 opened its own group:", slot_pos, slot_neg, zero_index.size())

    # ── every NaN is one group, not one group per row ─────────────────────────
    # NaN != NaN, so an un-normalized index opens a fresh group for every NaN row and
    # can never find any of them again — an unbounded group count from one bad column.
    var nan_index = HashIndex(8)
    var n1 = _nan()
    var n2 = _nan() * 2.0
    var first_nan = nan_index.get_or_assign(n1, 0)
    var second_nan = nan_index.get_or_assign(n2, 1)
    if (
        isnan(n1)
        and isnan(n2)
        and normalize_bits(n1) == CANONICAL_NAN_BITS
        and first_nan == 0
        and second_nan == 0
        and nan_index.size() == 1
    ):
        passed += 1
        print("  ✅ every NaN collapses to one group instead of one group per row")
    else:
        failed += 1
        print("  ❌ NaN keys multiplied:", nan_index.size())

    # ── ordinary keys get distinct slots, and lookups find them again ─────────
    var index = HashIndex(8)
    var assigned = List[Int]()
    for i in range(40):
        assigned.append(index.get_or_assign(Float64(i) * 1.5, len(assigned)))
    var all_distinct = True
    for i in range(len(assigned)):
        if assigned[i] != i:
            all_distinct = False
    if all_distinct and index.size() == 40:
        passed += 1
        print("  ✅ 40 distinct keys get 40 distinct slots in insertion order")
    else:
        failed += 1
        print("  ❌ slot assignment wrong, size =", index.size())

    # ── resize preserves every key ────────────────────────────────────────────
    # 40 keys into a capacity-8 table forces several doublings. A rehash that walks a
    # different probe sequence than insert did drops keys, and the aggregate then
    # reopens them as new groups — a split total with no error anywhere.
    var all_found = True
    for i in range(40):
        if index.find(Float64(i) * 1.5) != i:
            all_found = False
    if all_found and index.capacity() > 8:
        passed += 1
        print(
            "  ✅ all 40 keys survive the resizes to capacity",
            index.capacity(),
        )
    else:
        failed += 1
        print("  ❌ keys lost across resize")

    # ── an absent key is -1, never a slot ─────────────────────────────────────
    if index.find(999.25) == -1 and not index.contains(999.25):
        passed += 1
        print("  ✅ an absent key reports -1 rather than an occupied slot")
    else:
        failed += 1
        print("  ❌ absent key resolved to a slot")

    # ── the load factor actually triggers growth ──────────────────────────────
    var growing = HashIndex(4)
    var start_capacity = growing.capacity()
    for i in range(100):
        var _s = growing.get_or_assign(Float64(i), i)
    if growing.capacity() > start_capacity and growing.size() == 100:
        passed += 1
        print(
            "  ✅ capacity grew",
            start_capacity,
            "->",
            growing.capacity(),
            "holding 100 keys",
        )
    else:
        failed += 1
        print("  ❌ table did not grow:", growing.capacity())

    # ── hash_bits is a pure function of the bits ──────────────────────────────
    if hash_bits(normalize_bits(3.25)) == hash_float(3.25) and hash_float(
        3.25
    ) != hash_float(3.26):
        passed += 1
        print("  ✅ hash_float agrees with hash_bits and separates near neighbours")
    else:
        failed += 1
        print("  ❌ hash_float/hash_bits disagree")

    # ── composite keys: distinct tuples stay distinct ─────────────────────────
    # (1,2) and (2,1) are different groups. An index that folded the columns with an
    # order-independent combiner (xor, add) would merge them.
    var composite = CompositeKeyIndex(2, 8)
    var key_ab = List[Float64]()
    key_ab.append(1.0)
    key_ab.append(2.0)
    var key_ba = List[Float64]()
    key_ba.append(2.0)
    key_ba.append(1.0)
    var slot_ab = composite.get_or_assign(key_ab, 0)
    var slot_ba = composite.get_or_assign(key_ba, 1)
    if slot_ab == 0 and slot_ba == 1 and composite.size() == 2:
        passed += 1
        print("  ✅ (1,2) and (2,1) are different groups — the fold is order-aware")
    else:
        failed += 1
        print("  ❌ composite keys merged:", slot_ab, slot_ba)

    # ── the same tuple resolves to the same slot ──────────────────────────────
    var key_ab_again = List[Float64]()
    key_ab_again.append(1.0)
    key_ab_again.append(2.0)
    if composite.get_or_assign(key_ab_again, 99) == 0 and composite.find(
        key_ab_again
    ) == 0:
        passed += 1
        print("  ✅ re-presenting a tuple returns its existing slot, not a new one")
    else:
        failed += 1
        print("  ❌ the same tuple got a second slot")

    # ── the stored key tuple is recoverable ──────────────────────────────────
    var recovered = composite.key_at(1)
    if len(recovered) == 2 and recovered[0] == 2.0 and recovered[1] == 1.0:
        passed += 1
        print("  ✅ key_at recovers the tuple a slot was opened with")
    else:
        failed += 1
        print("  ❌ key_at wrong:", len(recovered))

    # ── composite resize preserves every tuple ───────────────────────────────
    var wide = CompositeKeyIndex(3, 4)
    for i in range(60):
        var k = List[Float64]()
        k.append(Float64(i))
        k.append(Float64(i * 2))
        k.append(Float64(i % 7))
        var _s = wide.get_or_assign(k, i)
    var wide_ok = True
    for i in range(60):
        var k = List[Float64]()
        k.append(Float64(i))
        k.append(Float64(i * 2))
        k.append(Float64(i % 7))
        if wide.find(k) != i:
            wide_ok = False
    if wide_ok and wide.size() == 60:
        passed += 1
        print("  ✅ 60 three-column tuples survive the composite resizes")
    else:
        failed += 1
        print("  ❌ composite resize lost tuples")

    # ── an absent tuple is -1 ────────────────────────────────────────────────
    var missing = List[Float64]()
    missing.append(-1.0)
    missing.append(-1.0)
    missing.append(-1.0)
    if wide.find(missing) == -1:
        passed += 1
        print("  ✅ an absent tuple reports -1")
    else:
        failed += 1
        print("  ❌ absent tuple resolved to a slot")

    # ── hash_indices folds the requested positions, in order ──────────────────
    var flat = List[Float64]()
    flat.append(1.0)
    flat.append(2.0)
    flat.append(3.0)
    var cols_01 = List[Int]()
    cols_01.append(0)
    cols_01.append(1)
    var cols_10 = List[Int]()
    cols_10.append(1)
    cols_10.append(0)
    var cols_02 = List[Int]()
    cols_02.append(0)
    cols_02.append(2)
    if (
        hash_indices(flat, cols_01) != hash_indices(flat, cols_10)
        and hash_indices(flat, cols_01) != hash_indices(flat, cols_02)
        and hash_indices(flat, cols_01) == hash_indices(flat, cols_01)
    ):
        passed += 1
        print("  ✅ hash_indices is order-sensitive, position-sensitive, deterministic")
    else:
        failed += 1
        print("  ❌ hash_indices wrong")

    # ── out-of-range indices are skipped, not read ───────────────────────────
    # Reading past the end of a List is an uncatchable crash, so skipping is the only
    # safe option; the assertion is that a bad index contributes NOTHING rather than
    # contributing garbage.
    var bad_cols = List[Int]()
    bad_cols.append(0)
    bad_cols.append(99)
    bad_cols.append(-3)
    var only_first = List[Int]()
    only_first.append(0)
    if hash_indices(flat, bad_cols) == hash_indices(flat, only_first):
        passed += 1
        print("  ✅ out-of-range indices are skipped rather than read")
    else:
        failed += 1
        print("  ❌ an out-of-range index contributed to the hash")

    # ── row_indices does the column-major arithmetic, visibly ─────────────────
    # 3 rows, so column 0 occupies [0,1,2] and column 1 occupies [3,4,5].
    var two_cols = List[Int]()
    two_cols.append(0)
    two_cols.append(1)
    var row0 = row_indices(two_cols, 0, 3)
    var row2 = row_indices(two_cols, 2, 3)
    if (
        len(row0) == 2 and row0[0] == 0 and row0[1] == 3
        and len(row2) == 2 and row2[0] == 2 and row2[1] == 5
    ):
        passed += 1
        print("  ✅ row_indices maps (col, row) to col*n_rows + row")
    else:
        failed += 1
        print("  ❌ row_indices wrong")

    # ── a row out of range yields no indices, rather than reading elsewhere ───
    if (
        len(row_indices(two_cols, 3, 3)) == 0
        and len(row_indices(two_cols, -1, 3)) == 0
        and len(row_indices(two_cols, 0, 0)) == 0
    ):
        passed += 1
        print("  ✅ an out-of-range row yields no indices")
    else:
        failed += 1
        print("  ❌ out-of-range row produced indices")

    # ── hash_row ACTUALLY DEPENDS ON `row` now ────────────────────────────────
    # This is the regression that matters. The previous signature took a `row` and
    # never read it, so every call hashed row 0 whatever was asked for. The old test
    # only ever passed row 0, so it could not have caught it.
    var grid = List[Float64]()
    for i in range(6):
        grid.append(Float64(i))   # col 0 = [0,1,2], col 1 = [3,4,5]
    var h_row0 = hash_row(grid, two_cols, 0, 3)
    var h_row1 = hash_row(grid, two_cols, 1, 3)
    var h_row2 = hash_row(grid, two_cols, 2, 3)
    if h_row0 != h_row1 and h_row1 != h_row2 and h_row0 != h_row2:
        passed += 1
        print("  ✅ hash_row gives three different hashes for three different rows")
    else:
        failed += 1
        print("  ❌ hash_row ignores its row argument")

    # ── and it agrees with the explicit two-step form ─────────────────────────
    if hash_row(grid, two_cols, 1, 3) == hash_indices(
        grid, row_indices(two_cols, 1, 3)
    ):
        passed += 1
        print("  ✅ hash_row equals hash_indices(row_indices(...)) exactly")
    else:
        failed += 1
        print("  ❌ hash_row and the two-step form disagree")

    print("  [columnar.hash_index] Passed:", passed, "Failed:", failed)
