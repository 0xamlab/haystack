"""composed.mojo — ONE route for a grouped aggregate, composed from the pieces
that each won a piece of the H2O group-by suite, plus the cost none of them
attacked.

WHY A COMPOSED MODULE AND NOT FOUR ENGINES. Four separate attacks each beat the
shipped route on a different question, and each was measured in its own window
against its own reference. A page cannot publish four engines: a caller names a
question, not an engine. This module is the single decision — probe, choose,
answer — and it is the thing that gets measured, because composition can lose
what the pieces won and only the composed number is honest.

WHAT EACH PIECE CONTRIBUTES, and it is imported rather than re-implemented:

  `query.coded_dense`   the flat packed accumulator record and its four band
                        scans (`_scan_shared_vec` / `_scan_shared` /
                        `_scan_shared_dyn` / `_scan_percol`), plus the ONE key
                        guard `_dense_code`. Won q1 and q4.
  `query.packedkey`     the hash-free mixed-radix domain probe and the packed
                        composite-key engine. Won q2, the only question whose
                        key is two columns.
  `query.aggregate_late`the fused late-materialised radix engine, kept as the
                        fallback for a key domain that is genuinely not dense.
  `query.aggregate`     everything frozen: `GroupAccumulator.merge_from`,
                        `has_answer`, `value_for`, `_col_guard_flags`,
                        `group_by_many_parallel`. The NaN policy arrives from
                        here by construction, not by restatement.

WHAT THE COMPOSITION ADDS — three costs that only show up once the pieces are
put together, and that no individual attack could see:

  1. THE MERGE, PARALLELISED. Every dense attack shrank the SCAN. At K=100 the
     O(groups x aggregates x bands) merge is 4800 folds and invisible. At the
     1e5-code questions (q3/q5/q7) it is 1.6M-4.8M folds, each reading a
     different 3.2 MB worker region, and the sibling measurements put it at
     8-12 ms of an 18-25 ms call — i.e. the single largest remaining term, and
     a purely SERIAL one. It parallelises over GROUP RANGES, which is the one
     decomposition that keeps the answer bit-identical: each group's fold over
     workers stays in ascending worker order, untouched. The threshold is
     measured, not assumed, because an empty `parallelize` on this host costs
     0.44-0.53 ms under load and would swamp q1.

  2. THE EXTREMUM SEED, PARALLELISED. min/max seed every (worker, code,
     aggregate) payload to the canonical NaN. At K=100 that is 1600 writes; at
     q7's shape it is 100001 x 2 x 16 = 3.2M SERIAL writes before the scan can
     start. Each worker seeds only its own private region, inside the band it
     already owns, so the cost disappears into the existing fan-out with no
     second `parallelize`.

  3. THE WORKER COUNT IS PART OF THE ROUTE. `group_by_coded_dense` asks for
     `cores * DENSE_BANDS_PER_CORE` = 32 bands, at which the 64 MiB dense state
     budget REFUSES 1e5 codes outright (measured: 122 MiB at 32, 61 MiB at 16).
     A composed router that did not cap the band count would silently fall back
     on exactly the three questions the dense record was extended to reach.
     `compose_dense_workers` is that cap and it is public and pure.

  Two smaller ones, recorded because composition is where they surfaced:
  `packedkey` and `coded_dense` both claimed status 334 for different refusals
  — fixed at the source (packedkey moved to 336) with `compose_status_name` as
  the registry that now proves the 330-339 block has no duplicate; and the
  `_finish_many` extraction is fused INTO the parallel merge, so the 1e5-group
  questions no longer materialise 19 MB of intermediate `GroupAccumulator`
  stripes only to walk them again.

CORRECTNESS. Every route this module can choose is bit-identical to an engine
that already shipped, at the worker count the plan names:

  DENSE  == `group_by_coded_dense_parallel(..., plan.workers)`
         == `group_by_coded_parallel(..., plan.workers)`
         == `group_by_many` on the H2O shapes
  PACKED == `group_by_packed_parallel(..., plan.workers)` == `group_by_many`
  LATE   == `group_by_many_radix_fused` == `group_by_many_radix` == `group_by_many`
  SHIPPED is `group_by_many_parallel` itself.

The parallel merge is bit-identical to the serial merge and not merely close:
the fold sequence per group is unchanged, and the suite pins the two against
each other over signed zeros, both NaN payloads, infinities and Welford means,
on bit patterns rather than on `==`.

BOUNDS. A key that is not a code refuses the whole call and the router answers
with the shipped engine — it never writes out of the dense array, because
`_dense_code` decides that in ONE place and the band reports a flag rather than
storing. That discipline is load-bearing, not stylistic: an index past the end
of a Mojo buffer fires an assertion that kills the worker process and `try` does
not contain it.
"""
from max.algorithm import parallelize
from std.sys import info

