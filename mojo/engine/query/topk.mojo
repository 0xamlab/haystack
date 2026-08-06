"""query.topk — bounded top-k selection over a flat Float64 column.

Why this module exists next to `query.executor.top_k_indices`
------------------------------------------------------------
`executor.top_k_indices` keeps a k-element ORDERED list and, for every row, walks that
list from the front to find an insertion point. Its own docstring states the cost:
`O(n*k)` comparisons. That is the right shape for the batch-sized chunks an operator
chain passes around (k=10 over a few thousand rows), and it is the wrong shape the
moment a caller asks for the top 1000 of a hundred million — 1e11 comparisons.

Measured on this host against `numpy.argpartition` (introselect, O(n)), the executor
path loses by more than two orders of magnitude at k=1000, and the loss GROWS linearly
in k. See `benchmarks/mojo_benchmarks/bench_vs_topk.mojo` for the numbers and the
crossover. This module is the answer to that measurement, and it is additive: nothing
in `executor.mojo` changes, so every existing caller keeps its semantics exactly.

Three things make it O(n) with a small constant
-----------------------------------------------
1. **A BOUNDED MIN-HEAP, not a sorted list.** The heap is ordered by "worse", so its
   root is the worst of the k kept rows. A row that does not beat the root is rejected
   in ONE comparison; a row that does beat it costs `O(log k)` to sift, not `O(k)` to
   shift. Total `O(n + c*log k)` where `c` is the number of rows that ever beat the
   running threshold. For random input `c` is `O(k*log(n/k))` — about 11,500 for
   k=1000 and n=1e8, i.e. 0.01% of the rows — and the benchmark REPORTS `c`, so the
   claim is checkable rather than asserted.

   The worst case is monotonically improving input (already sorted ascending, for a
   descending top-k), where every row beats the threshold and `c = n`. That is `O(n
   log k)`, still not `O(n*k)`. The benchmark measures that adversarial order too,
   because a selection kernel whose cost depends on input order must say by how much.

2. **A SIMD THRESHOLD SCREEN.** The rejection test is `value <= threshold`, which is
   the same test for eight lanes at once. A W-wide block whose maximum is below the
   threshold cannot contain a candidate and is skipped whole, so the steady state is
   one wide load plus one horizontal max per W elements. The kernel then reads 8 bytes
   per element and does almost nothing with them, which makes it bandwidth-bound —
   and therefore parallelisable, which is point 3.

   The screen admits a block whose max EQUALS the threshold rather than skipping it.
   That is deliberate and it is a correctness requirement, not caution: with the tie
   rule below, a row whose value equals the threshold still displaces the root when
   its index is lower, so skipping on equality would silently return a different set
   on tied data.

3. **CONTIGUOUS BANDS, then one merge.** Each worker selects the top k of its own band
   into its own slot, and the merge feeds those `workers*k` candidates through the same
   heap. Bands are contiguous, never interleaved indices: interleaving would have every
   core touch every cache line and measure coherence traffic instead of bandwidth.

THE TIE RULE, AND WHY IT IS STRONGER THAN NUMPY'S
-------------------------------------------------
Rows are ordered by `(value, index)`: better value first, and among equal values the
LOWER row index first. That is a strict total order over distinct rows, so **the top-k
set and its order are a unique function of the input** — the same rule
`executor.top_k_indices` gets from its strict comparison, kept deliberately so the two
agree on tied data rather than merely on distinct data.

`numpy.argpartition` makes no such promise: which of several equal values lands in the
partition is an implementation detail of introselect's pivoting, and it can differ
between NumPy versions, dtypes and array lengths. So on tied data the two can return
different index sets that are both correct top-k sets. A comparison must therefore
check the multiset of VALUES for equality and check index equality only where the
k-th and (k+1)-th values differ. The benchmark does exactly that and says which case
it is in.

Consequently `top_k_flat_parallel` returns the same list for every worker count, and
the same list as `top_k_flat`. Not "the same set" — the same list, element for
element, because the merge order cannot affect the result of a total order. That is
asserted with `==`, not a tolerance.

WHAT IS NOT HERE
----------------
No nulls. `Float64Array` carries a validity bitmap and `executor.top_k_indices`
honours it through `nulls_last`; this module takes a dense `List[Float64]` and has no
absence concept, because the bitmap lookup per element is the dominant cost at k=10
and a caller with no nulls should not pay it. A caller with nulls uses the executor
path, or compacts first. `top_k_indices_dense` bridges the two for the no-null case
and REFUSES rather than guesses when the column has a null.
"""
from std.algorithm import parallelize
from std.sys import info

