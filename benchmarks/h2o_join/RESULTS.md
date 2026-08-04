# H2O db-benchmark join track, 0.5 GB tier — serial baseline, then a real parallel probe+gather

**Still not a win, after a real fix. This stays in `benchmarks/`, never `gitbook/`, per
this project's own standing rule: a GitBook page publishes only on a minimum ratio >
1.00 against BOTH DuckDB and Polars, on every question.** The original serial baseline
below cleared that bar on exactly one of five questions against one of two references
(q1 vs DuckDB). `mojo/engine/query/join.mojo`'s probe and gather have since been
parallelized (row-banded, same blueprint as `query.aggregate.group_by_many_radix`'s
counted scatter — see that file's own "Parallel probe and gather" docstring section),
and the **"Update (2026-08)" section below is the current, honest picture**: Algenta
now wins outright against DuckDB on 4 of 5 questions and roughly halves the Polars gap
on all 5 — but every question is still a loss against Polars (6.4x-12.1x), so the page
still does not ship. The two sections below are kept in chronological order —
"Results" is the original serial-path measurement (now superseded), "Update (2026-08)"
is the current parallel-path measurement — so the gap-closure is visible, not just the
final number.

This was the honest "before" picture for the join-track work the feasibility research
proposed (a shape-aware router + a partitioned/radix hash-join variant, mirroring the
groupby page's own playbook — see `gitbook/benchmarks/dataframe-groupby.md`). At the
time this table was measured, no engine code had changed for this pass: this was
measurement only, of the plane exactly as it shipped then: `Query.join()` →
`plan._apply_join` → always `hash_join_indices` (the `method` field defaults to
`"hash"` and nothing inspects key shape). It still describes the serial path exactly —
`hash_join_indices` and `materialize` still take this path below their own new
row-count thresholds (see the Update section) — so it is retained as ground truth for
what the parallel path is compared against, not deleted.

## Results

Minimum of 3 reps per engine per question, all three engines run on the same generated
data, same machine, same session (not yet the groupby page's full rotated-interleaved
methodology — see Scope). **Ratio = Algenta time / baseline time; above 1.00 means
Algenta is SLOWER** (the opposite sense from the groupby page's convention, chosen here
because every question but one is a loss and inverting the losing convention would read
as obscuring them).

| Question | dimension tier | out rows | Algenta (min) | DuckDB (min) | Polars (min) | Algenta/DuckDB | Algenta/Polars |
| --- | --- | --- | --- | --- | --- | --- | --- |
| q1 — small inner on id1 | small (10 rows) | 8,997,136 | 0.372s | 0.402s | 0.019s | **0.92x (faster)** | **19.7x** |
| q2 — medium inner on id2 | medium (10,000 rows) | 9,001,606 | 0.545s | 0.398s | 0.020s | **1.37x** | **27.5x** |
| q3 — medium left on id2 | medium (10,000 rows) | 10,000,000 | 0.576s | 0.500s | 0.037s | **1.15x** | **15.7x** |
| q4 — medium inner on id2* | medium (10,000 rows) | 9,001,606 | 0.554s | 0.394s | 0.021s | **1.40x** | **26.6x** |
| q5 — **big** inner on id3 | **big (10,000,000 rows, near 1:1)** | 9,000,000 | 2.395s | 0.450s | 0.098s | **5.33x** | **24.4x** |

\* The official suite's q4 joins on `id5`, the string form of `id2`. This engine has no
string dtype, and — following this project's own established H2O convention (see the
groupby page's Method section: "categorical columns are emitted as integer dictionary
codes for every engine equally") — every engine here got the same int64 `id2` for q4
too. **q4 is therefore the identical operation to q2 for all three engines**, not an
independent measurement; its near-equal numbers to q2 (0.554s vs 0.545s) are exactly
what that identity predicts, not a second finding.

## Correctness, checked before any timing was trusted

Every question's output row count is **identical on the bits** across Algenta, DuckDB
and Polars (8,997,136 / 9,001,606 / 10,000,000 / 9,001,606 / 9,000,000 — see table
above). The cross-engine checksum (`sum(v1) + sum(v2)` over the joined result, the same
quantity `join-duckdb.R`'s and `join-polars.py`'s own `chk` compute) agrees to a
relative difference no worse than ~2.4e-12 between Algenta and the two references on
every question — floating-point summation order, not a defect, the same tolerance class
the groupby page itself discloses for its own multi-column questions. `left_unmatched`
(998,394-1,002,864 depending on the key) matches `N - out_rows` exactly, and q3's LEFT
join correctly emits all 10,000,000 left rows (matched + unmatched-with-nulls) where
q2's INNER join on the identical key drops the 998,394 unmatched ones — the two paths
were checked against each other, not just against the row count.

## Why the gap: the current path is single-threaded, and it shows most on the biggest build side

`mojo/engine/query/join.mojo` — both `hash_join_indices` and `materialize` — contain no
reference to a thread, a worker pool, or parallel dispatch of any kind: the hash table
build, the probe, and the output gather are all one core, start to finish. DuckDB was
run with `PRAGMA THREADS=16` (this machine's physical core count) and Polars uses its
own global thread pool at the same default width. That asymmetry is the most likely
single driver of the pattern above:

* **Against DuckDB**, the three small-to-medium build sides (q1's 10-row `small`, q2-4's
  10,000-row `medium`) don't give 16-way parallelism much to chew on, so single-threaded
  Algenta lands within 1.0x-1.4x — it is even marginally *faster* on q1, where DuckDB's
  per-query planning/dispatch overhead outweighs the tiny table's work. **q5's 10,000,000-
  row `big` build side is exactly where that stops being true**: building a 1e7-row hash
  table is real, parallelizable work, and DuckDB's 16-way build+probe pulls it to 5.3x
  ahead of Algenta's one core — precisely the "near-1:1 dimension tier" risk the
  feasibility research named before this pass ran.
* **Against Polars**, the gap is large and roughly flat across all five questions
  (15.7x-27.5x) rather than concentrated on q5. That shape does not point at a
  build-side-parallelism story the way the DuckDB numbers do — it is more consistent
  with Polars' join being aggressively vectorized (SIMD key comparison/hashing) on top
  of being multi-threaded, i.e. a per-row constant-factor advantage that shows up
  everywhere, not just where the hash table is largest.

## Recommendation

**The gap is large, not router-shaped.** The groupby page's playbook — a router that
picks among *already-fast* existing kernels — worked there because all three of
`group_by_coded`/`group_by_many_banded`/`group_by_many_radix` were themselves
competitive engines; composing between them closed the remaining gap. Here there is
only one engine (`hash_join_indices`), it is single-threaded, and it loses to Polars by
15x-27x on every question including the ones where it beats or roughly matches DuckDB.
A shape-aware router with nothing else to route to would, at best, pick "hash" every
time it already does today.

What this baseline DOES support closing, specifically:

* **q5 / the big tier vs DuckDB (5.3x) is the one gap that looks structurally
  fixable with the exact tool the research proposed** — a partitioned/radix hash-join
  variant with real multi-core build+probe would plausibly close most of that 5.3x, since
  the DuckDB comparison there is consistent with a parallelism story, not a fundamentally
  different algorithm.
* **The 15x-27x Polars gap, present even on q1's 10-row build side, will not be closed by
  parallelism or partitioning alone.** Closing it needs the current serial
  `hash_join_indices`/`materialize` path itself to get faster per-row (SIMD-friendly
  hashing/comparison, fewer allocations in the chain-of-rows build, a tighter gather in
  `materialize`) before a router or a bigger-table-specific variant would have a
  competitive result to route to.

Net: this is worth continuing past this baseline, but the next phase is real single-
core engineering on `hash_join_indices`/`materialize` first — not a router, and not
router-plus-radix-variant alone. A router only pays off once there are at least two
genuinely competitive strategies to choose between, and today there is one, and it is
not yet competitive with either reference engine on 4 of 5 questions, nor with Polars on
any of them.

## Update (2026-08): the probe and gather are now parallel — real gap closure, still not a win

The recommendation above undersold one path: this section's own root-cause read (single
core, largest on the biggest build side) turned out to be directly fixable with an
in-tree technique, not a from-scratch redesign. `mojo/engine/query/join.mojo`'s
`hash_join_indices` probe loop and `materialize`'s per-column gather now fan out over
row bands — the same row-banded-parallel-over-ranges blueprint
`mojo/engine/query/composed.mojo`'s `group_by_many_parallel` established and the
GitBook groupby page published a win on (`gitbook/benchmarks/dataframe-groupby.md`),
adapted here to a per-row VARIABLE-size output (a probe emits 0, 1 or a whole
duplicate-key chain per row, unlike a fixed-slot group merge) via the same two-pass
"counted scatter" `query.aggregate.group_by_many_radix` already uses for the identical
reason: pass A counts survivors per worker with the same branch the serial walk takes, a
cheap serial prefix sum over `workers` (not rows) turns those counts into disjoint write
offsets, and pass B re-walks the same bands and writes at its own cursor with raw
indexed stores. Both new paths carry their own measured, real minimum-row threshold
below which the plain serial walk still runs unchanged (`JOIN_PROBE_PARALLEL_MIN_ROWS =
1<<19`, `JOIN_GATHER_PARALLEL_MIN_ROWS = 1<<18` — see the two constants' own docstrings
in `join.mojo` for the quiet/under-load overhead measurement they're derived from), and
the scatter's own write-cursor invariant is checked after every parallel run and falls
back to the serial walk on any mismatch rather than trust a mis-sized result. The build
side (`_build_right_index`) and `merge_join_indices` are unchanged — see the module
docstring's "Parallel probe and gather" section for the full design and why those two
were left for separate, harder follow-on work.

**Frozen-baseline discipline held exactly**: `hash_join_indices`'s and
`merge_join_indices`'s signatures, numeric semantics, and NaN/null-key handling are
byte-for-byte what this file's Correctness section above already documented — nothing
about what a join means changed, only how the existing single-threaded answer gets
computed. `mojo/tests/libs/test_query_join.mojo` (the original 33-case known-value
suite, unchanged) still passes 33/33. A new suite,
`mojo/tests/libs/test_query_join_parallel.mojo` (28/28), pins the parallel probe and
gather against their serial references row-for-row (not merely same-row-count or
same-multiset) at several worker counts including non-power-of-two ones, at scales past
both new thresholds, and re-runs every NaN/null/duplicate-key/unmatched-row edge case at
that scale.

### Correctness, re-checked at H2O scale before trusting any new timing

Same protocol as the original Correctness section: the parallel binary and a freshly
rebuilt, byte-for-byte **unmodified-serial** binary (from the commit the parallel branch
forked from) were run against the identical generated `/tmp/h2o_join` data, same
session. Row counts are identical to the original table above and to this session's
DuckDB/Polars run on every question (q1=8,997,136 / q2=9,001,606 / q3=10,000,000 /
q4=9,001,606 / q5=9,000,000), and the cross-engine checksum (`sum(v1) + sum(v2)`) is
**bit-identical between the serial and parallel Algenta binaries on every question**
(e.g. q1: `900289106.2571583`, both) — not merely close, exactly equal — and agrees with
DuckDB/Polars to the same ~1e-11-class relative tolerance already disclosed above.

### Results — parallel path, same protocol as the original table

Minimum of 3 reps per engine per question, all three engines run back to back on the
identical generated data, same machine, same session (still not yet the groupby page's
full rotated-interleaved methodology — see Scope, unchanged). Ratio convention is
unchanged from above: **Algenta time / baseline time; above 1.00 means Algenta is
slower.**

| Question | Algenta-parallel (min) | DuckDB (min) | Polars (min) | Algenta/DuckDB | Algenta/Polars |
| --- | --- | --- | --- | --- | --- |
| q1 — small inner on id1 | 0.163s | 0.328s | 0.017s | **0.50x (faster)** | **9.87x** |
| q2 — medium inner on id2 | 0.221s | 0.348s | 0.019s | **0.64x (faster)** | **11.56x** |
| q3 — medium left on id2 | 0.228s | 0.432s | 0.036s | **0.53x (faster)** | **6.40x** |
| q4 — medium inner on id2* | 0.219s | 0.339s | 0.018s | **0.65x (faster)** | **11.90x** |
| q5 — **big** inner on id3 | 1.184s | 0.376s | 0.098s | **3.15x** | **12.05x** |

For reference, this same session's re-verified **unmodified-serial** Algenta binary
(built from the pre-parallelization commit, same data, same session) measured
0.347s/0.520s/0.558s/0.523s/2.287s on q1-q5 — a real, reproducible ~2.1x-3.2x
probe+gather speedup from parallelization alone, consistent with the isolated
probe-only measurement taken while this change was being built.

**Against DuckDB**: Algenta now wins outright on 4 of 5 questions (q1-q4, all four of
which were losses or breakeven before — q1 goes from 0.92x to 0.50x, q2-q4 from
1.15x-1.40x losses to 0.53x-0.65x wins), and q5's big-tier loss — the one the original
"Why the gap" section named as "structurally fixable with the exact tool the research
proposed" — shrinks from 5.33x to 3.15x, a real ~41% reduction in that specific gap, not
a full close. **Against Polars**: every ratio roughly halves (e.g. q2: 27.5x → 11.56x,
q3: 15.7x → 6.40x) but **all five questions remain losses**, in the 6.4x-12.1x range —
exactly what the original "Why the gap" section predicted: Polars' advantage reads as a
flat per-row SIMD/vectorization constant factor, not a parallelism gap, and parallelism
does not touch a constant factor.

### Recommendation, updated

**Per the standing publish rule (minimum ratio > 1.00 against BOTH DuckDB and Polars,
every question), this still does not clear the bar — Polars alone blocks it, on all
five questions, exactly as predicted.** The DuckDB-side recommendation from the original
pass is now substantially executed (parallel probe+gather closed 4 of 5 DuckDB losses
into wins and shrank the fifth); the Polars-side recommendation stands exactly as
written above and is now the only remaining blocker: closing it needs the surviving
serial arithmetic in the probe's hash-and-chain-walk and the gather's per-cell bounds
check to get faster per row (SIMD-friendly hashing/comparison, fewer allocations),
not more threads — parallelism was the DuckDB-shaped half of this gap, not the
Polars-shaped half, and this pass closed the half it was built for.

## Method

* **Dataset.** The H2O db-benchmark J1 join data at the 0.5 GB tier: fact table `x` with
  10,000,000 rows, dimension tables `small` (10 rows, N/1e6), `medium` (10,000 rows,
  N/1e3) and `big` (10,000,000 rows, N/1e0 — the near-1:1 tier), generated by
  `benchmarks/h2o_join/generate.py`: a seeded (108), deterministic numpy port of
  `h2oai/db-benchmark`'s `_data/join-datagen.R` (fetched from the upstream repo for
  this pass) — same key-overlap spec (90% of each dimension table's key values are
  shared with the fact table, 10% are exclusive to each side), not the R generator's
  actual RNG stream. Measured key-overlap on the generated data: 89.97%-90.02% of `x`
  rows have a partner on each of `id1`/`id2`/`id3`, matching the spec's 90% target.
  `id4`/`id5`/`id6` (the official suite's string forms of `id1`/`id2`/`id3`) are not
  generated at all — see the q4 footnote above for why.
* **Timing.** Minimum of 3 repetitions per engine per question, all three back to back
  in one session (see Scope for what this is not yet). Every engine joins in-memory
  columns; no CSV parse is timed. The Algenta number times one `hash_join_indices` call
  plus one `materialize` call per repetition — the same "produce a full answer table"
  operation `CREATE TABLE ans AS SELECT ...` (DuckDB) and `.join()` (Polars) are timed
  doing.
* **Versions.** DuckDB 1.5.5 and Polars 1.43.1 (asserted at runtime by
  `run_baselines.py`, matching the groupby page's own pinned versions), DuckDB given
  `PRAGMA THREADS` set to this machine's core count, Polars at its default parallelism.
* **Hardware.** Apple M4 Max, 16 physical cores, Mojo 0.26.3.0.dev2026042305 compiled to
  a binary. Load average was 12-14 for the whole session (a contended host, like the
  groupby page's own disclosed 46-67 — not idle, but not controlled for by interleaving
  here yet; see Scope).
* **Correctness.** Row count and a cross-engine checksum compared on the bits before any
  timing was trusted — see the Correctness section above for the actual numbers.

## Scope — what this measurement is not (yet)

* **One tier, one session, no interleaving yet.** This is 3 reps per engine per
  question, back to back, in one measurement window — not the groupby page's rotated,
  interleaved, two-cycle methodology. The gap measured here (0.92x-27.5x depending on
  question and reference) is large enough on most cells that load-average noise is very
  unlikely to be the explanation, which is why this pass stopped at 3 reps rather than
  building the full interleaved harness first, per this task's own instruction not to
  over-invest in timing rigor before knowing whether the gap is closeable. The 5 GB and
  50 GB tiers are not measured at all.
* **q4 is not an independent measurement**, for the reason given above and in
  `bench_h2o_join.mojo`'s docstring.
* **The original table above measured the engine with no engine code changed.** That
  is no longer true of the current engine: the Update section's row-banded parallel
  probe and gather are real, merged-into-this-file's-history engine changes, kept
  disclosed above rather than silently overwriting the original table.
* **Still no router, no radix/partitioned hash-join variant, and the build side
  (`_build_right_index`) and `merge_join_indices` are still fully serial** — the Update
  section's parallelism is scoped to the probe and the gather only, per that section's
  own "what was left unchanged" note. The 5 GB and 50 GB tiers are still not measured.
  The Update section's own timing is likewise 3 reps, one session, not yet
  rotated-interleaved — the same caveat as the bullet above, carried forward rather than
  quietly upgraded.
* **Not comparable to the public leaderboard.** Same disclosure as the groupby page:
  the official suite's categorical join keys are strings; every engine here got integer
  dictionary codes instead, for internal comparability among the three engines measured
  on this page, not to reproduce a published leaderboard entry.

## Reproduce

```text title="generate data"
python benchmarks/h2o_join/generate.py
```

```text title="build and run Algenta"
mojo build -I mojo/engine benchmarks/mojo_benchmarks/bench_h2o_join.mojo -o /tmp/bench_h2o_join
/tmp/bench_h2o_join
```

```text title="DuckDB and Polars baselines"
python benchmarks/h2o_join/run_baselines.py
```

The parallel probe and gather (see the Update section above) are the default,
unconditional path in `join.mojo` above their own row-count thresholds — no build flag
or env var switches them on; the same `bench_h2o_join.mojo` build above already
measures the parallel path.

```text title="correctness suites for the parallel path"
mojo build -I mojo/engine mojo/tests/libs/test_query_join.mojo -o /tmp/test_query_join && /tmp/test_query_join
mojo build -I mojo/engine mojo/tests/libs/test_query_join_parallel.mojo -o /tmp/test_query_join_parallel && /tmp/test_query_join_parallel
```