from columnar.array import Float64Array
from columnar.batch import RecordBatch
from numeric.contract import AGG_AVG, AGG_COUNT, AGG_MAX, AGG_MIN, AGG_SUM
from query.aggregate import (
    CodedGroupedResult,
    GROUP_CODED_BAD_REQUEST,
    GROUP_CODED_CARDINALITY_INVALID,
    GROUP_CODED_KEY_NOT_A_CODE,
    GROUP_CODED_OK,
    GroupAccumulator,
    ManyGroupedResult,
    _canonical_nan,
    _col_guard_flags,
    _empty_many,
    _many_request_ok,
    group_by_many_parallel,
    planned_workers,
)
from query.aggregate_late import fused_late_applicable, group_by_many_radix_fused
from query.coded_dense import (
    DENSE_BANDS_PER_CORE,
    DENSE_MAX_CARDINALITY,
    DENSE_MAX_STATE_BYTES,
    GROUP_DENSE_OPCODE_UNSUPPORTED,
    GROUP_DENSE_STATE_TOO_LARGE,
    _BandOutcome,
    _RawF64,
    _RawPtrs,
    _dispatch_na,
    _dispatch_na_vec,
    _pad64,
    _scan_percol,
    _scan_shared_dyn,
    dense_record_stride,
    dense_route_status,
    dense_state_bytes,
    dense_supports_opcode,
)
from query.packedkey import (
    GROUP_PACKED_DOMAIN_TOO_LARGE,
    PackedDomain,
    group_by_packed_parallel,
    packed_route_ok,
    probe_packed_domain,
)

# ── the routes, as a closed set ───────────────────────────────────────────────
comptime COMPOSE_ROUTE_DENSE: Int = 1
"""One key column over a dense integral code domain: the flat packed record."""
comptime COMPOSE_ROUTE_PACKED: Int = 2
"""Several key columns whose integral spans multiply to a dense slot space."""
comptime COMPOSE_ROUTE_LATE: Int = 3
"""One key column, not dense, high cardinality: fused late-materialised radix."""
comptime COMPOSE_ROUTE_SHIPPED: Int = 4
"""Nothing above claims it — the shipped `group_by_many_parallel` answers."""


def compose_route_name(route: Int) -> String:
    """The route vocabulary, so a bench or a log prints a name and not a digit."""
    if route == COMPOSE_ROUTE_DENSE:
        return "dense"
    if route == COMPOSE_ROUTE_PACKED:
        return "packed"
    if route == COMPOSE_ROUTE_LATE:
        return "late"
    if route == COMPOSE_ROUTE_SHIPPED:
        return "shipped"
    return "unknown"


def compose_status_name(status: Int) -> String:
    """THE registry for the query plane's 330-339 status block.

    Its real job is to be the one place a duplicate is visible. Composing
    `coded_dense` and `packedkey` turned up two different refusals both numbered
    334, which no single-module test could see because each module's own
    `*_status_name` was internally consistent. The suite walks 330..339 through
    this function and asserts every name is distinct, so the next module that
    claims a taken number fails a test instead of shipping an ambiguity.
    """
    if status == GROUP_CODED_OK:
        return "ok"
    if status == GROUP_CODED_CARDINALITY_INVALID:
        return "cardinality_invalid"
    if status == GROUP_CODED_KEY_NOT_A_CODE:
        return "key_not_a_code"
    if status == GROUP_CODED_BAD_REQUEST:
        return "bad_request"
    if status == GROUP_DENSE_OPCODE_UNSUPPORTED:
        return "dense_opcode_unsupported"
    if status == GROUP_DENSE_STATE_TOO_LARGE:
        return "dense_state_too_large"
    if status == GROUP_PACKED_DOMAIN_TOO_LARGE:
        return "packed_domain_too_large"
    return "unassigned"


