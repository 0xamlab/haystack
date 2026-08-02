"""query.topk_dense — grouped TOP-2 over a single dense integral code column.

Additive to `query.coded_dense`; nothing there changes. Where `coded_dense`
answers "one number per group" (sum/mean/min/max/count), this answers "the two
largest raw VALUES per group" — the H2O db-benchmark's q8 shape
(`largest two v3 by id6`, ~100 000 groups at the 0.5 GB tier). No existing
engine in this plane can answer it: `GroupAccumulator` keeps a running
extremum, not a running top-k, and there is no accumulator field a k=2
selection could read back out of.

Why dense direct-index, again
------------------------------
Same argument `coded_dense`'s header makes: `id6` is already integral dictionary
codes in `[0, N/K)`, so the accumulator array is indexed by the code itself —
no hash, no probe. The per-group state is TWO Float64 payload slots
(`top1 >= top2`) instead of one, which is the only shape difference from a MAX
aggregate.

The fold is comparison-only, and that is the whole reason ordering never
depends on band count
------------------------------------------------------------------------------
`_fold_top2` performs no arithmetic that could reassociate — every operation is
a `>=` compare and a slot write. Two independent partitions' top-2 sets fold
into the union's top-2 by feeding one partition's pair through the other's
fold (`_accumulate_top2`), and the RESULT VALUES this produces do not depend on
which partition is folded into which, or in what order — unlike a sum or a
Welford mean, there is no floating-point association to drift. What CAN differ
across implementations is which of two bit-identical duplicate values is
labelled "first" when v3 ties exactly; H2O's v3 is a continuous
`round(uniform(0,100), 6)`, so an exact duplicate inside one 100-row group is
astronomically unlikely, and this module does not depend on it being absent —
a tie simply reports the same value twice, which is a correct answer to
"the two largest values" either way.

The seed, and why it needs its own array rather than the count trick
----------------------------------------------------------------------
`coded_dense`'s shared-count layout uses `count == 0` as "unseen" for free.
That shortcut needs every live row of a code to bump the SAME count, which is
true for a single independent aggregate but not obviously safe here once NaN
values are in play: a code whose only rows so far were NaN would have `top1`
still unseeded while a naive count-based "seen" flag would already say
otherwise. `_fold_top2` is defined to reject NaN outright (a NaN value ranks
nothing, matching this plane's extremum policy — see `query.aggregate`'s "NaN
values and the extrema"), so a `seen` byte array — `_scan_percol`'s idiom, not
`coded_dense`'s — is the correctness-preserving choice: first appearance is a
fact about ROWS, not about whether a value happened to rank.

What this promises
-------------------
Bit-for-bit reproducible at a fixed worker count (no drift possible: see
above), band-order first-appearance group ordering identical to every other
engine in this plane, and a typed refusal — never an out-of-bounds write — on
a key that is not a code, exactly `coded_dense`'s safety argument.
"""
from std.algorithm import parallelize
from std.sys import info

from columnar.array import Float64Array
from columnar.batch import RecordBatch
from query.aggregate import (
    GROUP_CODED_BAD_REQUEST,
    GROUP_CODED_CARDINALITY_INVALID,
    GROUP_CODED_KEY_NOT_A_CODE,
    GROUP_CODED_OK,
    _canonical_nan,
    planned_workers,
)
from query.coded_dense import DENSE_MAX_CARDINALITY, _dense_code, _pad64

# ── status: continuing query's 330-339 block. 330-333 query.aggregate's,
#    334/335 coded_dense's, 336 packedkey's. 337 is the next free slot. ──────
comptime GROUP_TOPK_STATE_TOO_LARGE: Int = 337
"""`workers x cardinality x 2` payload floats, plus bookkeeping, would exceed
`TOPK_MAX_STATE_BYTES`."""

