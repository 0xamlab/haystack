"""query.coded_dense — direct-index grouping over a FLAT, PACKED accumulator.

Additive to `query.aggregate`; nothing there changes. This module answers the
same question `group_by_coded` answers — group a single key column of integer
CODES, aggregate several value columns in one pass — and returns the same
`CodedGroupedResult`. The difference is entirely in the per-row state layout.

Why this exists: what `group_by_coded` actually spends
------------------------------------------------------
A stage-by-stage decomposition of `group_by_coded_parallel`'s serial path on
the H2O q1 shape (1e7 rows, K=100 codes, one SUM) attributed its 69.9 ms as:

  scan both columns, no grouping                    8.997 ms
  + the coded guard and `Int(k)`                   10.843 ms
  + first-appearance bookkeeping                    9.330 ms
  + a NARROW dense accumulator (flat pointer)       9.825 ms
  + a WIDE (64-byte-stride) accumulator, flat       8.644 ms
  + `List[List[GroupAccumulator]]` indirection     77.966 ms   <-- 9.0x
  the shipped `group_by_coded`, 1 worker            69.942 ms

So 88% of that path is neither hashing (there is none), nor bandwidth, nor
accumulator width. It is Mojo `List` element access — a bounds check plus a
nested pointer chase — on `sp[w][sbase + j]`, `ep[w][code]`, `vps[j][r]`,
`opcodes[j]` and `value_nulls[j]`, five of them per row per aggregate. The
same tax dominates the radix engine's pass 2 (`psp[p][sbase + j]`, 90% of its
wall time), which is why it is worth removing once, in a shape other engines
can adopt.

What this module changes, and only this
---------------------------------------
1. ONE contiguous `Float64` buffer holds every worker's accumulators. Row
   updates go through a raw `UnsafePointer` at a computed offset: no `List`
   bounds check, no nested chase, no per-worker `List` allocation.
2. The record is PACKED to exactly the slots the requested opcode reads.
   `size_of[GroupAccumulator]()` is 64 bytes; a SUM reads `count` and `total`
   (16 bytes), a mean reads `count` and `mean` (16). Measured amplification on
   the shipped path: 4.0x, and for a 3-aggregate question 192 bytes spanning
   THREE cache lines per row.
3. When no value column has nulls, all of a group's aggregates share ONE
   count — they must, since every live row feeds every aggregate — so the
   record becomes `[count, p_0 .. p_{n-1}]`: 32 bytes for a 3-mean question,
   ONE cache line, against 192.
4. That shared count doubles as the first-appearance flag. `count == 0` before
   the increment IS "this band has not seen this code", so the separate
   `seen` byte array and its per-row load disappear on the fast path.
5. Each worker's region is padded to a 64-byte multiple and the base pointer
   is 64-byte aligned, so no two workers share a cache line and no record
   straddles one.
6. min/max carry no `seen` field. The payload seeds to the canonical NaN and
   the fold is a SELECT, not a first-value branch — `_dense_min_fold` below.
   The branch it removes measured 2.18x on the H2O q7 shape.

What this module does NOT change — the identity contract
---------------------------------------------------------
Every number is produced by the same frozen primitives in the same order, and
the merge is the shipped `GroupAccumulator.merge_from`, called on accumulators
unpacked from this buffer. Concretely:

  * bands are `(n_rows + workers - 1) // workers` wide, identical to
    `group_by_coded_parallel`, so each worker folds exactly the same rows in
    the same order;
  * within a band, sums use `group_sum_update` and means use
    `group_mean_update` (Welford, NOT sum-then-divide) with the same count
    sequence `observe_sum` / `observe_mean` use;
  * across bands, the fold is `merge_from` per (code, aggregate) in
    WORKER-INDEX order — the identical association;
  * group ORDER is global first appearance, composed the identical way
    (walk workers in band order, take each worker's local first-appearance
    list, dedup);
  * extraction is the shared `_finish_many`, so answerability, `present` and
    `counts` cannot disagree by construction.

The consequence, which the suite asserts rather than assumes: at equal worker
count this route is BIT-IDENTICAL to `group_by_coded_parallel` on every
supported opcode — sums and means included, because equal association over
equal bands is equality, not tolerance.

NaN policy, unchanged and re-proven
-----------------------------------
A NaN VALUE counts, poisons sum/mean/m2 associatively, and contributes to NO
extremum — `query.aggregate`'s policy, the one the #459 defect broke twice
(once in `observe`, once again in `observe_min`). Here it survives the
sentinel encoding: `_dense_min_fold` takes a value only when the value is
ordered, so a NaN can neither seed nor move an extremum, and a group whose
values were ALL NaN still holds the seed at the end, which unpacks to
`seen = False` and therefore reports the canonical quiet NaN through
`value_for` — the same bit pattern, from the same code, as every other engine
in the plane. The suite pins all of it against `group_by_coded_parallel`.

Refusals are typed, and bounded BEFORE any allocation
------------------------------------------------------
Indexing a dense array with an out-of-range code is an out-of-bounds write,
which in Mojo is an uncatchable abort that takes the worker process and every
resident dataset with it — `try`/`except` does not contain it. So every
present key is validated in the FLOAT domain by `_dense_code` before it
indexes anything (NaN and negatives fail `k >= 0.0`; +inf and oversized fail
`k < bound`; `Int(k)` is reached only where `fptosi` is defined), and a
violation refuses the whole call with `GROUP_CODED_KEY_NOT_A_CODE`. The guard
is cheap: measured at +1.85 ms serial on 1e7 rows, about 1.6x LESS than one
accumulator update, so there is no cost argument for weakening it.

Allocation is bounded by BYTES, not by cardinality alone (rule 1c: a
per-item ceiling is not a bound on total allocation). This route allocates
exactly three arrays scaled by the state size:

  accumulators  workers * pad64(cardinality * stride) * 8 bytes
  order         workers * cardinality * 8 bytes
  seen          workers * cardinality bytes   (null-value layout only)

`dense_route_status` sums those against `DENSE_MAX_STATE_BYTES` and refuses
with `GROUP_DENSE_STATE_TOO_LARGE` before anything is allocated, so a caller
who names a 1e6 cardinality on a ten-row batch gets a status, not 2 GB.

Status codes are `query.aggregate`'s 330-339 block, reused deliberately: a
caller that already handles `coded_status_name` handles this engine too.
334 and 335 are new; 330-333 keep their exact meanings.
"""
from max.algorithm import parallelize
from std.sys import info