comptime COMPOSE_PROBE_ROWS: Int = 65_536
"""Rows in the cheap domain probe window, matching `CARDINALITY_PROBE_ROWS`."""

comptime COMPOSE_EXACT_DOMAIN_MIN_SPAN: Int = 4_096
"""Probed span at or above which the composed route pays for an EXACT domain
scan of the whole key column instead of trusting the probe window.

Not a tuning knob — a correctness-of-*routing* threshold with an argument. The
probe window is `COMPOSE_PROBE_ROWS` rows. If the true domain holds K values
roughly uniformly, the chance the window never sees the maximum is
`(1 - 1/K)^65536`: at K = 100 that is e^-655, i.e. never, so the window's
maximum IS the domain's and a probe-derived bound is safe and free. At
K = 100000 it is e^-0.66 = 52%, so a probe-derived bound would send half of all
1e5-code calls into a full wasted dense scan that then refuses on a key past
the bound and falls back. The refusal is safe either way — that is what the
guard is for — but a route that is only 48% available is not a route.

So: below the line, trust the window. At or above it, spend one parallel
min/max/integrality pass over the key column (80 MB, ~0.5 ms of the 20-40 ms
those questions cost) and get a bound that CANNOT refuse. 4096 is
`MAX_CODED_CARDINALITY`, the span at which the shipped router already stops
believing a dense array is the answer, so the composed route changes its mind
at exactly the same place rather than inventing a second boundary."""

comptime COMPOSE_FOLD_ESTIMATE_CEILING: Int = 1 << 40
"""Saturation ceiling for `compose_merge_folds`, so a nonsense shape cannot
multiply its way round the Int and come out as a small number.

Its OWN constant and not a multiple of the threshold below. It WAS a multiple,
and mutation M9 — which sets the threshold to 0 to check that the parallel
merge is a pure performance switch — collapsed the saturation ceiling to 0 with
it, turning an overflow guard off as a side effect of a tuning change. A safety
bound that moves when a tuning knob moves is not a safety bound."""

comptime COMPOSE_PARALLEL_MERGE_MIN_FOLDS: Int = 262_144
"""Accumulator folds (`groups x aggregates x workers`) at or above which the
merge is worth a fan-out.

Measured, and measured against a hostile constant: an EMPTY `parallelize` on
this host under load costs 0.44-0.53 ms (the sibling attack measured it twice
and deleted a fan-out because of it). q1's merge is 100 x 1 x 16 = 1600 folds
and takes microseconds, so fanning it out would be a pure 0.5 ms loss on a
2 ms query. q3's is 100000 x 2 x 16 = 3.2M folds. 262144 sits between them by
two orders of magnitude on each side, so the exact value cannot matter — which
is the property a threshold should have. Both sides of it produce the SAME
BITS, so it is a performance switch only and the suite proves that."""


@always_inline
def compose_dense_workers(
    cardinality: Int, n_aggs: Int, shared_count: Bool, requested: Int
) -> Int:
    """The largest worker count <= `requested` whose dense state fits the budget,
    or 0 when even one worker does not fit.

    Public and pure because it is the composition's third finding: the dense
    record reaches 1e5 codes only at a capped band count.
    `group_by_coded_dense`'s own default of `cores * DENSE_BANDS_PER_CORE` = 32
    is REFUSED there (122 MiB against a 64 MiB budget), so a router that did not
    cap would fall back on precisely the questions the dense record was widened
    to reach.

    Counts DOWN by one rather than halving. The first version halved — the
    budget is monotone in the worker count, so halving finds *an* admissible
    count and looks correct. It is not: at `requested = 17` it returns 8, while
    `requested = 16` returns 16, so asking for MORE parallelism silently
    delivered half of it. The suite's monotonicity check caught that (a
    property test, not an example), and the fix is to search the actual answer.
    `requested` is a band count — a small multiple of the core count — so the
    linear walk is at most a few dozen cheap arithmetic checks, once per call.
    """
    if cardinality <= 0 or n_aggs <= 0:
        return 0
    var w = requested
    if w < 1:
        w = 1
    while w >= 1:
        if dense_state_bytes(cardinality, n_aggs, w, shared_count) <= DENSE_MAX_STATE_BYTES:
            return w
        w -= 1
    return 0


