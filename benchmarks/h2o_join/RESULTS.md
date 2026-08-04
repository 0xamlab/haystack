# H2O db-benchmark join track, 0.5 GB tier — current unrouted hash-join baseline

**Not a win. This stays in `benchmarks/`, never `gitbook/`, per this project's own
standing rule: a GitBook page publishes only on a minimum ratio > 1.00 against BOTH
DuckDB and Polars, on every question.** That bar is cleared on exactly one of the five
questions against one of the two references (q1 vs DuckDB) and missed everywhere else,
most badly against Polars (15x-27x slower on every question) and on the "big"
near-1:1 dimension tier against DuckDB (5.3x slower) — the exact risk the feasibility
research flagged before this measurement pass started.

This is the honest "before" picture for the join-track work the feasibility research
proposed (a shape-aware router + a partitioned/radix hash-join variant, mirroring the
groupby page's own playbook — see `gitbook/benchmarks/dataframe-groupby.md`). No
engine code changed for this pass; this is measurement only, of the plane exactly as it
ships today: `Query.join()` → `plan._apply_join` → always `hash_join_indices` (the
`method` field defaults to `"hash"` and nothing inspects key shape).

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
* **No router, no radix/partitioned hash-join variant exists yet.** This file measures
  the engine exactly as it ships on `origin/main` today; no engine code changed for this
  pass.
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
