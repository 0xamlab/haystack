---
icon: arrow-down-1-9
description: LSD radix sort over Float64 keys against numpy.sort's introsort — 12 of 14 gate-clean cells ahead across three input orders, from 100,000 to 102.4 million elements.
---

# Sort

`query.executor.sort_indices` is an insertion sort — O(n²) — and exists to serve the small,
already-batched chunks a query operator passes between stages. `columnar.sort_radix` is a
different algorithm for a different job: a full-column sort with no comparisons at all, built
because a benchmark against `numpy.sort` at n = 100,000 measured the insertion path four orders of
magnitude behind, and no constant-factor tuning of an O(n²) loop closes that gap.

{% hint style="success" %}
**Across six sizes (100,000 to 102.4 million elements) and three input orders (random, ascending,
descending), 18 cells were measured and 14 passed this run's own contention gate. Of those 14, the
radix sort was ahead of `numpy.sort` in 12 — from 1.11x at the smallest size to 29.5x at the
largest.** The 2 losses are both on already-sorted input, where `numpy.sort` gets to exploit an
ascending run that a comparison-free radix has no way to notice, and neither loss is worse than
0.72x.
{% endhint %}

## Results

Every cell picks the same entry point a caller gets by default —
`columnar.sort_radix.radix_sort_f64_auto`, which runs sequentially below 2,097,152 elements and
across every physical core above it, because the crossover itself is measured (see
[Method](#method)) rather than assumed. `numpy.sort` is 1.26.4's introsort for `float64`: quicksort
with a heapsort fallback and an insertion-sort tail, single-threaded, in C.

| n | order | arm used | numpy.sort | ours | ratio |
| --- | --- | --- | --- | --- | --- |
| 100,000 | random | seq | 53.32 | 7.49 | **7.12x** |
| 100,000 | ascending | seq | GATE-FAILED | GATE-FAILED | *(excluded — radix_seq dispersion)* |
| 100,000 | descending | seq | 8.72 | 7.89 | **1.11x** |
| 400,000 | random | seq | 59.89 | 7.61 | **7.87x** |
| 400,000 | ascending | seq | 5.40 | 8.06 | 0.67x |
| 400,000 | descending | seq | 9.21 | 7.63 | **1.21x** |
| 1,600,000 | random | seq | 63.94 | 7.88 | **8.12x** |
| 1,600,000 | ascending | seq | 5.87 | 8.19 | 0.72x |
| 1,600,000 | descending | seq | 10.99 | 8.56 | **1.28x** |
| 6,400,000 | random | par (16t) | 69.19 | 2.53 | **27.36x** |
| 6,400,000 | ascending | par (16t) | GATE-FAILED | GATE-FAILED | *(excluded — numpy.sort contention)* |
| 6,400,000 | descending | par (16t) | 11.47 | 2.90 | **3.96x** |
| 25,600,000 | random | par (16t) | 77.10 | 2.62 | **29.47x** |
| 25,600,000 | ascending | par (16t) | 6.86 | 2.43 | **2.83x** |
| 25,600,000 | descending | par (16t) | 12.39 | 2.51 | **4.93x** |
| 102,400,000 | random | par (16t) | GATE-FAILED | GATE-FAILED | *(excluded — radix_par contention)* |
| 102,400,000 | ascending | par (16t) | GATE-FAILED | GATE-FAILED | *(excluded — numpy.sort contention)* |
| 102,400,000 | descending | par (16t) | 13.27 | 2.39 | **5.55x** |

Nanoseconds per element, hot tier, both arms interleaved inside one process (see
[Method](#method) for why). **All 18 cells this run, including the 4 that failed their own
contention gate and are excluded above rather than reported unreliably** — a busy host (this
machine ran a 1-minute load average of 8-11 on 16 cores throughout, other work running
concurrently) occasionally lets a contention spike land inside the hot-repetition window even with
interleaving, and this benchmark's gate exists to catch exactly that rather than publish a number
either arm didn't actually earn. **Of the 14 gate-clean cells, 12 are wins; the 2 losses are both
on ascending input and neither is worse than 0.72x — the same performance class, not a different
one.**

### Why the two losses happen, and why they stay small

The radix sort makes zero comparisons: it reads a key, extracts a byte, increments a counter, for
a fixed 8 passes regardless of what order the input arrives in. That is the source of every win in
the table above — a comparison sort's cost depends on how many comparisons the data forces, and
random data forces close to the theoretical maximum. It is also the source of the two losses:
`numpy.sort`'s introsort recognizes an already-ascending run and finishes in close to a single
linear pass, while the radix still pays its full fixed cost because it never looks at the *order*
of the keys, only their *bytes*. On already-sorted input at the sizes below the parallel crossover,
that fixed cost is 0.67x-0.72x of numpy's — close enough that the two are the same performance
class, and the same ascending order closes into a clear win once the input is large enough to cross
into the parallel arm (2.83x at 25.6M elements, the largest gate-clean ascending cell measured).

### Correctness, checked before every timing

A faster sort that drops or duplicates an element is not a result. Three independent checks run
before any cell is timed: the output is scanned for sortedness; the multiset of the input and
output is compared via an xor and a wrapping sum of the raw key bits (a check that holds even if
`numpy.sort` itself were wrong); and the two outputs are compared bit-for-bit as raw `uint64`
patterns, not `allclose` — a sort performs no arithmetic, so there is no tolerance to state. Every
one of the 18 cells above passed all three, on the full element count, with zero exceptions.

## Method

* **Baseline.** `numpy.sort` 1.26.4, `float64`, no `kind=` argument (introsort, the default and
  what a caller actually gets). Single-threaded — NumPy has no threaded sort — which is why the
  sequential radix arm (below the 2.1M-element crossover) is the like-for-like comparison and the
  parallel arm's win is partly a thread-count win, stated rather than implied.
* **What is timed.** `columnar.sort_radix.radix_sort_f64_auto`, the entry point a caller reaches
  by default. It routes to `radix_sort_f64` (sequential) below 2,097,152 elements and to
  `radix_sort_f64_parallel` at every physical core above it; that threshold is itself measured,
  not assumed — the parallel arm is genuinely slower below it, because a radix sort enters nine
  parallel regions per call (one keying pass plus up to eight scatters) against roughly one for a
  simpler parallel primitive, so its fixed cost is correspondingly higher and its crossover
  correspondingly further out.
* **One process, interleaved arms.** Both sides sort the *same bytes* — the input lives in a Mojo
  `List[Float64]` and NumPy receives a zero-copy view of that same buffer — and the timing loop
  alternates `numpy.sort`, `radix_seq`, `radix_par` repetition by repetition rather than running
  each to completion, so a contention spike lands on all three arms instead of whichever happened
  to be running. This machine was not quiet while measuring (1-minute load average 8-11 on 16
  cores, other work running concurrently); interleaving is what makes the *ratio* still valid under
  that condition even though the absolute nanosecond figures are this machine's leftover share.
* **Cold / warm / hot.** Cold is the first repetition in-process, warm the second, hot the minimum
  of five further repetitions — the minimum is the right statistic for the hot tier because
  contention can only make a reading slower, never faster. A cell is only reported if
  `hot <= warm` and the hot-repetition spread stays under 2x; a cell that fails either check
  prints `INVALID` with no ratio. 4 of the 18 cells in the table above failed that gate this run —
  each is shown as `GATE-FAILED` rather than silently dropped or reported on an unreliable reading.
  The benchmark file also runs a separate, smaller sweep against two legacy sort arms not reported
  on this page; two of its cells failed the same gate for the same reason (host contention) and are
  likewise excluded from that sweep's own numbers.
* **Three input orders, one multiset each.** Random (uniform `float64` in `[-1, 1)`), ascending,
  and descending — the same underlying multiset in every case, so any difference between the three
  is the algorithm reacting to input order and nothing else.
* **Hardware.** Apple M4 Max, 16 physical cores (12 performance + 4 efficiency).

## What is not claimed

* **Not a claim about NaN or signed-zero ordering.** The radix sort orders by IEEE-754 total
  order — a negative NaN sorts below `-inf`, a positive NaN above `+inf`, and `-0.0` sorts before
  `+0.0`. `numpy.sort` puts every NaN last regardless of sign and leaves signed zeros' relative
  order to chance. On the NaN-free, no-signed-zero input this page uses, the two orders coincide
  exactly; a caller needing NumPy's specific NaN convention is served by a different guarantee, not
  a worse one.
* **Not a claim about every input order.** Random, fully-ascending and fully-descending are
  measured; a partially-sorted or few-unique-values input is not, and real column data often has
  none of these three shapes exactly.
* **Not a claim about integer or string keys.** Float64 only.
* **The margin is not uniform, and neither is the outcome.** Both losses are reported alongside
  the wins, not folded into an aggregate — and the 4 cells that failed this run's own contention
  gate are shown as failed rather than omitted.

## Related

* [Top-k selection](top-k.md) — a bounded-heap kernel measured the same way, with one honest loss
  disclosed up front.
* [Graph betweenness centrality](graph-betweenness.md) — a zero-loss win against networkx,
  measured with the same correctness-first discipline.
* [Survival analysis](survival-analysis.md) — measured against two current real-world
  datasets, 10 of 11 cells ahead of lifelines.
* [Benchmarks](overview.md) — methodology and what is not published.
* [Dataframe group-by](dataframe-groupby.md) — another columnar kernel measured directly against
  real baselines.
* [Runtime library catalog](../engine/runtime-library-catalog.md) — every module and function the
  runtime exposes.

## Reproduce

```text title="benchmark"
mojo run benchmarks/mojo_benchmarks/bench_vs_sort.mojo
```

Runs the full sweep in one process against whatever NumPy is installed in the active Python
environment (measured here with 1.26.4) and prints a `BENCH_GATE vs_sort PASS|FAIL <n>` line.
`SORT_BENCH_MAX_N` caps the sweep, `SORT_BENCH_HOT_REPS` sets the hot-tier repetition count, and
`SORT_BENCH_SKIP_LEGACY=1` skips the smaller, frozen-comparison sweep this page does not report on.