@always_inline
def compose_merge_folds(n_groups: Int, n_aggs: Int, workers: Int) -> Int:
    """Accumulator folds the merge will perform — the parallel-merge decision's
    input, saturating rather than wrapping so a nonsense shape cannot come out
    the far side as a small number."""
    if n_groups <= 0 or n_aggs <= 0 or workers <= 0:
        return 0
    var lim = COMPOSE_FOLD_ESTIMATE_CEILING
    var a = n_groups
    if a > lim:
        return lim
    a = a * n_aggs
    if a > lim:
        return lim
    a = a * workers
    if a > lim:
        return lim
    return a


struct ComposedPlan(Copyable, Movable):
    """The whole routing decision, as data.

    Separate from the engines so a test can assert WHICH route a shape gets
    without running it, and so a bench can print the route next to the time. A
    router whose decision is only observable as a duration is a router nobody
    can gate.
    """

    var route: Int
    var workers: Int
    """The worker count the chosen engine will be called with. Bit-identity to a
    reference engine is per worker count, so this is the number a test must pass
    to the reference — publishing it is what makes the identity claim checkable
    rather than approximate."""
    var cardinality: Int
    """Dense code bound for the DENSE route (codes are absolute, so this is
    max+1 and low unused codes are simply wasted slots); 0 otherwise."""
    var domain: PackedDomain
    """Probed mixed-radix domain for the PACKED route; an invalid domain
    otherwise."""
    var shared_count: Bool
    var parallel_merge: Bool
    var exact_domain: Bool
    """Whether the DENSE bound came from a full pass over the key column rather
    than from the probe window. Reported so the extra pass is visible in a
    measurement instead of hiding inside the total."""
    var status: Int
    """Why a route was NOT taken, when that is interesting; `GROUP_CODED_OK`
    when the chosen route claimed the call outright."""

    def __init__(
        out self,
        route: Int,
        workers: Int,
        cardinality: Int,
        var domain: PackedDomain,
        shared_count: Bool,
        parallel_merge: Bool,
        exact_domain: Bool,
        status: Int,
    ):
        self.route = route
        self.workers = workers
        self.cardinality = cardinality
        self.domain = domain^
        self.shared_count = shared_count
        self.parallel_merge = parallel_merge
        self.exact_domain = exact_domain
        self.status = status

    def describe(self) -> String:
        return (
            compose_route_name(self.route)
            + " workers=" + String(self.workers)
            + " cardinality=" + String(self.cardinality)
            + " slots=" + String(self.domain.slots)
            + " shared_count=" + String(self.shared_count)
            + " parallel_merge=" + String(self.parallel_merge)
            + " exact_domain=" + String(self.exact_domain)
            + " status=" + compose_status_name(self.status)
        )


struct _ExactDomain(Copyable, Movable):
    """A key column's true integral range, or a reason there isn't one."""

    var dense: Bool
    var bound: Int
    """max + 1, so it is exactly the `cardinality` the dense array needs."""

    def __init__(out self, dense: Bool, bound: Int):
        self.dense = dense
        self.bound = bound


