"""test_streaming_frequency.mojo — known-value tests for the Count-Min lane.

Hand-written. Every reference here is something other than this module agreeing with itself:

  * **A width-1 sketch is EXACT and hand-derivable.** `cms_hash(x, 7, 1)` is
    `((x*7+17) % 1000003) % 1` == 0 for every `x`, so a one-column table has exactly one cell
    per row and every item increments all of them. After `n` adds, `frequency_query(anything)`
    is `n` -- no sketch involved, arithmetic. It is the tightest possible check on the
    minimum-over-rows reduction and on the total-mass accounting, and it needs no oracle.
  * **An exact count from a nested scan** over the input is the oracle for accuracy. The two
    Count-Min properties are asserted separately by kind: NEVER UNDER-STATES is absolute and is
    asserted for every key with no probability attached; the over-estimate against
    `stm_cms_epsilon(width) * total` is probabilistic and is asserted on the mean plus a stated
    multiple of `stm_cms_delta(depth)` on the breach fraction.
  * **The frozen `sketch.cms_hash` arithmetic, computed by hand.** `cms_hash(5, 7, 100)` is
    `(5*7+17) % 1000003 % 100 == 52`, and `cms_hash(5, 1000010, 100)` is
    `5000067 % 1000003 % 100`, and `5000067 - 5*1000003 == 52`, so it is 52 as well. Both are
    asserted, because that equality IS the frozen row-seed degeneracy this module keys around --
    every frozen seed `d * 1000003 + 7` is congruent to 7 modulo the frozen modulus.
  * **The one-pass sketch** is the oracle for merge, asserted CELL FOR CELL with `==` and no
    tolerance.

The forged-struct block at the end is the one that matters most. Five public functions in this
module used to take one well-typed JSON request and kill the worker process on an uncatchable
bounds assertion; a regression there does not fail this suite, it terminates the process running
it, so reaching the summary line is itself part of what is being asserted.
"""
from sketch import cms_hash, create_cms

from streaming.contract import (
    MAX_STM_DEPTH,
    MAX_STM_WIDTH,
    STM_ERR_DEPTH,
    STM_ERR_INCOMPATIBLE_MERGE,
    STM_ERR_INVALID_SKETCH,
    STM_ERR_ITEM_BUDGET,
    STM_ERR_PARAM_RANGE,
    STM_ERR_SNAPSHOT_SHAPE,
    STM_ERR_WIDTH,
    STM_OK,
    stm_cms_delta,
    stm_cms_epsilon,
    stm_status_name,
)
from streaming.frequency import (
    FREQUENCY_HEADER,
    FREQUENCY_MAX_DEPTH,
    FREQUENCY_MAX_WIDTH,
    FREQUENCY_SNAPSHOT_MAGIC,
    FrequencySketch,
    frequency_add,
    frequency_cell,
    frequency_empty,
    frequency_from_snapshot,
    frequency_frozen_row_collisions,
    frequency_heavy_hitters,
    frequency_ingest,
    frequency_ingest_prefix,
    frequency_ingest_weighted,
    frequency_keyed_row_collisions,
    frequency_merge,
    frequency_merge_snapshots,
    frequency_query,
    frequency_query_many,
    frequency_snapshot,
    frequency_suggested_depth,
)

#: The breach fraction is asserted against this multiple of `stm_cms_delta(depth)`. Stated
#: because asserting that NO key breaches an `e^-depth`-probability bound would be asserting
#: that an unlikely event is impossible.
comptime DELTA_MULTIPLE: Float64 = 8.0

#: A wrapping-multiply width. `3 * 6148914691236517206 == 2` in 64-bit arithmetic, which is how
#: a sibling package walked past a `rows * cols != len(dense)` guard and crashed the process.
comptime WRAPPING_WIDTH: Int = 6148914691236517206


def _keys(n: Int, n_distinct: Int) -> List[Int]:
    """A skewed stream: key `k` appears about `n / (n_distinct * (k + 1))` times, plus one.

    Deterministic, and skewed on purpose. A uniform stream spreads mass thinly and every cell
    ends near the mean, which is the easy case for a Count-Min sketch; a skewed one puts real
    mass behind a few keys so the collisions that the epsilon bound is about actually happen.
    """
    var out = List[Int]()
    var k = 0
    while len(out) < n:
        var key = k % n_distinct
        var repeats = n // (n_distinct * (key + 1)) + 1
        for _ in range(repeats):
            if len(out) >= n:
                break
            out.append(key * 7919)
        k += 1
    return out^


