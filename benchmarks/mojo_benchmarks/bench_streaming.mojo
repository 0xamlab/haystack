"""bench_streaming.mojo — the sketch claims, measured, and gated on SHAPE.

Prints `BENCH_GATE streaming PASS` when every shape assertion holds.

WHAT IS GATED, AND WHY NEVER A NANOSECOND COUNT
----------------------------------------------
An absolute timing gate measures the machine it ran on. Everything gated here is a property of
the ALGORITHM that survives a change of hardware:

1. **Per-item ingest cost is FLAT as the stream grows.** A sketch's whole reason to exist is
   that it costs O(1) per item and O(1) memory in the stream length. So `n` goes
   16,384 -> 32,768 -> 65,536 -> 131,072 and the gate is that nanoseconds PER ITEM stays inside
   a stated band. A hidden per-item rescan — the commonest way a streaming implementation stops
   being one — shows up immediately as a rising per-item cost, while a machine 10x faster or
   slower moves every number by the same factor and changes no verdict.

2. **Memory does NOT grow with the stream.** The distinct sketch holds `2^precision` registers
   and the frequency sketch `depth * width` cells whatever `n` is, and the quantile sketch holds
   O(k log(n/k)) items. Those are asserted as exact counts, not measured: the register count must
   be IDENTICAL across a 8x range of `n`, and the quantile sketch's stored-item count must grow
   by less than the logarithm of the size ratio times `k`.

3. **The bound claims are checked against exact answers at scale.** A performance number for a
   wrong answer is worthless. The exact distinct count and the exact per-key frequency are
   computed here, and the sketch's error is checked against `stm_hll_relative_error` and
   `stm_cms_epsilon` at every size — because an accuracy bug shows up at 131,072 items long
   before it shows up at 25.

4. **THE COST DISPARITY BETWEEN TWO O(n) LOOPS IS MEASURED AND REPORTED, NOT HIDDEN.** One
   budget unit means "a Philox4x64-10 round plus an increment" in `frequency` and "a deque
   compare" in `windows`, and those are not the same nanosecond count. Section 6 measures both at
   an IDENTICAL declared work charge and prints the ratio, so the disparity is a number a reader
   can see rather than a surprise. It is reported and bounded rather than gated at 1.0, because
   equalising it would mean lying about one of the two costs.

5. **The two WINDOW costs are genuinely different, and the gate is that the ratio GROWS.**
   `window_mean` is the frozen O(n) sliding sum and `window_std` is the frozen O(n*w) recompute.
   As `w` doubles at fixed `n`, the mean's cost must stay flat and the std's must roughly double,
   so the RATIO between them must grow. That is the shape that makes charging `n + w` for the
   std the error this package refuses to repeat: at n = 1,000,000 and w = 500,000 it is minutes
   of work behind a request that declared almost nothing.

6. **A merge is cheaper than a re-ingest, and the gate is the ratio.** The point of a mergeable
   sketch is that combining two partials does not cost what re-reading both streams costs. Gated
   as `merge_ns * 4 <= reingest_ns` at the largest size.

TIMING METHOD
-------------
Every timing is the MINIMUM of `REPEATS` runs. The workload is deterministic, so its true cost is
the floor and anything else on the machine can only add to it; a flatness gate over single shots
is a test of who else is on the box. A warm-up pass runs first, so the smallest size is not the
one paying for page faults.

EVERY INPUT COMES FROM THE FROZEN KEYED GENERATOR
------------------------------------------------
`determinism.counter_rng.rng_uniform` with an explicit `MASTER_SEED`, so every stream is a pure
function of `(seed, stream, index)`. Re-running measures the same work on the same data.
`random_float64` appears nowhere.
"""
from std.time import perf_counter_ns

from determinism.counter_rng import rng_uniform

