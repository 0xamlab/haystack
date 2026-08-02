"""query.comoments_packed — grouped JOINT co-moments over a packed composite
key, for the correlation/R^2 shape none of this plane's existing scans reach.

The gap this fills
-------------------
`query.packedkey`'s dense per-band record is a stripe of `GroupAccumulator`s,
one per (aggregate, value column) — built for "reduce column j independently
for each of several j", which is what every H2O question except this one
needs. The H2O db-benchmark's q9 (`R^2(v1, v2) by id2, id4`) needs a single
group-level accumulator that reads v1 AND v2 from the SAME row together:
`sum(x*y)` is not separable into "reduce x" plus "reduce y". No existing
`_scan_shared`/`_scan_percol` variant in `coded_dense`, and no per-column
stripe in `packedkey`, can express that — hence a new scan shape, not a new
opcode on an old one.

The five sums and why they are enough
--------------------------------------
Per group: `n`, `sum_x`, `sum_y`, `sum_xy`, `sum_x2`, `sum_y2`. Pearson's r in
the raw-moment form:

    r = (n*sum_xy - sum_x*sum_y) / sqrt((n*sum_x2 - sum_x^2) * (n*sum_y2 - sum_y^2))

and this module reports r^2 directly, because that is H2O's actual q9 metric
(`pow(corr(v1, v2), 2)`), not the plain correlation the task's prose shorthand
says — confirmed against the h2oai/db-benchmark query text and against this
repo's own `run_baselines.py` docstring, which excludes q9 as "grouped corr".

Association, and why this module does not chase `coded_dense`'s bit-identity
------------------------------------------------------------------------------
The six accumulated sums are combined ACROSS WORKERS by plain addition — the
same non-Welford combination `group_sum_update` uses for every SUM in this
plane. That means, exactly as `query.aggregate`'s module header states for
every sum in the plane: bit-identical at a FIXED worker count, and differing
from a different worker count only by floating-point association, not by
magnitude. v1 is 1..5 and v2 is 1..15 — small integers, so there is no
catastrophic cancellation in `sum_x2`/`sum_y2`/`sum_xy` at 1e7 rows to worry
about, and the correctness crosscheck against DuckDB/Polars is by TOLERANCE
(their `corr()` and this module's r^2 are two different formulas over two
different summation orders), never by bit pattern — unlike the SUM/MEAN
engines this plane already ships, which are checked bit-for-bit against a
sibling Mojo engine computing the identical frozen primitive.

Degeneracy
----------
A group with fewer than 2 rows, or with zero variance in x or y (every row's
v1 identical, or every row's v2 identical), has no correlation — DuckDB's
`corr()` returns NULL in both cases. `present[g]` is False there and the
reported r^2 is 0.0, matching this plane's "absent, not a real-looking
zero" numeric.contract rule.

Bounds
------
Reuses `query.packedkey.probe_packed_domain`/`PackedDomain` unchanged: the
mixed-radix pack, its guard (`_packed_digit`), and its two safety ceilings
(`MAX_PACKED_SLOTS`, and this module's own byte budget below) are exactly
`packedkey`'s, because a composite key that is unsafe to pack for one
aggregate shape is unsafe to pack for this one too — there is no reason for
the two modules to disagree about what a valid domain is.
"""
from std.algorithm import parallelize
from std.math import sqrt
from std.sys import info

from columnar.array import Float64Array
from columnar.batch import RecordBatch
from query.aggregate import (
    CARDINALITY_PROBE_ROWS,
    GROUP_CODED_BAD_REQUEST,
    GROUP_CODED_KEY_NOT_A_CODE,
    GROUP_CODED_OK,
    _col_guard_flags,
    planned_workers,
)
from query.packedkey import (
    GROUP_PACKED_DOMAIN_TOO_LARGE,
    MAX_PACKED_WIDTH,
    PackedDomain,
    packed_status_name,
    probe_packed_domain,
    _packed_digit,
)

# ── status: continuing query's 330-339 block. 337 is topk_dense's. ──────────
comptime GROUP_COMOMENT_STATE_TOO_LARGE: Int = 338
"""`workers x slots x 6` payload floats, plus bookkeeping, would exceed
`COMOMENT_MAX_STATE_BYTES`."""

comptime COMOMENT_MAX_STATE_BYTES: Int = 64 << 20
"""64 MiB scratch budget, `topk_dense`'s. The record here is 6 Float64s
(48 B) per (band, slot) against `packedkey`'s worst case of `n_aggs x 64 B`
`GroupAccumulator`s — narrower per slot at any aggregate count above one, so
this ceiling reaches at least as far as `packedkey`'s at the H2O q9 shape
(10 000 slots, width 2)."""


