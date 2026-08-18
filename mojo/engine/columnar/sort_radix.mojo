"""
columnar.sort_radix — LSD radix sort over Float64 keys, sequential and parallel. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_columnar_sort_radix.mojo
benchmark: benchmarks/mojo_benchmarks/bench_vs_sort.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

Why this module exists
----------------------
`query.executor.sort_indices` is an insertion sort and says so in its own docstring: "`columnar`
gains a merge sort when a chunk stops fitting." Chunks stopped fitting. A benchmark against
`numpy.sort` at n = 10^5 measured the insertion path at four orders of magnitude behind, and no
constant-factor work on an O(n^2) loop closes that. This is the promised sort, and it is a radix
rather than a merge for the reason below.

Why radix and not a comparison sort
-----------------------------------
A comparison sort cannot go below n·log2(n) comparisons, and the branch on each comparison is
data-dependent, so a random-input quicksort mispredicts on roughly every other element. That
misprediction, not the comparison, is what a tuned quicksort spends its time on.

A radix sort makes NO comparisons. It reads a key, extracts a byte, and increments a counter —
all branch-free. The cost is a fixed number of passes over memory rather than a term that grows
with n, so the work per element is CONSTANT in n:

    keying pass         read data, write keys, build all 8 histograms   16 B/elem
    up to 8 scatters    read key, write key to its bucket               16 B/elem each
    final scatter       read key, write Float64 result                  16 B/elem (fused)
    parallel arm only   re-read keys to rebuild the per-worker counts   +8 B/elem per pass
                        after the first (see the note in the parallel
                        function: a per-worker histogram expires as
                        soon as a scatter moves elements between bands)

That makes it a bandwidth problem, not an arithmetic one — which is the whole reason a parallel
arm exists below, and the reason the sequential arm's ns/element is FLAT across the size sweep
while a comparison sort's grows as log n.

The order-preserving key transform, which is the only subtle line here
----------------------------------------------------------------------
IEEE-754 doubles are not directly radix-sortable as unsigned integers: the sign bit is 1 for
negatives, so all negatives sort ABOVE all positives, and within the negatives the magnitude
order is reversed. Both are fixed by one xor:

    positive (sign 0)   set the sign bit          -> lands above every mapped negative
    negative (sign 1)   invert all 64 bits        -> reverses magnitude, lands below every positive

`_radix_key` does that and `_radix_unkey` inverts it exactly, so the transform is a bijection on
all 2^64 bit patterns and the sort neither loses nor invents a value.

WHERE THIS DIFFERS FROM `numpy.sort`, stated rather than buried
---------------------------------------------------------------
1. NaN. This kernel sorts by IEEE-754 TOTAL ORDER, so a negative NaN sorts below -inf and a
   positive NaN above +inf. `numpy.sort` puts every NaN at the END regardless of its sign bit.
   Neither is wrong — they are different orders — but a benchmark comparing the two must use
   NaN-free input, and a caller who needs numpy's convention must partition NaN out first.
2. Signed zero. -0.0 and +0.0 compare equal but have different bit patterns, and this kernel
   separates them (-0.0 first). A comparison sort leaves their relative order to chance.
3. Stability. Both the sequential and the parallel arm are stable on the KEY, which for a
   value-only sort is unobservable; it is stated because `sort_indices_multi` composes stable
   passes and would be able to use this.

Everything else — the multiset of outputs, and the ordering of every non-NaN value — agrees with
`numpy.sort` exactly, with no tolerance, because a permutation of the input contains no
arithmetic and therefore no rounding.
"""
from max.algorithm import parallelize
from std.memory import bitcast
from std.sys import info

# 8 bits per pass, 8 passes over a 64-bit key. 8 bits means a 256-entry histogram, 2 KiB of
# counters, which stays resident in L1 for the whole scatter. An 11-bit digit would cut the pass
# count to 6 but needs 2048 buckets, i.e. 2048 simultaneously-open write streams per worker —
# past what the store buffer and the TLB hold, so the scatter starts missing more than the two
# extra passes cost.
comptime RADIX_BITS: Int = 8
comptime RADIX_BUCKETS: Int = 1 << RADIX_BITS
comptime RADIX_MASK: UInt64 = UInt64(RADIX_BUCKETS - 1)
comptime RADIX_PASSES: Int = 8