from streaming.contract import (
    STM_OK,
    stm_cms_epsilon,
    stm_hll_relative_error,
    stm_kll_rank_error,
)
from streaming.distinct import (
    distinct_estimate,
    distinct_ingest,
    distinct_merge,
    distinct_register_count,
)
from streaming.drift import page_hinkley_scan
from streaming.frequency import (
    frequency_ingest,
    frequency_merge,
    frequency_query,
)
from streaming.quantiles import (
    quantile_at,
    quantile_ingest,
    quantile_merge,
)
from streaming.windows import window_mean, window_min, window_std

comptime MASTER_SEED: UInt64 = 0x53545245414D0001
comptime REPEATS: Int = 5

#: The per-item flatness band. Wide enough that a shared machine does not fail the gate, tight
#: enough that a hidden per-item rescan — which would grow the cost by the size ratio, 8x here —
#: cannot pass it.
comptime FLAT_RATIO: Float64 = 4.0

#: Sigma multiple for the HLL accuracy check at scale. Stated, because asserting an observed
#: error inside ONE sigma would be asserting that a coin lands heads.
comptime SIGMA_MULTIPLE: Float64 = 4.0


fn _keyed_ids(n: Int, n_distinct: Int, stream: UInt64) -> List[Int]:
    """`n` identifiers drawn from the frozen keyed generator, over `n_distinct` values."""
    var out = List[Int]()
    for i in range(n):
        var u = rng_uniform(MASTER_SEED, 0, 0, 0, 0, stream, UInt64(i))
        out.append(Int(u * Float64(n_distinct)) % n_distinct)
    return out^


fn _keyed_values(n: Int, stream: UInt64) -> List[Float64]:
    """`n` observations in [0, 1000) from the frozen keyed generator."""
    var out = List[Float64]()
    for i in range(n):
        out.append(rng_uniform(MASTER_SEED, 0, 0, 0, 0, stream, UInt64(i)) * 1000.0)
    return out^


fn _exact_distinct(items: List[Int]) -> Int:
    """The oracle: distinct count by a bitmap over the known-bounded id range."""
    var seen = List[Bool]()
    var top = 0
    for i in range(len(items)):
        if items[i] > top:
            top = items[i]
    for _ in range(top + 1):
        seen.append(False)
    var count = 0
    for i in range(len(items)):
        if not seen[items[i]]:
            seen[items[i]] = True
            count += 1
    return count


fn _exact_count(items: List[Int], key: Int) -> Int:
    """The oracle: how many times `key` appears, by a scan."""
    var seen = 0
    for i in range(len(items)):
        if items[i] == key:
            seen += 1
    return seen


fn _band(values: List[Float64]) -> Float64:
    """`max / min` over a list of per-unit costs. 1.0 means perfectly flat."""
    var lo = values[0]
    var hi = values[0]
    for i in range(len(values)):
        if values[i] < lo:
            lo = values[i]
        if values[i] > hi:
            hi = values[i]
    if lo <= 0.0:
        return 1.0
    return hi / lo