def compose_exact_domain(
    batch: RecordBatch, key_column: Int, n_workers: Int
) -> _ExactDomain:
    """The key column's exact `[0, max+1)` code bound, in one parallel pass, or
    `dense=False` when some live key is not a non-negative in-range integer.

    Every rejection is decided in float before any conversion, in the same order
    `_dense_code` uses, so this function and the guard cannot disagree about
    what a code is: NaN and negatives fail `not (k >= 0.0)` (spelled that way
    because `k < 0.0` is FALSE for NaN), +inf and anything past
    `DENSE_MAX_CARDINALITY` fail the ceiling test before `Int(k)` is reached,
    and `Float64(code) != k` rejects a fractional value that would otherwise
    alias onto its truncation's group.

    Nulls are skipped: a null key is not a code, it is tallied as
    `null_key_rows`, which is the frozen contract's rule and the scans' own.
    """
    var n_rows = batch.n_rows
    var key_col = batch.column(key_column)
    if n_rows <= 0:
        return _ExactDomain(True, 1)
    var workers = n_workers
    if workers < 1:
        workers = 1
    if workers > n_rows:
        workers = n_rows
    var band = (n_rows + workers - 1) // workers
    var maxes = List[Int](length=workers, fill=0)
    var oks = List[UInt8](length=workers, fill=1)
    var maxp = maxes.unsafe_ptr()
    var okp = oks.unsafe_ptr()
    var has_nulls = key_col.null_count() > 0 or key_col.length < n_rows
    var ceiling = Float64(DENSE_MAX_CARDINALITY)
    var kp = (key_col.values[].unsafe_ptr() + key_col.offset).as_unsafe_any_origin()

    @parameter
    def domain_worker(w: Int):
        var lo = w * band
        var hi = lo + band
        if hi > n_rows:
            hi = n_rows
        var local_max = 0
        var ok = True
        for r in range(lo, hi):
            if has_nulls and not key_col.is_valid_at(r):
                continue
            var k = kp[r]
            if not (k >= 0.0) or k >= ceiling:
                ok = False
                break
            var code = Int(k)
            if Float64(code) != k:
                ok = False
                break
            if code > local_max:
                local_max = code
        maxp[w] = local_max
        okp[w] = 1 if ok else 0

    parallelize[domain_worker](workers)
    # Keep the containers whose RAW pointers the closure captured alive past the
    # join: Mojo destroys a value after its last USE and `unsafe_ptr()` is not
    # one. This is rule 1b's use-after-free in the shape a JIT suite hides.
    _ = len(maxes) + len(oks)

    var best = 0
    for w in range(workers):
        if oks[w] == 0:
            return _ExactDomain(False, 0)
        if maxes[w] > best:
            best = maxes[w]
    return _ExactDomain(True, best + 1)


def compose_plan(
    batch: RecordBatch,
    key_columns: List[Int],
    value_columns: List[Int],
    opcodes: List[Int],
    n_workers: Int,
) -> ComposedPlan:
    """Choose the route. Probes, allocates nothing, scans at most the key
    column, and answers with everything the chosen engine needs.

    Order is by measured margin, widest first, and each step's refusal is a fact
    about the DATA rather than a preference:

      1. width 1 and a dense integral code domain -> DENSE. The widest measured
         margin on five of the six H2O questions.
      2. width > 1 and the spans multiply small -> PACKED. The only route for a
         composite key that does not hash.
      3. width 1, high cardinality, no nulls -> LATE. Not dense, so the fused
         radix's two passes are the best available.
      4. otherwise -> SHIPPED, unchanged.
    """
    var width = len(key_columns)
    var invalid = PackedDomain(GROUP_PACKED_DOMAIN_TOO_LARGE)
    var requested = n_workers
    if requested < 1:
        requested = 1
    if requested > batch.n_rows:
        requested = batch.n_rows
    if requested < 1:
        requested = 1

    if width == 0 or not _many_request_ok(value_columns, opcodes):
        return ComposedPlan(
            COMPOSE_ROUTE_SHIPPED, requested, 0, invalid^, False, False, False,
            GROUP_CODED_BAD_REQUEST,
        )

    var n_aggs = len(value_columns)
    var value_cols = List[Float64Array]()
    for j in range(n_aggs):
        value_cols.append(batch.column(value_columns[j]))
    var value_nulls = _col_guard_flags(value_cols, batch.n_rows)
    var shared_count = True
    for j in range(len(value_nulls)):
        if value_nulls[j]:
            shared_count = False

    var opcodes_ok = True
    for j in range(len(opcodes)):
        if not dense_supports_opcode(opcodes[j]):
            opcodes_ok = False

    # ── 1. DENSE ────────────────────────────────────────────────────────────
    if width == 1 and opcodes_ok:
        var probe = probe_packed_domain(batch, key_columns, COMPOSE_PROBE_ROWS)
        var probed_bound = 0
        var exact = False
        if probe.valid() and probe.width == 1:
            probed_bound = Int(probe.his[0])
            if probe.spans[0] >= COMPOSE_EXACT_DOMAIN_MIN_SPAN:
                # Above the line the window is not trustworthy — see
                # COMPOSE_EXACT_DOMAIN_MIN_SPAN. Buy the exact bound.
                var dom = compose_exact_domain(batch, key_columns[0], requested)
                if dom.dense:
                    probed_bound = dom.bound
                    exact = True
                else:
                    probed_bound = 0
        if probed_bound > 0:
            var w = compose_dense_workers(
                probed_bound, n_aggs, shared_count, requested
            )
            if w >= 1:
                var st = dense_route_status(
                    probed_bound, value_columns, opcodes, w, shared_count
                )
                if st == GROUP_CODED_OK:
                    var folds = compose_merge_folds(probed_bound, n_aggs, w)
                    return ComposedPlan(
                        COMPOSE_ROUTE_DENSE, w, probed_bound, invalid^,
                        shared_count,
                        folds >= COMPOSE_PARALLEL_MERGE_MIN_FOLDS,
                        exact, GROUP_CODED_OK,
                    )

    # ── 2. PACKED ───────────────────────────────────────────────────────────
    if width > 1:
        var domain = packed_route_ok(batch, key_columns, n_aggs, requested)
        if domain.valid():
            return ComposedPlan(
                COMPOSE_ROUTE_PACKED, requested, 0, domain^, shared_count,
                False, False, GROUP_CODED_OK,
            )

    # ── 3. LATE ─────────────────────────────────────────────────────────────
    if fused_late_applicable(batch, key_columns, value_columns, opcodes, requested):
        return ComposedPlan(
            COMPOSE_ROUTE_LATE, requested, 0, invalid^, shared_count, False,
            False, GROUP_CODED_OK,
        )

    # ── 4. SHIPPED ──────────────────────────────────────────────────────────
    return ComposedPlan(
        COMPOSE_ROUTE_SHIPPED, requested, 0, invalid^, shared_count, False,
        False, GROUP_CODED_OK,
    )


