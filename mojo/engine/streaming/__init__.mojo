"""
streaming — sketches and online estimators over unbounded streams. Zero Python.

What the tree already has, and why it is not enough
--------------------------------------------------
The frozen tree is not short of streaming arithmetic. It is short of streaming ANSWERS.

* `sketch.mojo` has a Count-Min table and a HyperLogLog register array with correct
  add and estimate arithmetic — and no merge, no snapshot, no keyed hash, and a
  row-seed schedule under which every Count-Min row computes the same column (all of
  `d * 1000003 + 7` are congruent to 7 modulo 1000003, so `depth` buys nothing).
  Measured: `cms_hash(5, 7, 100) == cms_hash(5, 1000010, 100) == 52`, and all four rows
  of a depth-4 sketch agree on 20,000 of the first 20,000 items.
* `pandas_groupby` has Welford's mean and M2 updates as pure scalar steps.
  `online_learning` has EMA, EMA-variance, streaming mean/variance and the DDM drift
  alert level. `timeseries_stats` has `rolling_mean` (an O(n) sliding sum) and
  `rolling_std` (an O(n*w) exact recompute per window). All correct, all callable,
  none of them a driver: each is one step of a loop nobody in the tree writes.
* `bloom_counting` answers membership with deletions, `token_bucket` answers
  admission, `structs.lru_cache` answers recency, `reservoir` answers sampling — and
  `reservoir` draws from `std.random.random_float64`, so its output cannot be
  reproduced, which is why a keyed lane is added beside it rather than it being called.
* There is no quantile sketch of any kind, no change-point or drift detector beyond
  DDM's single scalar step, no windowed minimum or maximum, and nothing anywhere that
  merges two partial summaries.

`sketch.mojo`, `pandas_groupby.mojo`, `online_learning.mojo`, `timeseries_stats.mojo`,
`sorting.mojo`, `anomaly.mojo`, `bloom_counting.mojo`, `token_bucket.mojo`,
`reservoir.mojo` and `structs/lru_cache.mojo` are frozen and unchanged. This package
CALLS them: the HyperLogLog register update and estimator, the Count-Min column
reduction, Welford's two updates, the EMA pair, DDM's alert level, `rolling_mean`,
`rolling_std`, `mergesort`, `percentile`, `philox_word` and `dims_fit` are all reached
rather than rewritten.

What is added is the part that was missing: a driver that consumes a whole stream, a
FLAT snapshot that crosses a process boundary, a MERGE that combines two partial
snapshots, an error bound stated as a function and checked against an exact
computation, and a refusal for every input that has no answer.

Modules:
  contract  — the one vocabulary: statuses 360-379, ceilings, work budget by division,
              the keyed Philox hash, and the four error CLAIMS as functions
  distinct  — HyperLogLog distinct counts: keyed ingest over the frozen registers,
              flat snapshot, EXACT merge (register-wise maximum), estimate or absence
  frequency — Count-Min frequencies with per-row keyed columns: flat snapshot, EXACT
              merge (cell-wise addition), point query, heavy hitters, and the frozen
              row-degeneracy probe that explains why the keying exists
  quantiles — a KLL compactor stack with keyed compaction coins: rank and quantile
              queries, flat snapshot, merge inside the stated rank error
  drift     — Page-Hinkley change detection, as a whole-series scan and as an
              explicit resumable state, plus a DDM scan over the frozen alert level
  windows   — windowed aggregates: O(n) monotonic-deque minimum, maximum and range,
              the frozen rolling mean and standard deviation with their costs charged,
              and EWMA/EWM-variance series over the frozen updates

Every public signature is flat — `List[Float64]`, `List[Int]`, `List[Bool]`, `Float64`,
`Int`, `Bool`, `String`, and structs declared in the same file as the function returning
them — so nothing is silently dropped from the runtime contract.

EVERY STRUCT IN THIS PACKAGE IS DECODED FROM CALLER JSON
--------------------------------------------------------
All fourteen of them. The generated dispatch parses them positionally and the runtime validates
FIELD TYPES only — never a relation between two fields — so `valid: true` beside an empty list
and a count field of 512 is a well-typed, accepted request. Every count field in every struct
here (`precision`, `depth`, `width`, `level_sizes`, `n`, `total`, `count`, `change_index`) is
therefore a CALLER-SUPPLIED number, and using one as a subscript bound instead of `len()` of the
list being indexed is the brief's "never trust a caller's count" relocated from a bare
`(List, Int)` pair into a struct field. It is exactly as fatal there: a read past a `List` end is
an uncatchable abort that kills the worker and every dataset resident in it, and `try/except` in
the dispatch arm does not contain it.

So each module carries ONE predicate that relates a struct's list lengths to its own count
fields, and every public entry point calls it before the first subscript:

  * `distinct._sketch_ok`   -- `len(registers) == 2^precision`, every register inside the range
                               the frozen update can produce, and `n_ingested > 0` implying at
                               least one non-zero register.
  * `frequency._shape_ok`   -- `depth * width == len(cells)`, decided by DIVISION through the
                               frozen `sparse_numerics.csr.dims_fit`, plus `_cell_in_range` per
                               cell READ so a point query stays O(depth).
  * `quantiles._levels_ok`  -- `sum(level_sizes) == len(values)`,
                               `len(compactions) == len(level_sizes)`,
                               `len(level_sizes) <= MAX_STM_LEVELS` checked BEFORE the weight
                               shift so `1 << i` cannot wrap, and the re-derived weight equal
                               to `n`.
  * `drift._state_ok`       -- every scalar finite, and `change_index` coherent with `detected`
                               and `count`.
  * `windows.window_summary_std` -- a forged summary validated before its variance is rooted.

None of those relations is expressible in a `counts:` block: the manifest grammar's `len(NAME)`
takes a PARAMETER name, and `len(sketch.cells)` is a struct field, which the checker reports as
`relation_unknown_parameter`. The kernel is the only place the relation can live, so it lives
there and is asserted by a forged-struct block in every suite.
"""