fn main() raises:
    print("bench_streaming — sketches over unbounded streams")
    print("")
    var failures = 0

    var sizes = List[Int]()
    sizes.append(16384)
    sizes.append(32768)
    sizes.append(65536)
    sizes.append(131072)

    # ── warm-up, so the smallest size is not the one paying for page faults ──
    var warm = _keyed_ids(4096, 512, 11)
    _ = distinct_ingest(warm, 12, 5)
    _ = frequency_ingest(warm, 512, 4, 5)
    _ = quantile_ingest(_keyed_values(4096, 12), 256, 5)

    print("── 1. HyperLogLog: per-item cost flat, memory constant, bound checked ──")
    var hll_per_item = List[Float64]()
    var hll_registers = List[Int]()
    var worst_sigma = 0.0
    for s in range(len(sizes)):
        var n = sizes[s]
        var items = _keyed_ids(n, n // 4, 21)
        var best_ns = 0
        for r in range(REPEATS):
            var t0 = perf_counter_ns()
            var sk = distinct_ingest(items, 12, 7)
            var t1 = perf_counter_ns()
            if sk.status != STM_OK:
                failures += 1
            if r == 0 or Int(t1 - t0) < best_ns:
                best_ns = Int(t1 - t0)
        var sketch = distinct_ingest(items, 12, 7)
        hll_registers.append(distinct_register_count(sketch))
        hll_per_item.append(Float64(best_ns) / Float64(n))
        var truth = _exact_distinct(items)
        var est = distinct_estimate(sketch)
        var claim = stm_hll_relative_error(12)
        var rel = (est.value - Float64(truth)) / Float64(truth)
        if rel < 0.0:
            rel = -rel
        var sigma = rel / claim.value
        if sigma > worst_sigma:
            worst_sigma = sigma
        print("   n =", n, " ns/item", hll_per_item[s], " registers", hll_registers[s],
              " exact", truth, " estimate", est.value, " sigma", sigma)
    var hll_band = _band(hll_per_item)
    if hll_band <= FLAT_RATIO:
        print("  ✅ ns per item is flat over an 8x size range: band", hll_band, "<=", FLAT_RATIO)
    else:
        failures += 1
        print("  ❌ ns per item is NOT flat: band", hll_band)
    var registers_constant = True
    for s in range(len(hll_registers)):
        if hll_registers[s] != hll_registers[0]:
            registers_constant = False
    if registers_constant and hll_registers[0] == 4096:
        print("  ✅ memory is 4096 registers at every size — constant in the stream length,",
              "which is the whole claim of a sketch")
    else:
        failures += 1
        print("  ❌ the register count moved with n")
    if worst_sigma <= SIGMA_MULTIPLE:
        print("  ✅ worst relative error", worst_sigma, "sigma over 4 sizes, inside the stated",
              SIGMA_MULTIPLE, "x the claimed 1.04/sqrt(m)")
    else:
        failures += 1
        print("  ❌ the HLL bound was breached at", worst_sigma, "sigma")

    print("")
    print("── 2. Count-Min: per-item cost flat in n, LINEAR in depth, bound checked ──")
    var cms_per_item = List[Float64]()
    var cms_cells = List[Int]()
    var worst_over = 0.0
    for s in range(len(sizes)):
        var n = sizes[s]
        var items = _keyed_ids(n, 2000, 31)
        var best_ns = 0
        for r in range(REPEATS):
            var t0 = perf_counter_ns()
            var sk = frequency_ingest(items, 512, 4, 9)
            var t1 = perf_counter_ns()
            if sk.status != STM_OK:
                failures += 1
            if r == 0 or Int(t1 - t0) < best_ns:
                best_ns = Int(t1 - t0)
        var sketch = frequency_ingest(items, 512, 4, 9)
        cms_cells.append(len(sketch.cells))
        cms_per_item.append(Float64(best_ns) / Float64(n))
        var eps = stm_cms_epsilon(512)
        var slack = eps.value * Float64(sketch.total)
        var under = 0
        var over_hi = 0.0
        for key in range(0, 2000, 97):
            var truth = _exact_count(items, key)
            var est = frequency_query(sketch, key)
            if est.count < truth:
                under += 1
            var over = Float64(est.count - truth)
            if over > over_hi:
                over_hi = over
        if under > 0:
            failures += 1
            print("   ❌ n =", n, ":", under, "keys UNDER-stated — the one absolute guarantee")
        var ratio = over_hi / slack
        if ratio > worst_over:
            worst_over = ratio
        print("   n =", n, " ns/item", cms_per_item[s], " cells", cms_cells[s],
              " worst over-estimate", over_hi, " of", slack, "allowed")
    var cms_band = _band(cms_per_item)
    if cms_band <= FLAT_RATIO:
        print("  ✅ ns per item is flat over an 8x size range: band", cms_band, "<=", FLAT_RATIO)
    else:
        failures += 1
        print("  ❌ ns per item is NOT flat: band", cms_band)
    var cells_constant = True
    for s in range(len(cms_cells)):
        if cms_cells[s] != cms_cells[0]:
            cells_constant = False
    if cells_constant and cms_cells[0] == 2048:
        print("  ✅ memory is 2048 cells at every size")
    else:
        failures += 1
        print("  ❌ the cell count moved with n")
    if worst_over <= 1.0:
        print("  ✅ worst over-estimate is", worst_over, "x the epsilon allowance — inside it")
    else:
        failures += 1
        print("  ❌ the epsilon allowance was breached by", worst_over, "x")

    # DEPTH IS A MULTIPLIER ON WORK, and the declared charge is the PRODUCT n*depth. Measured:
    # doubling depth at fixed n must roughly double the ingest cost. If it did not, the charge
    # would be over-stated; if the charge were `n + depth`, a depth-16 request would be sixteen
    # times the work behind an identical-looking declaration.
    var depth_items = _keyed_ids(32768, 2000, 33)
    var d2_ns = 0
    var d8_ns = 0
    for r in range(REPEATS):
        var t0 = perf_counter_ns()
        _ = frequency_ingest(depth_items, 512, 2, 9)
        var t1 = perf_counter_ns()
        if r == 0 or Int(t1 - t0) < d2_ns:
            d2_ns = Int(t1 - t0)
        var t2 = perf_counter_ns()
        _ = frequency_ingest(depth_items, 512, 8, 9)
        var t3 = perf_counter_ns()
        if r == 0 or Int(t3 - t2) < d8_ns:
            d8_ns = Int(t3 - t2)
    var depth_growth = Float64(d8_ns) / Float64(d2_ns)
    if depth_growth >= 2.0:
        print("  ✅ depth 2 -> 8 at fixed n grows the cost", depth_growth,
              "x — work is the PRODUCT n*depth, which is what the budget charges")
    else:
        failures += 1
        print("  ❌ depth did not multiply the work:", depth_growth, "x for a 4x depth")

    print("")
    print("── 3. KLL quantiles: per-item cost flat, memory LOGARITHMIC, bound checked ──")
    var kll_per_item = List[Float64]()
    var kll_stored = List[Int]()
    var kll_worst_rank = 0.0
    for s in range(len(sizes)):
        var n = sizes[s]
        var values = _keyed_values(n, 41)
        var best_ns = 0
        for r in range(REPEATS):
            var t0 = perf_counter_ns()
            var sk = quantile_ingest(values, 256, 3)
            var t1 = perf_counter_ns()
            if sk.status != STM_OK:
                failures += 1
            if r == 0 or Int(t1 - t0) < best_ns:
                best_ns = Int(t1 - t0)
        var sketch = quantile_ingest(values, 256, 3)
        kll_stored.append(len(sketch.values))
        kll_per_item.append(Float64(best_ns) / Float64(n))
        # The rank error against an exact count over the raw input. O(n) per probe, so a handful
        # of probes rather than all 99 — the suite does the full sweep.
        var claim = stm_kll_rank_error(256)
        var slack = claim.value * Float64(n)
        var worst = 0.0
        for p in range(1, 10):
            var q = Float64(p) / 10.0
            var got = quantile_at(sketch, q)
            var rank = 0
            for i in range(n):
                if values[i] <= got.value:
                    rank += 1
            var want = Float64(n) * q
            var err = Float64(rank) - want
            if err < 0.0:
                err = -err
            if err > worst:
                worst = err
        var ratio = worst / slack
        if ratio > kll_worst_rank:
            kll_worst_rank = ratio
        print("   n =", n, " ns/item", kll_per_item[s], " stored items", kll_stored[s],
              " worst rank error", worst, " of", slack, "allowed")
    var kll_band = _band(kll_per_item)
    if kll_band <= FLAT_RATIO:
        print("  ✅ ns per item is flat over an 8x size range: band", kll_band, "<=", FLAT_RATIO)
    else:
        failures += 1
        print("  ❌ ns per item is NOT flat: band", kll_band)
    # Memory grows LOGARITHMICALLY: an 8x size range adds 3 levels, each holding under k items,
    # so the stored count must grow by less than 3k = 768 across the range.
    # The BOUND is O(k log(n/k)): an 8x size range adds 3 levels, each holding under k items, so
    # the stored count may grow by at most 3k = 768. The MEASUREMENT on this data is that it does
    # not grow at all, because the cascade drains each level down to its leftover as soon as it
    # fills. The gate is the bound, and the measurement is printed beside it -- gating on the
    # stronger observed behaviour would fail on a stream that legitimately parks items mid-level.
    var stored_growth = kll_stored[len(kll_stored) - 1] - kll_stored[0]
    if stored_growth < 3 * 256 and kll_stored[0] > 0:
        print("  ✅ stored items went", kll_stored[0], "->",
              kll_stored[len(kll_stored) - 1], "over an 8x size range, a growth of",
              stored_growth, "against the O(k log(n/k)) allowance of 768 — memory is not O(n)")
    else:
        failures += 1
        print("  ❌ the quantile sketch's memory grew by", stored_growth, "— not logarithmic")
    if kll_worst_rank <= 1.0:
        print("  ✅ worst rank error is", kll_worst_rank, "x the claimed allowance — inside it")
    else:
        failures += 1
        print("  ❌ the KLL rank bound was breached by", kll_worst_rank, "x")

    print("")
    print("── 4. a MERGE costs less than a re-ingest ──")
    var big_n = sizes[len(sizes) - 1]
    var left_ids = _keyed_ids(big_n // 2, big_n // 8, 51)
    var right_ids = _keyed_ids(big_n // 2, big_n // 8, 52)
    var all_ids = List[Int]()
    for i in range(len(left_ids)):
        all_ids.append(left_ids[i])
    for i in range(len(right_ids)):
        all_ids.append(right_ids[i])
    var sk_left = distinct_ingest(left_ids, 12, 7)
    var sk_right = distinct_ingest(right_ids, 12, 7)
    var merge_ns = 0
    var reingest_ns = 0
    for r in range(REPEATS):
        var t0 = perf_counter_ns()
        var m = distinct_merge(sk_left, sk_right)
        var t1 = perf_counter_ns()
        if m.status != STM_OK:
            failures += 1
        if r == 0 or Int(t1 - t0) < merge_ns:
            merge_ns = Int(t1 - t0)
        var t2 = perf_counter_ns()
        _ = distinct_ingest(all_ids, 12, 7)
        var t3 = perf_counter_ns()
        if r == 0 or Int(t3 - t2) < reingest_ns:
            reingest_ns = Int(t3 - t2)
    print("   merge", merge_ns, "ns   re-ingest", reingest_ns, "ns over", big_n, "items")
    if merge_ns * 4 <= reingest_ns:
        print("  ✅ a distinct merge is at least 4x cheaper than re-reading both streams —",
              "which is what makes a partial snapshot worth shipping")
    else:
        failures += 1
        print("  ❌ merging is not materially cheaper than re-ingesting")

    var fq_left = frequency_ingest(left_ids, 512, 4, 9)
    var fq_right = frequency_ingest(right_ids, 512, 4, 9)
    var fmerge_ns = 0
    var freingest_ns = 0
    for r in range(REPEATS):
        var t0 = perf_counter_ns()
        _ = frequency_merge(fq_left, fq_right)
        var t1 = perf_counter_ns()
        if r == 0 or Int(t1 - t0) < fmerge_ns:
            fmerge_ns = Int(t1 - t0)
        var t2 = perf_counter_ns()
        _ = frequency_ingest(all_ids, 512, 4, 9)
        var t3 = perf_counter_ns()
        if r == 0 or Int(t3 - t2) < freingest_ns:
            freingest_ns = Int(t3 - t2)
    if fmerge_ns * 4 <= freingest_ns:
        print("  ✅ a frequency merge is at least 4x cheaper than re-ingesting:", fmerge_ns,
              "vs", freingest_ns, "ns")
    else:
        failures += 1
        print("  ❌ frequency merging is not materially cheaper:", fmerge_ns, freingest_ns)

    var qq_left = quantile_ingest(_keyed_values(big_n // 2, 61), 256, 3)
    var qq_right = quantile_ingest(_keyed_values(big_n // 2, 62), 256, 3)
    var qmerge_ns = 0
    for r in range(REPEATS):
        var t0 = perf_counter_ns()
        var m = quantile_merge(qq_left, qq_right)
        var t1 = perf_counter_ns()
        if m.status != STM_OK:
            failures += 1
        if r == 0 or Int(t1 - t0) < qmerge_ns:
            qmerge_ns = Int(t1 - t0)
    print("   quantile merge", qmerge_ns, "ns")

    print("")
    print("── 5. the TWO WINDOW COSTS are different, and the ratio GROWS with the window ──")
    var wv = _keyed_values(32768, 71)
    var widths = List[Int]()
    widths.append(64)
    widths.append(128)
    widths.append(256)
    var mean_ns = List[Float64]()
    var std_ns = List[Float64]()
    var min_ns = List[Float64]()
    for w in range(len(widths)):
        var width = widths[w]
        var m_best = 0
        var s_best = 0
        var n_best = 0
        for r in range(REPEATS):
            var t0 = perf_counter_ns()
            _ = window_mean(wv, width)
            var t1 = perf_counter_ns()
            if r == 0 or Int(t1 - t0) < m_best:
                m_best = Int(t1 - t0)
            var t2 = perf_counter_ns()
            _ = window_std(wv, width)
            var t3 = perf_counter_ns()
            if r == 0 or Int(t3 - t2) < s_best:
                s_best = Int(t3 - t2)
            var t4 = perf_counter_ns()
            _ = window_min(wv, width)
            var t5 = perf_counter_ns()
            if r == 0 or Int(t5 - t4) < n_best:
                n_best = Int(t5 - t4)
        mean_ns.append(Float64(m_best))
        std_ns.append(Float64(s_best))
        min_ns.append(Float64(n_best))
        print("   window", width, " mean", m_best, "ns   std", s_best, "ns   min", n_best,
              "ns   std/mean", Float64(s_best) / Float64(m_best))
    var mean_flat = _band(mean_ns) <= FLAT_RATIO
    var min_flat = _band(min_ns) <= FLAT_RATIO
    if mean_flat and min_flat:
        print("  ✅ the O(n) sliding mean and the O(n) monotonic-deque minimum are FLAT as the",
              "window grows 4x: bands", _band(mean_ns), "and", _band(min_ns))
    else:
        failures += 1
        print("  ❌ an O(n) window aggregate grew with the window:", _band(mean_ns),
              _band(min_ns))
    var std_grew = std_ns[len(std_ns) - 1] >= 2.0 * std_ns[0]
    var ratio_grew = (std_ns[2] / mean_ns[2]) > (std_ns[0] / mean_ns[0])
    if std_grew and ratio_grew:
        print("  ✅ the O(n*window) std grew", std_ns[2] / std_ns[0], "x over a 4x window and",
              "its ratio to the mean GREW — which is why the budget charges it as a product;",
              "charging n + window would put 800,000,000 element visits behind a cheap request")
    else:
        failures += 1
        print("  ❌ the std did not grow with the window:", std_ns[2] / std_ns[0])

    print("")
    print("── 6. one budget unit is NOT one nanosecond, and the disparity is reported ──")
    # THE HONEST VERSION OF A SHARED BUDGET. `frequency_ingest_prefix` charges n*depth for a
    # Philox4x64-10 round plus an increment per unit; `window_min` charges n*1 for a deque
    # compare; `window_std` charges n*window for an element visit. Those are all "one unit" and
    # they are not the same nanosecond count. Measured at an identical declared charge, printed
    # as a ratio, and BOUNDED rather than gated at 1.0 — equalising it would mean over-stating
    # one of the three, and an over-stated budget refuses valid requests.
    var charge_items = _keyed_ids(100000, 4000, 81)
    var charge_values = _keyed_values(1600000, 82)
    var freq_ns = 0
    var wmin_ns = 0
    var wstd_ns = 0
    for r in range(REPEATS):
        var t0 = perf_counter_ns()
        _ = frequency_ingest(charge_items, 512, 16, 9)
        var t1 = perf_counter_ns()
        if r == 0 or Int(t1 - t0) < freq_ns:
            freq_ns = Int(t1 - t0)
        var t2 = perf_counter_ns()
        _ = window_min(charge_values, 8)
        var t3 = perf_counter_ns()
        if r == 0 or Int(t3 - t2) < wmin_ns:
            wmin_ns = Int(t3 - t2)
        var t4 = perf_counter_ns()
        _ = window_std(charge_values, 1)
        var t5 = perf_counter_ns()
        if r == 0 or Int(t5 - t4) < wstd_ns:
            wstd_ns = Int(t5 - t4)
    var unit_lo = Float64(wstd_ns)
    var unit_hi = Float64(freq_ns)
    if Float64(wmin_ns) < unit_lo:
        unit_lo = Float64(wmin_ns)
    if Float64(wmin_ns) > unit_hi:
        unit_hi = Float64(wmin_ns)
    print("   1,600,000 declared units each: frequency", freq_ns, "ns   window_min", wmin_ns,
          "ns   window_std", wstd_ns, "ns")
    print("   spread across modules:", unit_hi / unit_lo, "x per declared unit")
    if unit_hi / unit_lo <= 200.0:
        print("  ✅ the per-unit spread is", unit_hi / unit_lo,
              "x, inside the stated 200x ceiling — the worst legal single request at the 2^27",
              "work ceiling is therefore seconds, not the 23.89s-under-a-cheap-charge precedent")
    else:
        failures += 1
        print("  ❌ the per-unit spread is", unit_hi / unit_lo, "x — a budget unit means too",
              "many different things for one ceiling to bound the work")

    print("")
    print("── 7. drift detection is O(n) with no per-update search ──")
    var drift_per_item = List[Float64]()
    for s in range(len(sizes)):
        var n = sizes[s]
        var values = _keyed_values(n, 91)
        var best_ns = 0
        for r in range(REPEATS):
            var t0 = perf_counter_ns()
            var verdict = page_hinkley_scan(values, 10.0, 500.0)
            var t1 = perf_counter_ns()
            if not verdict.present:
                failures += 1
            if r == 0 or Int(t1 - t0) < best_ns:
                best_ns = Int(t1 - t0)
        drift_per_item.append(Float64(best_ns) / Float64(n))
        print("   n =", n, " ns/observation", drift_per_item[s])
    var drift_band = _band(drift_per_item)
    if drift_band <= FLAT_RATIO:
        print("  ✅ ns per observation is flat over an 8x range: band", drift_band,
              "— Page-Hinkley keeps five scalars and searches nothing, which is why it was",
              "chosen over ADWIN's O(buckets)-per-update window search")
    else:
        failures += 1
        print("  ❌ per-observation drift cost is not flat:", drift_band)

    print("")
    print("── 8. determinism: the same seed gives a bit-identical sketch ──")
    var det_items = _keyed_ids(32768, 4096, 101)
    var run_a = distinct_ingest(det_items, 12, 7)
    var run_b = distinct_ingest(det_items, 12, 7)
    var identical = len(run_a.registers) == len(run_b.registers)
    if identical:
        for j in range(len(run_a.registers)):
            if run_a.registers[j] != run_b.registers[j]:
                identical = False
    var q_a = quantile_ingest(_keyed_values(32768, 102), 256, 3)
    var q_b = quantile_ingest(_keyed_values(32768, 102), 256, 3)
    var q_same = len(q_a.values) == len(q_b.values)
    if q_same:
        for j in range(len(q_a.values)):
            if q_a.values[j] != q_b.values[j]:
                q_same = False
    if identical and q_same:
        print("  ✅ two runs from the same seed produce bit-identical registers and a",
              "bit-identical compactor stack — every hash and every compaction coin is keyed")
    else:
        failures += 1
        print("  ❌ a sketch is not a pure function of its input and seed")

    print("")
    if failures == 0:
        print("BENCH_GATE streaming PASS")
    else:
        print("BENCH_GATE streaming FAIL " + String(failures))