# Below this, thread spawn and the per-pass barrier cost more than the bytes moved, so the
# parallel entry point routes to the sequential one. The value is MEASURED, not guessed —
# `benchmarks/mojo_benchmarks/bench_vs_sort.mojo` reports the crossover it observes, and the
# parallel arm is slower than sequential below it. Nine parallel regions are entered per sort
# (one keying pass plus up to eight scatters), so the fixed cost here is roughly nine times
# what a single-region kernel like `det_sum_parallel` pays, and the crossover is correspondingly
# further out.
comptime RADIX_PARALLEL_MIN_N: Int = 1 << 21

comptime RADIX_OK: Int = 0
comptime RADIX_ERR_COUNT: Int = 1


@fieldwise_init
struct RadixSortReport(Copyable, Movable):
    """What the sort did, so a benchmark can attribute a timing to an actual code path.

    `passes_run` is the number of the 8 byte passes that were not skipped. A pass whose digit is
    identical across every element moves nothing, so it is skipped, and a caller seeing
    `passes_run == 3` knows the keys shared their top five bytes — which is information about the
    DATA, not about the sort, and is exactly what explains a ns/element that beats the flat
    prediction.
    """

    var status: Int
    var length: Int
    var passes_run: Int
    var workers_used: Int


def _radix_key(x: Float64) -> UInt64:
    """Float64 -> UInt64 whose unsigned order is the IEEE-754 total order of the input."""
    var u = x.to_bits[DType.uint64]()
    # (u >> 63) is 0 or 1. Multiplying by all-ones turns 1 into the full mask and 0 into 0; the
    # or-in of the sign bit then handles the positive case. Two instructions, no branch.
    var mask = ((u >> 63) * 0xFFFFFFFFFFFFFFFF) | 0x8000000000000000
    return u ^ mask


def _radix_unkey(k: UInt64) -> Float64:
    """Exact inverse of `_radix_key` on all 2^64 patterns."""
    var mask = (((k >> 63) ^ 1) * 0xFFFFFFFFFFFFFFFF) | 0x8000000000000000
    return bitcast[DType.float64, 1](k ^ mask)


def radix_sort_f64_roundtrip_ok(x: Float64) -> Bool:
    """`_radix_unkey(_radix_key(x))` has the same bits as `x`.

    Exposed because it is the one property the whole module rests on and it is checkable on any
    value, including the ones a test cannot write literally. Bit comparison rather than `==`, so
    NaN and -0.0 are checked honestly instead of passing for the wrong reason.
    """
    return _radix_unkey(_radix_key(x)).to_bits[DType.uint64]() == x.to_bits[DType.uint64]()


