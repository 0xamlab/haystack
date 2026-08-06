"""query.packedkey — composite key PACKING: several bounded integer key columns
folded into ONE dense index, so a multi-column grouping direct-indexes an
accumulator array instead of hashing a tuple per row.

The shape this exists for
-------------------------
`query.aggregate.group_by_coded` already retires the hash for ONE key column of
small dictionary codes. Nothing did that for a key TUPLE, and the tuple case is
where hashing costs the most: `CompositeKeyIndex` folds `width` doubles per row
into a hash, probes, and on a miss appends `width` floats to a key list. The
H2O db-benchmark's q2 (`sum(v1) by id1, id2`) is exactly this shape, and both
key columns hold 100 distinct codes — 10 000 combinations, an 80 KB dense array.

So: probe each key column's integral range once, build a mixed-radix place
value from the per-column spans, and the composite key becomes

    slot = sum over c of (code[c] - lo[c]) * stride[c]

with `stride[0] = 1` and `stride[c] = stride[c-1] * span[c-1]`. That is one
multiply-add per key column per row against a hash fold plus a probe — and the
accumulator lookup becomes an array index, which is the same trade
`group_by_coded` makes, generalized to width > 1.

Per-column LO offsets, not just an upper bound
----------------------------------------------
`probe_coded_bound` takes `max + 1` and implicitly `lo = 0`, which is right for
dictionary codes but wasteful for any other integer domain: two columns of
calendar years (2000..2025, 26 real values each) would need 2026 x 2026 = 4.1 M
slots at `lo = 0` and 676 at their own `lo`. Since a mixed-radix pack has to
carry a per-column stride anyway, carrying a per-column `lo` is free — and it
is the difference between this route being available and refused on a large
class of real keys. The cost is that the guard is now two-sided (a key BELOW
`lo` refuses, exactly as one at or above `hi` does).

Why a dense array can be WORSE, and where the line is
-----------------------------------------------------
The product of the spans, not the number of distinct tuples actually present,
sets the state size. Two 100-code columns is 10 000 slots; `id3` x `id4` at
this tier is 100 001 x 101 = 10.1 M slots, and at
`size_of[GroupAccumulator]()` = 64 bytes per (slot, aggregate) per BAND that is
hundreds of gigabytes of state for a question with at most 1e7 distinct
tuples. Two independent ceilings therefore gate the route, both checked BEFORE
any allocation (rule 1c: a per-item ceiling is not a bound on total
allocation):

  * `MAX_PACKED_SLOTS` bounds the product itself, and is checked
    incrementally during the stride fold so the product cannot overflow `Int`
    on the way to being rejected;
  * `MAX_PACKED_STATE_BYTES` bounds what actually gets allocated — ALL SIX
    arrays, not just the accumulators (`packed_state_bytes` states the
    arithmetic). Counting one array and calling it a bound is the rubber-stamp
    failure rule 1c exists to prevent; the accumulators are 91% of the total
    here, and the other 9% is real.

Above them the route REFUSES and the caller keeps its hash engine. There is a
third, softer line — `PACKED_ROUTE_MAX_SLOTS` — which is not about safety but
about being faster: the final merge walks each band's locally-seen slots, and
the `seen`/`slot_to_group` arrays are `slots` long per band, so a domain far
sparser than the tuples present pays for emptiness. That constant is measured,
not reasoned; see its docstring.

What it promises
----------------
Bit-for-bit what `group_by_many_banded` returns on the same batch at the same
worker count. Same bands (contiguous, `ceil(n_rows / workers)`), same
band-local first-appearance order, same global merge in ascending worker
index, same frozen `GroupAccumulator.observe_op` / `merge_from` primitives —
so the NaN policy ("a NaN contributes to no extremum and to no mean") and the
Welford mean arrive unchanged, because this module never reimplements them. It
changes only how a row finds its accumulator.

The guard is the whole safety argument
--------------------------------------
A packed slot is written with no bounds check, so every key column is range
checked in FLOAT domain first (`k >= lo` rejects NaN and -inf; `k < hi` rejects
+inf and oversized), then integrality (`Float64(Int(k)) == k`). A violation
sets the band's `bad` flag and BREAKS — it never `return`s out of the band,
because a band that returns early has silently dropped its tail and the call
would ship a wrong answer. The whole call then refuses with
`GROUP_CODED_KEY_NOT_A_CODE` and the caller falls back. This matters more here
than anywhere: an out-of-range packed index is an out-of-bounds write into
`UnsafePointer` memory, which is an UNCATCHABLE abort that takes the worker
process and every resident dataset with it.
"""
from std.algorithm import parallelize
from std.memory import UnsafePointer, alloc
from std.sys import info
from std.sys.info import size_of