comptime TOPK_MAX_STATE_BYTES: Int = 64 << 20
"""Mirrors `coded_dense.DENSE_MAX_STATE_BYTES`: 64 MiB of transient per-call
scratch, an eighth of the 512 MiB single-object resident budget. The payload
here is narrower than `coded_dense`'s widest record (2 slots against up to 4),
so this budget admits MORE codes at the same worker count, not fewer."""


fn topk_status_name(status: Int) -> String:
    """The vocabulary this module can return, including query.aggregate's."""
    if status == GROUP_CODED_OK:
        return "ok"
    if status == GROUP_CODED_CARDINALITY_INVALID:
        return "cardinality_invalid"
    if status == GROUP_CODED_KEY_NOT_A_CODE:
        return "key_not_a_code"
    if status == GROUP_CODED_BAD_REQUEST:
        return "bad_request"
    if status == GROUP_TOPK_STATE_TOO_LARGE:
        return "state_too_large"
    return "unknown"


fn topk_state_bytes(cardinality: Int, workers: Int) -> Int:
    """Every byte `group_top2_dense_parallel` allocates, worst case.

    Three arrays, rule 1c: the payload (`workers x pad64(cardinality*2)` Float64s),
    the per-worker first-appearance order list (`workers x cardinality` Ints,
    worst case every worker sees every code) and the `seen` bitmap
    (`workers x cardinality` bytes).
    """
    if cardinality <= 0 or workers <= 0:
        return 0
    var payload = workers * _pad64(cardinality * 2) * 8
    var order = workers * cardinality * 8
    var seen = workers * cardinality
    return payload + order + seen


fn topk_route_status(cardinality: Int, workers: Int) -> Int:
    """Whether this route will accept the request, decided from shape alone —
    nothing allocated, nothing scanned. `group_top2_dense_parallel` calls
    exactly this, so a router's decision and the engine's decision cannot
    drift apart."""
    if cardinality <= 0 or cardinality > DENSE_MAX_CARDINALITY:
        return GROUP_CODED_CARDINALITY_INVALID
    var w = workers if workers > 0 else 1
    if topk_state_bytes(cardinality, w) > TOPK_MAX_STATE_BYTES:
        return GROUP_TOPK_STATE_TOO_LARGE
    return GROUP_CODED_OK


@always_inline
fn _fold_top2(mut top1: Float64, mut top2: Float64, value: Float64):
    """Fold one candidate value into a running (largest, second-largest) pair,
    IN PLACE.

    `top1`/`top2` are the canonical NaN when unseeded — `current != current` is
    the "no ordered value yet" test `coded_dense._dense_min_fold` uses, and this
    module never writes a NaN candidate INTO the pair (the first branch below
    rejects it), so the sentinel can never be confused with a value someone
    actually observed. Ties keep the EARLIER value in `top1`: `value >= top1`
    only fires strictly greater once `top1` is seeded, and the seeding branch
    (`not (top1 == top1)`) takes any first real value including one equal to
    an old `top2` — see the suite's tie block for why `>=` at the top and `>=`
    at the second slot both have to hold for a three-way tie to land all three
    correctly ranked.
    """
    if value != value:
        # NaN ranks nothing — this plane's extremum policy, unchanged.
        return
    if not (top1 == top1):
        # First real value this pair has ever seen.
        top1 = value
        return
    if value >= top1:
        top2 = top1
        top1 = value
        return
    if not (top2 == top2) or value >= top2:
        top2 = value


fn _accumulate_top2(mut m1: Float64, mut m2: Float64, b1: Float64, b2: Float64):
    """Fold ANOTHER (b1, b2) top-2 pair into the running accumulator (m1, m2),
    in place — the union-of-partitions merge.

    Correct because the union's top-2 can only be drawn from the accumulator's
    own top-2 so far plus the four candidates the new partition narrowed down
    to — folding `b1` then `b2` through `_fold_top2` reproduces exactly that
    selection, and `_fold_top2` performs no arithmetic, so the RESULT is the
    same whichever fixed order a caller folds partitions in (see the module
    header).
    """
    _fold_top2(m1, m2, b1)
    _fold_top2(m1, m2, b2)