def radix_sort_f64(data: List[Float64]) -> List[Float64]:
    """Sorted ascending copy of `data`, by LSD radix over the transformed key. No comparisons.

    Returns a copy rather than sorting in place to match `sorting.quicksort`'s contract, so the
    two are interchangeable in a benchmark and neither gets a free pass on allocation. The two
    UInt64 scratch buffers and the output are allocated INSIDE this function and therefore inside
    any timing of it; that is deliberate, because a caller cannot avoid them.
    """
    var n = len(data)
    var out = List[Float64](unsafe_uninit_length=n)
    if n <= 1:
        if n == 1:
            out[0] = data[0]
        return out^

    # ONE allocation of 2n keys rather than two of n, and the ping-pong is an offset swap into it.
    # Two separate `List`s would be the clearer expression of intent, but Mojo tracks a pointer's
    # origin in its type, so `src = dst` across two different lists does not typecheck. Halves of
    # one buffer share an origin and swap freely.
    var keys = List[UInt64](unsafe_uninit_length=2 * n)
    var hist = List[Int](length=RADIX_PASSES * RADIX_BUCKETS, fill=0)
    var offsets = List[Int](length=RADIX_BUCKETS, fill=0)

    var keyp = keys.unsafe_ptr()
    var src = keyp
    var dst = keyp + n
    var hp = hist.unsafe_ptr()
    var offp = offsets.unsafe_ptr()
    var dp = data.unsafe_ptr()
    var op = out.unsafe_ptr()

    # ── one pass to key the data AND fill all eight histograms ────────────────
    # Eight histograms in one traversal rather than one per pass: the data is read once instead
    # of eight times, and 16 KiB of counters is small enough to stay in L1 while it happens.
    for i in range(n):
        var k = _radix_key(dp[i])
        src[i] = k
        for p in range(RADIX_PASSES):
            hp[p * RADIX_BUCKETS + Int((k >> UInt64(RADIX_BITS * p)) & RADIX_MASK)] += 1

    # Which passes actually move anything. A pass where one bucket holds all n elements is the
    # identity, and skipping it is not an optimization for a special case — real Float64 data
    # very often shares its top bytes (exponent range), so this is the common path.
    var last_active = -1
    var passes_run = 0
    for p in range(RADIX_PASSES):
        var digit = Int((src[0] >> UInt64(RADIX_BITS * p)) & RADIX_MASK)
        if hp[p * RADIX_BUCKETS + digit] != n:
            last_active = p
            passes_run += 1

    if last_active < 0:
        # Every key identical in all eight bytes: the input is already one repeated value.
        for i in range(n):
            op[i] = _radix_unkey(src[i])
    else:
        for p in range(RADIX_PASSES):
            var digit0 = Int((src[0] >> UInt64(RADIX_BITS * p)) & RADIX_MASK)
            if hp[p * RADIX_BUCKETS + digit0] == n:
                continue

            var running = 0
            for b in range(RADIX_BUCKETS):
                offp[b] = running
                running += hp[p * RADIX_BUCKETS + b]

            var shift = UInt64(RADIX_BITS * p)
            if p == last_active:
                # Fused final pass: scatter straight into the Float64 result instead of writing
                # keys and then walking them again. Saves a full read+write pass over n*8 bytes,
                # which at three to nine total passes is 11-33% of all traffic.
                for i in range(n):
                    var k = src[i]
                    var b = Int((k >> shift) & RADIX_MASK)
                    op[offp[b]] = _radix_unkey(k)
                    offp[b] += 1
                break

            for i in range(n):
                var k = src[i]
                var b = Int((k >> shift) & RADIX_MASK)
                dst[offp[b]] = k
                offp[b] += 1
            var tmp = src
            src = dst
            dst = tmp

    # KEEP-ALIVE, and it is load-bearing rather than defensive.
    # Mojo destroys a value at its last USE, not at end of scope. Every access above went through
    # a raw pointer taken once, so without a use down here the compiler is entitled to free
    # `keys`, `hist` and `offsets` immediately after `unsafe_ptr()` — and it does. The first
    # version of this function was measured returning unsorted output for exactly that reason:
    # the histogram was being written into freed memory that the allocator had handed to someone
    # else. A single exit point plus these three uses is the fix.
    _ = len(keys)
    _ = len(hist)
    _ = len(offsets)
    return out^


def radix_sort_f64_report(data: List[Float64]) -> RadixSortReport:
    """The pass count `radix_sort_f64` would use, without the sort. Diagnostic only."""
    var n = len(data)
    if n <= 1:
        return RadixSortReport(RADIX_OK, n, 0, 1)
    var hist = List[Int](length=RADIX_PASSES * RADIX_BUCKETS, fill=0)
    var hp = hist.unsafe_ptr()
    var dp = data.unsafe_ptr()
    for i in range(n):
        var k = _radix_key(dp[i])
        for p in range(RADIX_PASSES):
            hp[p * RADIX_BUCKETS + Int((k >> UInt64(RADIX_BITS * p)) & RADIX_MASK)] += 1
    var k0 = _radix_key(dp[0])
    var passes_run = 0
    for p in range(RADIX_PASSES):
        var digit = Int((k0 >> UInt64(RADIX_BITS * p)) & RADIX_MASK)
        if hp[p * RADIX_BUCKETS + digit] != n:
            passes_run += 1
    _ = len(hist)
    return RadixSortReport(RADIX_OK, n, passes_run, 1)