from columnar.array import Float64Array

# ── status codes ──────────────────────────────────────────────────────────────

comptime TOPK_OK: Int = 0
comptime TOPK_ERR_COUNT: Int = 1
"""`n` is negative or longer than the array it indexes."""
comptime TOPK_ERR_HAS_NULLS: Int = 2
"""A dense entry point was handed a column with an absent value."""

# Lanes per screening load. Eight Float64 is 512 bits, wider than one NEON register on
# purpose: the compiler splits it into independent loads, and several loads in flight is
# what keeps the memory controller busy. Matches `measure_stream_bandwidth.mojo`.
comptime W: Int = 8


struct TopKSelection(Copyable, Movable):
    """The k best row indices, best first, plus what it cost to find them."""

    var indices: List[Int]
    var status: Int
    var n_considered: Int
    var candidates: Int
    """Rows that beat the running threshold and entered the heap.

    Reported rather than discarded because it is the number that decides whether this
    kernel is `O(n)` or `O(n log k)` on a given input, and a reader should not have to
    take that on trust. For random input it is `O(k log(n/k))`; for input already sorted
    into improving order it is `n`.
    """
    var workers: Int

    def __init__(
        out self,
        var indices: List[Int],
        status: Int,
        n_considered: Int,
        candidates: Int,
        workers: Int,
    ):
        self.indices = indices^
        self.status = status
        self.n_considered = n_considered
        self.candidates = candidates
        self.workers = workers


def _absent(status: Int, n: Int) -> TopKSelection:
    return TopKSelection(List[Int](), status, n, 0, 0)


# ── the total order ───────────────────────────────────────────────────────────


@always_inline
def _better[descending: Bool](
    left_value: Float64, left_index: Int, right_value: Float64, right_index: Int
) -> Bool:
    """True when `left` strictly precedes `right` under `(value, index)`.

    `descending` is a compile-time parameter so the comparison in the inner loop is a
    single machine compare rather than a branch on a runtime flag. The index tie-break
    is what makes this a strict total order, and therefore what makes the parallel
    result independent of the band partition.
    """
    if left_value == right_value:
        return left_index < right_index

    comptime if descending:
        return left_value > right_value
    else:
        return left_value < right_value


# ── the bounded heap ──────────────────────────────────────────────────────────
#
# A min-heap under `_better`: the parent is WORSE than both children, so slot 0 is the
# worst of the kept rows and the rejection threshold is a single load. Stored as two
# parallel arrays rather than a list of pairs so the value array stays contiguous.


@always_inline
def _sift_down[descending: Bool](
    key: UnsafePointer[Float64, origin=AnyOrigin[mut=True]],
    idx: UnsafePointer[Int, origin=AnyOrigin[mut=True]], size: Int, start: Int
):
    var parent = start
    while True:
        var child = 2 * parent + 1
        if child >= size:
            return
        # Take the WORSE child: the heap's root must be the global worst.
        if child + 1 < size and _better[descending](
            key[child], idx[child], key[child + 1], idx[child + 1]
        ):
            child += 1
        if not _better[descending](key[parent], idx[parent], key[child], idx[child]):
            return
        var tv = key[parent]
        var ti = idx[parent]
        key[parent] = key[child]
        idx[parent] = idx[child]
        key[child] = tv
        idx[child] = ti
        parent = child