from columnar.array import Float64Array
from columnar.batch import RecordBatch
from query.aggregate import (
    CARDINALITY_PROBE_ROWS,
    GROUP_CODED_BAD_REQUEST,
    GROUP_CODED_CARDINALITY_INVALID,
    GROUP_CODED_KEY_NOT_A_CODE,
    GROUP_CODED_OK,
    CodedGroupedResult,
    GroupAccumulator,
    ManyGroupedResult,
    _col_guard_flags,
    _empty_many,
    _many_request_ok,
    group_by_many_parallel,
    planned_workers,
)

# ── status: query owns 330-339. 330-333 are query.aggregate's, 334/335 are
#    query.coded_dense's, 336 is ours. 336 and NOT 334: this module and
#    coded_dense were written in parallel and both claimed 334, so composing
#    them made one number mean two different refusals to any caller that
#    switches on the status. The composed route resolves it here, at the
#    source, rather than by mapping in the router — a status vocabulary that is
#    ambiguous at the boundary is ambiguous, and `compose_status_name` in
#    `query.composed` is the single registry that now proves the block has no
#    duplicates.
comptime GROUP_PACKED_DOMAIN_TOO_LARGE: Int = 336
"""The key columns' integral spans multiply past `MAX_PACKED_SLOTS`, or the
resulting per-band state past `MAX_PACKED_STATE_BYTES`. Distinct from
`GROUP_CODED_CARDINALITY_INVALID`, which means the CALLER named a nonsense
cardinality: this one means the DATA's domain is too wide for a dense array, a
routing fact, not a caller bug."""


def packed_status_name(status: Int) -> String:
    """The vocabulary this module can return, including query.aggregate's."""
    if status == GROUP_CODED_OK:
        return "ok"
    if status == GROUP_CODED_CARDINALITY_INVALID:
        return "cardinality_invalid"
    if status == GROUP_CODED_KEY_NOT_A_CODE:
        return "key_not_a_code"
    if status == GROUP_CODED_BAD_REQUEST:
        return "bad_request"
    if status == GROUP_PACKED_DOMAIN_TOO_LARGE:
        return "domain_too_large"
    return "unknown"


comptime MAX_PACKED_WIDTH: Int = 8
"""Key columns per packed grouping.

Not a memory bound — `MAX_PACKED_SLOTS` is. This bounds the per-row inner loop
and the reconstruction loop, and 8 integer key columns whose spans multiply
under a million is already a narrow shape. Wider tuples keep the hash."""

comptime MAX_PACKED_SLOTS: Int = 1 << 20
"""Ceiling on the span PRODUCT — the dense array's length, per band.

1 048 576 slots is 73 MiB of per-band state at one aggregate (64 bytes of
accumulator plus 9 of bookkeeping per slot) and 1.17 GiB at 16 bands, which is
why `MAX_PACKED_STATE_BYTES` exists on top of it: this constant alone does NOT
bound what gets allocated, it only bounds one array's length. Checked
incrementally inside the stride fold, so a product that would overflow `Int` is
rejected before it is computed rather than after."""

comptime MAX_PACKED_STATE_BYTES: Int = 256 << 20
"""Ceiling on `bands x slots x n_aggs x size_of[GroupAccumulator]()` — the
actual allocation, which is the number rule 1c says to bound, and the ceiling
that actually binds this route's reach.

Half the 512 MiB single-object resident ceiling, for scratch that is freed
before the call returns. `packed_state_bytes` states the full arithmetic; the
shapes it admits and refuses, at width 2 and 16 bands:

  * H2O q2 (10 000 slots, 1 aggregate): 12.0 MiB — in.
  * H2O q2 with 3 aggregates: 34.4 MiB — in.
  * the largest 1-aggregate product that fits: 213 722 slots — so the routing
    line at 131 072 is reachable and 262 144 is not.
  * id1 x id2 x id4 (1e6 slots), 1 aggregate: 1.20 GiB — REFUSED, and
    correctly: 1e6 dense slots for at most 1e6 present tuples is an array the
    size of the answer, which is exactly where hashing wins.

The 64-byte accumulator sets that reach, so a narrower record would extend it —
but note the counterfactual measured here refutes the speed half of that idea:
at one aggregate a packed 16-byte (count, total) record and a two-array
struct-of-arrays layout were both NO faster than the 64-byte accumulator
(8.40 and 8.47 ms against 6.49 ms for the accumulator itself, same session,
identical checksums). Narrowing would buy REACH, not throughput, at this
aggregate count."""

