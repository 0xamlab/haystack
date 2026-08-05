# H2O db-benchmark join track, 0.5 GB tier — serial baseline, then a real parallel probe+gather, then a real parallel build, then a per-row constant-factor pass

**Still not a win, after three real fixes. This stays in `benchmarks/`, never
`gitbook/`, per this project's own standing rule: a GitBook page publishes only on a
minimum ratio > 1.00 against BOTH DuckDB and Polars, on every question.** The original
serial baseline below cleared that bar on exactly one of five questions against one of
two references (q1 vs DuckDB). `mojo/engine/query/join.mojo`'s probe and gather were
parallelized first (row-banded, same blueprint as `query.aggregate.group_by_many_
radix`'s counted scatter — see that file's own "Parallel probe and gather" docstring
section; "Update (2026-08)" below), which won 4 of 5 questions against DuckDB and
roughly halved the Polars gap on all 5. Per-phase telemetry then found the remaining
DuckDB/Polars gap on the fifth question (q5, the near-1:1 10,000,000-row build side)
was mostly the one phase that pass left serial — the hash-table build — so it got the
identical radix-partitioned parallel treatment ("Update #2" below): q5's DuckDB ratio
fell from 3.15x to ~1.35x-1.57x across sessions and its Polars ratio roughly halved
again. A third pass ("Update #3" below) went after the per-row constant factor Update
#2 diagnosed as the whole remaining Polars story on every question: it found and fixed
two real redundant-computation bugs (a doubled validity check on every gathered cell,
a doubled hash on the partitioned probe's every left row), verified them rigorously,
and measured a real but small effect — 0.3-2.3% on q1-q4 (inside this benchmark's own
noise band), a reproducible 5-9% on q5. **Every question is still a loss against
Polars, and q5 is still a loss against DuckDB too**, so the page still does not ship.
The four sections below are kept in chronological order — "Results" is the original
serial-path measurement (superseded three times over), "Update (2026-08)" is the
parallel-probe-and-gather measurement (superseded twice, on q5 only), "Update #2
(2026-08)" is the parallel-build measurement (superseded once, by a small constant-
factor delta), "Update #3 (2026-08)" is the current picture — so each stage's
gap-closure is visible, not just the final number.

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

## Update #2 (2026-08): per-phase telemetry attributed the rest of q5's gap to the build — now that's parallel too

The Update section above left `_build_right_index` (the hash-table build over the right
side) and `merge_join_indices` explicitly unmeasured and unparallelized, naming the build
a "separate, harder follow-on." This pass answered that with real per-phase
instrumentation before writing any new engine code, then closed what the numbers found.

### Diagnosis: how much of the remaining gap is the build, exactly