@always_inline
def _heapify[descending: Bool](
    key: UnsafePointer[Float64, origin=AnyOrigin[mut=True]],
    idx: UnsafePointer[Int, origin=AnyOrigin[mut=True]], size: Int
):
    """Floyd's bottom-up build: O(k), not O(k log k)."""
    var start = size // 2 - 1
    while start >= 0:
        _sift_down[descending](key, idx, size, start)
        start -= 1


def _heap_sort_best_first[descending: Bool](
    key: UnsafePointer[Float64, origin=AnyOrigin[mut=True]],
    idx: UnsafePointer[Int, origin=AnyOrigin[mut=True]], size: Int
):
    """In-place heapsort leaving the array BEST FIRST.

    Each pop moves the current worst to the end of the shrinking active region, so the
    worst ends up last and the best ends up at slot 0 — which is the order
    `executor.top_k_indices` returns, and the order a caller printing a top-10 wants.
    O(k log k) once, never inside the scan.
    """
    var active = size
    while active > 1:
        var tv = key[0]
        var ti = idx[0]
        key[0] = key[active - 1]
        idx[0] = idx[active - 1]
        key[active - 1] = tv
        idx[active - 1] = ti
        active -= 1
        _sift_down[descending](key, idx, active, 0)


# ── the scan ──────────────────────────────────────────────────────────────────


def _scan_band[descending: Bool](
    values: UnsafePointer[Float64, origin=AnyOrigin[mut=False]],
    lo: Int,
    hi: Int,
    k: Int,
    key: UnsafePointer[Float64, origin=AnyOrigin[mut=True]],
    idx: UnsafePointer[Int, origin=AnyOrigin[mut=True]],
    mut size: Int,
    mut candidates: Int,
):
    """Fold `values[lo, hi)` into the heap at `key`/`idx`, which has room for `k`.

    `size` is in/out so a merge pass can keep folding into a heap the band scans built.
    """
    var i = lo

    # Fill first. Until the heap holds k rows every row is a candidate, so there is no
    # threshold to screen against and the wide path would only add a branch.
    while size < k and i < hi:
        key[size] = values[i]
        idx[size] = i
        size += 1
        candidates += 1
        i += 1
    if size == 0:
        return
    # Unconditionally, not `if size == k`. A band shorter than k leaves the array
    # un-heapified, and `_heap_sort_best_first` would then sort a non-heap — a wrong
    # answer reachable only through the private path, which is exactly the kind that
    # survives a test suite.
    _heapify[descending](key, idx, size)

    # Steady state: screen W at a time against the root, descend only into blocks that
    # could contain a candidate.
    while i + W <= hi:
        var block = values.load[width=W, alignment=8](i)

        comptime if descending:
            if block.reduce_max() < key[0]:
                i += W
                continue
        else:
            if block.reduce_min() > key[0]:
                i += W
                continue

        for lane in range(W):
            var v = block[lane]
            var at = i + lane
            if _better[descending](v, at, key[0], idx[0]):
                key[0] = v
                idx[0] = at
                _sift_down[descending](key, idx, size, 0)
                candidates += 1
        i += W

    # Tail. Scalar for correctness rather than speed: a wide load at `hi - W + 1` would
    # read past the buffer, and an out-of-bounds read here is an uncatchable abort.
    while i < hi:
        var v = values[i]
        if _better[descending](v, i, key[0], idx[0]):
            key[0] = v
            idx[0] = i
            _sift_down[descending](key, idx, size, 0)
            candidates += 1
        i += 1


