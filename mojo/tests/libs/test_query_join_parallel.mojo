"""test_query_join_parallel.mojo — bit-for-bit checks for the row-banded parallel
probe and gather added to `query.join` (2026-08, "Parallel probe and gather").

`test_query_join.mojo`'s known-value tests exercise every semantic edge case (NaN
keys, null keys, duplicate keys, unmatched rows, LEFT vs INNER) but at row counts far
below `JOIN_PROBE_PARALLEL_MIN_ROWS` / `JOIN_GATHER_PARALLEL_MIN_ROWS`, so none of
them ever touch the parallel code path — they only prove the serial path, which the
parallel path was never allowed to change anyway.

This file proves the OTHER half: at row counts comfortably past both thresholds, the
parallel probe (`_hash_join_probe_parallel`) and the parallel gather
(`_take_column_join`) are compared against their serial references — not "same row
count", not "same multiset" — ROW FOR ROW, index for index, at several worker counts
including non-power-of-two ones (3, 7) so a band boundary that doesn't land on a
round number is exercised too. It also re-runs every edge case the module's own
docstring calls load-bearing (NaN key, null key, duplicate key, unmatched row) at
this scale, because a bug that only shows up once a band boundary crosses a
duplicate-key chain or a NaN row would be invisible at the known-value suite's size.

The public `hash_join_indices`/`materialize` entry points are ALSO checked directly
at this scale (not just the private helpers), so the threshold dispatch inside
`_hash_join_probe` and `materialize` itself is proven end to end, not merely its
building blocks.

Parallel build (2026-08 follow-on)
-----------------------------------
The section below ("build-parallel checks") does the identical job for
`_build_right_index_parallel` (the radix-partitioned build) and its paired
`_hash_join_probe_serial_partitioned`/`_hash_join_probe_parallel_partitioned`: every
right-side shape here is at or above `JOIN_BUILD_PARALLEL_MIN_ROWS`, and every result
is compared — row for row, not row count, not multiset — against the plain serial
`_build_right_index` + `_hash_join_probe_serial` reference, at several worker counts.
The heavy-duplicate-key shape is the one that specifically exercises "duplicate keys
across different partitions must chain together correctly" (`_build_right_index_
parallel`'s own docstring): with `n_rows` an order of magnitude above the key
`modulus`, the same key is guaranteed to recur across many different worker BANDS
(contiguous row ranges), while radix-partitioning guarantees every occurrence lands in
the SAME partition regardless of which band it came from — this shape would silently
under-count matches (each partition-local chain missing the other bands' rows of the
same key) if that guarantee were ever violated. `hash_join_indices` itself is also
checked end to end with a right side above the build threshold, so the real dispatch
path — not just the private helpers — is proven, not merely its building blocks.
"""
from columnar.array import Float64Array, float64_with_nulls
from columnar.batch import RecordBatch, schema_of, take_column
from query.join import (
    JOIN_BUILD_PARALLEL_MIN_ROWS,
    JOIN_DIRECT_ADDRESS_MAX_DENSITY,
    JOIN_GATHER_PARALLEL_MIN_ROWS,
    JOIN_INNER,
    JOIN_LEFT,
    JOIN_PROBE_PARALLEL_MIN_ROWS,
    NO_ROW,
    _build_direct_address_table,
    _build_right_index,
    _build_right_index_parallel,
    _hash_join_probe_parallel,
    _hash_join_probe_parallel_clustered,
    _hash_join_probe_parallel_direct_address,
    _hash_join_probe_parallel_partitioned,
    _hash_join_probe_serial,
    _hash_join_probe_serial_direct_address,
    _hash_join_probe_serial_partitioned,
    _take_column_join,
    hash_join_indices,
    materialize,
)
from columnar.hash_index import HashIndex


def _batch1(var name: String, var values: List[Float64], var mask: List[Bool]) -> RecordBatch:
    var n = len(values)
    var cols = List[Float64Array]()
    cols.append(float64_with_nulls(values^, mask))
    var names = List[String]()
    names.append(name^)
    return RecordBatch(schema_of(names^), cols^, n)


def _w2(a: Int, b: Int) -> List[Int]:
    var out = List[Int]()
    out.append(a)
    out.append(b)
    return out^


def _w3(a: Int, b: Int, c: Int) -> List[Int]:
    var out = List[Int]()
    out.append(a)
    out.append(b)
    out.append(c)
    return out^


def _w4(a: Int, b: Int, c: Int, d: Int) -> List[Int]:
    var out = List[Int]()
    out.append(a)
    out.append(b)
    out.append(c)
    out.append(d)
    return out^


def _xorshift_next(state: UInt64) -> UInt64:
    var s = state
    s = s ^ (s << 13)
    s = s ^ (s >> 7)
    s = s ^ (s << 17)
    return s