fn _top2_reference(values: List[Float64], mut top1: Float64, mut top2: Float64) -> Int:
    """The two largest ORDERED values in `values`, by a full scan — the
    reference `_fold_top2`/`_accumulate_top2` are checked against, spelled with no
    cleverness: track (top1, top2) with an explicit `seen` count rather than a
    NaN sentinel, so this and the fast fold cannot share a bug.

    Writes into `top1`/`top2` and returns `ranked_count`: how many of them are
    real (0, 1 or 2), which the caller reads as `present1`/`present2`.
    """
    top1 = 0.0
    top2 = 0.0
    var seen = 0
    for i in range(len(values)):
        var v = values[i]
        if v != v:
            continue
        if seen == 0:
            top1 = v
            seen = 1
        elif seen == 1:
            if v >= top1:
                top2 = top1
                top1 = v
            else:
                top2 = v
            seen = 2
        else:
            if v >= top1:
                top2 = top1
                top1 = v
            elif v >= top2:
                top2 = v
    return seen


struct Top2GroupedResult(Copyable, Movable):
    """One dense key column's groups, each with its top-2 ranked values.

    `key_tuples` holds the dense code (as a Float64) of each group, in global
    first-appearance order — the same convention every other engine in this
    plane uses. `top1[g] >= top2[g]` whenever both are present.
    """

    var key_tuples: List[Float64]
    var top1: List[Float64]
    var top2: List[Float64]
    var present1: List[Bool]
    var present2: List[Bool]
    var null_key_rows: Int

    fn __init__(
        out self,
        var key_tuples: List[Float64],
        var top1: List[Float64],
        var top2: List[Float64],
        var present1: List[Bool],
        var present2: List[Bool],
        null_key_rows: Int,
    ):
        self.key_tuples = key_tuples^
        self.top1 = top1^
        self.top2 = top2^
        self.present1 = present1^
        self.present2 = present2^
        self.null_key_rows = null_key_rows

    fn n_groups(self) -> Int:
        return len(self.key_tuples)


fn _empty_top2() -> Top2GroupedResult:
    return Top2GroupedResult(
        List[Float64](), List[Float64](), List[Float64](), List[Bool](), List[Bool](), 0
    )


struct CodedTop2Result(Copyable, Movable):
    """A `Top2GroupedResult` plus the status that says whether it exists —
    `query.aggregate.CodedGroupedResult`'s shape, reused deliberately."""

    var status: Int
    var result: Top2GroupedResult

    fn __init__(out self, status: Int, var result: Top2GroupedResult):
        self.status = status
        self.result = result^

    fn ok(self) -> Bool:
        return self.status == GROUP_CODED_OK


fn group_top2_dense(
    batch: RecordBatch, key_column: Int, cardinality: Int, value_column: Int
) -> CodedTop2Result:
    """The two largest values of `value_column` per code in `key_column`.
    `planned_workers` picks the worker count."""
    return group_top2_dense_parallel(
        batch, key_column, cardinality, value_column,
        planned_workers(batch.n_rows, info.num_physical_cores()),
    )