fn comoment_status_name(status: Int) -> String:
    if status == GROUP_CODED_OK:
        return "ok"
    if status == GROUP_CODED_BAD_REQUEST:
        return "bad_request"
    if status == GROUP_CODED_KEY_NOT_A_CODE:
        return "key_not_a_code"
    if status == GROUP_PACKED_DOMAIN_TOO_LARGE:
        return "domain_too_large"
    if status == GROUP_COMOMENT_STATE_TOO_LARGE:
        return "state_too_large"
    return packed_status_name(status)


comptime COMOMENT_STRIDE: Int = 6
"""[count, sum_x, sum_y, sum_xy, sum_x2, sum_y2] per (band, slot)."""


fn comoment_state_bytes(slots: Int, workers: Int) -> Int:
    """Every byte `group_comoments_packed_parallel` allocates, worst case —
    rule 1c, all three arrays: the payload, the per-band first-appearance
    order list and the `seen` bitmap."""
    if slots <= 0 or workers <= 0:
        return 0
    var payload = workers * slots * COMOMENT_STRIDE * 8
    var order = workers * slots * 8
    var seen = workers * slots
    return payload + order + seen


fn comoment_route_ok(
    batch: RecordBatch, key_columns: List[Int], n_workers: Int
) -> PackedDomain:
    """`probe_packed_domain` plus this module's own byte ceiling — the
    single testable decision `group_comoments_packed_parallel` also makes."""
    var domain = probe_packed_domain(batch, key_columns, CARDINALITY_PROBE_ROWS)
    if not domain.valid():
        return domain^
    var bands = n_workers
    if bands < 1:
        bands = 1
    if comoment_state_bytes(domain.slots, bands) > COMOMENT_MAX_STATE_BYTES:
        return PackedDomain(GROUP_COMOMENT_STATE_TOO_LARGE)
    return domain^


struct ComomentGroupedResult(Copyable, Movable):
    """One packed key tuple's groups, each with n / r^2 from the joint (x, y)
    moments. `key_tuples` is flat, `key_width` wide per group — the
    `MultiGroupedResult` layout every multi-key engine in this plane uses."""

    var key_tuples: List[Float64]
    var key_width: Int
    var count: List[Float64]
    var r2: List[Float64]
    var present: List[Bool]
    var null_key_rows: Int

    fn __init__(
        out self,
        var key_tuples: List[Float64],
        key_width: Int,
        var count: List[Float64],
        var r2: List[Float64],
        var present: List[Bool],
        null_key_rows: Int,
    ):
        self.key_tuples = key_tuples^
        self.key_width = key_width
        self.count = count^
        self.r2 = r2^
        self.present = present^
        self.null_key_rows = null_key_rows

    fn n_groups(self) -> Int:
        if self.key_width <= 0:
            return 0
        return len(self.key_tuples) // self.key_width


fn _empty_comoments(width: Int) -> ComomentGroupedResult:
    return ComomentGroupedResult(
        List[Float64](), width, List[Float64](), List[Float64](), List[Bool](), 0
    )


struct CodedComomentResult(Copyable, Movable):
    var status: Int
    var result: ComomentGroupedResult

    fn __init__(out self, status: Int, var result: ComomentGroupedResult):
        self.status = status
        self.result = result^

    fn ok(self) -> Bool:
        return self.status == GROUP_CODED_OK


@always_inline
fn _r2_from_moments(
    n: Float64, sx: Float64, sy: Float64, sxy: Float64, sx2: Float64, sy2: Float64,
    mut r2: Float64, mut present: Bool,
):
    """Pearson r, squared, from the five raw moments, written into `r2`/
    `present` — absent (`r2=0.0, present=False`) when fewer than two rows or
    either side has zero variance (matching DuckDB's `corr()` returning NULL
    in both cases)."""
    if n < 2.0:
        r2 = 0.0
        present = False
        return
    var denx = n * sx2 - sx * sx
    var deny = n * sy2 - sy * sy
    if not (denx > 0.0) or not (deny > 0.0):
        # `not (x > 0.0)` catches NaN too (unordered), not merely `<= 0.0`.
        r2 = 0.0
        present = False
        return
    var num = n * sxy - sx * sy
    var r = num / sqrt(denx * deny)
    r2 = r * r
    present = True


fn group_comoments_packed(
    batch: RecordBatch, key_columns: List[Int], domain: PackedDomain,
    x_column: Int, y_column: Int,
) -> CodedComomentResult:
    """`group_comoments_packed_parallel`'s drop-in, at `planned_workers`'s
    count."""
    return group_comoments_packed_parallel(
        batch, key_columns, domain, x_column, y_column,
        planned_workers(batch.n_rows, info.num_physical_cores()),
    )


