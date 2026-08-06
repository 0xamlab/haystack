---
icon: filter
description: Bounded top-k selection over a flat Float64 column, against numpy.argpartition — a real loss at the smallest size tested, and a 5x-163x win at every size above it.
---

# Top-k selection

`query.executor.top_k_indices` keeps a k-element ordered list and, for every row, walks it from the
front to find an insertion point — its own docstring states the cost, `O(n·k)` comparisons. That
is the right shape for the small, batch-sized chunks a query operator passes between stages; it is
the wrong shape for "the top 1,000 of a hundred million," which is `1e11` comparisons.
`query.topk` is a bounded min-heap with a SIMD threshold screen instead: a row that does not beat
the current worst-kept value is rejected in one comparison, so the cost is close to `O(n)` rather
than `O(n·k)`.

{% hint style="success" %}
**One real loss, and it is reported first: at the smallest size tested (100,000 elements) and the
largest k tested (1,000 — 1% of the column), `numpy.argpartition` is 1.33x faster.** At every other
size — 1 million, 10 million and 100 million elements, every k from 10 to 1,000 — the SIMD-screened
heap is ahead, from 5.4x at the small end to **163x** at the largest size and smallest k. 10 of the
11 gate-clean cells measured are wins.
{% endhint %}

## Results

Every cell uses the entry point a caller gets by default — `top_k_flat_auto`, which runs
single-threaded below 4,194,304 elements and across every physical core above it (see
[Method](#method) for why that threshold, not a rounder one). `numpy.argpartition` is 1.26.4's
introselect, single-threaded — NumPy has no threaded partition.

| n | k | arm used | numpy.argpartition | ours | ratio |
| --- | --- | --- | --- | --- | --- |
| 100,000 | 10 | 1 thread | 97.5 µs | 9.7 µs | **10.10x** |
| 100,000 | 100 | 1 thread | 95.1 µs | 17.7 µs | **5.38x** |
| 100,000 | 1,000 | 1 thread | 98.0 µs | 130.2 µs | 0.75x |
| 1,000,000 | 10 | 1 thread | 7.0 ms | 77.8 µs | **89.52x** |
| 1,000,000 | 100 | 1 thread | 7.0 ms | 94.5 µs | **74.48x** |
| 1,000,000 | 1,000 | 1 thread | 6.8 ms | 303.9 µs | **22.27x** |
| 10,000,000 | 10 | 16 threads | 72.9 ms | 447.3 µs | **162.92x** |
| 10,000,000 | 100 | 16 threads | 67.2 ms | 432.0 µs | **155.49x** |
| 10,000,000 | 1,000 | 16 threads | 67.6 ms | 1.12 ms | **60.36x** |
| 100,000,000 | 10 | 16 threads | 415.9 ms | 3.33 ms | **124.80x** |
| 100,000,000 | 100 | 16 threads | GATE-FAILED | GATE-FAILED | *(excluded — contention)* |
| 100,000,000 | 1,000 | 16 threads | 417.1 ms | 4.28 ms | **97.46x** |

Hot-tier wall time per call. **1 of 12 cells failed this run's own contention gate and is shown as
`GATE-FAILED` rather than reported unreliably.** Of the 11 gate-clean cells: 10 wins, 1 loss.

### Why the one loss happens, and where it stops

At n=100,000 and k=1,000, a caller is asking for the top 1% of the column. The min-heap's whole
advantage is rejecting most rows in a single comparison against the current worst-kept value —
but with 1,000 slots to fill and only 100,000 rows to fill them from, a much larger share of rows
end up displacing something in the heap, each at `O(log k)` instead of the heap-miss's `O(1)`. The
SIMD screen still runs, but the win it buys shrinks as k grows relative to n. The same k=1,000 at
ten times the column size (1,000,000 elements, still k=1,000 — now 0.1% of the column) is already a
22.27x win, and the trend continues from there: the loss is specific to *this exact combination* of
a small column and a large fraction, not a property of large k in general.

### Correctness, checked before every timing

Every cell's result was checked against `numpy.argpartition` as a **bit-exact digest match** — not
of the values alone, but of the (index, value) pairing, so a comparison sort that happened to
select the same values in a different arrangement would not pass. All 12 cells matched exactly, and
the tie rule (`(value, index)`, better value first, lower index breaking ties) is a strict total
order deliberately stronger than NumPy's own guarantee: `argpartition` makes no promise about
*which* index lands in the partition when values are equal, so the two are compared as multisets
of values first and as exact index sets only where the k-th and (k+1)-th values provably differ.
Separately, this kernel's own four internal arms (the plain heap, the buffered heap, and both at
every thread count) were cross-checked against each other and found to return the **identical
list, not merely the same set** — the merge order cannot change the result of a strict total order,
and that identity is what makes the parallel arm safe to call by default.

## Method

* **Baseline.** `numpy.argpartition`, `float64`, `numpy` 1.26.4. Single-threaded, and the sequential
  arm here (below the 4.19M-element crossover) is the like-for-like comparison for exactly that
  reason.
* **What is timed.** `query.topk.top_k_flat_auto`, the entry point a caller reaches by default. It
  runs `top_k_flat` (single thread, buffered — 2k slots of scratch that make the cost per accepted
  candidate O(1) amortised rather than O(log k)) below `TOPK_PARALLEL_MIN_ELEMENTS` = 4,194,304
  elements, and `top_k_flat_parallel` at every physical core above it. Both return the identical
  list, so the choice between them is a cost decision with no semantic content.
* **Data.** One 100,000,000-element array of counter-based SplitMix64 uniform `[0, 1)` values,
  generated once; every swept size is a PREFIX of that same array, so NumPy selects from
  bit-identical data at every size rather than a freshly-drawn sample.
* **Cold / warm / hot.** Cold is the first call at a given `(arm, n, k)` in-process, warm the
  second, hot the minimum of 25 further repetitions. A cell is reported only if the hot reading is
  not slower than warm and the hot-repetition spread stays under a stated bound; 1 of the 12 cells
  above failed that check this run (16-thread arm at the largest size and k=100) and is shown as
  `GATE-FAILED` rather than fudged or dropped.
* **Two processes, not interleaved — disclosed rather than presented as stronger than it is.**
  Unlike the [sort](sort.md) benchmark, which sorts the same bytes inside one process via a
  zero-copy view, this comparison ran the Mojo arm and the NumPy arm as separate process
  invocations rather than alternating rounds within one process. That is weaker evidence against
  contention than in-process interleaving, and it is stated plainly: this machine was not idle
  during either run (1-minute load average 8-11 on 16 cores, other work running concurrently), and
  the ratios above should be read as directionally reliable at the sizes where the margin is large
  (every cell except the k=1,000-at-small-n loss, where the margin is closer and the two-process
  method matters more).
* **Hardware.** Apple M4 Max, 16 physical cores (12 performance + 4 efficiency).

## What is not claimed

* **Not a claim about nulls.** This kernel takes a dense `List[Float64]` with no absence concept;
  a column with nulls is served by `query.executor.top_k_indices`, which honors the validity
  bitmap, or by `top_k_indices_dense`, which refuses rather than guesses when nulls are present.
* **Not a claim about adversarial input order.** The data here is uniform random. Monotonically
  improving input (already sorted toward the kept direction) is a different, harder case for this
  kernel specifically — every row beats the running threshold, so the SIMD screen never rejects
  anything — and is not measured on this page.
* **Not interleaved, so absolute numbers carry more contention risk than the sort page's do.** See
  Method. The one reported loss is inside the range where that matters most.
* **Not a claim about integer or string keys.** Float64 only.

## Related

* [Sort](sort.md) — a comparison-free algorithm measured the same way, with a genuinely stronger
  (in-process, interleaved) methodology.
* [Benchmarks](overview.md) — methodology and what is not published.
* [Dataframe group-by](dataframe-groupby.md) — another columnar kernel measured directly against
  real baselines.

## Reproduce

```text title="benchmark"
mojo run benchmarks/mojo_benchmarks/bench_vs_topk.mojo
python3 benchmarks/mojo_benchmarks/bench_vs_topk_numpy.py
```

The Mojo arm prints its own internal cross-check (all four of its arms agree, element for element)
and a `TOPK_DIGEST` line per cell; the NumPy script prints the matching `TOPKNP_DIGEST` line, and
the two must agree exactly for the comparison to mean anything. Both print
`BENCH_GATE ... PASS|FAIL <n>` on completion.