def group_by_composed_dense_parallel(
    batch: RecordBatch,
    key_column: Int,
    cardinality: Int,
    value_columns: List[Int],
    opcodes: List[Int],
    n_workers: Int,
    parallel_merge: Bool,
) -> CodedGroupedResult:
    """`group_by_coded_dense_parallel`'s answer, bit for bit, with the serial
    tail removed.

    Identical by construction where it matters: the same four band scans, the
    same `_dense_code` guard, the same band split (`ceil(n_rows / workers)`),
    the same first-appearance composition (workers in band order, each worker's
    local list in order), the same frozen `merge_from` per (group, aggregate) in
    ascending worker order, and the same `has_answer`/`value_for` extraction.

    Different in three places, none of which can move a bit:

      * the min/max seed runs INSIDE each band, over that band's own private
        region only — the same writes, on the thread that owns the memory;
      * the merge and the extraction are FUSED and may run over parallel group
        ranges. Groups are independent and each group's fold order over workers
        is untouched, so this is a decomposition of the loop, not a
        re-association of the arithmetic;
      * the output arrays are pre-sized and written by index instead of
        appended, which is what makes the group ranges independent.

    `parallel_merge` is the caller's (i.e. `compose_plan`'s) decision so the
    two settings can be compared for bit equality in a test — which is the only
    way to know the claim above is true rather than plausible.
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

    # The route decision is `dense_route_status` and nothing else, so this
    # engine and a router that consulted it cannot drift apart.
    var status = dense_route_status(
        cardinality, value_columns, opcodes, workers, shared_count
    )
    if status != GROUP_CODED_OK:
        return CodedGroupedResult(status, _empty_many())

    var key_has_nulls = key_col.null_count() > 0 or key_col.length < n_rows
    var bound = Float64(cardinality)
    var stride = dense_record_stride(n_aggs, shared_count)
    var region = _pad64(cardinality * stride)

    # Owning containers rather than `alloc`: every refusal path returns early
    # and a container cannot leak on one. +8 is alignment headroom.
    var acc = List[Float64](length=workers * region + 8, fill=0.0)
    var acc_raw = acc.unsafe_ptr().as_unsafe_any_origin()
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

    var vptrs = List[UnsafePointer[Float64, origin=MutAnyOrigin]](capacity=n_aggs)
    for j in range(n_aggs):
        vptrs.append((value_cols[j].values[].unsafe_ptr() + value_cols[j].offset).as_unsafe_any_origin())
    var vpp = vptrs.unsafe_ptr().as_unsafe_any_origin()
    var ops_local = opcodes.copy()
    var opp = ops_local.unsafe_ptr().as_unsafe_any_origin()
    var vnulls = List[UInt8](length=n_aggs, fill=0)
    for j in range(n_aggs):
        vnulls[j] = 1 if value_nulls[j] else 0
    var vnp = vnulls.unsafe_ptr().as_unsafe_any_origin()

    var pay0 = 1
    var paystep = 1 if shared_count else 2

    var nan_seed = _canonical_nan()
    var wants_extremum = False
    for j in range(n_aggs):
        if opcodes[j] == AGG_MIN or opcodes[j] == AGG_MAX:
            wants_extremum = True

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
        # ── the seed, inside the band that owns the memory ─────────────────
        # Composition finding 2. Exactly the writes the serial prologue made,
        # on the thread whose private region they land in: same addresses, same
        # value, no ordering between workers to preserve because no two workers
        # touch the same byte.
        if wants_extremum:
            for code in range(cardinality):
                var base = code * stride
                for j in range(n_aggs):
                    if opp[j] == AGG_MIN or opp[j] == AGG_MAX:
                        accw[base + pay0 + j * paystep] = nan_seed
        var out: _BandOutcome
        if not shared_count:
            out = _scan_percol(
                lo, hi, accw, ordw, seenp + w * cardinality, kp, vpp, opp, vnp,
                value_cols, key_col, key_has_nulls, bound, stride, n_aggs,
            )
        elif n_aggs > 3 or uniform_op < 0:
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
    _ = len(vptrs) + len(vnulls) + len(ops_local) + len(acc) + len(order) + len(seen)

    for w in range(workers):
        if wbad[w] != 0:
            # A key that is not a code refuses the WHOLE call. Reported by a
            # flag from the band rather than by a store, because the store
            # would have been the out-of-bounds write that kills the process.
            return CodedGroupedResult(GROUP_CODED_KEY_NOT_A_CODE, _empty_many())

    # ── global first-appearance order: workers in band order, each worker's
    #    local list already in first-appearance order. Serial and it must be:
    #    the answer's group ORDER is defined by it.
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
    var gp = g_order.unsafe_ptr()
    var key_tuples = List[Float64](length=n_groups, fill=0.0)
    var values = List[Float64](length=n_groups * n_aggs, fill=0.0)
    var present = List[Bool](length=n_groups * n_aggs, fill=False)
    var counts = List[Float64](length=n_groups * n_aggs, fill=0.0)
    var keyp = key_tuples.unsafe_ptr()
    var valp = values.unsafe_ptr()
    var prep = present.unsafe_ptr()
    var cntp = counts.unsafe_ptr()

    # ── merge + extract, one group range at a time ──────────────────────────
    # Composition finding 1. `merge_one_range` is the ONLY definition of the
    # merge; the serial and parallel settings both call it, so they cannot
    # diverge — the parallel case is the same function over a partition of the
    # same index range. Per group the fold walks workers 0..workers-1 in order,
    # which is the association `group_by_coded_parallel` uses, so the answer is
    # bit-identical rather than close.
    @parameter
    def merge_one_range(g_lo: Int, g_hi: Int):
        for i in range(g_lo, g_hi):
            var code = gp[i]
            keyp[i] = Float64(code)
            for j in range(n_aggs):
                var op = opp[j]
                var acc_g = GroupAccumulator(Float64(code))
                for w in range(workers):
                    var base = w * region + code * stride
                    var cidx = base if shared_count else base + 2 * j
                    var c = accp[cidx]
                    if c == 0.0:
                        # An empty side moves nothing — `merge_from`'s own first
                        # branch, taken here rather than entered. Not the same
                        # as folding from zero: 0.0 + -0.0 is +0.0.
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
                    acc_g.merge_from(other)
                var flat = i * n_aggs + j
                # `_finish_many`'s extraction, cell for cell — pre-sized and
                # written by index instead of appended, which is what makes the
                # ranges independent.
                var answerable = acc_g.has_answer(op)
                valp[flat] = acc_g.value_for(op) if answerable else 0.0
                prep[flat] = answerable
                cntp[flat] = acc_g.count

    if parallel_merge and n_groups > 0:
        var mw = workers
        if mw > n_groups:
            mw = n_groups
        var gband = (n_groups + mw - 1) // mw

        @parameter
        def merge_worker(m: Int):
            var g_lo = m * gband
            var g_hi = g_lo + gband
            if g_hi > n_groups:
                g_hi = n_groups
            if g_lo < g_hi:
                merge_one_range(g_lo, g_hi)

        parallelize[merge_worker](mw)
    else:
        merge_one_range(0, n_groups)
    _ = (
        len(acc) + len(order) + len(g_order) + len(ops_local)
        + len(key_tuples) + len(values) + len(present) + len(counts)
    )

    var out_ops = opcodes.copy()
    return CodedGroupedResult(
        GROUP_CODED_OK,
        ManyGroupedResult(
            key_tuples^, 1, n_aggs, out_ops^, values^, present^, counts^,
            null_key_rows,
        ),
    )



def group_by_composed_parallel(
    batch: RecordBatch,
    key_columns: List[Int],
    value_columns: List[Int],
    opcodes: List[Int],
    n_workers: Int,
) -> ManyGroupedResult:
    """THE composed route: plan, then answer. Signature-compatible with
    `group_by_many_parallel`, and a total function — every refusal falls through
    to the shipped engine, so there is no input on which this returns something
    a caller has to check.
    """
    var plan = compose_plan(batch, key_columns, value_columns, opcodes, n_workers)
    return group_by_composed_planned(
        batch, key_columns, value_columns, opcodes, plan
    )


def group_by_composed_planned(
    batch: RecordBatch,
    key_columns: List[Int],
    value_columns: List[Int],
    opcodes: List[Int],
    plan: ComposedPlan,
) -> ManyGroupedResult:
    """Answer under an already-made plan, so a bench can time the plan and the
    engine separately and a test can force a route.

    Every branch that can refuse at SCAN time (a key past the probed bound is
    the only one) falls back to `group_by_many_parallel`, which is the shipped
    engine itself rather than a second implementation of it.
    """
    if plan.route == COMPOSE_ROUTE_DENSE:
        var dense = group_by_composed_dense_parallel(
            batch, key_columns[0], plan.cardinality, value_columns, opcodes,
            plan.workers, plan.parallel_merge,
        )
        if dense.ok():
            # MOVED, not copied. `.copy()` here deep-copies four Lists — at the
            # 1e5-group questions that is ~5 MB of memcpy per call, charged to
            # the route for nothing, since `dense` is a local about to die.
            return dense.result.copy()
        return group_by_many_parallel(
            batch, key_columns, value_columns, opcodes, plan.workers
        )
    if plan.route == COMPOSE_ROUTE_PACKED:
        var packed = group_by_packed_parallel(
            batch, key_columns, plan.domain, value_columns, opcodes, plan.workers
        )
        if packed.ok():
            return packed.result.copy()
        return group_by_many_parallel(
            batch, key_columns, value_columns, opcodes, plan.workers
        )
    if plan.route == COMPOSE_ROUTE_LATE:
        return group_by_many_radix_fused(
            batch, key_columns, value_columns, opcodes, plan.workers
        )
    return group_by_many_parallel(
        batch, key_columns, value_columns, opcodes, plan.workers
    )


def group_by_composed(
    batch: RecordBatch,
    key_columns: List[Int],
    value_columns: List[Int],
    opcodes: List[Int],
) -> ManyGroupedResult:
    """`group_by_many`'s drop-in, at the composed route's own band count.

    `cores * DENSE_BANDS_PER_CORE` and not `cores`: over-decomposition is the
    load-robustness lever the sibling attack measured (q4 7.427 -> 4.801 ms,
    q1 3.327 -> 2.352 ms under load; a wash on a quiet machine), because
    `parallelize` can hand a free thread the next band instead of blocking on a
    straggler band that landed on an E-core.

    It is also what makes `compose_dense_workers` load-bearing rather than
    decorative. Asking for 32 is REFUSED outright at 1e5 codes (122 MiB against
    a 64 MiB budget), so the cap is what keeps q3/q5/q7 on the dense route at
    16 while q1/q2/q4 keep all 32 bands. Requesting `cores` instead would have
    made the cap a no-op — which is exactly what mutation M4 exposed: with the
    cap deleted the suite stayed green, because nothing was ever asking for
    more bands than the budget allowed.

    Note the association consequence, stated rather than buried: at 32 bands
    the answer is a different (legal) fold association from `group_by_many`'s
    16, in the same way `group_by_coded_parallel` at 32 differs from itself at
    16. Bit identity is at EQUAL worker count and `ComposedPlan.workers`
    publishes which one to use.
    """
    return group_by_composed_parallel(
        batch,
        key_columns,
        value_columns,
        opcodes,
        planned_workers(
            batch.n_rows, info.num_physical_cores() * DENSE_BANDS_PER_CORE
        ),
    )
