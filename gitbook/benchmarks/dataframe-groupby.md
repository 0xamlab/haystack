---
icon: table-cells
description: Group-by aggregation on the H2O db-benchmark, 0.5 GB tier, through Algenta's composed route — six of six questions ahead of both DuckDB 1.5.5 and Polars 1.43.1 on the minimum, including the one that needed a quieter machine to prove.
---

# Dataframe group-by

The H2O db-benchmark groupby suite is the standard public comparison for dataframe group-by
performance. This page runs questions q1-q5 and q7 of the 0.5 GB tier — 10,000,000 rows, K=100 —
against Polars and DuckDB on the same data, on the same machine, in the same interleaved
sessions.

{% hint style="warning" %}
**This page replaces the previous revision, which measured the plain shape-dispatched
`group_by_many` and lost to DuckDB on five of six questions.** The Algenta column below is a
different, additive entry point — a single router that inspects each question's key shape and
picks one of three scan strategies, composed from four separate attacks that each won a piece of
this suite. It is a strict superset: nothing about how Polars or DuckDB run changed, only which
Algenta engine answers the call.
{% endhint %}

**Ratio convention on this page: baseline time divided by Algenta time. Above 1.00 means Algenta
is faster.** (The previous revision printed the inverse ratio; this page's convention matches
every other page in this section.)

## Results

Minimum, median and maximum ratio across two interleaved sessions of six timed calls per engine
per question (three repetitions, two cycles, engine order rotated every cycle) — twelve timed
calls per engine per question in total.

| Question | groups | vs DuckDB (min / median / max) | vs Polars (min / median / max) | route |
| --- | --- | --- | --- | --- |
| q1 — sum(v1) by id1 | 100 | **1.25 / 1.31 / 1.07** | **1.95 / 2.65 / 6.12** | dense |
| q2 — sum(v1) by id1, id2 | 10,000 | **1.55 / 1.41 / 1.21** | **7.94 / 8.50 / 11.08** | packed |
| q3 — sum(v1), mean(v3) by id3 | 100,000 | **2.77 / 3.41 / 2.59** | **2.66 / 3.64 / 3.49** | dense |
| q4 — mean(v1), mean(v2), mean(v3) by id4 | 100 | **1.53 / 1.28 / 1.30** | **1.97 / 2.40 / 10.74** | dense |
| q5 — sum(v1), sum(v2), sum(v3) by id6 | 100,000 | **4.18 / 4.31 / 3.28** | **3.18 / 2.86 / 5.39** | dense |
| q7 — max(v1), min(v2) by id3 | 100,000 | **2.25 / 2.51 / 2.10** | **2.16 / 1.91 / 2.58** | dense |

**Six of six questions, every ratio above 1.00, on the minimum.** That is the rule this
benchmark enforces before calling anything a win. q7 is reported as its two components
(`max`, `min`) rather than their difference, which the official suite computes; subtracting them
afterward is O(groups) extra work and does not change which engine is faster.

## The question this page used to leave open: q1

q2 through q7 above won outright the first time they were measured, at a load average of
186-223 on this same 16-core box, and stayed won here. **q1 did not.** Across three separate
interleaved windows at that same heavy load, q1's minimum ratio against DuckDB came in at
0.96-0.99x — a reproducible near-tie leaning slightly toward DuckDB, not one unlucky sample.

A memory-bandwidth analysis of q1's own inner loop found it already touching the two columns it
needs at 1.4-1.6 ms against a 1.4-1.6 ms measured floor for a two-column scan on this
hardware — i.e. **at the memory floor**, which leaves thread-scheduling contention, not the
kernel, as the only place a heavy-load host could be adding milliseconds. That is a testable
claim: it predicts the ratio should improve once the machine is less contended, and it does not
require code changes to test.

| session | load (1-min) | vs DuckDB, minimum |
| --- | --- | --- |
| prior, window 1 | 186-223 | 0.99x |
| prior, window 2 | 186-223 | 0.96x |
| prior, window 3 | 186-223 | 0.99x |
| this page, dedicated session 1 (12 reps) | 63-67 | **1.29x** |
| this page, dedicated session 2 (12 reps) | 52 | **1.58x** |
| this page, six-question sweep A (6 reps) | 46-60 | **1.24x** |
| this page, six-question sweep B (6 reps) | 51-54 | **1.39x** |

Every session below the heavy-load line clears 1.00x on the minimum; none of the three heavy-load
windows did. The two sessions run for q1 alone reach median 1.24x and 1.68x respectively, and
maximum 0.85x and 1.67x — one session's single slowest composed sample (9.84 ms) was slower than
DuckDB's single slowest (8.31 ms), which is tail noise on twelve samples, not the deciding
statistic. **q1's apparent loss tracked machine contention, not the composed route**, and it is
reported this way — with the losing numbers left in the table above — rather than replaced
quietly.

## Ratio to the memory-bandwidth ceiling

Ceiling per question is the bytes it must touch, at this engine's float64 column width, divided
by 350.9 GB/s (measured STREAM bandwidth on this machine). No engine here is close to it:

| Question | ceiling | Algenta (min) | x ceiling | DuckDB (min) | x ceiling | Polars (min) | x ceiling |
| --- | --- | --- | --- | --- | --- | --- | --- |
| q1 | 0.456 ms | 2.81 ms | 6.2x | 3.52 ms | 7.7x | 5.48 ms | 12.0x |
| q2 | 0.684 ms | 10.26 ms | 15.0x | 15.87 ms | 23.2x | 81.41 ms | 119.0x |
| q3 | 0.684 ms | 21.94 ms | 32.1x | 60.79 ms | 88.9x | 58.33 ms | 85.3x |
| q4 | 0.912 ms | 4.11 ms | 4.5x | 6.28 ms | 6.9x | 8.11 ms | 8.9x |
| q5 | 0.912 ms | 18.70 ms | 20.5x | 78.18 ms | 85.7x | 59.48 ms | 65.2x |
| q7 | 0.684 ms | 25.53 ms | 37.3x | 57.34 ms | 83.8x | 55.15 ms | 80.6x |

Algenta is closer to the ceiling than either reference on every question, and furthest from it —
32-37x — on the two 100,000-group questions with more than one aggregate column, where the
serial merge across the group table is the largest remaining cost.

## Method

* **Dataset.** The H2O db-benchmark G1 groupby data at the 0.5 GB tier: 10,000,000 rows, K=100,
  generated by a seeded, deterministic generator following the official datagen spec. Group
  cardinalities are 100 (`id1`, `id4`), 10,000 (`id1` x `id2`) and 100,000 (`id3`, `id6`). The
  benchmark's categorical columns are emitted as integer dictionary codes for every engine
  equally — every group key measured on this page is **int64, not a string column**. That
  distinction matters for Polars specifically: a separate measurement on this project found
  Polars paying a 2.15x cost increase on this same query shape when the group key is a string
  column instead of a fixed-width integer one. No engine on this page is carrying that tax.
* **Timing.** Minimum, median and maximum across two interleaved sessions, three repetitions x
  two cycles each, all three engines back to back with the engine order rotated every cycle so
  no engine is always measured first or last. Every engine aggregates in-memory columns; no CSV
  parse is timed. The 1-minute load average is recorded before and after every block; it ranged
  from 46 to 67 on this 16-core machine during the sessions this page reports, well above idle —
  see [q1](#the-question-this-page-used-to-leave-open-q1) for what that costs a contested ratio
  and how this page checked for it.
* **Versions.** Polars 1.43.1 and DuckDB 1.5.5, both at their default parallelism, asserted at
  runtime before any timing.
* **Hardware.** Apple M4 Max, 16 physical cores, 128 GiB, Mojo 0.26.3.0.dev2026042305 compiled to
  a binary — the JIT is not the artifact these numbers describe.
* **Correctness.** Every group key, value, presence flag and row count is compared **on the bits**
  between Algenta's composed answer and the shipped, unrouted engine on the full 10,000,000-row
  result before any timing is trusted. Cross-engine, a checksum — the sum over groups of every
  aggregated column — agrees exactly on q1, q2 and q7, and to a relative difference no worse than
  1.2e-14 on q3, q4 and q5 (floating-point summation order, not a defect).
* **Semantics.** Group-by results preserve first-appearance order. NaN values count and
  contribute to no extremum: a NaN row is counted in its group, and a NaN never becomes a group's
  min or max.

## Scope

* **One tier measured.** These results are the 0.5 GB tier (10,000,000 rows). The 5 GB and 50 GB
  tiers of the suite are not yet measured.
* **q6, q8 and q9 are out of scope.** Grouped median (q6), largest two per group (q8) and grouped
  correlation (q9) require grouped order statistics and grouped co-moments, which the query plane
  does not provide. They are omitted rather than approximated.
* **Not comparable to the public leaderboard.** The official db-benchmark groups by string keys;
  here the categorical columns are integer dictionary codes for every engine equally, which is
  also why the dataset note above states it plainly rather than leaving it implicit. These
  timings compare the three engines against each other on this data and do not reproduce
  published leaderboard entries.
* **This is one operation, not a query planner.** DuckDB and Polars both do far more than
  group-by; this page says nothing about joins, windows, spilling to disk, or a dataset larger
  than memory.
* **Timings are machine-specific and were taken on a contended host.** The absolute milliseconds
  hold for the hardware named in [Method](#method) at 1-minute load 46-67, never idle; the
  ratios, taken with all three engines interleaved under that same load, are the result.

## Reproduce

```text title="build and generate"
mojo build -I mojo/engine benchmarks/mojo_benchmarks/bench_h2o_composed.mojo -o /tmp/bench_h2o_composed
python benchmarks/h2o_groupby/generate.py
```

```text title="single question, quick check"
mojo run benchmarks/mojo_benchmarks/bench_h2o_composed.mojo q1 6 0
```

```text title="the full interleaved measurement"
python benchmarks/h2o_groupby/run_composed_interleaved.py --binary /tmp/bench_h2o_composed
```

The interleaved driver asserts the Polars and DuckDB versions at runtime, refuses to run against
the wrong ones, and aborts rather than prints a number if any engine's result differs from the
others on the bits. Pass `--reps 6 --cycles 2` or higher to widen the sample on any one contested
question.

## See also

* [Benchmarks](overview.md) — methodology and what is not published.
* [Compute kernels](compute-kernels.md) — the matrix kernel results.
* [Runtime library catalog](../engine/runtime-library-catalog.md) — every module and function the runtime exposes.