# ── the buffered scan: bounded work per ACCEPTED candidate ────────────────────
#
# THE MEASUREMENT THAT FORCED THIS, stated before the code because the code only makes
# sense as an answer to it. `_scan_band` costs O(log k) per accepted candidate. On random
# input almost nothing is accepted, so it does not matter. On input already sorted into
# IMPROVING order every element is accepted, and the sift dominates: measured on this
# host at n = 10,000,000, one thread,
#
#     ascending input, heap scan:   13.4 / 19.0 / 30.8 ns/elem at k = 10 / 100 / 1000
#     ascending input, argpartition: 0.82 ns/elem, flat in k
#
# — a 16x to 37x LOSS, because introselect's median-of-3 finds a perfect pivot on sorted
# data while our heap sifts n times. Reporting that and stopping would have been honest
# but lazy. The fix is to stop paying O(log k) per acceptance:
#
#   * accepted candidates are APPENDED to a 2k buffer, which is O(1);
#   * when the buffer fills, one `_nth_element` pass reduces it to the best k, which is
#     O(k) for k new candidates, so O(1) amortised each;
#   * the screening threshold is then the k-th best, exactly as before.
#
# Total work is O(n) plus O(1) per acceptance in BOTH orders. The buffer costs 2k
# Float64 and 2k Int of extra memory, which at k = 1000 is 32 KB and fits in L2.


def _nth_element[descending: Bool](
    key: UnsafePointer[Float64, origin=AnyOrigin[mut=True]],
    idx: UnsafePointer[Int, origin=AnyOrigin[mut=True]],
    lo0: Int,
    hi0: Int,
    target: Int,
):
    """Partition `[lo0, hi0)` so slot `target` holds the (target+1)-th best.

    Introselect, for the same reason NumPy uses it: quickselect with a median-of-3 pivot
    is O(m) on the inputs that occur and O(m^2) on the ones an adversary picks, so the
    recursion depth is capped and the tail falls back to a heapsort of the remaining
    region, which is O(m log m) unconditionally. Without the cap this kernel's worst case
    would be worse than the one it was written to fix.
    """
    var lo = lo0
    var hi = hi0
    var guard = 0
    while hi - lo > 1:
        guard += 1
        if guard > 48:
            var m = hi - lo
            _heapify[descending](key + lo, idx + lo, m)
            _heap_sort_best_first[descending](key + lo, idx + lo, m)
            return

        # Median of first, middle and last into slot `lo`, so a sorted or reverse-sorted
        # region — the two that make a naive pivot quadratic — splits evenly.
        var mid = lo + (hi - lo) // 2
        var last = hi - 1
        # Three compares put best at `lo`, median at `mid`, worst at `last`; the fourth
        # move brings the median to `lo` where the partition expects its pivot.
        if _better[descending](key[mid], idx[mid], key[lo], idx[lo]):
            _swap_slots(key, idx, mid, lo)
        if _better[descending](key[last], idx[last], key[lo], idx[lo]):
            _swap_slots(key, idx, last, lo)
        if _better[descending](key[last], idx[last], key[mid], idx[mid]):
            _swap_slots(key, idx, last, mid)
        _swap_slots(key, idx, lo, mid)

        var pv = key[lo]
        var pi = idx[lo]
        var store = lo + 1
        for s in range(lo + 1, hi):
            if _better[descending](key[s], idx[s], pv, pi):
                _swap_slots(key, idx, s, store)
                store += 1
        _swap_slots(key, idx, lo, store - 1)

        var pivot_at = store - 1
        if pivot_at == target:
            return
        if target < pivot_at:
            hi = pivot_at
        else:
            lo = pivot_at + 1


@always_inline
def _swap_slots(
    key: UnsafePointer[Float64, origin=AnyOrigin[mut=True]],
    idx: UnsafePointer[Int, origin=AnyOrigin[mut=True]],
    a: Int,
    b: Int,
):
    if a == b:
        return
    var tv = key[a]
    var ti = idx[a]
    key[a] = key[b]
    idx[a] = idx[b]
    key[b] = tv
    idx[b] = ti