comptime PACKED_ROUTE_MAX_SLOTS: Int = 1 << 17
"""The routing line, MEASURED — above this many slots the router prefers the
existing hash engines even though the dense route would still be legal.

Not a safety bound (the two above are) and not a guess. Measured on this machine
at 1e7 rows, ONE aggregate, `num_physical_cores()` = 16 bands, two synthetic key
columns derived from id3 so the present tuples FILL the product rather than
sitting sparsely inside it — the dense array's favourable case, so this is an
upper bound on where the route should be preferred. Best hash engine per row is
whichever of banded / radix won that row; every packed result was asserted
bit-identical to banded. `benchmarks/h2o_groupby/sweep_packed.mojo`:

    slots  | best hash ms | packed ms | packed wins by
      256  |        63.7  |     5.63  |  11.3x
     1024  |        64.5  |     9.84  |   6.6x
    10000  |        93.8  |    18.89  |   5.0x   <- the H2O q2 product
    32761  |        71.4  |    25.84  |   2.8x
    65536  |        90.7  |    33.84  |   2.7x
    99856  |        83.8  |    68.26  |   1.2x
   100352  |       106.8  |    65.43  |   1.6x

Absolutes are load-inflated (this ran at ~10 of 16 cores busy) but the rows are
adjacent in one session, so the ratios are honest. The advantage decays
monotonically because the merge walks every band's seen list and the
`seen` / `slot_to_group` arrays are `slots` long while the useful work is not.

131 072 is the line because the win is still real at the largest product
measured (1.2-1.6x at ~1e5) and because it is the largest power of two the byte
budget can even run at 16 bands, one aggregate and width 2: the next step,
262 144, needs 329 MiB and is refused. Above ~1e5 the honest statement is
"measured margin is thin", not "measured loss".

`group_by_packed_parallel` enforces only the safety ceilings, never this line,
so a caller who knows its domain is dense can still pin the route above it."""


struct PackedDomain(Copyable, Movable):
    """The mixed-radix place value a key tuple packs into, probed once.

    `los[c]`/`his[c]` are the inclusive/exclusive integral bounds column `c`
    must satisfy at scan time, as Float64 so the guard compares in float domain
    before `Int()` is reached. `lo_ints[c]` is the same low bound as an Int for
    the subtraction, `strides[c]` its place value, `spans[c]` its radix.
    `slots` is the product, and 0 means "no packed route" — every rejection
    (too wide, non-integral, no present keys, product too large) collapses to
    that one signal, with `status` carrying which.
    """

    var width: Int
    var los: List[Float64]
    var his: List[Float64]
    var lo_ints: List[Int]
    var spans: List[Int]
    var strides: List[Int]
    var slots: Int
    var status: Int

    def __init__(out self, status: Int):
        """An empty, invalid domain carrying why."""
        self.width = 0
        self.los = List[Float64]()
        self.his = List[Float64]()
        self.lo_ints = List[Int]()
        self.spans = List[Int]()
        self.strides = List[Int]()
        self.slots = 0
        self.status = status

    def __init__(
        out self,
        var los: List[Float64],
        var his: List[Float64],
        var lo_ints: List[Int],
        var spans: List[Int],
        var strides: List[Int],
        slots: Int,
    ):
        self.width = len(los)
        self.los = los^
        self.his = his^
        self.lo_ints = lo_ints^
        self.spans = spans^
        self.strides = strides^
        self.slots = slots
        self.status = GROUP_CODED_OK

    def valid(self) -> Bool:
        return self.slots > 0 and self.width > 0

    def describe(self) -> String:
        var out = String("PackedDomain(status=") + packed_status_name(self.status)
        out += ", width=" + String(self.width) + ", slots=" + String(self.slots)
        for c in range(self.width):
            out += (
                "; c" + String(c) + " in [" + String(self.los[c]) + ", "
                + String(self.his[c]) + ") span=" + String(self.spans[c])
                + " stride=" + String(self.strides[c])
            )
        return out^