def _shuffle(mut arr: List[Int], seed: Int):
    """Fisher-Yates, `_xorshift_next`-driven — the same shuffle shape
    `benchmarks/h2o_join/generate.py`'s `rng.shuffle` plays for `id3`, just without a
    numpy dependency here."""
    var state = UInt64(seed) + 1
    var n = len(arr)
    for i in range(n - 1, 0, -1):
        state = _xorshift_next(state)
        var j = Int(state % UInt64(i + 1))
        var tmp = arr[i]
        arr[i] = arr[j]
        arr[j] = tmp


def _shared_permutation(total: Int, seed: Int) -> List[Int]:
    """A permutation of `1..total` — the exact shape `benchmarks/h2o_join/generate.py`'s
    `split_xlr` draws `id3` from, which is what makes direct-addressing valid for it:
    every value in this range is distinct and present exactly once."""
    var perm = List[Int]()
    for i in range(1, total + 1):
        perm.append(i)
    _shuffle(perm, seed)
    return perm^


def _dense_left_batch(perm: List[Int], n: Int, seed: Int) -> RecordBatch:
    """`lhs_pool` in `split_xlr`'s own naming: `perm[0:n]` (the "common" + "left-only"
    slices, concatenated), reshuffled — matching `sample_all`'s behavior when
    `len(pool) == size`: a pure shuffle, no padding."""
    var lhs_pool = List[Int]()
    for i in range(n):
        lhs_pool.append(perm[i])
    _shuffle(lhs_pool, seed)
    var values = List[Float64]()
    var mask = List[Bool]()
    for i in range(len(lhs_pool)):
        values.append(Float64(lhs_pool[i]))
        mask.append(True)
    return _batch1("k", values^, mask^)


def _dense_left_batch_with_hazards(
    perm: List[Int], n: Int, seed: Int, nan_every: Int, null_every: Int
) -> RecordBatch:
    """`_dense_left_batch` with periodic NaN/null rows spliced in — proves the
    direct-address probe's unmatchable-key handling on a left column that is otherwise
    entirely within the dense-permutation shape."""
    var lhs_pool = List[Int]()
    for i in range(n):
        lhs_pool.append(perm[i])
    _shuffle(lhs_pool, seed)
    var values = List[Float64]()
    var mask = List[Bool]()
    var nan_value = Float64(0.0) / Float64(0.0)
    for i in range(len(lhs_pool)):
        if nan_every > 0 and i % nan_every == 0:
            values.append(nan_value)
            mask.append(True)
            continue
        if null_every > 0 and i % null_every == 0:
            values.append(0.0)
            mask.append(False)
            continue
        values.append(Float64(lhs_pool[i]))
        mask.append(True)
    return _batch1("k", values^, mask^)


def _dense_right_batch(perm: List[Int], n: Int, n_common: Int, total: Int, seed: Int) -> RecordBatch:
    """`rhs_pool` in `split_xlr`'s own naming: `perm[0:n_common]` ("common") concatenated
    with `perm[n:total]` ("right-only"), reshuffled — the build side that
    `_build_direct_address_table` must accept as a dense, unique-key span."""
    var rhs_pool = List[Int]()
    for i in range(n_common):
        rhs_pool.append(perm[i])
    for i in range(n, total):
        rhs_pool.append(perm[i])
    _shuffle(rhs_pool, seed)
    var values = List[Float64]()
    var mask = List[Bool]()
    for i in range(len(rhs_pool)):
        values.append(Float64(rhs_pool[i]))
        mask.append(True)
    return _batch1("k", values^, mask^)


def _sparse_range_right_batch(n_rows: Int) -> RecordBatch:
    """`n_rows - 1` contiguous keys plus one far outlier — a deliberately WIDE, SPARSE
    span (`JOIN_DIRECT_ADDRESS_MAX_DENSITY` must reject this) rather than a fixture
    that happens to be sparse by chance."""
    var values = List[Float64]()
    var mask = List[Bool]()
    for i in range(n_rows - 1):
        values.append(Float64(i))
        mask.append(True)
    values.append(Float64((n_rows - 1) * (JOIN_DIRECT_ADDRESS_MAX_DENSITY + 1)))
    mask.append(True)
    return _batch1("k", values^, mask^)