def _scan_band_buffered[descending: Bool](
    values: UnsafePointer[Float64, origin=AnyOrigin[mut=False]],
    lo: Int,
    hi: Int,
    k: Int,
    key: UnsafePointer[Float64, origin=AnyOrigin[mut=True]],
    idx: UnsafePointer[Int, origin=AnyOrigin[mut=True]],
    mut size: Int,
    mut candidates: Int,
):
    """As `_scan_band`, but `key`/`idx` must have room for `2*k`.

    On return `size <= k` and slots `[0, size)` hold the band's best rows in NO
    particular order — the caller sorts once. Identical SET and identical final list
    after the sort, because both scans keep exactly the top k under `_better`.
    """
    var i = lo
    while size < k and i < hi:
        key[size] = values[i]
        idx[size] = i
        size += 1
        candidates += 1
        i += 1
    if size < k:
        return

    _nth_element[descending](key, idx, 0, size, k - 1)
    size = k
    var thresh = key[k - 1]
    var thresh_i = idx[k - 1]

    while i + W <= hi:
        var block = values.load[width=W, alignment=8](i)

        comptime if descending:
            if block.reduce_max() < thresh:
                i += W
                continue
        else:
            if block.reduce_min() > thresh:
                i += W
                continue

        for lane in range(W):
            var v = block[lane]
            var at = i + lane
            if _better[descending](v, at, thresh, thresh_i):
                key[size] = v
                idx[size] = at
                size += 1
                candidates += 1
                if size == 2 * k:
                    _nth_element[descending](key, idx, 0, size, k - 1)
                    size = k
                    thresh = key[k - 1]
                    thresh_i = idx[k - 1]
        i += W

    while i < hi:
        var v = values[i]
        if _better[descending](v, i, thresh, thresh_i):
            key[size] = v
            idx[size] = i
            size += 1
            candidates += 1
            if size == 2 * k:
                _nth_element[descending](key, idx, 0, size, k - 1)
                size = k
                thresh = key[k - 1]
                thresh_i = idx[k - 1]
        i += 1

    if size > k:
        _nth_element[descending](key, idx, 0, size, k - 1)
        size = k


# ── public entry points ───────────────────────────────────────────────────────


def top_k_flat[descending: Bool = True, buffered: Bool = True](
    values: List[Float64], n: Int, k: Int
) -> TopKSelection:
    """The k best of `values[0, n)`, best first. Single thread.

    `k <= 0` is an empty result and `k >= n` is the whole prefix in sorted order — the
    same clamping `executor.top_k_indices` does, because a report asking for the top 10
    of 3 rows wants 3 rows rather than an error.

    `buffered` picks the scan, and BOTH return the identical list — it is a cost
    decision with no semantic content. `buffered=True` (the default, and the measured
    winner) pays 2k slots of scratch to make the cost per accepted candidate O(1)
    amortised instead of O(log k); `buffered=False` is the plain bounded heap and is
    kept reachable so the benchmark can measure what the buffer buys rather than assert
    it. See the comment above `_nth_element`.

    @capability top_k_flat
    complexity: O(n + c log k)
    counts:
    - n <= len(values) [kernel_validated]
    @endcapability
    """
    if n < 0 or n > len(values):
        return _absent(TOPK_ERR_COUNT, 0)
    var want = k
    if want > n:
        want = n
    if want <= 0:
        return TopKSelection(List[Int](), TOPK_OK, n, 0, 1)

    var slots = 2 * want if buffered else want
    var key = List[Float64](capacity=slots)
    var idx = List[Int](capacity=slots)
    for _ in range(slots):
        key.append(0.0)
        idx.append(0)
    var kp = key.unsafe_ptr()
    var ip = idx.unsafe_ptr()
    var size = 0
    var candidates = 0
    comptime if buffered:
        _scan_band_buffered[descending](
            values.unsafe_ptr(), 0, n, want, kp, ip, size, candidates
        )
        _heapify[descending](kp, ip, size)
    else:
        _scan_band[descending](values.unsafe_ptr(), 0, n, want, kp, ip, size, candidates)
    _heap_sort_best_first[descending](kp, ip, size)

    var out = List[Int](capacity=size)
    for i in range(size):
        out.append(ip[i])
    return TopKSelection(out^, TOPK_OK, n, candidates, 1)