def packed_state_bytes(slots: Int, n_aggs: Int, bands: Int, width: Int) -> Int:
    """EVERY byte `group_by_packed_parallel` allocates, worst case, saturating.

    Rule 1c: a bound that counts one of the arrays is not a bound. This counts
    all six, and the arithmetic is stated because it is a product of four
    caller-supplied terms:

      per (band, slot):  n_aggs x size_of[GroupAccumulator]()   `state`
                       + 1 byte                                 `seen`
                       + 8 bytes                                `band_orders`
                                                                 (worst case:
                                                                  every band
                                                                  sees every
                                                                  slot)
      per slot:          8 bytes                                `slot_to_group`
                       + n_aggs x size_of[GroupAccumulator]()   `out_stripes`
                       + width x 8 bytes                        `key_tuples`
                                                                 (worst case:
                                                                  every slot is
                                                                  a group)

    `_finish_many_packed`'s `values`/`present`/`counts` are 17 more bytes per
    (group, aggregate) and are deliberately NOT counted: they are the RESULT,
    which the caller receives and owns, not scratch this function is choosing
    to allocate. Everything above is freed before the call returns.

    Returns `MAX_PACKED_STATE_BYTES + 1` on any overflow, so a caller comparing
    against the ceiling REJECTS rather than wrapping to a small positive number.
    That failure mode is the whole reason this is a function and not an
    expression at the call site: `slots * n_aggs * 64 * bands` silently wraps to
    something under the ceiling for large arguments, and a bound computed from a
    wrapped product is a rubber stamp. Pinned by the suite at both a wrapping
    slot count and a wrapping band count.
    """
    if slots <= 0 or n_aggs <= 0 or bands <= 0 or width <= 0:
        return 0
    var acc_bytes = size_of[GroupAccumulator]()
    var over = MAX_PACKED_STATE_BYTES + 1

    # per (band, slot)
    var per_slot_band = n_aggs
    if per_slot_band > over // acc_bytes:
        return over
    per_slot_band = per_slot_band * acc_bytes + 9
    var banded_total = slots
    if banded_total > over // per_slot_band:
        return over
    banded_total *= per_slot_band
    if banded_total > over // bands:
        return over
    banded_total *= bands
    if banded_total > over:
        return over

    # per slot (output side, worst case every slot is a group)
    var per_slot = n_aggs
    if per_slot > over // acc_bytes:
        return over
    per_slot = per_slot * acc_bytes + 8
    if width > over // 8:
        return over
    per_slot += width * 8
    var out_total = slots
    if out_total > over // per_slot:
        return over
    out_total *= per_slot

    if banded_total > over - out_total:
        return over
    return banded_total + out_total


def probe_packed_domain(
    batch: RecordBatch, key_columns: List[Int], probe_rows: Int
) -> PackedDomain:
    """The packed place value these key columns support, judged from the first
    `min(probe_rows, n_rows)` rows.

    Every PRESENT probed key in every column must be an integral Float64; the
    column's `[min, max + 1)` becomes its bound and `max - min + 1` its radix.
    A column with no present key in the window has no evidence and refuses the
    whole tuple — the same "no evidence, no route" rule `probe_coded_bound`
    applies.

    One-sided in the same direction as the rest of the probe family: a row past
    the window can only be MORE out of range, never less, and out of range is a
    typed refusal from the scan, so a lying window costs one partial pass and
    never a wrong answer. Hash-free on purpose (compares and a truncation per
    key), because it runs in front of a question the dense route answers in
    single-digit milliseconds.
    """
    var width = len(key_columns)
    if width < 1 or width > MAX_PACKED_WIDTH:
        return PackedDomain(GROUP_CODED_BAD_REQUEST)
    var n = batch.n_rows
    if probe_rows < n:
        n = probe_rows
    if n <= 0:
        return PackedDomain(GROUP_CODED_CARDINALITY_INVALID)

    # The widest integral range a Float64 represents exactly, and therefore the
    # widest `Float64(Int(k)) == k` can vouch for. Beyond it the pack could
    # collide two distinct keys onto one slot.
    var exact_limit = Float64(1 << 53)

    var los = List[Float64](capacity=width)
    var his = List[Float64](capacity=width)
    var lo_ints = List[Int](capacity=width)
    var spans = List[Int](capacity=width)
    var strides = List[Int](capacity=width)

    for c in range(width):
        var col = batch.column(key_columns[c])
        var has_nulls = col.null_count() > 0 or col.length < n
        var kp = col.values[].unsafe_ptr() + col.offset
        var seen_any = False
        var lo = 0
        var hi = 0
        for r in range(n):
            if has_nulls and not col.is_valid_at(r):
                continue
            var k = kp[r]
            # Float domain first: NaN fails `k > -limit` (unordered), the
            # infinities and anything past 2^53 fail one of the two bounds, so
            # `Int(k)` is only reached where `fptosi` is defined and exact.
            if not (k > -exact_limit) or not (k < exact_limit):
                return PackedDomain(GROUP_CODED_KEY_NOT_A_CODE)
            var code = Int(k)
            if Float64(code) != k:
                return PackedDomain(GROUP_CODED_KEY_NOT_A_CODE)
            if not seen_any:
                lo = code
                hi = code
                seen_any = True
            else:
                if code < lo:
                    lo = code
                if code > hi:
                    hi = code
        if not seen_any:
            return PackedDomain(GROUP_CODED_CARDINALITY_INVALID)
        var span = hi - lo + 1
        if span < 1:
            return PackedDomain(GROUP_PACKED_DOMAIN_TOO_LARGE)
        los.append(Float64(lo))
        his.append(Float64(hi + 1))
        lo_ints.append(lo)
        spans.append(span)

    # Mixed-radix strides, product bounded INSIDE the fold so it can never
    # overflow on the way to being rejected.
    var slots = 1
    for c in range(width):
        strides.append(slots)
        if spans[c] > MAX_PACKED_SLOTS // slots:
            return PackedDomain(GROUP_PACKED_DOMAIN_TOO_LARGE)
        slots *= spans[c]
    if slots < 1 or slots > MAX_PACKED_SLOTS:
        return PackedDomain(GROUP_PACKED_DOMAIN_TOO_LARGE)
    return PackedDomain(los^, his^, lo_ints^, spans^, strides^, slots)