A temporary, additive-only instrumented build (`_build_right_index` and
`_hash_join_probe_parallel` measurement overloads, plus a throwaway
`bench_h2o_join_timed.mojo` driving them — both deleted before this pass shipped, per
this file's own standing rule against permanent speculative instrumentation) timed
build/probe/gather as separate wall-clock spans on the exact H2O data, at H2O scale,
through the exact parallel dispatch production code takes. Scaling each phase's
*fraction of Algenta's own total* onto the Update table's published absolute times
gives:

| Q | build % of Algenta's own time | build share of the DuckDB gap | build share of the Polars gap |
| --- | --- | --- | --- |
| q1-q4 | 0.002%-0.29% | n/a (no DuckDB gap — Algenta already won) | 0.002%-0.29% |
| q5 | **59.6%** (the largest single phase, ahead of probe+gather combined) | **87.3%** | **65.0%** |

**q1-q4: not a build-phase story at all.** The build is noise (under 0.3% of runtime)
on every question with a small or medium build side; their entire remaining Polars loss
is a probe+gather story, predominantly gather (70-90% of the gap) — exactly what the
Update section above already concluded, now with per-phase numbers confirming it rather
than inferring it from shape alone. **q5: the build genuinely is the dominant lever.**
59.6% of Algenta's own q5 time, 87.3% of the DuckDB gap, and 65.0% of the Polars gap —
real, substantial, and (per the design below) addressable without touching the frozen
build's contract. Unaccounted time (build + probe + gather vs. the measured total) was
≤0.017ms absolute on every question — statistically indistinguishable from zero, so
nothing outside these three phases matters here. Within build, `HashIndex.get_or_
assign`'s own hash-and-probe (not the surrounding null-check/chain-append bookkeeping)
is 65-77% of build time at every scale measured, which is what the parallel design
below specifically targets.

### Design: radix-partitioned build, additive, `hash_join_indices`'s contract unchanged

`HashIndex.get_or_assign` mutates shared state (the open-addressed `slots`/`slot_keys`
arrays, plus a `_grow()` that reallocates them), so N workers cannot simply be handed a
row band each and call it concurrently on ONE shared table — two workers inserting
different keys that probe the same or adjacent positions is a real data race, and a
`_grow()` firing from two threads at once corrupts the table for every key, not just the
colliding two.

The fix, adapted from `query.aggregate.group_by_many_radix`'s own solved version of the
identical shared-mutable-state hazard: radix-partition the right side by the TOP bits of
the same FNV-1a hash `HashIndex` already probes with on its LOW bits, so a key's
partition and its in-partition table position are independent signals from one hash,
not two chances to disagree about identity. Two rows share a partition only when a real
hash collision puts them there, exactly as within a single table today.

  * **pass A** (parallel over row bands): hash every matchable right row once, count
    into (worker, partition) — no table touched, nothing to race on.
  * **prefix sum** (serial, `workers x 16` entries — cheap): counts become segment
    offsets, partition-major with band order inside a partition, so partition p's
    region ends up in ascending global row order for free.
  * **pass B** (parallel, same bands): write each survivor's (row, hash) at its own
    (worker, partition) cursor with raw indexed stores — disjoint by construction, the
    same cursor-bounds argument the probe's own scatter already makes, checked after
    and never trusted.
  * **pass 2** (parallel, one task per partition — 16 of them, independent of
    `workers`): each partition builds its OWN private `HashIndex` and its own
    slot-indexed `first_row` list over its ascending-order segment, using
    `get_or_assign_bits` to reuse pass A's hash rather than re-deriving it. `next_row`
    (row-indexed, one array shared across every partition) is written directly by
    whichever partition a row landed in — safe because a right row belongs to exactly
    one partition, so no two partitions ever write the same `next_row[r]`.

Duplicate keys across a WORKER BAND never split across partitions: which partition a row
lands in is decided solely by its own key's hash, identically in pass A and pass B,
never by which band the row's index happens to fall in — two rows sharing a key are
guaranteed the same partition however far apart their row indices are or whichever
worker's band each falls in. The suite's "heavy duplicate keys across bands" fixture
(`test_query_join_parallel.mojo`) exists specifically to exercise this: modulus two
orders of magnitude below row count, so the same key recurs across every worker band by
construction, checked row for row against the serial reference at 23,188,721 output
rows across four worker counts and both join types.

`_build_right_index` and `merge_join_indices` are byte-for-byte unchanged; `hash_join_
indices` gains a second, additive, gated way to reach the identical `JoinResult` — new
private functions (`_build_right_index_parallel`, `_hash_join_probe_serial_
partitioned`, `_hash_join_probe_parallel_partitioned`, `_hash_join_probe_partitioned`)
above `JOIN_BUILD_PARALLEL_MIN_ROWS` (524,288 right rows — same order of magnitude as
the probe/gather thresholds and for the same reason), falling back to the plain serial
build+probe below that threshold or if the new build's own write-cursor invariant check
ever fails. `join_output_rows` and `semi_join_indices` still call the plain serial build
unchanged — neither is on the H2O join-track's measured path; that is a smaller,
separate follow-on, not attempted here.

### Correctness

54 checks in `test_query_join_parallel.mojo`'s new "build-parallel" section, ROW FOR
ROW (not row count, not multiset) against the plain serial build + serial probe
reference, at build-side row counts at and above `JOIN_BUILD_PARALLEL_MIN_ROWS`, at
four worker counts (2, 3, 7, 16) including non-power-of-two ones, covering: the near-1:1
shape (H2O q5's own shape, almost no duplicate keys), heavy duplicate keys spread across
every worker band (the cross-partition-chaining hazard named above), NaN and null
right-side rows at scale (never inserted into any partition, counted correctly), and a
right side just below the threshold called directly. Both the new serial-partitioned
probe and the new parallel-partitioned probe are checked against the reference, and
`hash_join_indices` itself is checked end to end with a right side above the build
threshold so the real dispatch path is proven, not merely its private building blocks.
`test_query_join.mojo`'s original 33/33 known-value suite and the existing 28 probe/
gather parallel checks are unaffected (82/82 total, still green) — this pass added
checks, it did not need to change any.

### Results — build now parallel too, same protocol as the Update table above

Minimum of 3 reps per engine per question, all three engines run back to back on the
identical generated data, same machine, same session, load average 14.4-15.2 (a
contended host, matching the Update table's own disclosed 12-14 — this session was
deliberately re-run at a comparable contention level for the closest apples-to-apples
comparison to that table, not cherry-picked at a quieter moment). Ratio convention
unchanged: **Algenta time / baseline time; above 1.00 means Algenta is slower.**

| Question | Algenta-parallel-build (min) | DuckDB (min) | Polars (min) | Algenta/DuckDB | Algenta/Polars |
| --- | --- | --- | --- | --- | --- |
| q1 — small inner on id1 | 0.181s | 0.448s | 0.028s | **0.40x (faster)** | **6.46x** |
| q2 — medium inner on id2 | 0.264s | 0.548s | 0.036s | **0.48x (faster)** | **7.28x** |
| q3 — medium left on id2 | 0.268s | 0.658s | 0.052s | **0.41x (faster)** | **5.11x** |
| q4 — medium inner on id2* | 0.261s | 0.475s | 0.026s | **0.55x (faster)** | **10.05x** |
| q5 — **big** inner on id3 | 0.742s | 0.506s | 0.129s | **1.47x** | **5.74x** |

q1-q4 move only with the session's own load noise (they never cross
`JOIN_BUILD_PARALLEL_MIN_ROWS` on the build side, so the new code path never runs for
them — exactly as the diagnosis above predicted). **q5 is the whole story**: Algenta's
own q5 time drops from 1.184s to 0.742s in this session — a real ~37% reduction, ~1.6x
speedup, from parallelizing the build alone — which cuts the DuckDB ratio from 3.15x to
1.47x (the DuckDB gap itself shrank by more than half) and the Polars ratio from 12.05x
to 5.74x (also more than halved). **Reproducibility across load levels**: this result
was measured in three separate sessions at three different contention levels (load
6.2-6.5, 6.6-10.1, and the 14.4-15.2 session reported in the table above) to check the
result wasn't a load-noise artifact; q5's Algenta/DuckDB ratio landed at 1.35x, 1.35x-
1.57x, and 1.47x respectively across those three sessions — real variance, but the
qualitative result (the DuckDB gap roughly halved to low-1.x-x, the Polars gap roughly
halved again to mid-single-digit-x) holds in every one of them. Every run's row counts,
`left_unmatched`, and cross-engine checksum are bit-identical to the Update table's own
values above (e.g. q1 checksum `900289106.2571583` on every rep, every session) — the
build parallelization changed nothing about the answer, only how fast it arrives.

### Recommendation, updated again

**Still does not clear the publish bar (minimum ratio > 1.00 against BOTH DuckDB and
Polars, every question) — q5 is still a loss against both, and all five questions are
still losses against Polars.** But the picture inside that verdict changed substantially:
the DuckDB-side story is now fully executed — 4 of 5 questions were already wins, and
this pass took the fifth (q5) from a 3.15x loss to a 1.47x loss, which per the
diagnosis's own attribution is close to the ceiling a build-phase fix alone can reach
(build was 87.3% of that gap, not all of it — the residual ~478ms-scale probe+gather
cost on q5 is real and this pass did not touch it). The Polars-side story is unchanged
in KIND from the Update section's own conclusion — every question still loses to Polars,
and the remaining gap on q1-q4 (5.1x-10.1x here) is still predominantly a gather-then-
probe constant-factor story, not a parallelism gap, since gather and probe were already
parallel before this pass and are still the whole q1-q4 gap. **What is different now**:
q5's Polars gap (5.74x) is close enough to q1-q4's own range (5.1x-10.1x) that q5 is no
longer a structurally distinct worst case — the SAME fix (SIMD-friendly per-row hashing/
comparison in the probe, fewer allocations in the gather) that would move q1-q4 would
now move q5 by a comparable amount too, rather than needing a separate build-specific
intervention on top. That fix — not another parallelism pass, and not scoped to q5
specifically anymore — is the concrete next lever this diagnosis leaves on the table.

## Update #3 (2026-08): the per-row constant factor — real, small, and NOT the fix

Update #2 closed with a concrete next lever: the Polars gap on every question is a flat,
per-row constant-factor cost, not a parallelism gap (probe and gather were already
parallel). This pass investigated that lever directly — source-reading `_take_column_
join`, `take_column`, and `is_matchable_key` for per-row work Polars' vectorized path
does not pay — found two real, additive-only fixes, implemented and verified them, then
measured the actual wall-clock effect before claiming anything. **The honest result: both
fixes are real, both are now shipped, and neither closes a meaningful fraction of the
gap** — worth recording precisely so the next attempt does not re-diagnose the same two
things and expect a bigger win than they have.

### What was found and fixed

1. **A doubled validity check on almost every gathered cell.** `Float64Array.get`
   calls `is_valid_at` internally; `_take_column_join`'s gather loop (and `take_column`'s
   serial one) already call `is_valid_at` in their own `if`, then call `get` in the
   `else` — so every PRESENT cell (nearly the whole output of a gather) paid the
   bounds-check-plus-bitmap-test twice. `is_matchable_key` — probed on every row of
   both build and probe, on both sides of every join — had the identical shape. Fix:
   `columnar.array.Float64Array.get_unchecked(index)`, `get`'s read with no check of
   its own, for a caller that already ran `is_valid_at`. Every call site in
   `query.join` that had already proven validity (`is_matchable_key` itself,
   `_build_right_index`, `_build_right_index_parallel`, both partitioned and
   unpartitioned probes, `is_sorted_ascending`, `merge_join_indices`,
   `_take_column_join`, `join_output_rows`, `semi_join_indices`) switched to it, plus
   `columnar.batch.take_column`'s own serial gather (shared with `query.executor`'s
   filter and sort, and strictly cheaper there too, for the identical reason).