def top_k_flat_parallel[descending: Bool = True, buffered: Bool = True](
    values: List[Float64], n: Int, k: Int, n_workers: Int
) -> TopKSelection:
    """`top_k_flat(values, n, k)` on `n_workers` threads. IDENTICAL list, every count.

    Not "the same set" — the same list, because `_better` is a strict total order and
    the top k of a total order does not depend on the order the candidates were offered.
    The suite asserts it with `==`.

    `n_workers <= 1` is `top_k_flat`, and so is a request whose bands would be shorter
    than `k` (every worker would return its whole band and the merge would re-scan all
    of `n`). Both are silent fallbacks rather than errors: a caller passing a computed
    core count that came back zero wants a working selection.

    THE CROSSOVER IS REAL AND IT IS NOT SMALL. Thread spawn/join plus `workers` heap
    allocations per call cost more than the scan itself below roughly a million
    elements, exactly as `determinism.det_sum_parallel` does. Measured numbers and the
    crossover point are in `benchmarks/mojo_benchmarks/bench_vs_topk.mojo`;
    `top_k_flat_auto` applies them.

    @capability top_k_flat_parallel
    complexity: O(n/p + p k log k)
    counts:
    - n <= len(values) [kernel_validated]
    @endcapability
    """
    if n < 0 or n > len(values):
        return _absent(TOPK_ERR_COUNT, 0)
    var want = k
    if want > n:
        want = n
    if want <= 0:
        return TopKSelection(List[Int](), TOPK_OK, n, 0, 1)

    var workers = n_workers
    if workers < 1:
        workers = 1
    var band = (n + workers - 1) // workers
    if workers <= 1 or band <= want:
        return top_k_flat[descending, buffered](values, n, want)

    # One slot per worker. Allocated per call, which is a cost this kernel pays and the
    # benchmark charges it for — it is half of why the crossover exists.
    var slots = 2 * want if buffered else want
    var w_key = List[List[Float64]](capacity=workers)
    var w_idx = List[List[Int]](capacity=workers)
    var w_size = List[Int](capacity=workers)
    var w_cand = List[Int](capacity=workers)
    for _ in range(workers):
        var key = List[Float64](capacity=slots)
        var idx = List[Int](capacity=slots)
        for _ in range(slots):
            key.append(0.0)
            idx.append(0)
        w_key.append(key^)
        w_idx.append(idx^)
        w_size.append(0)
        w_cand.append(0)

    var kp = w_key.unsafe_ptr()
    var ip = w_idx.unsafe_ptr()
    var sp = w_size.unsafe_ptr()
    var cp = w_cand.unsafe_ptr()
    var vp = values.unsafe_ptr()

    @parameter
    def select_band(w: Int):
        var lo = w * band
        var hi = lo + band
        if hi > n:
            hi = n
        if lo >= hi:
            return
        var size = 0
        var cand = 0
        comptime if buffered:
            _scan_band_buffered[descending](
                vp, lo, hi, want, kp[w].unsafe_ptr(), ip[w].unsafe_ptr(), size, cand
            )
        else:
            _scan_band[descending](
                vp, lo, hi, want, kp[w].unsafe_ptr(), ip[w].unsafe_ptr(), size, cand
            )
        sp[w] = size
        cp[w] = cand

    parallelize[select_band](workers)

    # Sequential merge through the SAME heap. O(workers * k * log k), which is nothing
    # beside the scan, and the total order makes the result independent of this loop's
    # order — so no worker-completion race can change the answer.
    var key = List[Float64](capacity=want)
    var idx = List[Int](capacity=want)
    for _ in range(want):
        key.append(0.0)
        idx.append(0)
    var mkp = key.unsafe_ptr()
    var mip = idx.unsafe_ptr()
    var size = 0
    var candidates = 0
    for w in range(workers):
        var count = sp[w]
        if count <= 0:
            continue
        candidates += cp[w]
        var band_key = kp[w].unsafe_ptr()
        var band_idx = ip[w].unsafe_ptr()
        for j in range(count):
            var v = band_key[j]
            var at = band_idx[j]
            if size < want:
                mkp[size] = v
                mip[size] = at
                size += 1
                if size == want:
                    _heapify[descending](mkp, mip, size)
            elif _better[descending](v, at, mkp[0], mip[0]):
                mkp[0] = v
                mip[0] = at
                _sift_down[descending](mkp, mip, size, 0)
    if size < want:
        _heapify[descending](mkp, mip, size)
    _heap_sort_best_first[descending](mkp, mip, size)

    var out = List[Int](capacity=size)
    for i in range(size):
        out.append(mip[i])
    return TopKSelection(out^, TOPK_OK, n, candidates, workers)