from columnar.array import Float64Array
from columnar.batch import RecordBatch
from numeric.contract import AGG_AVG, AGG_COUNT, AGG_MAX, AGG_MIN, AGG_SUM
from pandas_groupby import (
    group_count_update,
    group_max_update,
    group_mean_update,
    group_min_update,
    group_sum_update,
)
from query.aggregate import (
    CodedGroupedResult,
    GROUP_CODED_BAD_REQUEST,
    GROUP_CODED_CARDINALITY_INVALID,
    GROUP_CODED_KEY_NOT_A_CODE,
    GROUP_CODED_OK,
    GroupAccumulator,
    _canonical_nan,
    _col_guard_flags,
    _empty_many,
    _finish_many,
    _many_request_ok,
    planned_workers,
)

# ── status codes: continuing query.aggregate's 330-339 block ─────────────────
comptime GROUP_DENSE_OPCODE_UNSUPPORTED: Int = 334
"""The request names VAR or STD.

Sample variance needs `count`, `mean` and `m2` maintained together, which is
three payload slots plus the count and defeats the packing this route exists
for. `group_by_coded` answers those unchanged; this is a ROUTING signal, not
a failure."""

comptime GROUP_DENSE_STATE_TOO_LARGE: Int = 335
"""`workers x cardinality x stride` would exceed `DENSE_MAX_STATE_BYTES`."""

comptime DENSE_BANDS_PER_CORE: Int = 2
"""Row bands per physical core the unsuffixed entry point asks for.

OVER-DECOMPOSITION, and it is a ROBUSTNESS lever rather than a throughput one.
`parallelize` splits the rows into equal contiguous bands and the call finishes
when the SLOWEST band does, so with exactly one band per core a single
descheduled band — or, on a 12-P + 4-E-core machine, an E-core band — sets the
wall time. With two bands per core a thread that finishes early takes the next
band instead of idling.

Measured on this host while sibling jobs held a third to two thirds of 16 cores
(which is the environment here, not an anomaly): q4 at 32 bands 3.089 ms
against 3.579 at 16, q1 2.318 against 2.486 on the MIN of 15 interleaved
samples, and 1.22x / 1.09x on the MEDIAN — the win is concentrated in the tail,
which is exactly what a straggler explanation predicts.

Determinism is unaffected in KIND: the merge is a pure function of band index,
so a given band count is bit-reproducible. It does change the band count the
DEFAULT entry point uses, so `group_by_coded_dense` and `group_by_coded` no
longer share a band split, and their sums and means therefore differ by
association — exactly as `group_by_coded_parallel` at 16 differs from itself at
32. The BIT-IDENTITY claim in this module is, and only ever was, AT EQUAL
WORKER COUNT: call `group_by_coded_dense_parallel` with the reference's worker
count to hold it, which is what the suite and the H2O bench both do."""

comptime DENSE_MAX_CARDINALITY: Int = 1 << 20
"""Per-dimension ceiling on the dense array's code space.

Deliberately far above `query.aggregate.MAX_CODED_CARDINALITY` (4096): the
packed record is 4-8x smaller, so the cardinality at which a dense array stops
paying moves up with it, and the H2O id3/id6 shapes (1e5 codes) sit inside
this. It is NOT the operative bound — `DENSE_MAX_STATE_BYTES` is. This exists
so a nonsensical cardinality is rejected by shape before the byte arithmetic
is even attempted."""

comptime DENSE_MAX_STATE_BYTES: Int = 64 << 20
"""Total private-state budget across ALL workers, checked before allocating.

64 MiB, an eighth of the 512 MiB resident-dataset budget, because this state
is transient scratch that coexists with the dataset it is scanning rather than
replacing it. At 16 workers it admits 1e5 codes with 4 aggregates (16 x 1e5 x
5 slots x 8 B = 64 MB, right at the line) and refuses anything larger, which
is the honest place to stop: past that the array is no longer cache-resident
per worker and the hash engines stop losing."""