def packed_route_ok(
    batch: RecordBatch, key_columns: List[Int], n_aggs: Int, n_workers: Int
) -> PackedDomain:
    """`probe_packed_domain` plus the two routing gates, so the decision is one
    testable call: the measured `PACKED_ROUTE_MAX_SLOTS` line and the
    `MAX_PACKED_STATE_BYTES` allocation budget.

    Returns an INVALID domain (`valid()` false, `status` saying which gate) when
    the caller should keep its hash engine. `group_by_packed_parallel` does NOT
    consult the routing line — only the safety ceilings — so a caller that knows
    its domain is dense can still pin the route.
    """
    var domain = probe_packed_domain(batch, key_columns, CARDINALITY_PROBE_ROWS)
    if not domain.valid():
        return domain^
    if domain.slots > PACKED_ROUTE_MAX_SLOTS:
        return PackedDomain(GROUP_PACKED_DOMAIN_TOO_LARGE)
    var bands = n_workers
    if bands < 1:
        bands = 1
    if packed_state_bytes(domain.slots, n_aggs, bands, domain.width) > MAX_PACKED_STATE_BYTES:
        return PackedDomain(GROUP_PACKED_DOMAIN_TOO_LARGE)
    return domain^


@always_inline
def _packed_digit(k: Float64, lo_f: Float64, hi_f: Float64, lo_i: Int) -> Int:
    """The mixed-radix DIGIT for one key value, or -1 when it is not a code in
    `[lo_f, hi_f)`.

    THE guard, in one place, so every scan shape in this module walks the same
    ladder and none of them can be widened by accident. Float domain first —
    `k >= lo_f` is false for NaN (unordered) and for -inf, `k < hi_f` is false
    for +inf and for anything at or past the bound — so `Int(k)` is only reached
    where `fptosi` is defined, and `Float64(code) != k` then rejects every
    non-integral value. `hi_f` is EXCLUSIVE: a value equal to it is one slot
    group past the array, and the array is written without a bounds check.

    -1 is unambiguous as the refusal because a valid digit is `code - lo_i` with
    `code >= lo_i`, hence never negative. Returning a sentinel rather than
    raising is deliberate: the caller is inside a `parallelize` band and must
    set its flag and break, not unwind.
    """
    if not (k >= lo_f) or not (k < hi_f):
        return -1
    var code = Int(k)
    if Float64(code) != k:
        return -1
    return code - lo_i


def group_by_packed(
    batch: RecordBatch,
    key_columns: List[Int],
    domain: PackedDomain,
    value_columns: List[Int],
    opcodes: List[Int],
) -> CodedGroupedResult:
    """Fused grouping for a key TUPLE of bounded integers: the accumulator array
    is indexed by the packed key itself, no hash, no probe.

    On data every row of which satisfies `domain` this returns EXACTLY what
    `group_by_many` returns — same groups, same first-appearance order, same
    values, same bits — at the same worker count. A row outside `domain` is a
    typed refusal, never an out-of-bounds write.
    """
    return group_by_packed_parallel(
        batch,
        key_columns,
        domain,
        value_columns,
        opcodes,
        planned_workers(batch.n_rows, info.num_physical_cores()),
    )