fn group_top2_dense_parallel(
    batch: RecordBatch, key_column: Int, cardinality: Int, value_column: Int,
    n_workers: Int,
) -> CodedTop2Result:
    """`group_top2_dense` on an explicit worker count. 1 is the serial path.

    Bands are `ceil(n_rows / workers)`, identical to every other engine here,
    so this module's group ORDER matches theirs group for group on the same
    data. The fold has no floating-point association to preserve (see the
    module header), so unlike `coded_dense` there is no separate "bit-identical
    at equal worker count" claim to make beyond determinism itself.
    """
    var n_rows = batch.n_rows
    var key_col = batch.column(key_column)
    var value_col = batch.column(value_column)

    var workers = n_workers
    if workers < 1:
        workers = 1
    if workers > n_rows:
        workers = n_rows
    if workers < 1:
        workers = 1

    var status = topk_route_status(cardinality, workers)
    if status != GROUP_CODED_OK:
        return CodedTop2Result(status, _empty_top2())

    var key_has_nulls = key_col.null_count() > 0 or key_col.length < n_rows
    var value_has_nulls = value_col.null_count() > 0 or value_col.length < n_rows
    var bound = Float64(cardinality)
    var region = _pad64(cardinality * 2)

    var payload = List[Float64](length=workers * region, fill=0.0)
    var nan_seed = _canonical_nan()
    for i in range(len(payload)):
        payload[i] = nan_seed
    var payp = payload.unsafe_ptr()
    var order = List[Int](length=workers * cardinality, fill=0)
    var ordp = order.unsafe_ptr()
    var seen = List[UInt8](length=workers * cardinality, fill=0)
    var seenp = seen.unsafe_ptr()
    var olens = List[Int](length=workers, fill=0)
    var olenp = olens.unsafe_ptr()
    var wnulls = List[Int](length=workers, fill=0)
    var nullp = wnulls.unsafe_ptr()
    var wbad = List[UInt8](length=workers, fill=0)
    var badp = wbad.unsafe_ptr()

    var band = (n_rows + workers - 1) // workers
    var kp = key_col.values[].unsafe_ptr() + key_col.offset
    var vp = value_col.values[].unsafe_ptr() + value_col.offset

    @parameter
    fn topk_worker(w: Int):
        var lo = w * band
        var hi = lo + band
        if hi > n_rows:
            hi = n_rows
        var payw = payp + w * region
        var ordw = ordp + w * cardinality
        var seenw = seenp + w * cardinality
        var olen = 0
        var nulls = 0
        var bad = False
        for r in range(lo, hi):
            if key_has_nulls and not key_col.is_valid_at(r):
                nulls += 1
                continue
            var code = _dense_code(kp[r], bound)
            if code < 0:
                bad = True
                break
            if seenw[code] == 0:
                seenw[code] = 1
                ordw[olen] = code
                olen += 1
            if value_has_nulls and not value_col.is_valid_at(r):
                continue
            var base = code * 2
            var t1 = payw[base]
            var t2 = payw[base + 1]
            _fold_top2(t1, t2, vp[r])
            payw[base] = t1
            payw[base + 1] = t2
        olenp[w] = olen
        nullp[w] = nulls
        badp[w] = 1 if bad else 0

    parallelize[topk_worker](workers)
    _ = len(payload) + len(order) + len(seen)

    for w in range(workers):
        if wbad[w] != 0:
            return CodedTop2Result(GROUP_CODED_KEY_NOT_A_CODE, _empty_top2())

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

    var n_groups = len(g_order)
    var key_tuples = List[Float64](capacity=n_groups)
    var top1_out = List[Float64](capacity=n_groups)
    var top2_out = List[Float64](capacity=n_groups)
    var present1_out = List[Bool](capacity=n_groups)
    var present2_out = List[Bool](capacity=n_groups)
    for i in range(n_groups):
        var code = g_order[i]
        key_tuples.append(Float64(code))
        var m1 = nan_seed
        var m2 = nan_seed
        for w in range(workers):
            var base = w * region + code * 2
            _accumulate_top2(m1, m2, payload[base], payload[base + 1])
        top1_out.append(m1 if m1 == m1 else 0.0)
        top2_out.append(m2 if m2 == m2 else 0.0)
        present1_out.append(m1 == m1)
        present2_out.append(m2 == m2)

    return CodedTop2Result(
        GROUP_CODED_OK,
        Top2GroupedResult(
            key_tuples^, top1_out^, top2_out^, present1_out^, present2_out^,
            null_key_rows,
        ),
    )