@always_inline
def dense_supports_opcode(opcode: Int) -> Bool:
    """Whether the packed record can hold everything `opcode` reads.

    SUM (count+total), AVG (count+mean), MIN/MAX (count+extremum) and COUNT
    (count) each fit one count plus at most one payload slot. VAR and STD do
    not, and neither does an unrecognised opcode — an opcode this route does
    not KNOW must be refused rather than silently folded as something else,
    which is the whole reason `observe_op`'s fall-through to the full
    `observe` is safe there and would not be safe here.
    """
    return (
        opcode == AGG_SUM
        or opcode == AGG_AVG
        or opcode == AGG_MIN
        or opcode == AGG_MAX
        or opcode == AGG_COUNT
    )


@always_inline
def _pad64(n_slots: Int) -> Int:
    """`n_slots` Float64s rounded up to a whole 64-byte cache line."""
    return ((n_slots + 7) // 8) * 8


def dense_record_stride(n_aggs: Int, shared_count: Bool) -> Int:
    """Float64 slots per group record, in ONE place because the scan, the merge
    and the byte budget all index with it and they have to agree.

    Shared-count layout is `[count, p_0 .. p_{n-1}]`, rounded UP to a power of
    two at one and three aggregates so the whole record is one aligned SIMD
    vector: 2 slots for one aggregate, 4 for two or three. The single wasted
    slot at two aggregates is 8 bytes per group — 800 bytes at K=100 — against
    a record that one 32-byte load and one 32-byte store can carry instead of
    six scalar accesses. Above three aggregates the vector shape stops helping
    and the stride is exactly `1 + n_aggs`.

    Divergent-count layout keeps `[c_0, p_0, c_1, p_1, ...]`: its counts move
    independently, so there is no whole-record vector operation to align for.
    """
    if not shared_count:
        return 2 * n_aggs
    if n_aggs == 1:
        return 2
    if n_aggs <= MAX_UNROLLED_AGGS:
        return 4
    return 1 + n_aggs


def dense_state_bytes(cardinality: Int, n_aggs: Int, workers: Int, shared_count: Bool) -> Int:
    """Total bytes `group_by_coded_dense_parallel` will allocate, exactly.

    Public because the bound it feeds is the reason a caller can trust the
    route with a large cardinality: the arithmetic is checkable, not asserted.
    Counts all three arrays (rule 1c — one array's ceiling is not the total),
    and the `seen` array only on the layout that has one.
    """
    var stride = dense_record_stride(n_aggs, shared_count)
    var acc = workers * _pad64(cardinality * stride) * 8
    var order = workers * cardinality * 8
    var seen = 0 if shared_count else workers * cardinality
    return acc + order + seen


def dense_route_status(
    cardinality: Int,
    value_columns: List[Int],
    opcodes: List[Int],
    workers: Int,
    shared_count: Bool,
) -> Int:
    """Whether this route will accept the request — `GROUP_CODED_OK`, or the
    refusal code, decided from shape alone with nothing allocated and nothing
    scanned.

    One testable function so a router's decision and the engine's decision
    cannot drift apart: `group_by_coded_dense_parallel` calls exactly this and
    returns exactly what it says. `shared_count` is whether every value column
    is null-free (`_col_guard_flags` all False), which the caller reads off
    the batch — it changes the stride and therefore the byte bound.
    """
    if not _many_request_ok(value_columns, opcodes):
        return GROUP_CODED_BAD_REQUEST
    if cardinality <= 0 or cardinality > DENSE_MAX_CARDINALITY:
        return GROUP_CODED_CARDINALITY_INVALID
    for j in range(len(opcodes)):
        if not dense_supports_opcode(opcodes[j]):
            return GROUP_DENSE_OPCODE_UNSUPPORTED
    var w = workers if workers > 0 else 1
    if dense_state_bytes(cardinality, len(value_columns), w, shared_count) > DENSE_MAX_STATE_BYTES:
        return GROUP_DENSE_STATE_TOO_LARGE
    return GROUP_CODED_OK


@always_inline
def _dense_code(k: Float64, bound: Float64) -> Int:
    """The code `k` denotes, or -1 when `k` is not one — the ONLY place this
    module decides that, so the guard cannot be enforced at two strengths.

    Float domain first and deliberately: NaN and negatives fail `k >= 0.0`
    (note the `not (k >= 0.0)` spelling — `k < 0.0` is false for NaN), +inf
    and oversized values fail `k >= bound`, so `Int(k)` is reached only where
    `fptosi` is defined. `Float64(code) != k` then rejects a fractional value,
    which would otherwise alias onto its truncation's group. -1 is
    unambiguous: every accepted code is >= 0.
    """
    if not (k >= 0.0) or k >= bound:
        return -1
    var code = Int(k)
    if Float64(code) != k:
        return -1
    return code


@always_inline
def _dense_min_fold(current: Float64, value: Float64) -> Float64:
    """Running minimum where `current` is the canonical NaN until an ordered
    value has arrived — `observe_min`'s answer with no `seen` field and no
    first-value branch.

    Equal to `group_min_update` under the sentinel discipline, case by case,
    and the suite asserts it over NaN, +/-0.0 and +/-inf rather than trusting
    this comment:

      value is NaN            -> `current` unchanged. A NaN contributes to no
                                 extremum; it can neither seed nor move one.
      current is the sentinel -> `value`. First ordered value seeds, exactly
                                 as `observe_min`'s `if not self.seen`.
      otherwise               -> `group_min_update(current, value)`, i.e.
                                 `value if value < current else current`,
                                 which keeps `current` on a tie and therefore
                                 keeps FIRST APPEARANCE between +0.0 and -0.0.

    Written as one select so the whole fold is `fcmp` + `fcsel`: the branch
    this removes — the per-row `seen` test — measured 2.18x on the H2O q7
    shape, with a bit-identical checksum.
    """
    var ordered = value == value
    var unseeded = current != current
    if ordered and (unseeded or value < current):
        return value
    return current


@always_inline
def _dense_max_fold(current: Float64, value: Float64) -> Float64:
    """`_dense_min_fold` with `>`; equal to `group_max_update` under the same
    sentinel discipline, and pinned by the same suite block."""
    var ordered = value == value
    var unseeded = current != current
    if ordered and (unseeded or value > current):
        return value
    return current


def _dense_min_reference(current: Float64, seen: Bool, value: Float64) -> Float64:
    """`observe_min`'s extremum update spelled with the frozen primitive and an
    explicit `seen` flag — the reference `_dense_min_fold` is proven against.

    Not called on any hot path. It exists so the equivalence the fast fold
    claims is checked against code that visibly IS the shipped policy, rather
    than against a second copy of the fast one.
    """
    if value != value:
        return current
    if not seen:
        return value
    return group_min_update(current, value)


def _dense_max_reference(current: Float64, seen: Bool, value: Float64) -> Float64:
    """`_dense_min_reference` with `group_max_update`."""
    if value != value:
        return current
    if not seen:
        return value
    return group_max_update(current, value)


comptime MAX_UNROLLED_AGGS: Int = 3
"""Aggregate counts the scan is fully UNROLLED for, at compile time.

1, 2 and 3 cover every H2O groupby question this route answers (q1 one SUM,
q3/q7 two, q4/q5 three), which is why the ceiling is here and not higher. Above
it the dynamic loop takes over: correct, still flat-pointer, just carrying a
loop and one extra pointer load per aggregate per row.

Why unrolling is not cosmetic. With a RUNTIME aggregate count the value
pointers live in an array, so the row loop reads `vpp[j]` and then `vpp[j][r]`
— and the compiler cannot keep `vpp[j]` in a register across the accumulator
STORE, because it cannot prove the store does not alias the pointer array. Every
row then pays a dependent load it does not need. With `na` a compile-time
parameter the pointers become loop-invariant locals and the aliasing question
disappears. Measured on q1: 5.003 ms with the runtime loop against 2.658 with
the unrolled one, same data, same worker count, same session."""

alias _RawF64 = UnsafePointer[Float64, origin=MutAnyOrigin]
alias _RawPtrs = UnsafePointer[_RawF64, origin=MutAnyOrigin]


struct _BandOutcome(Copyable, Movable):
    """What one band reports back: its first-appearance count, its null-key
    tally, and whether it saw a key that is not a code.

    A struct rather than three out-parameters so a scan variant cannot forget
    one — `bad` in particular, which is the difference between a typed refusal
    and a wrong answer."""

    var olen: Int
    var nulls: Int
    var bad: Bool

    def __init__(out self, olen: Int, nulls: Int, bad: Bool):
        self.olen = olen
        self.nulls = nulls
        self.bad = bad


@always_inline
def _apply[op: Int](current: Float64, value: Float64, count: Float64) -> Float64:
    """One aggregate's payload update, selected at COMPILE time.

    Every arm is the frozen primitive `observe_op` would have used for that
    opcode, in the same call shape — which is what makes the packed record's
    answer bit-equal to the 64-byte accumulator's. AGG_COUNT touches no
    payload: its answer is the count slot, already updated by the caller."""

    @parameter
    if op == AGG_SUM:
        return group_sum_update(current, value)
    elif op == AGG_AVG:
        return group_mean_update(current, value, count)
    elif op == AGG_MIN:
        return _dense_min_fold(current, value)
    elif op == AGG_MAX:
        return _dense_max_fold(current, value)
    else:
        return current


@always_inline
def _apply_dyn(op: Int, current: Float64, value: Float64, count: Float64) -> Float64:
    """`_apply` reached with a RUNTIME opcode, for the mixed-request scans.

    A thin dispatch onto the same compile-time arms rather than a second copy
    of them. Written this way deliberately: the opcode-to-update mapping was
    spelled out three times in an earlier draft — once per scan variant — and a
    mutation that broke the mean in ONE of the three passed every test, because
    each caller happened to be covered by a different code path. One definition
    per opcode, four callers, and `MAX_UNROLLED_AGGS`-style routing decisions
    can no longer change what an aggregate MEANS."""
    if op == AGG_SUM:
        return _apply[AGG_SUM](current, value, count)
    if op == AGG_AVG:
        return _apply[AGG_AVG](current, value, count)
    if op == AGG_MIN:
        return _apply[AGG_MIN](current, value, count)
    if op == AGG_MAX:
        return _apply[AGG_MAX](current, value, count)
    return current


@always_inline
def _scan_shared[
    op: Int, na: Int
](
    lo: Int,
    hi: Int,
    accw: _RawF64,
    ordw: UnsafePointer[Int, origin=MutAnyOrigin],
    kp: _RawF64,
    vpp: _RawPtrs,
    key_col: Float64Array,
    key_has_nulls: Bool,
    bound: Float64,
    stride: Int,
) -> _BandOutcome:
    """One band, shared-count layout, ONE opcode, `na` aggregates — fully
    unrolled, value pointers in registers.

    The count is read before it is bumped, and `count == 0` at that moment IS
    "this band has not seen this code yet". That shortcut is only sound because
    no value column has nulls on this layout, so every scanned row of a code
    bumps it — which is why the divergent-count layout keeps a `seen` byte.
    """
    var p0 = vpp[0]
    var p1 = p0
    var p2 = p0

    @parameter
    if na > 1:
        p1 = vpp[1]

    @parameter
    if na > 2:
        p2 = vpp[2]
    var olen = 0
    var nulls = 0
    for r in range(lo, hi):
        if key_has_nulls and not key_col.is_valid_at(r):
            nulls += 1
            continue
        var code = _dense_code(kp[r], bound)
        if code < 0:
            # The whole call refuses, so nothing this band saw survives and
            # stopping here loses no information. NEVER a silent early exit:
            # `bad` travels back and the entry point returns a typed refusal.
            return _BandOutcome(olen, nulls, True)
        var base = code * stride
        var c = group_count_update(accw[base])
        accw[base] = c
        if c == 1.0:
            ordw[olen] = code
            olen += 1
        accw[base + 1] = _apply[op](accw[base + 1], p0[r], c)

        @parameter
        if na > 1:
            accw[base + 2] = _apply[op](accw[base + 2], p1[r], c)

        @parameter
        if na > 2:
            accw[base + 3] = _apply[op](accw[base + 3], p2[r], c)
    return _BandOutcome(olen, nulls, False)


@always_inline
def _scan_shared_vec[
    op: Int, na: Int
](
    lo: Int,
    hi: Int,
    accw: _RawF64,
    ordw: UnsafePointer[Int, origin=MutAnyOrigin],
    kp: _RawF64,
    vpp: _RawPtrs,
    key_col: Float64Array,
    key_has_nulls: Bool,
    bound: Float64,
    stride: Int,
) -> _BandOutcome:
    """`_scan_shared` for SUM and AVG with the whole record as ONE SIMD vector.

    The record is `[count, p_0 .. p_{na-1}]` padded to 2 or 4 slots
    (`dense_record_stride`) and the base pointer is 64-byte aligned, so it is
    one aligned 16- or 32-byte vector: a row costs one vector load, one vector
    arithmetic op and one vector store instead of `1 + na` scalar load/store
    pairs. Measured on the H2O q4 shape (three means) in one session:
    3.973 ms scalar against 3.250 ms vectorised at 16 bands.

    The arithmetic is bit-identical to the scalar path lane by lane, and that is
    a property of these two opcodes specifically:

      SUM  lane 0 gets `+ 1.0`, lane j+1 gets `+ v_j` — exactly
           `group_count_update` and `group_sum_update`.
      AVG  every lane computes `cur + (val - cur) / c` with `c` broadcast, which
           is `group_mean_update(cur, val, c)` — the SAME divide, not a
           reciprocal multiply, so no lane moves by an ulp. The frozen
           primitive's `if count <= 0.0` arm is statically unreachable here:
           `c` is the count AFTER the increment, so `c >= 1.0`.

    Lanes the request does not use (the padding slot at na == 2, and lane 0 on
    the AVG path) are fed their OWN current value, so their delta is exactly
    zero and the padding cannot drift into an inf or a NaN across 1e7 rows.

    MIN/MAX stay on the scalar `_scan_shared`: their fold is a select rather
    than an arithmetic op, and q1/q4 — the questions this vector path was
    measured on — do not use them.
    """
    comptime W = 2 if na == 1 else 4
    var p0 = vpp[0]
    var p1 = p0
    var p2 = p0

    @parameter
    if na > 1:
        p1 = vpp[1]

    @parameter
    if na > 2:
        p2 = vpp[2]
    var olen = 0
    var nulls = 0
    for r in range(lo, hi):
        if key_has_nulls and not key_col.is_valid_at(r):
            nulls += 1
            continue
        var code = _dense_code(kp[r], bound)
        if code < 0:
            return _BandOutcome(olen, nulls, True)
        var base = code * stride
        var cur = accw.load[width=W](base)
        var c = cur[0] + 1.0
        if c == 1.0:
            ordw[olen] = code
            olen += 1

        @parameter
        if op == AGG_SUM:
            var inc = SIMD[DType.float64, W](0.0)
            inc[0] = 1.0
            inc[1] = p0[r]

            @parameter
            if na > 1:
                inc[2] = p1[r]

            @parameter
            if na > 2:
                inc[3] = p2[r]
            accw.store(base, cur + inc)
        else:
            var vals = cur
            vals[1] = p0[r]

            @parameter
            if na > 1:
                vals[2] = p1[r]

            @parameter
            if na > 2:
                vals[3] = p2[r]
            var out = cur + (vals - cur) / SIMD[DType.float64, W](c)
            out[0] = c
            accw.store(base, out)
    return _BandOutcome(olen, nulls, False)


@always_inline
def _dispatch_na_vec[
    op: Int
](
    n_aggs: Int,
    lo: Int,
    hi: Int,
    accw: _RawF64,
    ordw: UnsafePointer[Int, origin=MutAnyOrigin],
    kp: _RawF64,
    vpp: _RawPtrs,
    key_col: Float64Array,
    key_has_nulls: Bool,
    bound: Float64,
    stride: Int,
) -> _BandOutcome:
    """Runtime aggregate count to the compile-time `_scan_shared_vec`. Called
    once per band, so the branch is per-band and never per-row. The caller has
    already established `1 <= n_aggs <= MAX_UNROLLED_AGGS`."""
    if n_aggs == 1:
        return _scan_shared_vec[op, 1](
            lo, hi, accw, ordw, kp, vpp, key_col, key_has_nulls, bound, stride
        )
    if n_aggs == 2:
        return _scan_shared_vec[op, 2](
            lo, hi, accw, ordw, kp, vpp, key_col, key_has_nulls, bound, stride
        )
    return _scan_shared_vec[op, 3](
        lo, hi, accw, ordw, kp, vpp, key_col, key_has_nulls, bound, stride
    )


@always_inline
def _dispatch_na[
    op: Int
](
    n_aggs: Int,
    lo: Int,
    hi: Int,
    accw: _RawF64,
    ordw: UnsafePointer[Int, origin=MutAnyOrigin],
    kp: _RawF64,
    vpp: _RawPtrs,
    key_col: Float64Array,
    key_has_nulls: Bool,
    bound: Float64,
    stride: Int,
) -> _BandOutcome:
    """Runtime aggregate count to the compile-time `_scan_shared` (scalar)."""
    if n_aggs == 1:
        return _scan_shared[op, 1](
            lo, hi, accw, ordw, kp, vpp, key_col, key_has_nulls, bound, stride
        )
    if n_aggs == 2:
        return _scan_shared[op, 2](
            lo, hi, accw, ordw, kp, vpp, key_col, key_has_nulls, bound, stride
        )
    return _scan_shared[op, 3](
        lo, hi, accw, ordw, kp, vpp, key_col, key_has_nulls, bound, stride
    )


def _scan_shared_dyn(
    lo: Int,
    hi: Int,
    accw: _RawF64,
    ordw: UnsafePointer[Int, origin=MutAnyOrigin],
    kp: _RawF64,
    vpp: _RawPtrs,
    opp: UnsafePointer[Int, origin=MutAnyOrigin],
    key_col: Float64Array,
    key_has_nulls: Bool,
    bound: Float64,
    stride: Int,
    n_aggs: Int,
) -> _BandOutcome:
    """Shared-count layout with MIXED opcodes or more than `MAX_UNROLLED_AGGS`
    aggregates. Same record, same guard, same first-appearance rule; the
    per-aggregate work is a runtime loop with a runtime opcode branch.

    The opcode branch is per (row, aggregate) rather than hoisted because a
    mixed request has no single opcode to hoist. It is a fully predictable
    branch on a value that does not change within a column, which is why this
    is the fallback rather than a second unrolled family."""
    var olen = 0
    var nulls = 0
    for r in range(lo, hi):
        if key_has_nulls and not key_col.is_valid_at(r):
            nulls += 1
            continue
        var code = _dense_code(kp[r], bound)
        if code < 0:
            return _BandOutcome(olen, nulls, True)
        var base = code * stride
        var c = group_count_update(accw[base])
        accw[base] = c
        if c == 1.0:
            ordw[olen] = code
            olen += 1
        for j in range(n_aggs):
            var idx = base + 1 + j
            accw[idx] = _apply_dyn(opp[j], accw[idx], vpp[j][r], c)
    return _BandOutcome(olen, nulls, False)


def _scan_percol(
    lo: Int,
    hi: Int,
    accw: _RawF64,
    ordw: UnsafePointer[Int, origin=MutAnyOrigin],
    seenw: UnsafePointer[UInt8, origin=MutAnyOrigin],
    kp: _RawF64,
    vpp: _RawPtrs,
    opp: UnsafePointer[Int, origin=MutAnyOrigin],
    vnp: UnsafePointer[UInt8, origin=MutAnyOrigin],
    value_cols: List[Float64Array],
    key_col: Float64Array,
    key_has_nulls: Bool,
    bound: Float64,
    stride: Int,
    n_aggs: Int,
) -> _BandOutcome:
    """One band, DIVERGENT-count layout: some value column has nulls, so each
    aggregate carries its own count and the record is `[c_0, p_0, c_1, p_1, ...]`.

    First appearance needs its own `seen` byte here and cannot reuse the count
    trick: a code whose every value was null still names a group — with count 0
    and no answer for mean/min/max, which is `numeric.contract`'s rule that a
    null is not a zero."""
    var olen = 0
    var nulls = 0
    for r in range(lo, hi):
        if key_has_nulls and not key_col.is_valid_at(r):
            nulls += 1
            continue
        var code = _dense_code(kp[r], bound)
        if code < 0:
            return _BandOutcome(olen, nulls, True)
        if seenw[code] == 0:
            seenw[code] = 1
            ordw[olen] = code
            olen += 1
        var base = code * stride
        for j in range(n_aggs):
            if vnp[j] != 0 and not value_cols[j].is_valid_at(r):
                continue
            var cidx = base + 2 * j
            var idx = cidx + 1
            var c = group_count_update(accw[cidx])
            accw[cidx] = c
            accw[idx] = _apply_dyn(opp[j], accw[idx], vpp[j][r], c)
    return _BandOutcome(olen, nulls, False)


def group_by_coded_dense(
    batch: RecordBatch,
    key_column: Int,
    cardinality: Int,
    value_columns: List[Int],
    opcodes: List[Int],
) -> CodedGroupedResult:
    """`group_by_coded` over a flat packed accumulator. Same answer, same
    status vocabulary, `planned_workers` picking the worker count.

    See the module docstring for what is identical and why. The short version:
    the only thing that changed is where the accumulators live.
    """
    return group_by_coded_dense_parallel(
        batch,
        key_column,
        cardinality,
        value_columns,
        opcodes,
        planned_workers(
            batch.n_rows, info.num_physical_cores() * DENSE_BANDS_PER_CORE
        ),
    )


def group_by_coded_dense_parallel(
    batch: RecordBatch,
    key_column: Int,
    cardinality: Int,
    value_columns: List[Int],
    opcodes: List[Int],
    n_workers: Int,
) -> CodedGroupedResult:
    """`group_by_coded_dense` on an explicit worker count. 1 is the serial path.

    Bands are `ceil(n_rows / workers)` and merge in worker-index order, the
    identical association `group_by_coded_parallel` uses, which is what makes
    the two bit-identical at equal worker count.
    """
    var n_aggs = len(value_columns)
    var n_rows = batch.n_rows
    var key_col = batch.column(key_column)
    var value_cols = List[Float64Array]()
    for j in range(n_aggs):
        value_cols.append(batch.column(value_columns[j]))
    var value_nulls = _col_guard_flags(value_cols, n_rows)
    var shared_count = True
    for j in range(len(value_nulls)):
        if value_nulls[j]:
            shared_count = False

    var workers = n_workers
    if workers < 1:
        workers = 1
    if workers > n_rows:
        workers = n_rows
    if workers < 1:
        workers = 1

    var status = dense_route_status(
        cardinality, value_columns, opcodes, workers, shared_count
    )
    if status != GROUP_CODED_OK:
        return CodedGroupedResult(status, _empty_many())

    var key_has_nulls = key_col.null_count() > 0 or key_col.length < n_rows
    var bound = Float64(cardinality)
    var stride = dense_record_stride(n_aggs, shared_count)
    var region = _pad64(cardinality * stride)

    # ── state: three flat arrays, zero-initialised by construction ───────────
    # `List(length=, fill=)` rather than `alloc` on purpose: every refusal path
    # below returns early, and an owning container cannot leak on one.  The +8
    # is alignment headroom for the 64-byte base.
    var acc = List[Float64](length=workers * region + 8, fill=0.0)
    var acc_raw = acc.unsafe_ptr().as_unsafe_any_origin()
    # Round the base up to a 64-byte boundary so no worker region shares a line
    # with another's and no power-of-two record straddles one — which is what
    # lets `_scan_shared_vec` use aligned vector loads. DEFENSIVE, not assumed:
    # measured on this host the allocator already returns 64-byte-aligned blocks
    # at these sizes (`addr % 64 == 0`, slack 0, over several lengths), so the
    # shim is normally a no-op. It exists because "normally" is not a guarantee,
    # and because an unaligned 32-byte NEON access is a silent slowdown rather
    # than an error, which is the kind of regression nothing would report.
    var slack = (8 - ((Int(acc_raw) // 8) % 8)) % 8
    var accp = acc_raw + slack
    var order = List[Int](length=workers * cardinality, fill=0)
    var ordp = order.unsafe_ptr().as_unsafe_any_origin()
    var seen = List[UInt8](length=1 if shared_count else workers * cardinality, fill=0)
    var seenp = seen.unsafe_ptr().as_unsafe_any_origin()
    var olens = List[Int](length=workers, fill=0)
    var olenp = olens.unsafe_ptr()
    var wnulls = List[Int](length=workers, fill=0)
    var nullp = wnulls.unsafe_ptr()
    var wbad = List[UInt8](length=workers, fill=0)
    var badp = wbad.unsafe_ptr()

    # Raw parallel arrays for the per-aggregate metadata, so the row loop
    # never touches a `List` element accessor.
    var vptrs = List[UnsafePointer[Float64, origin=MutAnyOrigin]](capacity=n_aggs)
    for j in range(n_aggs):
        vptrs.append((value_cols[j].values[].unsafe_ptr() + value_cols[j].offset).as_unsafe_any_origin())
    var vpp = vptrs.unsafe_ptr().as_unsafe_any_origin()
    # A local copy, not `opcodes.unsafe_ptr()`: the parameter's origin is not
    # mutable, and the scans take one raw pointer type.
    var ops_local = opcodes.copy()
    var opp = ops_local.unsafe_ptr().as_unsafe_any_origin()
    var vnulls = List[UInt8](length=n_aggs, fill=0)
    for j in range(n_aggs):
        vnulls[j] = 1 if value_nulls[j] else 0
    var vnp = vnulls.unsafe_ptr().as_unsafe_any_origin()

    # Payload slot of aggregate j inside a record, per layout.
    var pay0 = 1 if shared_count else 1
    var paystep = 1 if shared_count else 2

    # min/max seed their payload to the canonical NaN — "no ordered value yet".
    # Serial and off any hot path: cardinality x n_aggs x workers writes, and
    # only when an extremum was actually requested.
    var nan_seed = _canonical_nan()
    var wants_extremum = False
    for j in range(n_aggs):
        if opcodes[j] == AGG_MIN or opcodes[j] == AGG_MAX:
            wants_extremum = True
    if wants_extremum:
        for w in range(workers):
            var wbase = w * region
            for code in range(cardinality):
                var base = wbase + code * stride
                for j in range(n_aggs):
                    if opcodes[j] == AGG_MIN or opcodes[j] == AGG_MAX:
                        accp[base + pay0 + j * paystep] = nan_seed

    var band = (n_rows + workers - 1) // workers
    var uniform_op = opcodes[0]
    for j in range(1, n_aggs):
        if opcodes[j] != uniform_op:
            uniform_op = -1

    var kp = (key_col.values[].unsafe_ptr() + key_col.offset).as_unsafe_any_origin()

    @parameter
    def dense_worker(w: Int):
        var lo = w * band
        var hi = lo + band
        if hi > n_rows:
            hi = n_rows
        var accw = accp + w * region
        var ordw = ordp + w * cardinality
        var out: _BandOutcome
        if not shared_count:
            out = _scan_percol(
                lo, hi, accw, ordw, seenp + w * cardinality, kp, vpp, opp, vnp,
                value_cols, key_col, key_has_nulls, bound, stride, n_aggs,
            )
        elif n_aggs > MAX_UNROLLED_AGGS or uniform_op < 0:
            out = _scan_shared_dyn(
                lo, hi, accw, ordw, kp, vpp, opp, key_col, key_has_nulls,
                bound, stride, n_aggs,
            )
        elif uniform_op == AGG_SUM:
            out = _dispatch_na_vec[AGG_SUM](
                n_aggs, lo, hi, accw, ordw, kp, vpp, key_col, key_has_nulls,
                bound, stride,
            )
        elif uniform_op == AGG_AVG:
            out = _dispatch_na_vec[AGG_AVG](
                n_aggs, lo, hi, accw, ordw, kp, vpp, key_col, key_has_nulls,
                bound, stride,
            )
        elif uniform_op == AGG_MIN:
            out = _dispatch_na[AGG_MIN](
                n_aggs, lo, hi, accw, ordw, kp, vpp, key_col, key_has_nulls,
                bound, stride,
            )
        elif uniform_op == AGG_MAX:
            out = _dispatch_na[AGG_MAX](
                n_aggs, lo, hi, accw, ordw, kp, vpp, key_col, key_has_nulls,
                bound, stride,
            )
        else:
            out = _dispatch_na[AGG_COUNT](
                n_aggs, lo, hi, accw, ordw, kp, vpp, key_col, key_has_nulls,
                bound, stride,
            )
        olenp[w] = out.olen
        nullp[w] = out.nulls
        badp[w] = 1 if out.bad else 0

    parallelize[dense_worker](workers)
    # Keep every container whose RAW pointer the closure captured alive past the
    # join. Mojo destroys a value after its last USE, and `unsafe_ptr()` is not
    # one -- rule 1b's use-after-free, in the one shape a JIT suite hides.
    _ = len(vptrs) + len(vnulls) + len(ops_local) + len(acc) + len(order) + len(seen)

    for w in range(workers):
        if wbad[w] != 0:
            return CodedGroupedResult(GROUP_CODED_KEY_NOT_A_CODE, _empty_many())

    # ── global first-appearance order: workers in band order, each worker's
    #    local list already in first-appearance order. `group_by_coded_parallel`
    #    composes it exactly this way. ──────────────────────────────────────
    var g_seen = List[UInt8](length=cardinality, fill=0)
    var g_order = List[Int]()
    var null_key_rows = 0
    for w in range(workers):
        null_key_rows += wnulls[w]
        var obase = w * cardinality
        for i in range(olens[w]):
            var code = order[obase + i]
            if g_seen[code] == 0:
                g_seen[code] = 1
                g_order.append(code)

    # ── merge: the SHIPPED `merge_from`, per (code, aggregate), in worker-index
    #    order. Unpacking into a `GroupAccumulator` and calling the real merge
    #    is what makes the association identical rather than merely similar —
    #    including the copy-on-empty branch, which is not the same as folding
    #    from zero (0.0 + -0.0 is +0.0). O(groups x aggs x workers), never rows.
    var key_tuples = List[Float64](capacity=len(g_order))
    var out_stripes = List[GroupAccumulator](capacity=len(g_order) * n_aggs)
    for i in range(len(g_order)):
        var code = g_order[i]
        key_tuples.append(Float64(code))
        for j in range(n_aggs):
            var op = opcodes[j]
            var acc = GroupAccumulator(Float64(code))
            for w in range(workers):
                var base = w * region + code * stride
                var cidx = base if shared_count else base + 2 * j
                var c = accp[cidx]
                if c == 0.0:
                    # An empty side moves nothing — `merge_from`'s own first
                    # branch. Skipping it is that branch, not a shortcut past it.
                    continue
                var p = accp[base + pay0 + j * paystep]
                var other = GroupAccumulator(Float64(code))
                other.count = c
                if op == AGG_SUM:
                    other.total = p
                elif op == AGG_AVG:
                    other.mean = p
                elif op == AGG_MIN:
                    other.seen = p == p
                    other.minimum = p if other.seen else 0.0
                elif op == AGG_MAX:
                    other.seen = p == p
                    other.maximum = p if other.seen else 0.0
                acc.merge_from(other)
            out_stripes.append(acc^)

    return CodedGroupedResult(
        GROUP_CODED_OK,
        _finish_many(key_tuples, 1, out_stripes, n_aggs, opcodes, null_key_rows),
    )