def group_by_packed_parallel(
    batch: RecordBatch,
    key_columns: List[Int],
    domain: PackedDomain,
    value_columns: List[Int],
    opcodes: List[Int],
    n_workers: Int,
) -> CodedGroupedResult:
    """`group_by_packed` on an explicit band count. 1 band is the serial path.

    Parallel shape is `group_by_coded_parallel`'s, widened: contiguous equal
    bands, a private DENSE accumulator array per band indexed by the packed
    key, a band-local first-appearance list, and a merge in ascending band
    index. The merge walks each band's OWN seen list rather than all `slots`,
    so a sparse domain costs its emptiness once (the arrays) and not per band
    per group (the merge) — which is what `group_by_many_banded`'s
    O(workers x groups) merge does and what `PACKED_ROUTE_MAX_SLOTS` is drawn
    against.

    Enforces only the SAFETY ceilings, not the routing line: `MAX_PACKED_SLOTS`
    via the domain and `MAX_PACKED_STATE_BYTES` against the real band count.
    """
    if not _many_request_ok(value_columns, opcodes):
        return CodedGroupedResult(GROUP_CODED_BAD_REQUEST, _empty_many())
    var width = len(key_columns)
    if width < 1 or width > MAX_PACKED_WIDTH:
        return CodedGroupedResult(GROUP_CODED_BAD_REQUEST, _empty_many())
    if not domain.valid():
        # Propagate the PROBE's reason rather than flattening every rejection to
        # one code: an invalid domain has width 0, so a `domain.width != width`
        # check would report BAD_REQUEST for a domain that was refused because
        # the DATA was non-integral or too wide, which sends the next reader to
        # the call site instead of the data.
        var reason = domain.status
        if reason == GROUP_CODED_OK:
            reason = GROUP_PACKED_DOMAIN_TOO_LARGE
        return CodedGroupedResult(reason, _empty_many())
    if domain.width != width:
        return CodedGroupedResult(GROUP_CODED_BAD_REQUEST, _empty_many())
    if domain.slots > MAX_PACKED_SLOTS:
        return CodedGroupedResult(GROUP_PACKED_DOMAIN_TOO_LARGE, _empty_many())

    var n_aggs = len(value_columns)
    var n_rows = batch.n_rows
    var slots = domain.slots

    var bands = n_workers
    if bands < 1:
        bands = 1
    if bands > n_rows:
        bands = n_rows
    if bands < 1:
        # An empty batch: one band over zero rows, so the loop below is a no-op
        # and the result is zero groups — which is what every other engine
        # returns for it.
        bands = 1
    if packed_state_bytes(slots, n_aggs, bands, width) > MAX_PACKED_STATE_BYTES:
        return CodedGroupedResult(GROUP_PACKED_DOMAIN_TOO_LARGE, _empty_many())

    var key_cols = List[Float64Array]()
    for c in range(width):
        key_cols.append(batch.column(key_columns[c]))
    var value_cols = List[Float64Array]()
    for j in range(n_aggs):
        value_cols.append(batch.column(value_columns[j]))
    var value_nulls = _col_guard_flags(value_cols, n_rows)
    var key_null_flags = _col_guard_flags(key_cols, n_rows)
    var any_key_nulls = False
    for c in range(width):
        if key_null_flags[c]:
            any_key_nulls = True

    # ── per-band state, ONE contiguous allocation each ────────────────────────
    # Flat `UnsafePointer` rather than `List[List[...]]`: the nested-List index
    # is a bounds check plus a pointer chase per (band, slot, aggregate) touch,
    # which profiling put at ~28 cycles/row of pure indirection on exactly this
    # inner loop — 88% of a dense scan's serial time. The frozen accumulator
    # SEMANTICS are untouched; only its container changes.
    var stripe_count = bands * slots * n_aggs
    var state = alloc[GroupAccumulator](stripe_count)
    var seen = alloc[Bool](bands * slots)
    var band_orders = List[List[Int]](capacity=bands)
    for _ in range(bands):
        band_orders.append(List[Int]())
    var w_nulls = List[Int](length=bands, fill=0)
    var w_bad = List[Bool](length=bands, fill=False)
    var op_ptr = band_orders.unsafe_ptr()
    var np_ptr = w_nulls.unsafe_ptr()
    var bp_ptr = w_bad.unsafe_ptr()

    var lo_f = domain.los.unsafe_ptr()
    var hi_f = domain.his.unsafe_ptr()
    var lo_i = domain.lo_ints.unsafe_ptr()
    var stride = domain.strides.unsafe_ptr()
    var band_rows = (n_rows + bands - 1) // bands

    @parameter
    def packed_worker(w: Int):
        var lo_row = w * band_rows
        var hi_row = lo_row + band_rows
        if hi_row > n_rows:
            hi_row = n_rows
        var sbase_w = w * slots * n_aggs
        var ebase_w = w * slots
        # Each band initializes its OWN region: the writes are parallel, and
        # the memory is warm in the right cache when the scan reaches it.
        for i in range(slots * n_aggs):
            (state + sbase_w + i).init_pointee_move(GroupAccumulator(0.0))
        for i in range(slots):
            (seen + ebase_w + i).init_pointee_move(False)
        if lo_row >= hi_row:
            return

        var kps = List[UnsafePointer[Float64, origin=MutAnyOrigin]](capacity=width)
        for c in range(width):
            kps.append(key_cols[c].values[].unsafe_ptr() + key_cols[c].offset)
        var vps = List[UnsafePointer[Float64, origin=MutAnyOrigin]](capacity=n_aggs)
        for j in range(n_aggs):
            vps.append(value_cols[j].values[].unsafe_ptr() + value_cols[j].offset)
        var kp = kps.unsafe_ptr()
        var vp = vps.unsafe_ptr()
        var ops = opcodes.unsafe_ptr()
        var vnull = value_nulls.unsafe_ptr()
        var nulls = 0

        # `bad` is a LOCAL, written back once. Reading a shared `List[Bool]`
        # element per row put 16 bands' flags on one cache line and a load in
        # the inner loop for a condition that is false on every row of a
        # successful call.
        var bad = False

        # The slot COMMIT, shared by all three scan shapes below so they cannot
        # disagree about first-appearance order or which accumulator moves.
        # `slot` is in [0, slots) by construction — every digit came back
        # non-negative from `_packed_digit` and is bounded by its own column's
        # span, and the strides are that radix's place values. That is the whole
        # licence for the unchecked write.
        @parameter
        @always_inline
        def commit(r: Int, slot: Int):
            if not seen[ebase_w + slot]:
                seen[ebase_w + slot] = True
                op_ptr[w].append(slot)
            var sbase = sbase_w + slot * n_aggs
            for j in range(n_aggs):
                if not vnull[j] or value_cols[j].is_valid_at(r):
                    state[sbase + j].observe_op(ops[j], vp[j][r])

        # Width 1 and width 2 get the domain hoisted into SCALARS. In the
        # general loop every row re-reads `kp[c]`, `lo_f[c]`, `hi_f[c]`,
        # `lo_i[c]` and `stride[c]` through a pointer, which is ~5 extra L1
        # loads per key column per row — the indirection tax profiling measured
        # at 9x on exactly this shape. Width 2 is the H2O q2 shape and the one
        # this module exists for; wider tuples keep the general loop, where the
        # per-row work is larger anyway and the tax is proportionally smaller.
        # Both fast paths require NO key nulls, which `_col_guard_flags` false
        # already licenses as "every scanned slot is present and in range".
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
                    break  # the whole call refuses; nothing this band survives
                if null_key:
                    nulls += 1
                    continue
                commit(r, slot)
        bp_ptr[w] = bad
        np_ptr[w] = nulls

    parallelize[packed_worker](bands)

    for w in range(bands):
        if w_bad[w]:
            state.free()
            seen.free()
            return CodedGroupedResult(GROUP_CODED_KEY_NOT_A_CODE, _empty_many())

    # ── global first-appearance order: bands in band order, each band's local
    #    (already first-appearance) list in order — `group_by_many_banded`'s
    #    composition exactly, so the group order matches it group for group ──
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
    var out_stripes = List[GroupAccumulator](capacity=n_groups * n_aggs)
    for g in range(n_groups):
        var slot = g_order[g]
        # Unpack the mixed radix back to the original key values. Exact: only
        # integral Float64 inside [lo, hi) ever entered, and every such value
        # round-trips through Int.
        var first_key: Float64 = 0.0
        for c in range(width):
            var digit = (slot // domain.strides[c]) % domain.spans[c]
            var value = Float64(domain.lo_ints[c] + digit)
            key_tuples.append(value)
            if c == 0:
                first_key = value
        for _ in range(n_aggs):
            # Seeded from the first key column, matching what
            # `group_by_many_banded` puts in the unread `key` field.
            out_stripes.append(GroupAccumulator(first_key))

    # Merge in ascending band index, walking only the slots each band saw. For
    # any one group the bands therefore fold in the same sequence
    # `group_by_many_banded` folds them, which is why the floats are bit-equal
    # and not merely close.
    var osp = out_stripes.unsafe_ptr()
    for w in range(bands):
        var sbase_w = w * slots * n_aggs
        for i in range(len(band_orders[w])):
            var slot = band_orders[w][i]
            var g = slot_to_group[slot]
            for j in range(n_aggs):
                osp[g * n_aggs + j].merge_from(state[sbase_w + slot * n_aggs + j])

    state.free()
    seen.free()
    return CodedGroupedResult(
        GROUP_CODED_OK,
        _finish_many_packed(
            key_tuples^, width, out_stripes^, n_aggs, opcodes, null_key_rows
        ),
    )


def _finish_many_packed(
    var key_tuples: List[Float64],
    width: Int,
    var stripes: List[GroupAccumulator],
    n_aggs: Int,
    opcodes: List[Int],
    null_key_rows: Int,
) -> ManyGroupedResult:
    """`query.aggregate._finish_many`'s extraction, over owned inputs.

    Identical rule, deliberately: `value_for` / `has_answer` per (group,
    aggregate) and nothing else, so answerability and the all-NaN extremum
    canonicalization cannot diverge between this route and the hash routes. It
    exists only to avoid the two full list copies `_finish_many` makes of
    inputs this path has just built and will never reuse.
    """
    var values = List[Float64](capacity=len(stripes))
    var present = List[Bool](capacity=len(stripes))
    var counts = List[Float64](capacity=len(stripes))
    var n_groups = 0
    if n_aggs > 0:
        n_groups = len(stripes) // n_aggs
    for g in range(n_groups):
        for j in range(n_aggs):
            ref acc = stripes[g * n_aggs + j]
            var op = opcodes[j]
            var answerable = acc.has_answer(op)
            values.append(acc.value_for(op) if answerable else 0.0)
            present.append(answerable)
            counts.append(acc.count)
    return ManyGroupedResult(
        key_tuples^, width, n_aggs, opcodes.copy(), values^, present^, counts^,
        null_key_rows,
    )


def group_by_many_routed(
    batch: RecordBatch,
    key_columns: List[Int],
    value_columns: List[Int],
    opcodes: List[Int],
) -> ManyGroupedResult:
    """`query.aggregate.group_by_many`, with the packed route added in front.

    A drop-in: same signature, same promises, and on any batch the packed route
    declines or refuses, this IS `group_by_many` — the fallback is the call
    itself, not a reimplementation of it.
    """
    return group_by_many_routed_parallel(
        batch,
        key_columns,
        value_columns,
        opcodes,
        planned_workers(batch.n_rows, info.num_physical_cores()),
    )


def group_by_many_routed_parallel(
    batch: RecordBatch,
    key_columns: List[Int],
    value_columns: List[Int],
    opcodes: List[Int],
    n_workers: Int,
) -> ManyGroupedResult:
    """`group_by_many_parallel` with the packed route tried first.

    Order of decisions: a malformed request and width 0 belong to the existing
    entry point (it owns those answers); a worker count that clamps to <= 1
    also goes there, because the packed route's whole advantage is per-band
    private state. Then `packed_route_ok` decides, and a scan-time refusal
    falls through to the same call. A refusal costs one partial pass over data
    whose probe window lied — never a wrong answer.
    """
    if not _many_request_ok(value_columns, opcodes) or len(key_columns) == 0:
        return group_by_many_parallel(
            batch, key_columns, value_columns, opcodes, n_workers
        )
    var workers = n_workers
    if workers < 1:
        workers = 1
    if workers > batch.n_rows:
        workers = batch.n_rows
    if workers <= 1:
        return group_by_many_parallel(
            batch, key_columns, value_columns, opcodes, n_workers
        )
    var domain = packed_route_ok(batch, key_columns, len(value_columns), workers)
    if domain.valid():
        var packed = group_by_packed_parallel(
            batch, key_columns, domain, value_columns, opcodes, workers
        )
        if packed.ok():
            return packed.result.copy()
    return group_by_many_parallel(batch, key_columns, value_columns, opcodes, n_workers)