def _fractional_key_right_batch(n_rows: Int) -> RecordBatch:
    """`n_rows - 1` contiguous integer keys plus one fractional key —
    `_build_direct_address_table` must reject this, not round it to a slot."""
    var values = List[Float64]()
    var mask = List[Bool]()
    for i in range(n_rows - 1):
        values.append(Float64(i))
        mask.append(True)
    values.append(Float64(n_rows // 2) + 0.5)
    mask.append(True)
    return _batch1("k", values^, mask^)


def _left_batch(n_rows: Int, modulus: Int, nan_every: Int, null_every: Int, seed: Int) -> RecordBatch:
    """A left key column with real matches, misses, periodic NaN and periodic null.

    `nan_every`/`null_every` of 0 disables that hazard entirely (so a build-side
    fixture can skip both without a magic sentinel value)."""
    var values = List[Float64]()
    var mask = List[Bool]()
    var state = UInt64(seed) + 1
    var nan_value = Float64(0.0) / Float64(0.0)
    for i in range(n_rows):
        if nan_every > 0 and i % nan_every == 0:
            values.append(nan_value)
            mask.append(True)
            continue
        if null_every > 0 and i % null_every == 0:
            values.append(0.0)
            mask.append(False)
            continue
        state = _xorshift_next(state)
        values.append(Float64(Int(state % UInt64(modulus))))
        mask.append(True)
    return _batch1("k", values^, mask^)


def _right_batch(n_rows: Int, modulus: Int, seed: Int) -> RecordBatch:
    """A right key column with no hazards — the build side, whose own docstring
    already forbids inserting an unmatchable key, so this fixture does not test
    that path (the known-value suite already does, at small scale)."""
    var values = List[Float64]()
    var mask = List[Bool]()
    var state = UInt64(seed) + 1
    for i in range(n_rows):
        state = _xorshift_next(state)
        values.append(Float64(Int(state % UInt64(modulus))))
        mask.append(True)
    return _batch1("k", values^, mask^)


def _right_batch_with_hazards(n_rows: Int, modulus: Int, nan_every: Int, null_every: Int, seed: Int) -> RecordBatch:
    """A right (build-side) key column WITH periodic NaN and null rows — unlike
    `_right_batch` above, this exercises the parallel build's own unmatchable-key
    handling (null_keys counting, and never inserting an unmatchable key into any
    partition) at scale, not just the known-value suite's small-scale coverage of the
    plain serial build."""
    var values = List[Float64]()
    var mask = List[Bool]()
    var state = UInt64(seed) + 1
    var nan_value = Float64(0.0) / Float64(0.0)
    for i in range(n_rows):
        if nan_every > 0 and i % nan_every == 0:
            values.append(nan_value)
            mask.append(True)
            continue
        if null_every > 0 and i % null_every == 0:
            values.append(0.0)
            mask.append(False)
            continue
        state = _xorshift_next(state)
        values.append(Float64(Int(state % UInt64(modulus))))
        mask.append(True)
    return _batch1("k", values^, mask^)


def _results_equal(a_left: List[Int], a_right: List[Int], b_left: List[Int], b_right: List[Int]) -> Bool:
    if len(a_left) != len(b_left) or len(a_right) != len(b_right):
        return False
    for i in range(len(a_left)):
        if a_left[i] != b_left[i] or a_right[i] != b_right[i]:
            return False
    return True


def _check_probe_matches_serial(
    left: RecordBatch,
    right: RecordBatch,
    join_type: Int,
    workers: Int,
    mut passed: Int,
    mut failed: Int,
    label: String,
):
    var left_key = left.column(0)
    var right_key = right.column(0)
    var slot_of = HashIndex(64)
    var first_row = List[Int]()
    var next_row = List[Int]()
    _ = _build_right_index(right_key, right.n_rows, slot_of, first_row, next_row)

    var serial = _hash_join_probe_serial(
        left_key, left.n_rows, slot_of, first_row, next_row, join_type
    )
    var parallel = _hash_join_probe_parallel(
        left_key, left.n_rows, slot_of, first_row, next_row, join_type, workers
    )

    var same_len = serial.n_rows() == parallel.n_rows()
    var same_rows = same_len and _results_equal(
        serial.left_rows, serial.right_rows, parallel.left_rows, parallel.right_rows
    )
    var same_counters = (
        serial.left_unmatched == parallel.left_unmatched
        and serial.null_key_rows == parallel.null_key_rows
    )

    if same_rows and same_counters:
        passed += 1
        print(
            "  ✅",
            label,
            "workers=" + String(workers),
            "rows=" + String(serial.n_rows()),
        )
    else:
        failed += 1
        print(
            "  ❌",
            label,
            "workers=" + String(workers),
            "serial_rows=" + String(serial.n_rows()),
            "parallel_rows=" + String(parallel.n_rows()),
            "serial_unmatched=" + String(serial.left_unmatched),
            "parallel_unmatched=" + String(parallel.left_unmatched),
            "serial_null=" + String(serial.null_key_rows),
            "parallel_null=" + String(parallel.null_key_rows),
        )


def _check_build_matches_serial(
    left: RecordBatch,
    right: RecordBatch,
    join_type: Int,
    build_workers: Int,
    mut passed: Int,
    mut failed: Int,
    label: String,
):
    """The radix-partitioned parallel build (`_build_right_index_parallel`), probed
    both ways (serial-partitioned walk and parallel-partitioned scatter), compared
    ROW FOR ROW against the plain serial build (`_build_right_index`) probed with the
    plain serial walk (`_hash_join_probe_serial`) — the same reference every other
    check in this file uses. `right.n_rows` is the caller's responsibility to keep at
    or above `JOIN_BUILD_PARALLEL_MIN_ROWS`; this function does not gate on it, so a
    caller can also use it to probe right below the threshold if it chooses.
    """
    var left_key = left.column(0)
    var right_key = right.column(0)

    var slot_of = HashIndex(64)
    var ref_first_row = List[Int]()
    var ref_next_row = List[Int]()
    var ref_null_keys = _build_right_index(
        right_key, right.n_rows, slot_of, ref_first_row, ref_next_row
    )
    var reference = _hash_join_probe_serial(
        left_key, left.n_rows, slot_of, ref_first_row, ref_next_row, join_type
    )

    var tables = List[HashIndex]()
    var p_first_row = List[List[Int]]()
    var p_next_row = List[Int]()
    var build_ok = True
    var par_null_keys = _build_right_index_parallel(
        right_key, right.n_rows, build_workers, tables, p_first_row, p_next_row, build_ok
    )

    if not build_ok:
        failed += 1
        print("  ❌", label, "build_workers=" + String(build_workers), "build reported ok=False")
        return

    var got_serial = _hash_join_probe_serial_partitioned(
        left_key, left.n_rows, tables, p_first_row, p_next_row, join_type
    )
    var got_parallel = _hash_join_probe_parallel_partitioned(
        left_key, left.n_rows, tables, p_first_row, p_next_row, join_type, build_workers
    )

    var serial_ok = reference.n_rows() == got_serial.n_rows() and _results_equal(
        reference.left_rows, reference.right_rows, got_serial.left_rows, got_serial.right_rows
    ) and reference.left_unmatched == got_serial.left_unmatched and reference.null_key_rows == got_serial.null_key_rows

    var parallel_ok = reference.n_rows() == got_parallel.n_rows() and _results_equal(
        reference.left_rows, reference.right_rows, got_parallel.left_rows, got_parallel.right_rows
    ) and reference.left_unmatched == got_parallel.left_unmatched and reference.null_key_rows == got_parallel.null_key_rows

    var null_keys_ok = ref_null_keys == par_null_keys

    if serial_ok and parallel_ok and null_keys_ok:
        passed += 1
        print(
            "  ✅", label,
            "build_workers=" + String(build_workers),
            "right_rows=" + String(right.n_rows),
            "rows=" + String(reference.n_rows()),
        )
    else:
        failed += 1
        print(
            "  ❌", label,
            "build_workers=" + String(build_workers),
            "ref_rows=" + String(reference.n_rows()),
            "serial_partitioned_rows=" + String(got_serial.n_rows()),
            "parallel_partitioned_rows=" + String(got_parallel.n_rows()),
            "ref_null_keys=" + String(ref_null_keys),
            "par_null_keys=" + String(par_null_keys),
            "serial_ok=" + String(serial_ok),
            "parallel_ok=" + String(parallel_ok),
        )


def _check_clustered_probe_matches_serial(
    left: RecordBatch,
    right: RecordBatch,
    join_type: Int,
    build_workers: Int,
    mut passed: Int,
    mut failed: Int,
    label: String,
):
    """`_hash_join_probe_parallel_clustered` -- the partition-clustered probe, added
    to try to close H2O join q5's remaining DuckDB gap by keeping each partition's
    table repeatedly accessed instead of jumped between once per row -- pinned row
    for row against the same plain-serial reference every other check in this file
    uses. Reuses `_build_right_index_parallel`'s radix-partitioned build (the
    clustered probe's contract requires a partitioned build, same as the row-band
    partitioned probe it is an alternative to).
    """
    var left_key = left.column(0)
    var right_key = right.column(0)

    var slot_of = HashIndex(64)
    var ref_first_row = List[Int]()
    var ref_next_row = List[Int]()
    var ref_null_keys = _build_right_index(
        right_key, right.n_rows, slot_of, ref_first_row, ref_next_row
    )
    var reference = _hash_join_probe_serial(
        left_key, left.n_rows, slot_of, ref_first_row, ref_next_row, join_type
    )

    var tables = List[HashIndex]()
    var p_first_row = List[List[Int]]()
    var p_next_row = List[Int]()
    var build_ok = True
    var par_null_keys = _build_right_index_parallel(
        right_key, right.n_rows, build_workers, tables, p_first_row, p_next_row, build_ok
    )
    if not build_ok:
        failed += 1
        print("  ❌", label, "build_workers=" + String(build_workers), "build reported ok=False")
        return

    var got_clustered = _hash_join_probe_parallel_clustered(
        left_key, left.n_rows, tables, p_first_row, p_next_row, join_type, build_workers
    )

    var clustered_ok = reference.n_rows() == got_clustered.n_rows() and _results_equal(
        reference.left_rows, reference.right_rows, got_clustered.left_rows, got_clustered.right_rows
    ) and reference.left_unmatched == got_clustered.left_unmatched and reference.null_key_rows == got_clustered.null_key_rows

    var null_keys_ok = ref_null_keys == par_null_keys

    if clustered_ok and null_keys_ok:
        passed += 1
        print(
            "  ✅", label,
            "build_workers=" + String(build_workers),
            "right_rows=" + String(right.n_rows),
            "rows=" + String(reference.n_rows()),
        )
    else:
        failed += 1
        print(
            "  ❌", label,
            "build_workers=" + String(build_workers),
            "ref_rows=" + String(reference.n_rows()),
            "clustered_rows=" + String(got_clustered.n_rows()),
            "ref_null_keys=" + String(ref_null_keys),
            "par_null_keys=" + String(par_null_keys),
            "clustered_ok=" + String(clustered_ok),
        )


def _check_direct_address_matches_serial(
    left: RecordBatch,
    right: RecordBatch,
    join_type: Int,
    workers: Int,
    mut passed: Int,
    mut failed: Int,
    label: String,
):
    """`_build_direct_address_table` + both its probes -- the direct-addressing
    alternative to a hash table entirely, valid only for a dense-unique-integer key
    span -- pinned row for row against the same plain-serial reference every other
    check in this file uses. Asserts `build_ok` is True: the caller's fixture is
    constructed to BE the shape this path requires, so a False here is itself a
    failure, not a fallback to shrug off.
    """
    var left_key = left.column(0)
    var right_key = right.column(0)

    var slot_of = HashIndex(64)
    var ref_first_row = List[Int]()
    var ref_next_row = List[Int]()
    _ = _build_right_index(right_key, right.n_rows, slot_of, ref_first_row, ref_next_row)
    var reference = _hash_join_probe_serial(
        left_key, left.n_rows, slot_of, ref_first_row, ref_next_row, join_type
    )

    var table = List[Int]()
    var key_lo = 0
    var key_hi = 0
    var build_ok = True
    _ = _build_direct_address_table(
        right_key, right.n_rows, workers, table, key_lo, key_hi, build_ok
    )
    if not build_ok:
        failed += 1
        print(
            "  ❌", label, "workers=" + String(workers),
            "build reported ok=False (expected True on this shape)",
        )
        return

    var got_serial = _hash_join_probe_serial_direct_address(
        left_key, left.n_rows, table, key_lo, key_hi, join_type
    )
    var got_parallel = _hash_join_probe_parallel_direct_address(
        left_key, left.n_rows, table, key_lo, key_hi, join_type, workers
    )

    var serial_ok = reference.n_rows() == got_serial.n_rows() and _results_equal(
        reference.left_rows, reference.right_rows, got_serial.left_rows, got_serial.right_rows
    ) and reference.left_unmatched == got_serial.left_unmatched and reference.null_key_rows == got_serial.null_key_rows

    var parallel_ok = reference.n_rows() == got_parallel.n_rows() and _results_equal(
        reference.left_rows, reference.right_rows, got_parallel.left_rows, got_parallel.right_rows
    ) and reference.left_unmatched == got_parallel.left_unmatched and reference.null_key_rows == got_parallel.null_key_rows

    if serial_ok and parallel_ok:
        passed += 1
        print(
            "  ✅", label,
            "workers=" + String(workers),
            "right_rows=" + String(right.n_rows),
            "rows=" + String(reference.n_rows()),
        )
    else:
        failed += 1
        print(
            "  ❌", label,
            "workers=" + String(workers),
            "ref_rows=" + String(reference.n_rows()),
            "serial_da_rows=" + String(got_serial.n_rows()),
            "parallel_da_rows=" + String(got_parallel.n_rows()),
            "serial_ok=" + String(serial_ok),
            "parallel_ok=" + String(parallel_ok),
        )


def _check_direct_address_rejects_invalid_shape(
    right: RecordBatch,
    workers: Int,
    mut passed: Int,
    mut failed: Int,
    label: String,
):
    """Proves the guard rails actually reject what `_build_direct_address_table`'s own
    docstring says they must -- a fractional key, a duplicate key, or a span far wider
    than the row count -- rather than silently building a table this data does not
    support. The failure mode this exists to catch is `ok=True` on a shape that should
    have been refused, not the reverse.
    """
    var right_key = right.column(0)
    var table = List[Int]()
    var key_lo = 0
    var key_hi = 0
    var ok = True
    _ = _build_direct_address_table(right_key, right.n_rows, workers, table, key_lo, key_hi, ok)
    if not ok:
        passed += 1
        print("  ✅", label, "workers=" + String(workers), "correctly rejected (ok=False)")
    else:
        failed += 1
        print("  ❌", label, "workers=" + String(workers), "should have rejected but ok=True")


def _check_end_to_end_matches_serial(
    left: RecordBatch,
    right: RecordBatch,
    join_type: Int,
    mut passed: Int,
    mut failed: Int,
    label: String,
):
    """`hash_join_indices` itself (auto-dispatch) against the private serial walk —
    proves the threshold dispatch inside `_hash_join_probe`, not just the helper."""
    var left_key = left.column(0)
    var right_key = right.column(0)
    var slot_of = HashIndex(64)
    var first_row = List[Int]()
    var next_row = List[Int]()
    _ = _build_right_index(right_key, right.n_rows, slot_of, first_row, next_row)
    var serial = _hash_join_probe_serial(
        left_key, left.n_rows, slot_of, first_row, next_row, join_type
    )
    var dispatched = hash_join_indices(left, 0, right, 0, join_type)

    var same_rows = serial.n_rows() == dispatched.n_rows() and _results_equal(
        serial.left_rows, serial.right_rows, dispatched.left_rows, dispatched.right_rows
    )
    var same_counters = (
        serial.left_unmatched == dispatched.left_unmatched
        and serial.null_key_rows == dispatched.null_key_rows
    )
    if same_rows and same_counters:
        passed += 1
        print("  ✅", label, "rows=" + String(dispatched.n_rows()))
    else:
        failed += 1
        print(
            "  ❌", label,
            "serial_rows=" + String(serial.n_rows()),
            "dispatched_rows=" + String(dispatched.n_rows()),
        )


def _check_gather_matches_serial(
    source: Float64Array, indices: List[Int], mut passed: Int, mut failed: Int, label: String
):
    var serial = take_column(source, indices)
    var parallel = _take_column_join(source, indices)
    var ok = serial.length == parallel.length
    if ok:
        for i in range(serial.length):
            if serial.is_valid_at(i) != parallel.is_valid_at(i):
                ok = False
                break
            if serial.is_valid_at(i) and serial.get(i) != parallel.get(i):
                ok = False
                break
    if ok:
        passed += 1
        print("  ✅", label, "rows=" + String(serial.length))
    else:
        failed += 1
        print("  ❌", label, "mismatch at scale", serial.length, "vs", parallel.length)


def main() raises:
    var passed = 0
    var failed = 0

    print("  JOIN_PROBE_PARALLEL_MIN_ROWS =", JOIN_PROBE_PARALLEL_MIN_ROWS)
    print("  JOIN_GATHER_PARALLEL_MIN_ROWS =", JOIN_GATHER_PARALLEL_MIN_ROWS)

    var big_n = JOIN_PROBE_PARALLEL_MIN_ROWS + JOIN_PROBE_PARALLEL_MIN_ROWS // 2
    if big_n < 700_000:
        big_n = 700_000

    # ── shape 1: small build side (H2O q1's shape), no hazards ─────────────────
    var left1 = _left_batch(big_n, 1_000_000, 0, 0, 11)
    var right1 = _right_batch(10, 1_000_000, 12)
    var workers1 = _w4(2, 3, 7, 16)
    for wi in range(len(workers1)):
        var w = workers1[wi]
        _check_probe_matches_serial(
            left1, right1, JOIN_INNER, w, passed, failed,
            "small build side, INNER, no hazards",
        )
        _check_probe_matches_serial(
            left1, right1, JOIN_LEFT, w, passed, failed,
            "small build side, LEFT, no hazards",
        )

    # ── shape 2: medium build side with duplicate keys (H2O q2-4's shape) ──────
    var left2 = _left_batch(big_n, 10_000, 0, 0, 21)
    var right2 = _right_batch(10_000, 10_000, 22)
    var workers2 = _w3(2, 5, 16)
    for wi in range(len(workers2)):
        var w = workers2[wi]
        _check_probe_matches_serial(
            left2, right2, JOIN_INNER, w, passed, failed,
            "medium build side, INNER, duplicate keys",
        )
        _check_probe_matches_serial(
            left2, right2, JOIN_LEFT, w, passed, failed,
            "medium build side, LEFT, duplicate keys",
        )

    # ── shape 3: near-1:1 build side (H2O q5's shape) ───────────────────────────
    var left3 = _left_batch(big_n, big_n, 0, 0, 31)
    var right3 = _right_batch(big_n, big_n, 32)
    var workers3 = _w2(4, 16)
    for wi in range(len(workers3)):
        var w = workers3[wi]
        _check_probe_matches_serial(
            left3, right3, JOIN_INNER, w, passed, failed,
            "near-1:1 build side, INNER",
        )

    # ── shape 4: NaN keys AND null keys mixed in at scale, both join types ─────
    var left4 = _left_batch(big_n, 5_000, 97, 131, 41)
    var right4 = _right_batch(5_000, 5_000, 42)
    var workers4 = _w2(3, 16)
    for wi in range(len(workers4)):
        var w = workers4[wi]
        _check_probe_matches_serial(
            left4, right4, JOIN_INNER, w, passed, failed,
            "NaN + null keys at scale, INNER",
        )
        _check_probe_matches_serial(
            left4, right4, JOIN_LEFT, w, passed, failed,
            "NaN + null keys at scale, LEFT",
        )

    # ── shape 5: heavy duplicate-key chains (average chain length ~7) ──────────
    var left5 = _left_batch(big_n, 2_000, 0, 0, 51)
    var right5 = _right_batch(14_000, 2_000, 52)
    var workers5 = _w3(2, 9, 16)
    for wi in range(len(workers5)):
        var w = workers5[wi]
        _check_probe_matches_serial(
            left5, right5, JOIN_INNER, w, passed, failed,
            "heavy duplicate chains, INNER",
        )

    # ── end-to-end: hash_join_indices's OWN dispatch, at scale ──────────────────
    _check_end_to_end_matches_serial(
        left1, right1, JOIN_INNER, passed, failed, "hash_join_indices dispatch, small build"
    )
    _check_end_to_end_matches_serial(
        left1, right1, JOIN_LEFT, passed, failed, "hash_join_indices dispatch, small build, LEFT"
    )
    _check_end_to_end_matches_serial(
        left4, right4, JOIN_LEFT, passed, failed,
        "hash_join_indices dispatch, NaN + null keys, LEFT",
    )
    # right3 (near-1:1, big_n rows) is already at/above JOIN_BUILD_PARALLEL_MIN_ROWS,
    # so this is the one end-to-end check that actually exercises the NEW parallel
    # build inside `hash_join_indices`'s own dispatch, not just the small-build path
    # every check above this one takes.
    _check_end_to_end_matches_serial(
        left3, right3, JOIN_INNER, passed, failed,
        "hash_join_indices dispatch, near-1:1 build at/above JOIN_BUILD_PARALLEL_MIN_ROWS",
    )

    # ── build-parallel checks: `_build_right_index_parallel`'s radix-partitioned
    #    build, at and above JOIN_BUILD_PARALLEL_MIN_ROWS, compared row for row
    #    against the plain serial build — see the module docstring's "Parallel
    #    build" section. ──────────────────────────────────────────────────────────
    print("  JOIN_BUILD_PARALLEL_MIN_ROWS =", JOIN_BUILD_PARALLEL_MIN_ROWS)

    var build_n = JOIN_BUILD_PARALLEL_MIN_ROWS + JOIN_BUILD_PARALLEL_MIN_ROWS // 8
    var build_workers = _w4(2, 3, 7, 16)

    # near-1:1 build side (right3/left3, already >= JOIN_BUILD_PARALLEL_MIN_ROWS):
    # nearly every right row is its own distinct key, so almost no duplicate-key
    # chaining happens anywhere — the tier the diagnosis found build dominates on.
    for wi in range(len(build_workers)):
        var w = build_workers[wi]
        _check_build_matches_serial(
            left3, right3, JOIN_INNER, w, passed, failed,
            "build-parallel, near-1:1 (H2O q5 shape)",
        )
        _check_clustered_probe_matches_serial(
            left3, right3, JOIN_INNER, w, passed, failed,
            "build-parallel, near-1:1 (H2O q5 shape)",
        )
        _check_build_matches_serial(
            left3, right3, JOIN_LEFT, w, passed, failed,
            "build-parallel, near-1:1 (H2O q5 shape), LEFT",
        )
        _check_clustered_probe_matches_serial(
            left3, right3, JOIN_LEFT, w, passed, failed,
            "build-parallel, near-1:1 (H2O q5 shape), LEFT",
        )

    # heavy duplicate keys spread across the WHOLE row range: `modulus` is two
    # orders of magnitude below `build_n`, so the same key recurs across every
    # worker band by construction — this is what would silently under-count if
    # cross-partition duplicate chaining were ever wrong (see this fixture's own
    # note in the module docstring).
    var left6 = _left_batch(big_n, 20_000, 0, 0, 61)
    var right6 = _right_batch(build_n, 20_000, 62)
    for wi in range(len(build_workers)):
        var w = build_workers[wi]
        _check_build_matches_serial(
            left6, right6, JOIN_INNER, w, passed, failed,
            "build-parallel, heavy duplicate keys across bands",
        )
        _check_clustered_probe_matches_serial(
            left6, right6, JOIN_INNER, w, passed, failed,
            "build-parallel, heavy duplicate keys across bands",
        )
        _check_build_matches_serial(
            left6, right6, JOIN_LEFT, w, passed, failed,
            "build-parallel, heavy duplicate keys across bands, LEFT",
        )
        _check_clustered_probe_matches_serial(
            left6, right6, JOIN_LEFT, w, passed, failed,
            "build-parallel, heavy duplicate keys across bands, LEFT",
        )

    # NaN and null right-side rows at scale: never inserted into any partition,
    # counted correctly, and a left row that would have matched one is unmatched
    # like any other miss.
    var left7 = _left_batch(big_n, 20_000, 53, 67, 71)
    var right7 = _right_batch_with_hazards(build_n, 20_000, 97, 131, 72)
    for wi in range(len(build_workers)):
        var w = build_workers[wi]
        _check_build_matches_serial(
            left7, right7, JOIN_INNER, w, passed, failed,
            "build-parallel, NaN + null right rows at scale",
        )
        _check_clustered_probe_matches_serial(
            left7, right7, JOIN_INNER, w, passed, failed,
            "build-parallel, NaN + null right rows at scale",
        )
        _check_build_matches_serial(
            left7, right7, JOIN_LEFT, w, passed, failed,
            "build-parallel, NaN + null right rows at scale, LEFT",
        )
        _check_clustered_probe_matches_serial(
            left7, right7, JOIN_LEFT, w, passed, failed,
            "build-parallel, NaN + null right rows at scale, LEFT",
        )

    # a right side just BELOW the build threshold must still match — proves the
    # function itself is correct even when a caller uses it off the beaten path,
    # not merely when `hash_join_indices`'s own dispatch would pick it.
    var right8 = _right_batch(10_000, 3_000, 82)
    var left8 = _left_batch(big_n, 3_000, 0, 0, 81)
    _check_build_matches_serial(
        left8, right8, JOIN_INNER, 4, passed, failed,
        "build-parallel, below JOIN_BUILD_PARALLEL_MIN_ROWS (called directly)",
    )

    # ── direct-address checks: `_build_direct_address_table` and both its probes,
    #    the direct-addressing alternative to a hash table entirely for a dense-
    #    unique-integer key span (H2O join-track q5's actual `id3` shape) — see
    #    `benchmarks/h2o_join/RESULTS.md`'s Update #6. ──────────────────────────────
    print("  JOIN_DIRECT_ADDRESS_MAX_DENSITY =", JOIN_DIRECT_ADDRESS_MAX_DENSITY)

    var da_n = 2_000
    var da_total = (da_n * 11) // 10
    var da_common = (da_n * 9) // 10
    var da_perm = _shared_permutation(da_total, 91)
    var da_left = _dense_left_batch(da_perm, da_n, 92)
    var da_right = _dense_right_batch(da_perm, da_n, da_common, da_total, 93)
    var da_workers = _w3(2, 7, 16)
    for wi in range(len(da_workers)):
        var w = da_workers[wi]
        _check_direct_address_matches_serial(
            da_left, da_right, JOIN_INNER, w, passed, failed,
            "direct-address, dense unique id3-shaped keys, INNER",
        )
        _check_direct_address_matches_serial(
            da_left, da_right, JOIN_LEFT, w, passed, failed,
            "direct-address, dense unique id3-shaped keys, LEFT",
        )

    # same dense shape, but with periodic NaN/null spliced into the LEFT column —
    # proves the unmatchable-key branch on an otherwise-conforming build.
    var da_left_hazards = _dense_left_batch_with_hazards(da_perm, da_n, 94, 97, 131)
    _check_direct_address_matches_serial(
        da_left_hazards, da_right, JOIN_LEFT, 7, passed, failed,
        "direct-address, dense unique id3-shaped keys, NaN + null left rows, LEFT",
    )

    # guard rails: each of these must be REJECTED (ok=False), not silently accepted.
    _check_direct_address_rejects_invalid_shape(
        right2, 4, passed, failed,
        "direct-address correctly rejects a duplicate-key right side",
    )
    _check_direct_address_rejects_invalid_shape(
        _fractional_key_right_batch(1_000), 4, passed, failed,
        "direct-address correctly rejects a fractional-key right side",
    )
    _check_direct_address_rejects_invalid_shape(
        _sparse_range_right_batch(1_000), 4, passed, failed,
        "direct-address correctly rejects a sparse-range right side",
    )

    # ── gather: _take_column_join vs take_column, at and above the threshold ───
    var gather_n = JOIN_GATHER_PARALLEL_MIN_ROWS + JOIN_GATHER_PARALLEL_MIN_ROWS // 3
    var gather_source = _right_batch(gather_n, gather_n, 61)
    var gather_indices = List[Int]()
    var gstate = UInt64(7)
    for i in range(gather_n):
        gstate = _xorshift_next(gstate)
        var pick = Int(gstate % UInt64(gather_n + 200))
        # deliberately include some out-of-range indices (NO_ROW-shaped) so the
        # null-substitution branch runs under the parallel path too.
        if pick >= gather_n:
            gather_indices.append(NO_ROW)
        else:
            gather_indices.append(pick)
    _check_gather_matches_serial(
        gather_source.column(0), gather_indices, passed, failed,
        "parallel gather vs serial take_column, with NO_ROW mixed in",
    )

    # ── materialize end to end, at scale, both sides prefixed and gathered ──────
    var mat_result = hash_join_indices(left2, 0, right2, 0, JOIN_LEFT)
    var mat_batch = materialize(left2, right2, mat_result, "r_")
    var ref_left_col = take_column(left2.column(0), mat_result.left_rows)
    var ref_right_col = take_column(right2.column(0), mat_result.right_rows)
    var mat_ok = (
        mat_batch.n_rows == mat_result.n_rows()
        and mat_batch.width() == 2
        and mat_batch.schema.name_at(1) == "r_k"
    )
    if mat_ok:
        for i in range(mat_batch.n_rows):
            if mat_batch.columns[0].is_valid_at(i) != ref_left_col.is_valid_at(i):
                mat_ok = False
                break
            if mat_batch.columns[0].is_valid_at(i) and mat_batch.columns[0].get(i) != ref_left_col.get(i):
                mat_ok = False
                break
            if mat_batch.columns[1].is_valid_at(i) != ref_right_col.is_valid_at(i):
                mat_ok = False
                break
            if mat_batch.columns[1].is_valid_at(i) and mat_batch.columns[1].get(i) != ref_right_col.get(i):
                mat_ok = False
                break
    if mat_ok:
        passed += 1
        print("  ✅ materialize end-to-end at scale matches take_column column for column")
    else:
        failed += 1
        print("  ❌ materialize end-to-end mismatch at scale")

    print("  [query.join parallel] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("query.join parallel: " + String(failed) + " check(s) failed")
