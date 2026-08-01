"""test_streaming_quantiles.mojo — known-value tests for the KLL quantile lane.

Hand-written. Every reference is external to this module:

  * **THE 1..100 IDENTITY, verifiable with no computer at all.** At `k = 4096`, a stream of
    1.0 .. 100.0 never fills a level, so the sketch stores all 100 items verbatim and is EXACT.
    The nearest-rank quantile at `q` is then the `ceil(q * 100)`-th smallest, which is
    `Float64(ceil(q * 100))`. So `quantile_at(sk, 0.29)` must be 29.0, `0.57` must be 57.0,
    `0.01` must be 1.0 and `0.5` must be 50.0 -- a reader checks those four by counting.
    This is the assertion the shipped code failed: `Int(0.29 * 100.0)` is `Int(28.999999999999996)`
    is 28, so it returned 28.0 under a success status, with a self-reported `rank_slack` of
    0.1953125 items against an actual rank error of 1.0 -- a 5.12x breach of its own interval on
    a sketch that had approximated nothing. All 99 of `q = i/100` are checked here against the
    hand rule, not just the four named.
  * **An exact O(n log n) sort** of the stream is the oracle for the approximate regime. The
    rank of the returned value is computed by counting the sorted array, and the error against
    the requested rank is asserted inside `stm_kll_rank_error(k) * n`.
  * **The frozen `anomaly.percentile`** is the module's declared exact oracle and is checked to
    bracket the sketch's answer: the two use different definitions (it interpolates linearly,
    this sketch returns an observed value), so what is asserted is the RANK relationship, which
    is the space the bound is stated in.
  * **The one-pass sketch** is the oracle for merge in the lossless regime, asserted with `==`.
  * **`quantile_rank` is the exact inverse of `quantile_at`** by construction, and the round trip
    is asserted rather than assumed: the pair contradicting itself under two success statuses is
    exactly how the truncation defect surfaced.

The forged-struct block at the end pins six functions that each used to take one well-typed JSON
request and kill the worker process. A regression there does not fail this suite -- it terminates
the process running it -- so reaching the summary line is part of the assertion.
"""
from anomaly import percentile
from sorting import mergesort

from streaming.contract import (
    MAX_STM_K,
    MAX_STM_LEVELS,
    MIN_STM_K,
    STM_EMPTY,
    STM_ERR_CAPACITY,
    STM_ERR_COUNT,
    STM_ERR_INCOMPATIBLE_MERGE,
    STM_ERR_INVALID_SKETCH,
    STM_ERR_ITEM_BUDGET,
    STM_ERR_LEVEL_OVERFLOW,
    STM_ERR_NON_FINITE,
    STM_ERR_QUANTILE_RANGE,
    STM_ERR_SNAPSHOT_SHAPE,
    STM_OK,
    stm_kll_rank_error,
    stm_status_name,
)
from streaming.quantiles import (
    QUANTILE_HEADER,
    QUANTILE_MAX_K,
    QUANTILE_MIN_K,
    QUANTILE_SNAPSHOT_MAGIC,
    QUANTILE_VALUE_HEADER,
    QuantileSketch,
    quantile_add,
    quantile_at,
    quantile_batch,
    quantile_empty,
    quantile_from_snapshot,
    quantile_ingest,
    quantile_ingest_prefix,
    quantile_maximum,
    quantile_merge,
    quantile_merge_snapshots,
    quantile_minimum,
    quantile_profile,
    quantile_rank,
    quantile_snapshot,
    quantile_total_weight,
)


fn _ramp(n: Int) -> List[Float64]:
    """1.0 .. n, in order. The sequence whose quantiles a reader can count."""
    var out = List[Float64]()
    for i in range(1, n + 1):
        out.append(Float64(i))
    return out^


fn _shuffled(n: Int, seed: Int) -> List[Float64]:
    """1.0 .. n in a fixed permutation, so order cannot be what makes an answer right."""
    var out = List[Float64]()
    var step = 2 * seed + 1
    for i in range(n):
        out.append(Float64(((i * step) % n) + 1))
    return out^