# THE MEASURED CROSSOVER on this host, from `bench_vs_topk.mojo` at k = 100. Below it the
# thread spawn/join plus `workers` per-call allocations cost more than the scan they save.
# The constant is a MEASUREMENT and the benchmark prints the table either side of it:
#
#     n          1 thread     16 threads   speedup
#     262,144     0.2325       1.5984       0.15x
#     1,048,576   0.1562       0.4693       0.33x
#     2,097,152   0.1432       0.2161       0.66x
#     4,194,304   0.1252       0.1010       1.24x   <- first win
#     8,388,608   0.1337       0.0929       1.44x
#     67,108,864  0.1174       0.0401       2.93x
#
# (ns per element; the 4,194,304 row is from an earlier run of the same file, because in
# the interleaved run that cell failed its own dispersion gate and reported no ratio.)
#
# Two caveats a caller should have, both of which argue for this value rather than a
# lower one. The measurement was taken at a load average of 30-80 on 16 cores, and
# contention penalises the 16-thread arm far more than the 1-thread arm, so the true
# quiet-machine crossover is very probably LOWER than this. And the penalty below the
# crossover is severe — 0.03x at n = 16,384, a 33x slowdown — while the reward just above
# it is 1.2x. The asymmetry says to sit above the measured point, not on it.
comptime TOPK_PARALLEL_MIN_ELEMENTS: Int = 4_194_304


def top_k_flat_auto[descending: Bool = True, buffered: Bool = True](
    values: List[Float64], n: Int, k: Int
) -> TopKSelection:
    """`top_k_flat` below the measured crossover, `top_k_flat_parallel` above it.

    Returns the identical list either way — the branch is a performance decision with
    no semantic content, which is only true because the parallel form is exact.
    """
    if n < TOPK_PARALLEL_MIN_ELEMENTS:
        return top_k_flat[descending, buffered](values, n, k)
    return top_k_flat_parallel[descending, buffered](
        values, n, k, info.num_physical_cores()
    )


def top_k_indices_dense(
    column: Float64Array, k: Int, descending: Bool
) -> TopKSelection:
    """The `Float64Array` bridge for a column with no nulls.

    REFUSES with `TOPK_ERR_HAS_NULLS` when the validity bitmap shows an absence, rather
    than treating a missing value as 0.0 or as very small. A top-k that silently ranked
    absences would be a wrong answer that looks like a right one, and the caller has
    `executor.top_k_indices` for the nullable case with an explicit `nulls_last`.

    The null screen is O(n) and separate from the scan, so this entry point is
    deliberately slower than `top_k_flat` on the same data. That is the cost of not
    guessing; a caller who already knows the column is dense should hold the values.
    """
    var n = column.length
    if column.null_count() != 0:
        return _absent(TOPK_ERR_HAS_NULLS, n)
    var values = List[Float64](capacity=n)
    for i in range(n):
        values.append(column.get(i))
    if descending:
        return top_k_flat_auto[True](values, n, k)
    return top_k_flat_auto[False](values, n, k)