fn group_comoments_packed_parallel(
    batch: RecordBatch, key_columns: List[Int], domain: PackedDomain,
    x_column: Int, y_column: Int, n_workers: Int,
) -> CodedComomentResult:
    """Grouped `count`, `sum_x`, `sum_y`, `sum_xy`, `sum_x2`, `sum_y2` per
    packed key slot, reduced to r^2, in one pass reading x and y from the
    SAME row.

    Bands, first-appearance order and the guard ladder mirror
    `query.packedkey.group_by_packed_parallel` exactly (same `_packed_digit`,
    same "a key that is not a code refuses the WHOLE call" discipline, same
    band split) — the only change is the per-slot record's SHAPE, from an
    array of independent `GroupAccumulator`s to one joint 6-field record.
    """
    var width = len(key_columns)
    if width < 1 or width > MAX_PACKED_WIDTH:
        return CodedComomentResult(GROUP_CODED_BAD_REQUEST, _empty_comoments(width))
    if not domain.valid():
        var reason = domain.status
        if reason == GROUP_CODED_OK:
            reason = GROUP_PACKED_DOMAIN_TOO_LARGE
        return CodedComomentResult(reason, _empty_comoments(width))
    if domain.width != width:
        return CodedComomentResult(GROUP_CODED_BAD_REQUEST, _empty_comoments(width))

    var n_rows = batch.n_rows
    var slots = domain.slots

    var bands = n_workers
    if bands < 1:
        bands = 1
    if bands > n_rows:
        bands = n_rows
    if bands < 1:
        bands = 1
    if comoment_state_bytes(slots, bands) > COMOMENT_MAX_STATE_BYTES:
        return CodedComomentResult(GROUP_COMOMENT_STATE_TOO_LARGE, _empty_comoments(width))

    var key_cols = List[Float64Array]()
    for c in range(width):
        key_cols.append(batch.column(key_columns[c]))
    var x_col = batch.column(x_column)
    var y_col = batch.column(y_column)
    var value_cols_xy = List[Float64Array]()
    value_cols_xy.append(x_col.copy())
    value_cols_xy.append(y_col.copy())
    var vg = _col_guard_flags(value_cols_xy, n_rows)
    var x_has_nulls = vg[0]
    var y_has_nulls = vg[1]
    var key_null_flags = _col_guard_flags(key_cols, n_rows)
    var any_key_nulls = False
    for c in range(width):
        if key_null_flags[c]:
            any_key_nulls = True

    var payload = List[Float64](length=bands * slots * COMOMENT_STRIDE, fill=0.0)
    var payp = payload.unsafe_ptr()
    var seen = List[UInt8](length=bands * slots, fill=0)
    var seenp = seen.unsafe_ptr()
    var band_orders = List[List[Int]](capacity=bands)
    for _ in range(bands):
        band_orders.append(List[Int]())
    var op_ptr = band_orders.unsafe_ptr()
    var w_nulls = List[Int](length=bands, fill=0)
    var np_ptr = w_nulls.unsafe_ptr()
    var w_bad = List[Bool](length=bands, fill=False)
    var bp_ptr = w_bad.unsafe_ptr()

    var lo_f = domain.los.unsafe_ptr()
    var hi_f = domain.his.unsafe_ptr()
    var lo_i = domain.lo_ints.unsafe_ptr()
    var stride = domain.strides.unsafe_ptr()
    var band_rows = (n_rows + bands - 1) // bands
    var xp = x_col.values[].unsafe_ptr() + x_col.offset
    var yp = y_col.values[].unsafe_ptr() + y_col.offset

    @parameter
    fn comoment_worker(w: Int):
        var lo_row = w * band_rows
        var hi_row = lo_row + band_rows
        if hi_row > n_rows:
            hi_row = n_rows
        var pbase_w = w * slots * COMOMENT_STRIDE
        var ebase_w = w * slots
        if lo_row >= hi_row:
            return

        var kps = List[UnsafePointer[Float64, origin=MutAnyOrigin]](capacity=width)
        for c in range(width):
            kps.append(key_cols[c].values[].unsafe_ptr() + key_cols[c].offset)
        var kp = kps.unsafe_ptr()
        var nulls = 0
        var bad = False

        @parameter
        @always_inline
        fn commit(r: Int, slot: Int):
            if not (x_has_nulls and not x_col.is_valid_at(r)) and not (
                y_has_nulls and not y_col.is_valid_at(r)
            ):
                if seenp[ebase_w + slot] == 0:
                    seenp[ebase_w + slot] = 1
                    op_ptr[w].append(slot)
                var base = pbase_w + slot * COMOMENT_STRIDE
                var x = xp[r]
                var y = yp[r]
                payp[base] = payp[base] + 1.0
                payp[base + 1] = payp[base + 1] + x
                payp[base + 2] = payp[base + 2] + y
                payp[base + 3] = payp[base + 3] + x * y
                payp[base + 4] = payp[base + 4] + x * x
                payp[base + 5] = payp[base + 5] + y * y
            elif seenp[ebase_w + slot] == 0:
                # The key names a group even when this row's (x, y) pair is
                # incomplete — matching "a row whose value is null still
                # belongs to the group" elsewhere in this plane. The group
                # exists; this row simply moves no moment.
                seenp[ebase_w + slot] = 1
                op_ptr[w].append(slot)

        if not any_key_nulls and width == 1:
            var kp0 = kp[0]
            var lo0 = lo_f[0]
            var hi0 = hi_f[0]
            var li0 = lo_i[0]
            for r in range(lo_row, hi_row):
                var d0 = _packed_digit(kp0[r], lo0, hi0, li0)
                if d0 < 0:
                    bad = True
                    break
                commit(r, d0)
        elif not any_key_nulls and width == 2:
            var kp0 = kp[0]
            var kp1 = kp[1]
            var lo0 = lo_f[0]
            var hi0 = hi_f[0]
            var li0 = lo_i[0]
            var lo1 = lo_f[1]
            var hi1 = hi_f[1]
            var li1 = lo_i[1]
            var st1 = stride[1]
            for r in range(lo_row, hi_row):
                var d0 = _packed_digit(kp0[r], lo0, hi0, li0)
                var d1 = _packed_digit(kp1[r], lo1, hi1, li1)
                if d0 < 0 or d1 < 0:
                    bad = True
                    break
                commit(r, d0 + d1 * st1)
        else:
            for r in range(lo_row, hi_row):
                var null_key = False
                var slot = 0
                for c in range(width):
                    if any_key_nulls and not key_cols[c].is_valid_at(r):
                        null_key = True
                        break
                    var d = _packed_digit(kp[c][r], lo_f[c], hi_f[c], lo_i[c])
                    if d < 0:
                        bad = True
                        break
                    slot += d * stride[c]
                if bad:
                    break
                if null_key:
                    nulls += 1
                    continue
                commit(r, slot)
        bp_ptr[w] = bad
        np_ptr[w] = nulls

    parallelize[comoment_worker](bands)

    for w in range(bands):
        if w_bad[w]:
            return CodedComomentResult(GROUP_CODED_KEY_NOT_A_CODE, _empty_comoments(width))

    var slot_to_group = List[Int](length=slots, fill=-1)
    var g_order = List[Int]()
    var null_key_rows = 0
    for w in range(bands):
        null_key_rows += w_nulls[w]
        for i in range(len(band_orders[w])):
            var slot = band_orders[w][i]
            if slot_to_group[slot] < 0:
                slot_to_group[slot] = len(g_order)
                g_order.append(slot)

    var n_groups = len(g_order)
    var key_tuples = List[Float64](capacity=n_groups * width)
    var counts_out = List[Float64](capacity=n_groups)
    var r2_out = List[Float64](capacity=n_groups)
    var present_out = List[Bool](capacity=n_groups)
    for g in range(n_groups):
        var slot = g_order[g]
        for c in range(width):
            var digit = (slot // domain.strides[c]) % domain.spans[c]
            key_tuples.append(Float64(domain.lo_ints[c] + digit))
        var n: Float64 = 0.0
        var sx: Float64 = 0.0
        var sy: Float64 = 0.0
        var sxy: Float64 = 0.0
        var sx2: Float64 = 0.0
        var sy2: Float64 = 0.0
        for w in range(bands):
            var base = w * slots * COMOMENT_STRIDE + slot * COMOMENT_STRIDE
            n += payload[base]
            sx += payload[base + 1]
            sy += payload[base + 2]
            sxy += payload[base + 3]
            sx2 += payload[base + 4]
            sy2 += payload[base + 5]
        counts_out.append(n)
        var r2: Float64 = 0.0
        var present: Bool = False
        _r2_from_moments(n, sx, sy, sxy, sx2, sy2, r2, present)
        r2_out.append(r2)
        present_out.append(present)

    return CodedComomentResult(
        GROUP_CODED_OK,
        ComomentGroupedResult(
            key_tuples^, width, counts_out^, r2_out^, present_out^, null_key_rows,
        ),
    )