def radix_sort_f64_parallel(data: List[Float64], n_workers: Int) -> List[Float64]:
    """`radix_sort_f64` across `n_workers` threads. Identical output, same multiset, same order.

    How a scatter is parallelized without a lock
    -------------------------------------------
    The obvious hazard is that two workers want to append to the same bucket. It is removed by
    computing, before any worker writes, exactly where each (worker, bucket) pair's run begins:
    buckets in ascending order, and within a bucket the workers in ascending index order. Because
    each worker owns a CONTIGUOUS ascending band of the input, that layout is precisely the
    stable order, and every worker writes to a disjoint half-open interval. No atomics, no
    retries, and the result does not depend on which worker finishes first — so this arm is
    bit-identical to the sequential arm, not merely equivalent.

    Contiguous bands rather than strided indices, for the same reason `det_sum_parallel` uses
    them: strided workers would share cache lines on every access and the measurement would be of
    coherence traffic instead of bandwidth.

    This function does NOT apply `RADIX_PARALLEL_MIN_N`; `radix_sort_f64_auto` does. The split is
    deliberate: a benchmark cannot locate a crossover through an entry point that hides the slow
    side of it, so the arm that always threads is exposed and the arm that decides is separate.
    Callers should reach for `radix_sort_f64_auto` and let it choose.

    @capability radix_sort_f64_parallel
    complexity: O(n)
    counts:
    - n_workers is a thread count, not an element count [not_a_count]
    @endcapability
    """
    var n = len(data)
    var workers = n_workers
    if workers < 1:
        workers = 1
    if n < 2 or workers <= 1:
        return radix_sort_f64(data)
    if workers > n:
        workers = n

    var out = List[Float64](unsafe_uninit_length=n)
    # One 2n buffer, ping-ponged by offset — see the note in `radix_sort_f64`.
    var keys = List[UInt64](unsafe_uninit_length=2 * n)
    # Per-worker histograms, flat: [worker][pass][bucket]. 16 workers x 8 x 256 x 8 B = 256 KiB.
    var whist = List[Int](length=workers * RADIX_PASSES * RADIX_BUCKETS, fill=0)
    # Per-worker counts for the pass about to run, flat: [worker][bucket]. Recomputed per pass —
    # see the "why the keying histogram expires" note below.
    var dhist = List[Int](length=workers * RADIX_BUCKETS, fill=0)
    var woff = List[Int](length=workers * RADIX_BUCKETS, fill=0)

    var keyp = keys.unsafe_ptr()
    var src = keyp
    var dst = keyp + n
    var dp = data.unsafe_ptr()
    var op = out.unsafe_ptr()
    var whp = whist.unsafe_ptr()
    var dhp = dhist.unsafe_ptr()
    var wop = woff.unsafe_ptr()

    var band = (n + workers - 1) // workers
    var pn = n
    var pband = band
    var pw = workers

    @parameter
    def key_band(w: Int) capturing:
        var lo = w * pband
        var hi = lo + pband
        if hi > pn:
            hi = pn
        var base = w * RADIX_PASSES * RADIX_BUCKETS
        for i in range(lo, hi):
            var k = _radix_key(dp[i])
            src[i] = k
            for p in range(RADIX_PASSES):
                whp[base + p * RADIX_BUCKETS + Int((k >> UInt64(RADIX_BITS * p)) & RADIX_MASK)] += 1

    parallelize[key_band](workers)

    # Global counts, and therefore which passes move anything.
    var total = List[Int](length=RADIX_PASSES * RADIX_BUCKETS, fill=0)
    var tp = total.unsafe_ptr()
    for w in range(workers):
        var base = w * RADIX_PASSES * RADIX_BUCKETS
        for j in range(RADIX_PASSES * RADIX_BUCKETS):
            tp[j] += whp[base + j]

    var last_active = -1
    for p in range(RADIX_PASSES):
        var digit = Int((src[0] >> UInt64(RADIX_BITS * p)) & RADIX_MASK)
        if tp[p * RADIX_BUCKETS + digit] != pn:
            last_active = p

    @parameter
    def unkey_only(w: Int) capturing:
        var lo = w * pband
        var hi = lo + pband
        if hi > pn:
            hi = pn
        for i in range(lo, hi):
            op[i] = _radix_unkey(src[i])

    if last_active < 0:
        parallelize[unkey_only](workers)
        # Keep-alive before the single exit — see the note in `radix_sort_f64`.
        _ = len(keys)
        _ = len(whist)
        _ = len(dhist)
        _ = len(woff)
        _ = len(total)
        return out^

    # Both closures below are defined ONCE, outside the pass loop, and read the current pass out of
    # `cur_shift` / `cur_final`. Same shape as `gemm/blocked.mojo`, which hoists its captured
    # values rather than closing over loop-local ones.
    var cur_shift: UInt64 = 0
    var cur_final = False

    # WHY THE KEYING HISTOGRAM EXPIRES AFTER ONE PASS — the bug this cost, stated so it is not
    # reintroduced. The keying pass builds a per-worker count for all eight digits at once, and
    # the obvious move is to reuse those counts for all eight scatters. It is wrong. A GLOBAL
    # digit histogram is order-independent, which is why the sequential arm can build all eight up
    # front; a PER-WORKER histogram is not, because it counts the elements that happen to lie in
    # that worker's band, and every scatter permutes which elements those are. Reusing the stale
    # counts gives two workers overlapping write ranges: measured on a 16-element case, two output
    # slots were written twice and two were never written at all, and at n = 1e6 it left 28% of
    # the array out of order. So the counts for pass p are rebuilt from the CURRENT buffer, in
    # parallel, immediately before pass p scatters. That costs one extra streaming read of 8 B per
    # element per pass after the first, and it is the price of a correct parallel LSD radix.
    @parameter
    def hist_band(w: Int) capturing:
        var lo = w * pband
        var hi = lo + pband
        if hi > pn:
            hi = pn
        var mine = dhp + w * RADIX_BUCKETS
        for i in range(lo, hi):
            mine[Int((src[i] >> cur_shift) & RADIX_MASK)] += 1

    @parameter
    def scatter_band(w: Int) capturing:
        var lo = w * pband
        var hi = lo + pband
        if hi > pn:
            hi = pn
        var mine = wop + w * RADIX_BUCKETS
        if cur_final:
            for i in range(lo, hi):
                var k = src[i]
                var b = Int((k >> cur_shift) & RADIX_MASK)
                op[mine[b]] = _radix_unkey(k)
                mine[b] += 1
        else:
            for i in range(lo, hi):
                var k = src[i]
                var b = Int((k >> cur_shift) & RADIX_MASK)
                dst[mine[b]] = k
                mine[b] += 1

    var first_active = True
    for p in range(RADIX_PASSES):
        var digit0 = Int((src[0] >> UInt64(RADIX_BITS * p)) & RADIX_MASK)
        if tp[p * RADIX_BUCKETS + digit0] == pn:
            continue

        cur_shift = UInt64(RADIX_BITS * p)
        cur_final = p == last_active

        if first_active:
            # The keying pass counted the original layout, and for the first scatter the layout is
            # still the original one. Free.
            for w in range(workers):
                var from_base = w * RADIX_PASSES * RADIX_BUCKETS + p * RADIX_BUCKETS
                var to_base = w * RADIX_BUCKETS
                for b in range(RADIX_BUCKETS):
                    dhp[to_base + b] = whp[from_base + b]
            first_active = False
        else:
            for j in range(workers * RADIX_BUCKETS):
                dhp[j] = 0
            parallelize[hist_band](pw)

        # Bucket-major, worker-minor prefix. This single loop is what makes the parallel scatter
        # both lock-free and stable; it is O(buckets * workers) = 4096 and does not scale with n.
        var running = 0
        for b in range(RADIX_BUCKETS):
            for w in range(workers):
                wop[w * RADIX_BUCKETS + b] = running
                running += dhp[w * RADIX_BUCKETS + b]

        parallelize[scatter_band](pw)

        if cur_final:
            break
        var tmp = src
        src = dst
        dst = tmp

    # Keep-alive before the single exit — see the note in `radix_sort_f64`. Without these five
    # lines the compiler frees the key buffer and the histograms at `unsafe_ptr()` and every
    # worker scatters into memory it does not own.
    _ = len(keys)
    _ = len(whist)
    _ = len(dhist)
    _ = len(woff)
    _ = len(total)
    return out^


def radix_sort_f64_auto(data: List[Float64]) -> List[Float64]:
    """`radix_sort_f64_parallel` at every core, sequential below the measured crossover.

    The entry point a caller who does not want to think about thread counts should use. It exists
    so that the crossover lives in ONE place — here — rather than being rediscovered by every
    caller, and so that a caller below the crossover is not silently made slower by asking for
    threads.
    """
    if len(data) < RADIX_PARALLEL_MIN_N:
        return radix_sort_f64(data)
    var cores = info.num_physical_cores()
    if cores < 1:
        cores = 1
    return radix_sort_f64_parallel(data, cores)