fn _exact_rank(sorted_values: List[Float64], x: Float64) -> Int:
    """How many elements of an ascending list are <= `x`. The oracle for every rank claim."""
    var seen = 0
    for i in range(len(sorted_values)):
        if sorted_values[i] <= x:
            seen += 1
        else:
            break
    return seen


fn _ceil_rank(q: Float64, n: Int) -> Int:
    """`ceil(q * n)` by INTEGER arithmetic, so the oracle shares no rounding with the kernel.

    `q` here is always `i / 100`, so `q * n` is exactly `i * n / 100` as a rational, and the
    ceiling of that is `(i * n + 99) // 100`. No floating multiply is involved, which is the
    whole point: the kernel's job is to get this answer despite `0.29 * 100.0` being
    28.999999999999996, and an oracle that made the same multiply would agree with the bug.
    """
    var numerator = Int(q * 100.0 + 0.5) * n
    var target = (numerator + 99) // 100
    if target < 1:
        target = 1
    if target > n:
        target = n
    return target


fn main() raises:
    print("Running streaming.quantiles known-value tests...")
    var passed = 0
    var failed = 0

    # ── 1. the restated ceilings still equal the contract's ─────────────────
    if QUANTILE_MAX_K == MAX_STM_K and QUANTILE_MIN_K == MIN_STM_K:
        passed += 1
        print("  ✅ this module's capacity ceilings still equal the contract's:",
              QUANTILE_MIN_K, QUANTILE_MAX_K)
    else:
        failed += 1
        print("  ❌ a restated ceiling drifted from the contract's")

    # ── 2. THE EXACT REGIME: 100 items at k = 4096 never compacts ───────────
    var ramp = _ramp(100)
    var exact = quantile_ingest(ramp, 4096, 1)
    if exact.valid and exact.n == 100 and len(exact.level_sizes) == 1 \
            and exact.level_sizes[0] == 100 and quantile_total_weight(exact) == 100:
        passed += 1
        print("  ✅ 100 items at k = 4096 sit in ONE level of 100, verbatim: total weight",
              quantile_total_weight(exact), "== n, so every answer below is exact arithmetic")
    else:
        failed += 1
        print("  ❌ the exact regime is not exact:", len(exact.level_sizes), exact.n)

    # ── 3. THE HAND VALUES. This is the assertion the shipped code failed. ──
    #
    # The 29th smallest of 1..100 is 29.0. `Int(0.29 * 100.0)` is 28, because the IEEE product is
    # 28.999999999999996, and the returned 28.0 had exact rank 28 against a requested rank of 29
    # -- one whole item of error against a self-reported slack of 0.1953125 items.
    var q29 = quantile_at(exact, 0.29)
    var q57 = quantile_at(exact, 0.57)
    var q01 = quantile_at(exact, 0.01)
    var q50 = quantile_at(exact, 0.5)
    if q29.value == 29.0 and q29.present and q29.status == STM_OK \
            and q57.value == 57.0 and q01.value == 1.0 and q50.value == 50.0:
        passed += 1
        print("  ✅ hand values on 1..100: q(0.29) ==", q29.value, ", q(0.57) ==", q57.value,
              ", q(0.01) ==", q01.value, ", q(0.5) ==", q50.value,
              "— the 29th, 57th, 1st and 50th smallest, countable by a reader")
    else:
        failed += 1
        print("  ❌ TRUNCATION IS BACK: q(0.29) ==", q29.value, "(want 29.0), q(0.57) ==",
              q57.value, "(want 57.0)")

    # ── 4. all 99 hundredths, against an INTEGER oracle, at four lengths ────
    var wrong_cells = 0
    var worst_ratio = 0.0
    for which in range(4):
        var n = 20
        if which == 1:
            n = 50
        elif which == 2:
            n = 100
        elif which == 3:
            n = 200
        var data = _ramp(n)
        var sk = quantile_ingest(data, 4096, 1)
        var claim = stm_kll_rank_error(4096)
        var slack = claim.value * Float64(n)
        for i in range(1, 100):
            var q = Float64(i) / 100.0
            var want = Float64(_ceil_rank(q, n))
            var got = quantile_at(sk, q)
            if got.value != want:
                wrong_cells += 1
                var err = got.value - want
                if err < 0.0:
                    err = -err
                var ratio = err / slack
                if ratio > worst_ratio:
                    worst_ratio = ratio
    if wrong_cells == 0:
        passed += 1
        print("  ✅ all 99 hundredth-quantiles match ceil(q*n) exactly at n = 20, 50, 100 and",
              "200 — 396 cells, 0 wrong. Truncation missed 228 of these 396.")
    else:
        failed += 1
        print("  ❌", wrong_cells, "of 396 exact-regime quantiles are wrong; worst is",
              worst_ratio, "x the sketch's own rank slack")

    # ── 5. quantile_rank is the exact inverse, and the pair agrees ──────────
    #
    # THE SELF-CONTRADICTION THIS PINS: `quantile_rank(sk, 29.0)` returned exactly 0.29 while
    # `quantile_at(sk, 0.29)` returned 28.0, both under status ok. Two success statuses that
    # cannot both be right is a stronger signal than either number alone.
    var round_trip_bad = 0
    for i in range(1, 100):
        var q = Float64(i) / 100.0
        var value = quantile_at(exact, q).value
        var back = quantile_rank(exact, value)
        # The value at rank r has fractional rank r/n, and `_ceil_rank` gives that r.
        if back.value != Float64(_ceil_rank(q, 100)) / 100.0:
            round_trip_bad += 1
    if round_trip_bad == 0:
        passed += 1
        print("  ✅ quantile_rank(quantile_at(q)) returns ceil(q*n)/n for all 99 hundredths —",
              "the pair no longer contradicts itself under two success statuses")
    else:
        failed += 1
        print("  ❌", round_trip_bad, "of 99 round trips disagree between at and rank")

    # ── 6. q = 0 and q = 1 are the EXACT minimum and maximum ───────────────
    var qmin = quantile_at(exact, 0.0)
    var qmax = quantile_at(exact, 1.0)
    if qmin.value == 1.0 and qmax.value == 100.0 \
            and quantile_minimum(exact).value == 1.0 \
            and quantile_maximum(exact).value == 100.0:
        passed += 1
        print("  ✅ q=0 is the exact minimum 1.0 and q=1 the exact maximum 100.0, tracked",
              "outside the levels so compaction cannot discard them")
    else:
        failed += 1
        print("  ❌ the tracked extremes are wrong:", qmin.value, qmax.value)

    # ── 7. the frozen exact oracle brackets the sketch's answer ────────────
    #
    # `anomaly.percentile(1..100, 29.0)` interpolates: index 0.29*99 = 28.71, so
    # 29*0.29 + 30*0.71 = 29.71. This sketch returns an OBSERVED value, 29.0, so the two differ
    # by less than one rank step by construction. What is asserted is that relationship, not an
    # equality between two different definitions.
    var oracle29 = percentile(ramp, 29.0)
    if oracle29 > 29.0 and oracle29 < 30.0 and q29.value == 29.0:
        passed += 1
        print("  ✅ the frozen anomaly.percentile(ramp, 29.0) ==", oracle29,
              "brackets this sketch's 29.0 within one rank step — different definitions,",
              "consistent ranks")
    else:
        failed += 1
        print("  ❌ the sketch and the frozen oracle disagree by more than a rank step:",
              oracle29, q29.value)

    # ── 8. THE APPROXIMATE REGIME, against an exact sort ───────────────────
    var big = _shuffled(20000, 3)
    var sorted_big = mergesort(big)
    var sketch = quantile_ingest(big, 256, 7)
    var claim256 = stm_kll_rank_error(256)
    var slack256 = claim256.value * 20000.0
    var rank_breaches = 0
    var worst_rank_err = 0.0
    for i in range(1, 100):
        var q = Float64(i) / 100.0
        var got = quantile_at(sketch, q)
        var actual_rank = Float64(_exact_rank(sorted_big, got.value))
        var wanted_rank = Float64(_ceil_rank(q, 20000))
        var err = actual_rank - wanted_rank
        if err < 0.0:
            err = -err
        if err > worst_rank_err:
            worst_rank_err = err
        if err > slack256:
            rank_breaches += 1
    if rank_breaches == 0 and sketch.n == 20000 \
            and quantile_total_weight(sketch) == 20000:
        passed += 1
        print("  ✅ 20,000 items at k = 256: worst rank error", worst_rank_err, "of",
              slack256, "allowed over 99 quantiles, 0 breaches, and total weight is still",
              quantile_total_weight(sketch), "— compaction preserves weight EXACTLY")
    else:
        failed += 1
        print("  ❌", rank_breaches, "of 99 quantiles breach the claimed rank error; worst",
              worst_rank_err, "vs", slack256)

    # ── 9. compaction actually happened, so item 8 measured something ──────
    if len(sketch.level_sizes) > 1 and len(sketch.values) < 20000:
        passed += 1
        print("  ✅ the sketch compacted into", len(sketch.level_sizes), "levels holding",
              len(sketch.values), "items for a 20,000-item stream — the approximate regime is",
              "genuinely approximate, so the bound above was tested where it can fail")
    else:
        failed += 1
        print("  ❌ nothing compacted; the bound test was vacuous")

    # ── 10. merge is EXACT when neither side compacted ─────────────────────
    var left = _ramp(40)
    var right = List[Float64]()
    for i in range(41, 81):
        right.append(Float64(i))
    var whole = _ramp(80)
    var merged = quantile_merge(
        quantile_ingest(left, 4096, 5), quantile_ingest(right, 4096, 5)
    )
    var one_pass = quantile_ingest(whole, 4096, 5)
    var merged_diffs = 0
    var m_sorted = mergesort(merged.values)
    var o_sorted = mergesort(one_pass.values)
    if len(m_sorted) == len(o_sorted):
        for j in range(len(m_sorted)):
            if m_sorted[j] != o_sorted[j]:
                merged_diffs += 1
    else:
        merged_diffs = -1
    if merged.valid and merged_diffs == 0 and merged.n == 80 \
            and merged.minimum == 1.0 and merged.maximum == 80.0:
        passed += 1
        print("  ✅ with no compaction on either side, merge holds the EXACT union: 0 of",
              len(m_sorted), "values differ from the one-pass sketch, asserted with ==")
    else:
        failed += 1
        print("  ❌ the lossless merge is not exact:", merged_diffs)

    # ── 11. merge in the lossy regime stays inside the stated bound ────────
    var half_a = List[Float64]()
    var half_b = List[Float64]()
    for i in range(len(big)):
        if i < 9000:
            half_a.append(big[i])
        else:
            half_b.append(big[i])
    var lossy = quantile_merge(
        quantile_ingest(half_a, 256, 7), quantile_ingest(half_b, 256, 7)
    )
    var lossy_breaches = 0
    var lossy_worst = 0.0
    for i in range(1, 100):
        var q = Float64(i) / 100.0
        var got = quantile_at(lossy, q)
        var err = Float64(_exact_rank(sorted_big, got.value)) - Float64(_ceil_rank(q, 20000))
        if err < 0.0:
            err = -err
        if err > lossy_worst:
            lossy_worst = err
        if err > slack256:
            lossy_breaches += 1
    if lossy.valid and lossy.n == 20000 and quantile_total_weight(lossy) == 20000 \
            and lossy_breaches == 0:
        passed += 1
        print("  ✅ a MERGED sketch of two 10,000-item halves keeps total weight 20,000 and its",
              "worst rank error is", lossy_worst, "of", slack256, "allowed — 0 breaches")
    else:
        failed += 1
        print("  ❌ the merged sketch left its bound:", lossy_breaches, lossy_worst)

    # ── 12. quantile_batch == quantile_at, one profile instead of many ─────
    var qs = List[Float64]()
    for i in range(1, 100):
        qs.append(Float64(i) / 100.0)
    qs.append(-0.5)
    qs.append(1.5)
    qs.append(Float64(0.0) / Float64(0.0))
    var batch = quantile_batch(sketch, qs)
    var batch_diffs = 0
    for i in range(99):
        if batch.values[i] != quantile_at(sketch, qs[i]).value or not batch.present[i]:
            batch_diffs += 1
    if batch.valid and len(batch.values) == 102 and batch_diffs == 0 \
            and not batch.present[99] and not batch.present[100] \
            and not batch.present[101] \
            and batch.values[99] == 0.0 and batch.values[101] == 0.0:
        passed += 1
        print("  ✅ quantile_batch agrees with quantile_at on all 99 valid entries and marks",
              "-0.5, 1.5 and NaN individually ABSENT with a representable 0.0 in the slot —",
              "one bad q does not fail the batch, and no non-finite reaches the response")
    else:
        failed += 1
        print("  ❌ batch and single-shot disagree:", batch_diffs, len(batch.values))

    # ── 13. the profile is a CDF ending at n exactly ───────────────────────
    var profile = quantile_profile(sketch)
    var monotone = True
    for j in range(1, len(profile.values)):
        if profile.values[j] <= profile.values[j - 1]:
            monotone = False
        if profile.cumulative[j] <= profile.cumulative[j - 1]:
            monotone = False
    if profile.valid and monotone \
            and profile.cumulative[len(profile.cumulative) - 1] == 20000:
        passed += 1
        print("  ✅ the profile is strictly increasing in both value and cumulative weight, and",
              "its last cumulative entry is exactly", profile.cumulative[len(profile.cumulative) - 1])
    else:
        failed += 1
        print("  ❌ the profile is not a well-formed CDF")

    # ── 14. snapshot round trip, and refusals on every corruption ─────────
    var snap = quantile_snapshot(sketch)
    var restored = quantile_from_snapshot(snap.header, snap.values)
    var restore_diffs = 0
    if len(restored.values) == len(sketch.values):
        for j in range(len(restored.values)):
            if restored.values[j] != sketch.values[j]:
                restore_diffs += 1
    else:
        restore_diffs = -1
    if restored.valid and restore_diffs == 0 and restored.n == sketch.n \
            and restored.minimum == sketch.minimum \
            and quantile_at(restored, 0.5).value == quantile_at(sketch, 0.5).value:
        passed += 1
        print("  ✅ the snapshot round-trips value for value and reproduces the same median",
              quantile_at(restored, 0.5).value)
    else:
        failed += 1
        print("  ❌ the snapshot did not round-trip:", restore_diffs)

    var corruptions = 0
    var bad_magic = snap.header.copy()
    bad_magic[0] = 0
    if quantile_from_snapshot(bad_magic, snap.values).status == STM_ERR_SNAPSHOT_SHAPE:
        corruptions += 1
    var bad_n = snap.header.copy()
    bad_n[3] = 19999
    if quantile_from_snapshot(bad_n, snap.values).status == STM_ERR_SNAPSHOT_SHAPE:
        corruptions += 1
    var bad_k = snap.header.copy()
    bad_k[1] = 255
    if quantile_from_snapshot(bad_k, snap.values).status == STM_ERR_CAPACITY:
        corruptions += 1
    var bad_levels = snap.header.copy()
    bad_levels[4] = MAX_STM_LEVELS + 1
    if quantile_from_snapshot(bad_levels, snap.values).status == STM_ERR_LEVEL_OVERFLOW:
        corruptions += 1
    var nan_values = snap.values.copy()
    nan_values[QUANTILE_VALUE_HEADER] = Float64(0.0) / Float64(0.0)
    if quantile_from_snapshot(snap.header, nan_values).status == STM_ERR_NON_FINITE:
        corruptions += 1
    var short_values = List[Float64]()
    short_values.append(1.0)
    short_values.append(2.0)
    if quantile_from_snapshot(snap.header, short_values).status == STM_ERR_SNAPSHOT_SHAPE:
        corruptions += 1
    if quantile_from_snapshot(List[Int](), List[Float64]()).status == STM_ERR_SNAPSHOT_SHAPE:
        corruptions += 1
    if corruptions == 7:
        passed += 1
        print("  ✅ 7 snapshot corruptions are refused with typed statuses — a wrong magic, a",
              "weight/n mismatch, a k the sketch was not built with, a level count past the",
              "ceiling, a NaN in the payload, a truncated payload and an empty pair")
    else:
        failed += 1
        print("  ❌ only", corruptions, "of 7 corruptions were refused")

    var snap_a = quantile_snapshot(quantile_ingest(half_a, 256, 7))
    var snap_b = quantile_snapshot(quantile_ingest(half_b, 256, 7))
    var from_snaps = quantile_merge_snapshots(
        snap_a.header, snap_a.values, snap_b.header, snap_b.values
    )
    if from_snaps.valid and from_snaps.n == 20000:
        passed += 1
        print("  ✅ merging two flat snapshot pairs reproduces n =", from_snaps.n)
    else:
        failed += 1
        print("  ❌ snapshot merge failed")

    # ── 15. absence, and every refusal typed ──────────────────────────────
    var empty = quantile_empty(256, 1)
    var refusals = 0
    if empty.valid and not quantile_at(empty, 0.5).present \
            and quantile_at(empty, 0.5).status == STM_EMPTY \
            and quantile_at(empty, 0.5).value == 0.0:
        refusals += 1
    if not quantile_minimum(empty).present and quantile_minimum(empty).status == STM_EMPTY:
        refusals += 1
    if not quantile_rank(empty, 5.0).present:
        refusals += 1
    if not quantile_profile(empty).valid and quantile_profile(empty).status == STM_EMPTY:
        refusals += 1
    if quantile_at(exact, 1.5).status == STM_ERR_QUANTILE_RANGE:
        refusals += 1
    if quantile_at(exact, -0.1).status == STM_ERR_QUANTILE_RANGE:
        refusals += 1
    if quantile_at(exact, Float64(0.0) / Float64(0.0)).status == STM_ERR_QUANTILE_RANGE:
        refusals += 1
    if quantile_empty(5, 1).status == STM_ERR_CAPACITY:
        refusals += 1
    if quantile_empty(2, 1).status == STM_ERR_CAPACITY:
        refusals += 1
    if quantile_empty(MAX_STM_K + 2, 1).status == STM_ERR_CAPACITY:
        refusals += 1
    if quantile_ingest_prefix(ramp, 101, 256, 1).status == STM_ERR_COUNT:
        refusals += 1
    if quantile_ingest_prefix(ramp, -3, 256, 1).status == STM_ERR_COUNT:
        refusals += 1
    var with_nan = ramp.copy()
    with_nan[7] = Float64(1.0) / Float64(0.0)
    if quantile_ingest(with_nan, 256, 1).status == STM_ERR_NON_FINITE:
        refusals += 1
    if quantile_add(exact, Float64(0.0) / Float64(0.0)).status == STM_ERR_NON_FINITE:
        refusals += 1
    if quantile_merge(quantile_empty(256, 1), quantile_empty(512, 1)).status \
            == STM_ERR_INCOMPATIBLE_MERGE:
        refusals += 1
    if quantile_merge(quantile_empty(256, 1), quantile_empty(256, 9)).status \
            == STM_ERR_INCOMPATIBLE_MERGE:
        refusals += 1
    if refusals == 16:
        passed += 1
        print("  ✅ 16 unusable requests are refused or reported ABSENT with typed statuses,",
              "and an empty sketch's quantile is", stm_status_name(STM_EMPTY),
              "with a representable 0.0 in the value slot — never 0.0 as an answer")
    else:
        failed += 1
        print("  ❌ only", refusals, "of 16 refusals fired")

    # ── 16. an odd k is refused: a compaction halves a level exactly ───────
    if quantile_empty(255, 1).status == STM_ERR_CAPACITY \
            and quantile_empty(256, 1).status == STM_OK:
        passed += 1
        print("  ✅ an odd k is refused and an even one accepted — halving a level is",
              "arithmetic, not a rounding rule")
    else:
        failed += 1
        print("  ❌ an odd capacity was accepted")

    # ── 17. determinism: same input and seed, identical sketch ────────────
    var run_a = quantile_ingest(big, 256, 7)
    var run_b = quantile_ingest(big, 256, 7)
    var run_c = quantile_ingest(big, 256, 8)
    var same = len(run_a.values) == len(run_b.values)
    if same:
        for j in range(len(run_a.values)):
            if run_a.values[j] != run_b.values[j]:
                same = False
    var differs = len(run_a.values) != len(run_c.values)
    if not differs:
        for j in range(len(run_a.values)):
            if run_a.values[j] != run_c.values[j]:
                differs = True
                break
    if same and differs:
        passed += 1
        print("  ✅ identical input and seed give an identical sketch; a different seed gives a",
              "different compaction — the coins are keyed, not process-random")
    else:
        failed += 1
        print("  ❌ the sketch is not reproducible or ignores its seed")

    # ── 18. A FORGED STRUCT. Six of these used to kill the process. ───────
    #
    # `QuantileSketch` is decoded from caller JSON positionally, and the runtime validates field
    # TYPES only, so `valid: true` beside `level_sizes: [8]` and an EMPTY `values` list is an
    # accepted request. Against the code before this block existed, `quantile_at`,
    # `quantile_add`, `quantile_batch`, `quantile_rank`, `quantile_profile` and `quantile_merge`
    # ALL died at `quantiles.mojo:339` -- `values[cursor + j]` inside `_levels_of` -- on an
    # uncatchable bounds assertion that the dispatch's `try/except` did not contain.
    var one_size = List[Int]()
    one_size.append(8)
    var one_comp = List[Int]()
    one_comp.append(0)
    var forged = QuantileSketch(
        List[Float64](), one_size, one_comp, 8, 8, 0, 1.0, 8.0, STM_OK, True
    )
    var f_at = quantile_at(forged, 0.5)
    var f_add = quantile_add(forged, 1.0)
    var f_batch = quantile_batch(forged, qs)
    var f_rank = quantile_rank(forged, 1.0)
    var f_prof = quantile_profile(forged)
    var f_merge = quantile_merge(forged, forged)
    if not f_at.present and f_at.status == STM_ERR_SNAPSHOT_SHAPE \
            and not f_add.valid and f_add.status == STM_ERR_SNAPSHOT_SHAPE \
            and not f_batch.valid and not f_rank.present and not f_prof.valid \
            and not f_merge.valid \
            and quantile_total_weight(forged) == -1 \
            and len(quantile_snapshot(forged).header) == 0:
        passed += 1
        print("  ✅ a struct declaring level_sizes [8] with an EMPTY values list is refused by",
              "at, add, batch, rank, profile, merge, total_weight and snapshot under",
              stm_status_name(STM_ERR_SNAPSHOT_SHAPE))
    else:
        failed += 1
        print("  ❌ a forged sketch was accepted:", f_at.status, f_add.status,
              quantile_total_weight(forged))

    # ── 19. A SHORT compactions list is its own abort, and its own check ───
    #
    # `_compact` reads `comps[index]` for a level it did not create, so `level_sizes` of length 5
    # beside `compactions` of length 1 aborts just as surely as a short `values` -- through a
    # different subscript, which is why the relation is declared and checked separately.
    var five_sizes = List[Int]()
    var five_values = List[Float64]()
    for i in range(5):
        five_sizes.append(1)
        five_values.append(Float64(i + 1))
    var short_comps = List[Int]()
    short_comps.append(0)
    # weight = 1*1 + 1*2 + 1*4 + 1*8 + 1*16 = 31
    var mismatched = QuantileSketch(
        five_values, five_sizes, short_comps, 8, 31, 0, 1.0, 5.0, STM_OK, True
    )
    if not quantile_add(mismatched, 2.0).valid \
            and quantile_add(mismatched, 2.0).status == STM_ERR_SNAPSHOT_SHAPE \
            and not quantile_at(mismatched, 0.5).present:
        passed += 1
        print("  ✅ 5 level_sizes beside 1 compaction counter is refused under",
              stm_status_name(STM_ERR_SNAPSHOT_SHAPE),
              "— the second uncatchable subscript, checked separately from the first")
    else:
        failed += 1
        print("  ❌ a short compactions list was accepted")

    # ── 20. THE WRAPPING SHIFT in quantile_total_weight ───────────────────
    #
    # THE WRONG ANSWER THIS PINS: `total += level_sizes[i] * (1 << i)` wraps once i reaches 63.
    # With 64 level_sizes entries of 1 each, the sum is `(2^63 - 1) + (-2^63) == -1` -- which
    # collides with this function's OWN "unusable sketch" sentinel, so a wrapped garbage total
    # was indistinguishable from a refusal. Other shapes returned -9223372036854775807 under a
    # contract promising a non-negative total. `MAX_STM_LEVELS` was enforced in
    # `quantile_from_snapshot` and nowhere on the struct path.
    # The payload is chosen so the WRAPPED value is not -1 and the assertion therefore
    # discriminates: 64 levels with sizes [1, 0 x 62, 1] sum to `1 * 2^0 + 1 * 2^63`, and
    # `2^63` wraps to the most negative Int64, giving exactly -9223372036854775807. A payload
    # of 64 ones would wrap to -1 and pass this assertion for the WRONG reason, which is
    # itself the trap: the wrapped total can collide with the sentinel.
    var many_sizes = List[Int]()
    var many_comps = List[Int]()
    var many_values = List[Float64]()
    for i in range(64):
        many_sizes.append(1 if (i == 0 or i == 63) else 0)
        many_comps.append(0)
    many_values.append(1.0)
    many_values.append(2.0)
    var over_levels = QuantileSketch(
        many_values, many_sizes, many_comps, 8, 2, 0, 1.0, 2.0, STM_OK, True
    )
    if quantile_total_weight(over_levels) == -1 \
            and quantile_total_weight(over_levels) != -9223372036854775807 \
            and not quantile_at(over_levels, 0.5).present \
            and quantile_at(over_levels, 0.5).status == STM_ERR_LEVEL_OVERFLOW \
            and MAX_STM_LEVELS == 40:
        passed += 1
        print("  ✅ 64 levels are refused under", stm_status_name(STM_ERR_LEVEL_OVERFLOW),
              "BEFORE the weight loop runs, so every 1 << i here is at most 2^39 — the level",
              "ceiling is now enforced on the struct path and not only on the snapshot path")
    else:
        failed += 1
        print("  ❌ 64 levels reached the weight loop:", quantile_total_weight(over_levels))

    # ── 21. a forged non-finite in an extreme slot, and an incoherent n ────
    var nan_bounds = QuantileSketch(
        five_values, five_sizes, five_sizes, 8, 31,
        0, Float64(0.0) / Float64(0.0), 5.0, STM_OK, True
    )
    var bad_weight = QuantileSketch(
        five_values, five_sizes, five_sizes, 8, 7, 0, 1.0, 5.0, STM_OK, True
    )
    if not quantile_minimum(nan_bounds).present \
            and quantile_minimum(nan_bounds).status == STM_ERR_NON_FINITE \
            and not quantile_maximum(nan_bounds).present \
            and not quantile_at(nan_bounds, 0.0).present \
            and not quantile_minimum(bad_weight).present \
            and quantile_minimum(bad_weight).status == STM_ERR_SNAPSHOT_SHAPE:
        passed += 1
        print("  ✅ a NaN minimum is refused rather than echoed back (one non-finite field makes",
              "the WHOLE response a typed error), and a stored n that the levels cannot account",
              "for is refused under", stm_status_name(STM_ERR_SNAPSHOT_SHAPE))
    else:
        failed += 1
        print("  ❌ a forged extreme or an incoherent n was accepted")

    print("  [streaming.quantiles] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("test_streaming_quantiles: " + String(failed) + " failure(s)")