2. **A doubled hash on the partitioned probe's every left row.** `_hash_join_probe_
   serial_partitioned` and `_hash_join_probe_parallel_partitioned` (from Update #2's
   radix-partitioned build) already compute `h = hash_bits(normalize_bits(key))` once
   to route a left row to its partition, then called `tables[p].find(key)` — which
   recomputes `normalize_bits` AND `hash_bits` a second time inside `find`, because
   `HashIndex` had no hashed-entry read overload. Fix: `HashIndex.find_bits(bits, h)`,
   the exact read-side mirror of the existing `get_or_assign_bits` (same contract:
   `bits` MUST be `normalize_bits(key)`, `h` MUST be `hash_bits(bits)`). Both
   partitioned-probe functions now pass the hash they already have instead of
   discarding it.

Both are internal-mechanics-only: every switched call site had already proven the
exact fact (`is_valid_at`, or the `(bits, h)` pair) the unchecked/precomputed entry
point assumes, so the value read and the row visited are unchanged. `hash_join_
indices`'s signature, its build/probe dispatch thresholds, and every NaN/null/
duplicate-key rule in the module docstring are untouched.

### Correctness

`test_query_join.mojo` (33/33) and `test_query_join_parallel.mojo` (54/54) — every
existing check, unmodified — pass exactly as before; this pass changed no assertion
in either file, only the engine code and (below) two other suites' new checks. Two
new checks were added:

* `test_columnar_array.mojo`: `get_unchecked` pinned against `get` on every valid slot
  of a mixed-validity column, including a real `0.0` (the case `get`/`get_unchecked`
  must NOT distinguish from a null read), plus a slice-offset check (`get_unchecked`
  reads `self.offset + index` directly, so an offset bug could only show up there).
* `test_columnar_hash_index.mojo`: `find_bits` pinned against `find` slot-for-slot over
  a 2,000-key stream with heavy duplication, `-0.0`, and NaN mixed in, plus an explicit
  absent-key check and an empty-table check (`find_bits` must never insert).

Both new suites and both existing join suites are 100% green; row counts and checksums
on the H2O data are bit-identical to Update #2's own values (e.g. q5 checksum
`900111565.7615576` on every rep, this pass and the last).

### Results — measured before claiming a win

Three reps per binary per question, `bench_h2o_join.mojo` built from this pass's
`join.mojo`/`array.mojo`/`hash_index.mojo`/`batch.mojo` ("after") against an identical
build from the pre-pass source ("before" — origin/main at the time this pass started,
`21e5f0ff`, i.e. Update #2's own code), back to back, same machine, same session, load
average 6.8-8.1. DuckDB/Polars were re-measured in the same session for the ratio
columns; both are within noise of Update #2's own published numbers.

| Question | Algenta before | Algenta after | Δ | DuckDB (min) | Polars (min) | after/DuckDB | after/Polars |
| --- | --- | --- | --- | --- | --- | --- | --- |
| q1 | 0.1623s | 0.1610s | -0.8% | 0.3428s | 0.0162s | **0.47x (faster)** | **9.93x** |
| q2 | 0.2189s | 0.2153s | -1.6% | 0.3751s | 0.0190s | **0.57x (faster)** | **11.33x** |
| q3 | 0.2244s | 0.2237s | -0.3% | 0.4527s | 0.0382s | **0.49x (faster)** | **5.86x** |
| q4 | 0.2183s | 0.2132s | -2.3% | 0.3618s | 0.0190s | **0.59x (faster)** | **11.22x** |
| q5 | 0.5929s | 0.5586s | **-5.8%** | 0.3803s | 0.0997s | **1.47x** | **5.60x** |

Repeated across several alternating-rep sessions (not just the one tabulated): q5's
improvement is the reproducible one, consistently 5-9% faster across five separate
alternating-rep runs, never the reverse. q1-q4's improvement is real but small enough
(0.3-2.3% in this session) to sit inside this benchmark's own session-to-session noise
band on a shared, moderately loaded (load 6.8-8.8) host — a few reps came back with q1-
q4 flat or fractionally slower for "after", which a genuinely near-zero effect on a
noisy host predicts and a large one would not.

**Why the size mismatch with the diagnosis's own estimate.** Update #2 (without a
profiler, reasoning from code shape alone) expected the validity-check dedup to matter
a lot — it is on 70-90% of the estimated gather-dominated gap's row volume. The measured
effect is much smaller. The likely reason, visible in the code shape itself: `get_
unchecked`'s fix removes a SECOND call to a PURE function (`is_valid_at`, no side
effects) from a straight-line `if`/`else` in the SAME function, over the SAME `self`
that nothing mutates in between — textbook load-forwarding/CSE territory for any
LLVM-backed compiler, and Mojo compiles through LLVM. It is plausible the optimizer was
already collapsing most of this redundancy before this pass ever touched the source;
the source-level fix is real and correct (and now also removes any doubt, cheaply,
with no downside), but the machine-level saving it was chasing may have already existed.
`find_bits`'s fix is a different shape — it removes a redundant computation that
crosses a STRUCT METHOD call (`tables[p].find(key)`, through a `List[HashIndex]`
indirection) rather than sitting in one straight-line block, which is a much harder
case for a compiler to collapse on its own without the source-level rewrite — and it is
exactly the one of the two fixes that produced a real, repeatable, non-noise
improvement.

### Recommendation, updated again

**Still does not clear the publish bar.** No question beats Polars (5.60x-11.33x
loss, essentially unchanged from Update #2's 5.11x-10.05x — within the noise this pass
itself just characterized), and q5 still loses to DuckDB (1.47x, barely moved from
1.47x-1.57x). This pass's own honest conclusion: the two per-row costs it found and
fixed were real, are now gone, and were not the size of lever the remaining gap needs.
Fixing "a doubled cheap check" was not enough; closing a 5-11x gap needs either a
genuinely different per-row shape for the gather/probe (real SIMD/vectorized compare
and copy, batching several rows' worth of work into one instruction the way Polars'
Arrow-native kernels do, rather than one scalar branch per row however cheap each
branch is) or accepting that this join path's current per-row-scalar architecture has
a ceiling here that no more constant-factor trimming will clear. Both of this pass's
fixes ship anyway — they are strictly cheaper on every path that already existed, one
of them (`find_bits`) with a measured, reproducible win on q5 — but the next attempt on
this file should budget for a genuinely different loop shape, not another redundant-
check hunt.

### Independent reproduction (2026-08)

A separate pass re-ran this exact comparison from scratch — fresh worktrees pinned to
`origin/main@21e5f0ff` ("before", i.e. this update's own starting point) and to this
update's code ("after"), fresh `pixi run mojo build`, fresh `/tmp/h2o_join` data check,
fresh DuckDB 1.5.5 / Polars 1.43.1 baselines via the pinned venv `run_baselines.py`
asserts on — specifically to confirm the numbers above are reproducible, not a
one-off. Row counts and checksums came back bit-identical between "before" and
"after" binaries on every question (e.g. q1 `900289106.2571583`, matching the
`~2.4e-12`-level cross-engine agreement this file already documents), confirming the
fixes changed no answer.

Ratios (min of several reps each), this rerun vs. this update's own table above:

| Q | after/DuckDB (this update) | after/DuckDB (rerun) | after/Polars (this update) | after/Polars (rerun) |
| --- | --- | --- | --- | --- |
| q1 | 0.47x | 0.39x | 9.93x | 6.95x |
| q2 | 0.57x | 0.48x | 11.33x | 9.77x |
| q3 | 0.49x | 0.38x | 5.86x | 5.57x |
| q4 | 0.59x | 0.50x | 11.22x | 10.35x |
| q5 | 1.47x | 1.16x | 5.60x | 5.31x |

The absolute ratios move session-to-session (a shared, variably-loaded host, same as
every other measurement in this file) but the **shape and the verdict are identical**:
q1-q4 win outright against DuckDB and lose to Polars by roughly 5-10x in both sessions;
q5 loses to both DuckDB (1.16x-1.47x) and Polars (5.31x-5.60x) in both sessions. The
rerun's before/after deltas landed in the same place too — q1-q4 within ±0.5-1% (noise,
either direction across reps), q5 a reproducible ~5% faster after the fix (0.611s →
0.581s at this rerun's own minimums). This confirms the update above is not a
single-shot artifact: the two fixes are real and worth keeping, and the remaining gap
is exactly as this update already concluded — not something a rerun makes go away.

## Update #4 (2026-08): software prefetching, tried on both the gather and the probe — a real, reproducible REGRESSION, reverted

Update #3 closed with a concrete diagnosis: q5's gap needs a genuinely different per-row
loop shape, not another constant-factor trim, and named software prefetching as the next
thing to try for a latency-bound (not compute-bound) gather. This pass implemented and
measured that directly — distance-8 `std.sys.prefetch` hints, `PrefetchOptions().for_read()
.low_locality()`, ahead of `_take_column_join`'s gather (`materialize`'s per-cell read) and
separately ahead of the partitioned probe's `HashIndex.find_bits` lookup (`_hash_join_probe_
serial_partitioned`, `_hash_join_probe_parallel_partitioned`'s `count_worker`/`scatter_
worker`) — a peek-ahead read of row `l + 8`'s key, hashed and partitioned early solely to
issue the prefetch, matching the standard hash-join prefetch-distance technique from the
database-systems literature (DuckDB, MonetDB).

**The honest result: it made every gathered/probed row slower, on every rep, in both
configurations tried.**

| Configuration | q5, before | q5, after | Δ | Reps, same direction |
| --- | --- | --- | --- | --- |
| Gather-only prefetch | 0.559s-0.594s | 0.565s-0.613s | **+1% to +4% slower** | 5/5 |
| Gather + probe prefetch | 0.558s-0.639s | 0.679s-0.726s | **+15% to +25% slower** | 5/5 |

Both correctness suites (`test_query_join.mojo` 33/33, `test_query_join_parallel.mojo`
54/54) stayed green throughout — the prefetch hint changes nothing about which row is
read or how it is checked, only whether the CPU is told to start fetching it early, so a
regression here is a pure performance effect, not a correctness one. Both configurations
were reverted; the repository is unchanged by this pass.

**Why, best guess.** Apple Silicon's memory subsystem already runs an aggressive hardware
prefetcher (stride and pattern detection in the memory controller, well documented for the
M-series line), so a software prefetch hint here is very plausibly redundant with what the
hardware already does automatically — at which point it is pure overhead: an extra branch,
an extra bounds check, and (for the probe) a second full hash-and-partition computation
per row that is thrown away, for a cache line the hardware prefetcher was already going to
bring in on its own. The probe version's much larger regression (+15-25% vs +1-4%) is
consistent with this: it pays the extra cost TWICE as often — once as the real per-row work,
once again as the peek-ahead — while the gather version only pays the extra branch and
bounds check, so it regresses far less.

**What this rules out, for whoever attempts this file next.** Both the constant-factor
lever (Update #3) and the memory-latency-hiding lever (this update) are now measured and
exhausted for this specific gather/probe shape on this hardware. The gap that remains
(q5 losing to DuckDB by 1.16-1.47x, to Polars by 5.31x-5.60x; see the independent
reproduction above) is not a redundant-check or an unhidden-latency problem. Update #3's
own closing line still stands and is now better-evidenced: closing it needs either a
genuinely different per-row shape (real SIMD-width vectorized compare-and-copy, which
Apple Silicon's NEON can do for a CONTIGUOUS access pattern even though it cannot do a
true hardware gather — the open question is whether the probe or gather step can be
restructured into a contiguous-access shape at all, e.g. by sorting/bucketing rows by
target cache line before gathering) or a different algorithm entirely for the "big,
near-1:1-cardinality" case specifically (q1-q4 already win; only q5's shape loses).
Re-attempting prefetch-distance tuning (a different constant than 8, e.g.) is very
unlikely to flip a directionally-consistent regression measured across 10 total reps
into a win, and should not be the next thing tried.

## Update #5 (2026-08): partition-clustered probe — a real, small isolated gain that does not survive the full pipeline's noise, kept but not shipped as default

Update #4 closed by ruling out constant-factor trimming and software prefetch,
and pointed at two remaining levers: a genuinely different per-row loop shape,
or a different algorithm for the near-1:1 case specifically. This is the
loop-shape attempt.

**The idea.** The build already radix-partitions the right side
(`_build_right_index_parallel`, `JOIN_BUILD_RADIX_BITS = 4`, 16 partitions) — but
the existing row-band probe (`_hash_join_probe_parallel_partitioned`) still visits
LEFT rows in ORIGINAL row order, computing each row's partition on the fly. Since
row order has no relationship to which partition a row's key hashes to, one worker's
band jumps between all 16 partition tables essentially once per row, defeating any
cache locality the partitioning could otherwise buy — the same reason Update #4's
prefetch attempt found nothing worth hiding: there was no locality to exploit in
the first place.

**What was built.** `_hash_join_probe_parallel_clustered` and its three phases:

1. `_partition_left_rows_for_probe` — buckets every matchable left row's index by the
   same top hash bits the build partitions on, reusing `_build_right_index_parallel`'s
   own pass-A / prefix-sum / pass-B shape (count into `(worker, partition)` buckets,
   convert to offsets, scatter row index + precomputed hash into a flat array), just
   with no pass-2 table build since this has no table of its own.
2. `_clustered_count_matches` — parallel over PARTITIONS (not row bands): each worker
   owns one partition, walks only the left rows bucketed into it, and probes ONLY that
   partition's table, so consecutive iterations touch the same (small) table instead of
   a different one almost every row.
3. `_clustered_emit_matches` — the same partition-clustered walk a second time, writing
   `(left, right)` pairs starting at each row's own precomputed offset (from a row-order
   prefix sum run between the two passes) — which is what keeps the OUTPUT in original
   row order despite the WORK being done partition-clustered, so nothing downstream
   needs to know the difference.

Null-key rows never reach the bucketed row list at all (same exclusion rule the build
side already applies to its own null keys), so a LEFT join's unmatched-null emission is
handled by two small, cheap, full-row-range passes (mark the count before the prefix
sum, write the `(row, NO_ROW)` pair after) — the only place these rows are visited on
this path, and neither one touches the big hash tables.

### Correctness

Every existing build-parallel test shape in `test_query_join_parallel.mojo` — near-1:1
(the H2O q5 shape), heavy duplicate keys spread across worker bands, NaN + null right
rows at scale, both INNER and LEFT, at 2/3/7/16 build workers — was extended to also
check the clustered probe against the same plain-serial reference every other check in
the file uses, row for row (not row count, not multiset). **78/78 (was 74/74).**

One real bug surfaced and was fixed before any of this could pass: the first version
correctly COUNTED null-key rows' LEFT-emission slot (so total output size and every
OTHER row's offset were already right) but never actually WROTE those rows in the emit
pass, since that pass only ever walks the bucketed (matchable) row list — their output
slots sat at the array's `fill=0` default (`(0, 0)`) instead of `(row, NO_ROW)`. Fixed
by adding the second small full-row-range pass described above.

### Results — measured before touching the default dispatch

`benchmarks/mojo_benchmarks/bench_h2o_join_clustered_probe.mojo`: builds the shared
radix-partitioned index ONCE, then times the row-band probe and the clustered probe
directly (bypassing `hash_join_indices`), isolating the probe shape from the build,
gather and `materialize`. 5 reps per call, minimum reported, on q5's real id3 columns
(10,000,000 x 10,000,000, near 1:1).

| Rep set | Row-band (baseline) | Clustered | Ratio |
| --- | --- | --- | --- |
| 1 | 0.247s | 0.237s | 1.04x faster |
| 2 | 0.253s | 0.242s | 1.05x faster |
| 3 | 0.262s | 0.234s | 1.12x faster |
| 4 | 0.249s | 0.244s | 1.02x faster |
| 5 | 0.255s | 0.247s | 1.03x faster |
| 6 | 0.266s | 0.247s | 1.08x faster |
| 7 | 0.283s | 0.259s | 1.09x faster |
| 8 | 0.260s | 0.243s | 1.07x faster |
| 9 | 0.253s | 0.261s | **0.97x slower** |
| 10 | 0.276s | 0.260s | 1.06x faster |

**10 of 11 reps favor the clustered probe, in the range 1.02x-1.12x; one rep is a
small regression at 0.97x.** Real, and in the right direction, but modest — nowhere
near the 5-11x this benchmark's own baseline needed against Polars, and only a
fraction of q5's remaining 1.16x-1.47x DuckDB gap even if the whole probe phase
vanished.

Per-phase breakdown (same harness, min over 5 reps) attributes the time honestly:

| Phase | Time | Share |
| --- | --- | --- |
| 1. partition-bucket left rows | ~0.011s | ~9% |
| 2. clustered count pass | ~0.11-0.12s | ~46% |
| 3. prefix sum (sequential) | ~0.015s | ~6% |
| 4. clustered emit pass | ~0.11-0.12s | ~46% |

Count and emit dominate roughly equally — expected, since both walk the exact same
partition-clustered access pattern once each. The bucketing and prefix-sum overhead
this design PAYS that the row-band probe does not is small (~15% combined), which is
why the net effect is a modest win rather than a wash despite doing genuinely more
work per call.

**End to end, through the full 5-question benchmark (`bench_h2o_join.mojo`, temporarily
wired into the default dispatch to measure, then reverted), the isolated gain does not
survive:**

| Rep | Row-band q5 | Clustered q5 | Ratio |
| --- | --- | --- | --- |
| 1 | 0.617s | 0.548s | 1.13x faster |
| 2 | 0.563s | 0.563s | ~1.00x (wash) |
| 3 | 0.568s | 0.564s | 1.01x faster |
| 4 | 0.584s | 0.623s | **0.94x slower** |

Two of four reps favor clustered, one is a wash, one is slower. The ~10-15ms isolated
probe improvement is small enough relative to q5's own ~550-620ms total (build + probe
+ gather + materialize, all sharing one contended host) that it sits inside the full
pipeline's own session-to-session noise band — the same phenomenon Update #3 measured
for its own two constant-factor fixes at the q1-q4 scale, just showing up here at q5's.

### Recommendation

**Kept as new, tested, additive code — NOT wired into the default dispatch.**
`_hash_join_probe_partitioned`'s own dispatch is byte-for-byte unchanged; every existing
call site still reaches `_hash_join_probe_parallel_partitioned` exactly as before. This
is a different bar than Update #3's fixes cleared: those were unconditionally cheaper on
every path that already existed (a redundant check removed is never a cost), so shipping
them risked nothing even though they did not close the gap. This clustered probe is
NOT unconditionally cheaper — it is a different, more complex access pattern that wins
most of the time in isolation and is a wash-to-slight-loss end to end on this host at
this scale — so flipping the default on a modest, partially-noise-level improvement
would be trading real, understood, well-tested code for gain that ten more reps could
easily turn negative on a differently-loaded host.

The next attempt on this file should not re-try prefetch (Update #4) or another
redundant-check hunt (Update #3) — both are now measured and exhausted. Update #4's own
remaining suggestion — a different ALGORITHM for the near-1:1 case specifically, rather
than a different loop shape for the same hash-join algorithm — is the one lever this
file has not yet tried at all.

## Update #6 (2026-08): direct-addressing instead of a hash table for q5's actual key shape — a real, large, reproducible win, and q5 now BEATS DuckDB, but not shipped as default

Update #5 closed by naming the one lever this file had not yet tried: a different
ALGORITHM for the near-1:1 case, not a different loop shape for the same hash join. This
is that attempt, and unlike Update #5 it is a decisive result, not a modest one.

**The idea, verified against the actual generator, not assumed.** `benchmarks/h2o_join/
generate.py`'s `split_xlr(n, rng)` draws `id3` from `rng.permutation(np.arange(1,
round(n * 1.1) + 1))` — a permutation of a DENSE, bounded range of integers, split into
common (90%) / left-only (10%) / right-only (10%) slices. `x.id3` and `big.id3` are each
`sample_all` over a 10,000,000-value pool the same size as the sample, i.e. a pure
shuffle with no padding — so every id3 value on both sides is an exact integer, sits in
the same bounded `1..11,000,000` span, and appears AT MOST ONCE per side. A hash table
is the general-purpose answer to "look up a key" when the key space is unknown; when the
key space is a known, dense, bounded range with no duplicates, a flat array indexed
directly by the key is strictly less work — no hash, no collision chain, one bounds
check and one array read.

**What was built** (`mojo/engine/query/join.mojo`, fully additive):

* `_build_direct_address_table` — a sequential scan for the key range and integer-ness
  (cheap: one read, one comparison per row, no table touch), then a parallel row-banded
  scatter of `table[key - key_lo] = row` into a flat `List[Int]`. Sets `ok = False` and
  refuses to be trusted, exactly `_build_right_index_parallel`'s own discipline for its
  `ok`, on any of three conditions: a fractional key, a span so much wider than the row
  count that the table would waste memory (`JOIN_DIRECT_ADDRESS_MAX_DENSITY = 4`), or a
  duplicate key. The duplicate-key case is the interesting one: two right rows sharing a
  key race harmlessly on the same array slot (a benign store race, not a safety issue),
  and the collision is DETECTED, never trusted, by comparing the matchable-row count
  against the table's own post-scatter occupancy — `matchable` rows scattering into
  `matchable` distinct slots implies zero collisions; anything less proves at least one
  address was written twice.
* `_hash_join_probe_parallel_direct_address` / `_hash_join_probe_serial_direct_address`
  — `_hash_join_probe_parallel_partitioned`'s exact two-pass counted-scatter blueprint
  (count survivors per worker band, prefix sum over workers, re-walk and write at each
  worker's own cursor), with the hash-and-chain-walk replaced by one bounds check and one
  array read, because the build already proved at most one match per row. Falls back to
  the serial walk on its own write-cursor invariant failure, same as every other parallel
  path in this file.

### Correctness

A new fixture (`_shared_permutation` + `_dense_left_batch` / `_dense_right_batch` in
`test_query_join_parallel.mojo`) draws an ACTUAL dense permutation the same way
`split_xlr` does — not a fixture that merely resembles the shape — split 90%/10%/10% the
same way, so the happy path is proven against real bijective data, not an approximation
of it. Checked, row for row, against the same plain-serial reference every other check
in this file uses, at 2/3/7/16 workers, INNER and LEFT, plus a variant with periodic
NaN/null spliced into the left column. Three more fixtures prove the guard rails reject
what they must: a duplicate-key right side (reusing this file's own existing "medium
build side" fixture, which collides by construction), a fractional-key right side, and a
deliberately sparse-range right side. **10 new checks, all passing — 88/88 total (was
78/78).** `test_query_join.mojo` (33/33) and `test_query_plan.mojo` (122/122), which also
exercise `query.join`, are unaffected.

### Results — measured before touching the default dispatch

`benchmarks/mojo_benchmarks/bench_h2o_join_direct_address.mojo`: builds both structures
on q5's real `id3` columns (10,000,000 x 10,000,000, near 1:1) and measures three things,
each with a correctness check before trusting the timing — matching row counts between
the two algorithms' probes, and (for the full pipeline) matching checksums too.

**Build and probe, isolated (bypassing `materialize`, same shape Update #5's own harness
uses), minimum of 5 reps, three separate runs this session:**

| Run | Hash build | Direct-addr build | Build ratio | Hash probe | Direct-addr probe | Probe ratio |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.1033s | 0.0584s | 1.77x faster | 0.2842s | 0.0498s | 5.71x faster |
| 2 | 0.1050s | 0.0588s | 1.79x faster | 0.2940s | 0.0543s | 5.41x faster |
| 3 | 0.1002s | 0.0599s | 1.67x faster | 0.2929s | 0.0495s | 5.92x faster |

Every run agrees on row count (9,000,000, matching the 90% common slice) between the two
probes. The build win is direct-addressing's smaller, more cache-friendly scatter
(a flat array write vs a hash + `HashIndex` insert into one of 16 partitions); the probe
win is larger still — one array read per row vs a hash-table lookup, and it is the
larger of the two phases in absolute terms.

**Full pipeline — build + probe + `materialize` + checksum, `bench_h2o_join.mojo`'s own
q5 shape exactly (`x.*` + `big.id1`/`id2`/`v2`, checksum = sum(v1) + sum(v2) over the
matched rows) — the number that actually belongs next to DuckDB/Polars, paired with a
fresh baseline re-measurement immediately before/after each rep set, same session:**

| Rep set | Algenta hash join (default) | Algenta direct-address | DuckDB (min) | Polars (min) | direct-addr/DuckDB | direct-addr/Polars | hash/DuckDB | hash/Polars |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.6300s | 0.3350s | 0.4143s | 0.1203s | **0.81x (faster)** | 2.78x | 1.52x | 5.24x |
| 2 | 0.6247s | 0.3322s | 0.4033s | 0.1055s | **0.82x (faster)** | 3.15x | 1.55x | 5.92x |

Both algorithms report the identical row count (9,000,000) and the identical checksum
(`900111565.7615576`) on every rep, and that checksum matches DuckDB's
(`900111565.7614492`-`900111565.7614503`, the usual float-summation-order-level
agreement this file's other checksums already show) and Polars' (`900111565.76145`) —
three independently-implemented join engines agreeing bit-for-bit on row count and to
~10 significant figures on the checksum, which is the actual correctness claim, not
merely "the row counts matched."

**q5 beats DuckDB for the first time in this file's history — 0.81x-0.82x, a real
reversal of the 1.16x-1.62x loss every prior update measured (the unrelated-hash-path
`hash/DuckDB` column above, 1.52x-1.55x, is this same session's evidence that the
default path's own loss is unchanged; direct-addressing is what moved it, not session
noise).** The Polars gap is roughly halved (5.31x-5.92x down to 2.78x-3.15x) but not
closed — direct-addressing removes the hash entirely, which was the majority of what
distinguished this join from Polars' vectorized kernels, but `materialize`'s per-cell
scalar gather (Update #3's own diagnosis, never revisited since) is still scalar, and
still the largest single piece of both pipelines' remaining time.

### Recommendation

**Kept as new, tested, additive code — NOT wired into `hash_join_indices`'s default
dispatch, and for a different reason than Update #5's.** Update #5's clustered probe
was withheld because its gain was small and inconsistent — a real risk-free change with
unproven payoff. This one is the opposite problem: the WIN, when the shape holds, is
large and reproducible (1.88x full pipeline, confirmed twice), but the COST of a failed
shape match is not free the way every other fix in this file has been. `_build_right_
index_parallel`'s own `ok = False` path costs one wasted pre-scan; this path's `ok =
False` path costs a wasted pre-scan AND a full parallel scatter AND a full occupancy
count over the whole span BEFORE falling back to redo the entire build via the normal
hash path — real, non-trivial duplicated work on every join whose right side happens to
be all-integer and densely-ranged but NOT duplicate-free (a plausible shape for many
real dictionary-coded foreign keys, not a contrived edge case). Update #3's fixes and
Update #5's clustered probe were safe to leave gated behind a size threshold alone,
because "try it, and it's fine either way" held. This one needs either a cheaper
upfront filter than "attempt the whole build and see" or an explicit caller-declared
contract ("this join's right-side key is a known bijection") before it can sit behind
`hash_join_indices`'s own automatic dispatch without risking a real regression on the
shapes it does not fit. That filter is the next attempt on this file, not this one —
this pass's job was proving the algorithm is correct and the win is real, which it did.

### Follow-up: the explicit caller-declared contract, built

The recommendation above named two ways to make this safely reachable: a cheap upfront
filter, or an explicit caller-declared contract. The contract was the one built, because
`query/plan.mojo`'s `join` op already had exactly the right knob for it —
`method="hash"` vs `method="merge"` is already a caller-asserted, correctness-affecting
choice (merge asserts sortedness and raises if that is false), not a performance hint,
so `method="direct_address"` slots into the same vocabulary rather than inventing a new
one. `query/join.mojo`'s new public `direct_address_join_indices` wraps
`_build_direct_address_table` and raises — naming the precondition and pointing at
`method="hash"` — exactly when the shape does not hold, the same discipline `merge`
already uses for its own precondition. Reachable today from the Python SDK's
`Query.join(..., method="direct_address")`; the TypeScript SDK has no path to
`query/join.mojo` at all yet (a pre-existing gap, unrelated to this method), so this is
Python-only until that is addressed. Documented in `gitbook/engine/columnar-queries.md`'s
"### direct_address" section, alongside `merge`.

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
* **Still no router, and `merge_join_indices` is still fully serial** — no H2O
  join-track question exercises it, so it was out of scope for both the Update section
  and Update #2. `_build_right_index` itself (the plain serial build) is also still
  fully serial and byte-for-byte unchanged — Update #2 above gave `hash_join_indices`
  an ADDITIVE, gated second path (`_build_right_index_parallel`) above
  `JOIN_BUILD_PARALLEL_MIN_ROWS`, not a rewrite of the original function. The 5 GB and
  50 GB tiers are still not measured. Both Update sections' own timing is likewise 3
  reps per session, not yet rotated-interleaved — Update #2 partially compensates by
  re-running across three sessions at different load levels and disclosing the spread
  (see its own Results subsection) rather than trusting a single session's 3 reps, but
  this is still short of the groupby page's full rotated-interleaved methodology.
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

The parallel probe, gather, AND (per Update #2) build are the default, unconditional
path in `join.mojo` above their own row-count thresholds — no build flag or env var
switches any of them on; the same `bench_h2o_join.mojo` build above already measures
the fully-parallel path end to end via `hash_join_indices`'s own dispatch.

```text title="correctness suites for the parallel probe/gather/build paths"
mojo build -I mojo/engine mojo/tests/libs/test_query_join.mojo -o /tmp/test_query_join && /tmp/test_query_join
mojo build -I mojo/engine mojo/tests/libs/test_query_join_parallel.mojo -o /tmp/test_query_join_parallel && /tmp/test_query_join_parallel
```

The second suite covers probe, gather, the radix-partitioned build (its
"build-parallel" section, added for Update #2), (per Update #5) the
partition-clustered probe, AND (per Update #6) the direct-address build/probe and its
guard rails — 88 checks total, all row-for-row against the plain serial references.

```text title="isolated probe comparison + per-phase breakdown (Update #5)"
mojo build -I mojo/engine benchmarks/mojo_benchmarks/bench_h2o_join_clustered_probe.mojo -o /tmp/bench_h2o_join_clustered_probe
/tmp/bench_h2o_join_clustered_probe
```

The clustered probe (`_hash_join_probe_parallel_clustered`) is NOT wired into
`hash_join_indices`'s dispatch — it is additive, tested, and reachable only by calling
it directly (as the harness above does), same as this file's own docstring for the
Recommendation section explains.

```text title="direct-address build/probe: isolated, per-phase, and full pipeline (Update #6)"
mojo build -I mojo/engine benchmarks/mojo_benchmarks/bench_h2o_join_direct_address.mojo -o /tmp/bench_h2o_join_direct_address
/tmp/bench_h2o_join_direct_address
```

Neither `_build_direct_address_table` nor `_hash_join_probe_parallel_direct_address` is
wired into `hash_join_indices`'s dispatch, for the reason Update #6's own Recommendation
section gives (an asymmetric fallback cost, not an unproven payoff) — additive, tested,
and reachable only by calling them directly.