def _exact_count(items: List[Int], key: Int) -> Int:
    """The oracle: how many times `key` appears, by a scan. No sketch involved."""
    var seen = 0
    for i in range(len(items)):
        if items[i] == key:
            seen += 1
    return seen


def _distinct_keys(items: List[Int]) -> List[Int]:
    """Every distinct key, in first-appearance order, by an O(n^2) scan."""
    var out = List[Int]()
    for i in range(len(items)):
        var seen = False
        for j in range(len(out)):
            if out[j] == items[i]:
                seen = True
                break
        if not seen:
            out.append(items[i])
    return out^


def main() raises:
    print("Running streaming.frequency known-value tests...")
    var passed = 0
    var failed = 0

    # ── 1. the restated ceilings still equal the contract's ─────────────────
    if FREQUENCY_MAX_WIDTH == MAX_STM_WIDTH and FREQUENCY_MAX_DEPTH == MAX_STM_DEPTH:
        passed += 1
        print("  ✅ this module's ceilings still equal the contract's:",
              FREQUENCY_MAX_WIDTH, FREQUENCY_MAX_DEPTH)
    else:
        failed += 1
        print("  ❌ a restated ceiling drifted from the contract's")

    # ── 2. A WIDTH-1 SKETCH IS EXACT, and the value is hand-derived ─────────
    #
    # `cms_hash(x, 7, 1) == ((x*7+17) % 1000003) % 1 == 0` for every x, so one column means one
    # cell per row and every add touches all of them. 40 adds -> every query is exactly 40.
    var flat = frequency_ingest(_keys(40, 5), 1, 3, 11)
    var flat_q = frequency_query(flat, 7919 * 3)
    var flat_absent = frequency_query(flat, -12345)
    if flat.valid and flat.total == 40 and flat_q.count == 40 \
            and flat_absent.count == 40 and flat_absent.present \
            and frequency_cell(flat, 0, 0) == 40 and frequency_cell(flat, 2, 0) == 40:
        passed += 1
        print("  ✅ a width-1 sketch is exact by construction: every query returns the total 40,",
              "including a key never added — the degenerate case, stated rather than hidden")
    else:
        failed += 1
        print("  ❌ the width-1 identity failed:", flat_q.count, flat.total)

    # ── 3. never under-states: the one ABSOLUTE Count-Min guarantee ─────────
    var stream = _keys(4000, 120)
    var sk = frequency_ingest(stream, 512, 4, 31)
    var keys = _distinct_keys(stream)
    var under = 0
    var breaches = 0
    var over_sum = 0.0
    var eps = stm_cms_epsilon(512)
    var dlt = stm_cms_delta(4)
    var slack = eps.value * Float64(sk.total)
    for i in range(len(keys)):
        var truth = _exact_count(stream, keys[i])
        var est = frequency_query(sk, keys[i])
        if est.count < truth:
            under += 1
        var over = Float64(est.count - truth)
        over_sum += over
        if over > slack:
            breaches += 1
    if under == 0:
        passed += 1
        print("  ✅ over", len(keys), "keys of a 4000-item stream NOT ONE estimate under-states",
              "the exact count — the only Count-Min property with no probability attached")
    else:
        failed += 1
        print("  ❌", under, "keys under-stated their true count")

    var mean_over = over_sum / Float64(len(keys))
    if mean_over <= slack:
        passed += 1
        print("  ✅ mean over-estimate", mean_over, "is inside the epsilon allowance", slack,
              "(eps", eps.value, "x total", sk.total, ")")
    else:
        failed += 1
        print("  ❌ mean over-estimate", mean_over, "exceeds the allowance", slack)

    var breach_fraction = Float64(breaches) / Float64(len(keys))
    if breach_fraction <= DELTA_MULTIPLE * dlt.value:
        passed += 1
        print("  ✅ breach fraction", breach_fraction, "inside", DELTA_MULTIPLE, "x delta",
              dlt.value, "—", breaches, "of", len(keys), "keys exceeded eps*total")
    else:
        failed += 1
        print("  ❌ breach fraction", breach_fraction, "exceeds", DELTA_MULTIPLE, "x", dlt.value)

    # A DELIBERATELY NARROW SKETCH, so the bound is tested where it can actually fail. 120 keys
    # in 64 columns collide by the pigeonhole principle, so the over-estimate above is not zero
    # and the epsilon allowance is doing work rather than being trivially satisfied.
    var tight = frequency_ingest(stream, 64, 4, 31)
    var tight_eps = stm_cms_epsilon(64)
    var tight_slack = tight_eps.value * Float64(tight.total)
    var tight_under = 0
    var tight_breaches = 0
    var tight_max_over = 0
    for i in range(len(keys)):
        var truth = _exact_count(stream, keys[i])
        var est = frequency_query(tight, keys[i])
        if est.count < truth:
            tight_under += 1
        var over = est.count - truth
        if over > tight_max_over:
            tight_max_over = over
        if Float64(over) > tight_slack:
            tight_breaches += 1
    if tight_under == 0 and tight_max_over > 0 \
            and Float64(tight_breaches) / Float64(len(keys)) <= DELTA_MULTIPLE * dlt.value:
        passed += 1
        print("  ✅ at width 64 the sketch genuinely collides — worst over-estimate",
              tight_max_over, "against slack", tight_slack, "— and STILL never under-states;",
              tight_breaches, "of", len(keys), "keys breach eps*total")
    else:
        failed += 1
        print("  ❌ narrow-sketch bound failed:", tight_under, tight_max_over, tight_breaches)

    # ── 4. the FROZEN row-seed degeneracy, by hand ──────────────────────────
    #
    # `cms_hash(5, 7, 100)` is `(5*7+17) % 1000003 % 100` = `52 % 100` = 52.
    # `cms_hash(5, 1000010, 100)` is `5000067 % 1000003 % 100`, and `5000067 - 5*1000003 = 52`,
    # so it is 52 as well. Every frozen seed `d*1000003 + 7` is congruent to 7 modulo 1000003,
    # which is why every frozen row computes the same column and `depth` buys nothing.
    var frozen_seeds = create_cms(64, 4)
    var seeds_congruent = True
    for d in range(4):
        if frozen_seeds.hash_seeds[d] % 1000003 != 7:
            seeds_congruent = False
    if cms_hash(5, 7, 100) == 52 and cms_hash(5, 1000010, 100) == 52 \
            and seeds_congruent and frozen_seeds.hash_seeds[1] == 1000010:
        passed += 1
        print("  ✅ hand-computed: cms_hash(5, 7, 100) == cms_hash(5, 1000010, 100) == 52, and",
              "all 4 frozen row seeds are 7 modulo 1000003 — the defect the keying works around")
    else:
        failed += 1
        print("  ❌ the frozen hash arithmetic is not what the module's justification claims")

    var probe = List[Int]()
    for i in range(2000):
        probe.append(i)
    var frozen_collisions = frequency_frozen_row_collisions(probe, 4096, 4)
    var keyed_collisions = frequency_keyed_row_collisions(probe, 4096, 4, 5)
    if frozen_collisions == 2000 and keyed_collisions == 0:
        passed += 1
        print("  ✅ all 4 FROZEN rows agree on 2000 of 2000 items; the KEYED rows agree on",
              keyed_collisions, "— depth means nothing in the first case and everything in the second")
    else:
        failed += 1
        print("  ❌ the collision measurement changed:", frozen_collisions, keyed_collisions)

    # ── 5. merge is EXACT, cell for cell ────────────────────────────────────
    var half_a = List[Int]()
    var half_b = List[Int]()
    for i in range(len(stream)):
        if i < 1700:
            half_a.append(stream[i])
        else:
            half_b.append(stream[i])
    var merged = frequency_merge(
        frequency_ingest(half_a, 512, 4, 31), frequency_ingest(half_b, 512, 4, 31)
    )
    var cell_diffs = 0
    for i in range(len(sk.cells)):
        if merged.cells[i] != sk.cells[i]:
            cell_diffs += 1
    if merged.valid and cell_diffs == 0 and merged.total == sk.total:
        passed += 1
        print("  ✅ merge(sketch(A), sketch(B)) == sketch(A ++ B) cell for cell: 0 of",
              len(sk.cells), "cells differ, and the totals agree at", merged.total)
    else:
        failed += 1
        print("  ❌ merge is not exact:", cell_diffs, "cells differ")

    # Merge is NOT idempotent, and the asymmetry with distinct_merge is asserted rather than
    # left to a reader: merge(a, a) doubles every count, which is correct for A ++ A.
    var doubled = frequency_merge(sk, sk)
    if doubled.valid and doubled.total == 2 * sk.total \
            and doubled.cells[0] == 2 * sk.cells[0]:
        passed += 1
        print("  ✅ merge(a, a) DOUBLES: total", doubled.total, "vs", sk.total,
              "— not idempotent, unlike distinct_merge, so a replay must be de-duplicated")
    else:
        failed += 1
        print("  ❌ merge(a, a) is not the sketch of A ++ A")

    # ── 6. snapshot round trip ──────────────────────────────────────────────
    var snap = frequency_snapshot(sk)
    var restored = frequency_from_snapshot(snap)
    var snap_diffs = 0
    for i in range(len(sk.cells)):
        if restored.cells[i] != sk.cells[i]:
            snap_diffs += 1
    if len(snap) == FREQUENCY_HEADER + 512 * 4 and restored.valid and snap_diffs == 0 \
            and restored.total == sk.total and restored.seed == sk.seed:
        passed += 1
        print("  ✅ snapshot is", len(snap), "ints (5-word header + 2048 cells) and round-trips",
              "cell for cell")
    else:
        failed += 1
        print("  ❌ the snapshot did not round-trip:", len(snap), snap_diffs)

    var merged_snaps = frequency_merge_snapshots(
        frequency_snapshot(frequency_ingest(half_a, 512, 4, 31)),
        frequency_snapshot(frequency_ingest(half_b, 512, 4, 31)),
    )
    if merged_snaps.valid and merged_snaps.total == sk.total:
        passed += 1
        print("  ✅ merging two flat snapshots reproduces the one-pass total", merged_snaps.total)
    else:
        failed += 1
        print("  ❌ snapshot merge disagreed with the one-pass sketch")

    # ── 7. weighted ingest agrees with repeated ingest ──────────────────────
    var w_items = List[Int]()
    var w_counts = List[Int]()
    w_items.append(11)
    w_counts.append(3)
    w_items.append(22)
    w_counts.append(5)
    var weighted = frequency_ingest_weighted(w_items, w_counts, 64, 3, 4)
    var repeated = frequency_empty(64, 3, 4)
    repeated = frequency_add(repeated, 11, 3)
    repeated = frequency_add(repeated, 22, 5)
    var w_diff = 0
    for i in range(len(weighted.cells)):
        if weighted.cells[i] != repeated.cells[i]:
            w_diff += 1
    if weighted.valid and w_diff == 0 and weighted.total == 8 \
            and frequency_query(weighted, 11).count == 3:
        passed += 1
        print("  ✅ weighted ingest and repeated frequency_add build the same table; total 8,",
              "query(11) == 3")
    else:
        failed += 1
        print("  ❌ weighted ingest disagrees with repeated add:", w_diff, weighted.total)

    # ── 8. refusals: every one typed, none of them a coerced answer ─────────
    var refusals = 0
    if frequency_empty(0, 4, 1).status == STM_ERR_WIDTH:
        refusals += 1
    if frequency_empty(MAX_STM_WIDTH + 1, 4, 1).status == STM_ERR_WIDTH:
        refusals += 1
    if frequency_empty(64, 0, 1).status == STM_ERR_DEPTH:
        refusals += 1
    if frequency_empty(64, MAX_STM_DEPTH + 1, 1).status == STM_ERR_DEPTH:
        refusals += 1
    if frequency_ingest_prefix(stream, len(stream) + 1, 64, 2, 1).status == STM_ERR_SNAPSHOT_SHAPE \
            or frequency_ingest_prefix(stream, len(stream) + 1, 64, 2, 1).status != STM_OK:
        refusals += 1
    if frequency_ingest_prefix(stream, -3, 64, 2, 1).status != STM_OK:
        refusals += 1
    if frequency_add(frequency_empty(64, 2, 1), 5, -1).status == STM_ERR_PARAM_RANGE:
        refusals += 1
    if frequency_merge(frequency_empty(64, 2, 1), frequency_empty(128, 2, 1)).status \
            == STM_ERR_INCOMPATIBLE_MERGE:
        refusals += 1
    if frequency_merge(frequency_empty(64, 2, 1), frequency_empty(64, 2, 9)).status \
            == STM_ERR_INCOMPATIBLE_MERGE:
        refusals += 1
    if len(frequency_snapshot(frequency_empty(0, 4, 1))) == 0:
        refusals += 1
    if frequency_from_snapshot(List[Int]()).status == STM_ERR_SNAPSHOT_SHAPE:
        refusals += 1
    var wrong_magic = frequency_snapshot(sk)
    wrong_magic[0] = 0x44495354
    if frequency_from_snapshot(wrong_magic).status == STM_ERR_SNAPSHOT_SHAPE:
        refusals += 1
    if refusals == 12:
        passed += 1
        print("  ✅ 12 unusable requests are refused with typed statuses — a bad width, a bad",
              "depth, a count past the end, a negative count, a negative add, two incompatible",
              "merges, an empty payload and a distinct-count snapshot fed to the wrong reader")
    else:
        failed += 1
        print("  ❌ only", refusals, "of 12 refusals fired")

    # ── 9. frequency_cell guards a SUBSCRIPT in both directions ─────────────
    if frequency_cell(sk, -1, 0) == -1 and frequency_cell(sk, 0, -1) == -1 \
            and frequency_cell(sk, 4, 0) == -1 and frequency_cell(sk, 0, 512) == -1 \
            and frequency_cell(sk, 0, 0) >= 0:
        passed += 1
        print("  ✅ frequency_cell refuses a negative row, a negative column and both",
              "over-range ends with -1, and returns a real cell for (0, 0)")
    else:
        failed += 1
        print("  ❌ a subscript escaped its guard")

    # ── 10. frequency_suggested_depth routes to the frozen optimiser ────────
    if frequency_suggested_depth(4096, 512) >= 1 \
            and frequency_suggested_depth(4096, 512) <= FREQUENCY_MAX_DEPTH \
            and frequency_suggested_depth(0, 512) == 1 \
            and frequency_suggested_depth(4096, 0) == 1:
        passed += 1
        print("  ✅ frequency_suggested_depth(4096, 512) ==",
              frequency_suggested_depth(4096, 512), "and clamps into [1,",
              FREQUENCY_MAX_DEPTH, "] rather than returning the frozen 0 for a saturated table")
    else:
        failed += 1
        print("  ❌ the suggested depth left its clamp")

    # ── 11. A FORGED STRUCT. Five of these used to kill the process. ────────
    #
    # `FrequencySketch` is decoded from caller JSON positionally and the runtime validates field
    # TYPES only, so `valid: true` beside `width: 512, depth: 4` and an EMPTY `cells` list is an
    # accepted request. Against the code before this block existed, `frequency_query`,
    # `frequency_query_many`, `frequency_heavy_hitters`, `frequency_add` and `frequency_cell`
    # each died on an uncatchable bounds assertion. `frequency_cell(sketch, 0, 0)` is the
    # pointed one: it guarded `row < depth` and `col < width`, both fields of the SAME forged
    # struct, so both guards passed while the read walked off an empty list.
    var forged = FrequencySketch(List[Int](), 512, 4, 0, 0, STM_OK, True)
    var f_query = frequency_query(forged, 3)
    var f_many = frequency_query_many(forged, probe)
    var f_hh = frequency_heavy_hitters(forged, probe, 0.5)
    var f_add = frequency_add(forged, 3, 1)
    var f_merge = frequency_merge(forged, forged)
    if not f_query.present and f_query.status == STM_ERR_SNAPSHOT_SHAPE \
            and not f_many.present and not f_hh.present \
            and not f_add.valid and f_add.status == STM_ERR_SNAPSHOT_SHAPE \
            and not f_merge.valid \
            and frequency_cell(forged, 0, 0) == -1 \
            and len(frequency_snapshot(forged)) == 0:
        passed += 1
        print("  ✅ a struct declaring 512x4 with an EMPTY cell list is refused by query,",
              "query_many, heavy_hitters, add, merge, cell and snapshot under",
              stm_status_name(STM_ERR_SNAPSHOT_SHAPE))
    else:
        failed += 1
        print("  ❌ a forged sketch was accepted:", f_query.status, f_add.status,
              frequency_cell(forged, 0, 0))

    # ── 12. the SHAPE relation is decided by DIVISION, never a product ──────
    #
    # `3 * 6148914691236517206 == 2` in wrapping 64-bit arithmetic. A guard written as
    # `depth * width != len(cells)` would compare 2 against 2 and pass. `stm_cells_fit`
    # delegates to the frozen `sparse_numerics.csr.dims_fit`, which divides.
    var two_cells = List[Int]()
    two_cells.append(1)
    two_cells.append(2)
    var wrapping = FrequencySketch(two_cells, WRAPPING_WIDTH, 3, 2, 0, STM_OK, True)
    if 3 * WRAPPING_WIDTH == 2 and frequency_cell(wrapping, 0, 0) == -1 \
            and not frequency_query(wrapping, 1).present \
            and not frequency_add(wrapping, 1, 1).valid:
        passed += 1
        print("  ✅ width", WRAPPING_WIDTH, "x depth 3 wraps to exactly 2 cells and is still",
              "refused — the shape check divides rather than multiplying")
    else:
        failed += 1
        print("  ❌ a wrapping product walked past the shape check")

    # ── 13. A NON-FINITE THRESHOLD IS REFUSED, not answered ────────────────
    #
    # THE WRONG ANSWER THIS PINS: `NaN < 0.0` and `NaN > 1.0` are BOTH false, so a NaN passed a
    # plain range gate, `threshold` became NaN, every `count >= NaN` was false, and the function
    # returned an empty list -- which its own contract read as "no heavy hitters". A refusal was
    # reported as an answer, and the bare `List[Int]` return could not have said otherwise.
    var nan = Float64(0.0) / Float64(0.0)
    var inf = Float64(1.0) / Float64(0.0)
    var cands = List[Int]()
    cands.append(7919 * 0)
    cands.append(104729)
    var hh_nan = frequency_heavy_hitters(sk, cands, nan)
    var hh_inf = frequency_heavy_hitters(sk, cands, inf)
    var hh_all = frequency_heavy_hitters(sk, cands, 0.0)
    var hh_none = frequency_heavy_hitters(sk, cands, 1.0)
    if not hh_nan.present and hh_nan.status == STM_ERR_PARAM_RANGE \
            and not hh_inf.present and hh_inf.status == STM_ERR_PARAM_RANGE \
            and hh_all.present and len(hh_all.items) == 2 \
            and hh_none.present and len(hh_none.items) == 0:
        passed += 1
        print("  ✅ a NaN and an infinite min_fraction are REFUSED under",
              stm_status_name(STM_ERR_PARAM_RANGE), "while fraction 1.0 legitimately returns 0",
              "hitters with present == True — a refusal and 'none of them' are now different")
    else:
        failed += 1
        print("  ❌ a non-finite threshold was answered:", hh_nan.present, hh_nan.status)

    # ── 14. query_many carries its own presence flag ────────────────────────
    var many = frequency_query_many(sk, cands)
    if many.present and many.n_items == 2 and len(many.items) == 2 \
            and many.items[0] == frequency_query(sk, cands[0]).count \
            and frequency_query_many(sk, List[Int]()).present:
        passed += 1
        print("  ✅ query_many agrees with query element for element, and an EMPTY item list is",
              "still present == True — asking about nothing is a request with an answer")
    else:
        failed += 1
        print("  ❌ query_many lost its presence distinction")

    # ── 15. a forged total is refused, so the reported slack is a real bound ─
    var neg_total = FrequencySketch(sk.cells, 512, 4, -5, 31, STM_OK, True)
    var big_total = FrequencySketch(sk.cells, 512, 4, 1 << 62, 31, STM_OK, True)
    # Width 1 for the cell case, so there is exactly one column and every query READS the
    # forged cell. A bad cell in a column no query touches cannot change any answer, which is
    # why the check is per cell read rather than a whole-table scan on a point query -- an
    # O(depth*width) guard in front of an O(depth) query is the cost inversion this package
    # charges its budgets to avoid.
    var over_cell = List[Int]()
    over_cell.append(99)
    over_cell.append(0)
    var cell_above_total = FrequencySketch(over_cell, 1, 2, 5, 0, STM_OK, True)
    var neg_cell = List[Int]()
    neg_cell.append(-1)
    neg_cell.append(0)
    var cell_negative = FrequencySketch(neg_cell, 1, 2, 5, 0, STM_OK, True)
    if not frequency_query(neg_total, 1).present \
            and frequency_query(neg_total, 1).status == STM_ERR_ITEM_BUDGET \
            and not frequency_query(big_total, 1).present \
            and frequency_cell(cell_above_total, 0, 0) == -1 \
            and not frequency_query(cell_above_total, 1).present \
            and frequency_query(cell_above_total, 1).status == STM_ERR_SNAPSHOT_SHAPE \
            and not frequency_query(cell_negative, 1).present \
            and len(frequency_snapshot(cell_negative)) == 0:
        passed += 1
        print("  ✅ a negative total, a total past the mass ceiling, a cell above the total and",
              "a negative cell are all refused — so the epsilon*total slack reported beside an",
              "estimate is a bound on something, and the never-under-states property holds")
    else:
        failed += 1
        print("  ❌ a forged total or cell produced an estimate with a meaningless bound")

    print("  [streaming.frequency] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("test_streaming_frequency: " + String(failed) + " failure(s)")
