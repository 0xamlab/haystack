---
icon: chart-mixed
description: Distinct counts, frequencies and quantiles from summaries that fit in constant memory, merge across workers, survive a restart, and report absence rather than zero when there is no answer.
---

# Streaming sketches

Four kernel modules that answer a question about a stream in far less space than the stream:
how many distinct things went past, how often a particular key appeared, what the 95th
percentile is, and whether the distribution has shifted. They run as compiled kernels inside
the runtime that ships with the SDK — there is nothing to start and nothing to install
separately.

A sketch is worth having when three things are true, and this package treats all three as
claims you can check rather than folklore:

1. **It merges.** Two workers each summarise half a stream, ship a summary, and the combination
   is the summary of the whole stream. For distinct counts and frequencies that holds exactly.
2. **Its error bound is a function you can call**, so the interval arrives beside the number.
3. **It is reproducible.** Every hash and every internal coin flip is derived from a seed you
   supply, so two runs — and two machines — produce identical summaries from identical input.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# 50,000 events over 12,000 distinct ids, summarised in 4,096 registers.
sketch = runtime.execute(
    "streaming.distinct", "distinct_ingest",
    [ids, 12, 5],          # ids, precision, seed
)["result"]

est = runtime.execute("streaming.distinct", "distinct_estimate", [sketch])["result"]

est["value"]           # 12191.02... against an exact 12,000
est["relative_error"]  # 0.01625 — the claimed one-sigma error for 4,096 registers
est["present"]         # True
```

## The modules

| Module | What it answers |
| --- | --- |
| `streaming.contract` | the package's one status vocabulary, its size ceilings, its keyed hash, and each of the four error bounds as a callable function |
| `streaming.distinct` | how many distinct items a stream contained — in constant memory, merging exactly |
| `streaming.frequency` | how often a given key appeared, with an over-estimate bound and its confidence |
| `streaming.quantiles` | any quantile of a stream, and the inverse: the rank of a given value |
| `streaming.drift` | whether and where a series changed, from a resumable five-number detector |

## Absence is not zero

The failure this package is built to avoid is a monitoring number that reads as normal because
the data stopped arriving. Every answer therefore carries a `present` flag, and when `present`
is `False` the value slot holds `0.0` and means nothing:

```python
empty = runtime.execute("streaming.quantiles", "quantile_empty", [256, 1])["result"]
q = runtime.execute("streaming.quantiles", "quantile_at", [empty, 0.5])["result"]

q["present"]   # False
q["status"]    # 361 — no_observations_so_no_answer_exists
q["value"]     # 0.0 — representable, and not an answer
```

That is deliberately different from a frequency query against an empty sketch, which is
`present == True` with a count of `0`. Nothing having been added determines every **count**
exactly, and determines no **quantile** at all. The two facts are not the same and do not look
the same.

The same distinction runs through the refusals. A quantile outside `[0, 1]` is not clamped,
because clamping turns a unit mix-up — `95` for the 95th percentile — into the maximum, which
looks like an answer:

```python
runtime.execute("streaming.quantiles", "quantile_at", [sketch, 1.5])["result"]["status"]
# 374 — quantile_outside_unit_interval
```

## Distinct counts

`distinct_ingest` builds a summary in `2^precision` registers, and the memory does not grow
with the stream. `precision` is the accuracy dial: `4` gives 16 registers and a claimed 26%
relative error, `12` gives 4,096 and 1.6%, `16` gives 65,536 and 0.41%.

```python
ids = [1, 2, 3, 2, 1, 7, 7, 9]      # five distinct values

sk = runtime.execute("streaming.distinct", "distinct_ingest", [ids, 4, 5])["result"]
est = runtime.execute("streaming.distinct", "distinct_estimate", [sk])["result"]

est["value"]            # 5.995... for a true 5
est["relative_error"]   # 0.26 — sixteen registers is a smoke-test size, and says so
est["n_ingested"]       # 8 — add CALLS, not distinct items
```

`n_ingested` counts additions and is reported so you can tell "no data" from "data whose
cardinality is small". It is not part of the cardinality answer.

**Merging is exact.** The summary of two halves combined is bit-identical to the summary of the
whole, so a partial summary is worth shipping:

```python
left  = runtime.execute("streaming.distinct", "distinct_ingest", [ids_a, 12, 5])["result"]
right = runtime.execute("streaming.distinct", "distinct_ingest", [ids_b, 12, 5])["result"]

both = runtime.execute("streaming.distinct", "distinct_merge", [left, right])["result"]
```

Merging is also idempotent in the registers, so replaying a partial summary after a crash
cannot double-count a distinct item. Two summaries built with different `precision` or a
different `seed` are refused rather than coerced — they are two different hash functions, and
combining them has no meaning.

**A summary survives a restart.** `distinct_snapshot` flattens it to a list of integers and
`distinct_from_snapshot` reads it back, validating every field, because the caller of that
function is a stored payload rather than a programmer:

```python
snap = runtime.execute("streaming.distinct", "distinct_snapshot", [sk])["result"]
back = runtime.execute("streaming.distinct", "distinct_from_snapshot", [snap])["result"]
```

The validation includes relations *between* fields, not only ranges within them. A payload
whose registers are all zero while declaring five additions is refused, because a stream of
five items cannot have zero distinct items:

```python
forged = [0x44495354, 4, 0, 5] + [0] * 16     # every field individually in range
runtime.execute("streaming.distinct", "distinct_from_snapshot", [forged])["result"]["status"]
# 371 — snapshot_shape_inconsistent
```

An estimate is also projected onto the interval a cardinality can occupy. A stream of `n`
additions has between 1 and `n` distinct items, so an estimate above `n` is provably too high
and is reported as `n`.

## Frequencies

`frequency_ingest` builds a `depth` x `width` counter table. Two bounds apply and they are
different in kind:

* **Never under-states.** Absolute, with no probability attached. The estimate for a key is at
  least its true count, always.
* **Over-states by at most `epsilon * total`,** with probability at least `1 - delta`.
  `epsilon` is about `e / width` and `delta` is about `e^-depth`, and both arrive attached to
  every estimate:

```python
sk = runtime.execute("streaming.frequency", "frequency_ingest",
                     [keys, 2048, 5, 11])["result"]     # keys, width, depth, seed

q = runtime.execute("streaming.frequency", "frequency_query", [sk, 7])["result"]

q["count"]     # 20 — and the exact count is also 20
q["total"]     # 10000
q["epsilon"]   # 0.00133...
q["delta"]     # 0.00673...
q["slack"]     # 13.30... — epsilon * total, the absolute allowance for this query
```

So the honest reading of that result is "between 7 and 20", and `slack` saves you the
multiplication.

Rows are independently keyed, which is what makes `depth` mean something: each row is an
independent upper bound, so taking the minimum over `depth` of them drives the failure
probability down as `e^-depth`. `frequency_frozen_row_collisions` and
`frequency_keyed_row_collisions` let you measure that independence on your own data rather than
take it on trust.

A Count-Min table cannot enumerate its own keys — it stores counters, not items — so
`frequency_heavy_hitters` takes the candidate set from you, who has it. A non-finite threshold
is refused rather than answered, because "no candidate met a NaN threshold" and "no heavy
hitters" are different facts:

```python
hh = runtime.execute("streaming.frequency", "frequency_heavy_hitters",
                     [sk, candidates, 0.05])["result"]

hh["present"]   # True
hh["items"]     # the candidates whose estimate is at least 5% of total mass

bad = runtime.execute("streaming.frequency", "frequency_heavy_hitters",
                      [sk, candidates, float("nan")])["result"]

bad["present"]  # False
bad["status"]   # 377 — parameter_out_of_range
bad["items"]    # [] — and that emptiness is NOT "none of them"
```

Merging adds the tables cell for cell and is exact. Unlike a distinct-count merge it is **not**
idempotent: merging a table with itself doubles every count, which is the right arithmetic for
concatenating a stream with itself, and the reason a replayed partial must be de-duplicated by
you.

A width of 1 is legal and is exactly the degenerate case you would expect: one column means
every key shares one counter, so every query returns the total. That is stated rather than
hidden, because it is the shape a misconfigured `width` takes.

## Quantiles

`quantile_ingest` builds a compactor stack whose memory is proportional to `k` times the
logarithm of the stream length — 128 stored items for a 131,072-item stream at `k = 256`, and
the same 128 across an eightfold size range. `k` is the accuracy dial: the rank of a returned
value is claimed to be within `8/k * n` of the requested rank.

The definition is **nearest-rank**: `quantile_at(sk, q)` returns the smallest observed value
whose estimated rank is at least `ceil(q * n)`. Every value it returns is a value that actually
occurred; nothing is interpolated.

```python
ramp = [float(i) for i in range(1, 101)]     # 1.0 .. 100.0

sk = runtime.execute("streaming.quantiles", "quantile_ingest", [ramp, 4096, 1])["result"]

runtime.execute("streaming.quantiles", "quantile_at", [sk, 0.29])["result"]["value"]  # 29.0
runtime.execute("streaming.quantiles", "quantile_at", [sk, 0.95])["result"]["value"]  # 95.0
runtime.execute("streaming.quantiles", "quantile_at", [sk, 1.0])["result"]["value"]   # 100.0
```

At `k = 4096` a hundred items never fill a level, so that summary holds all hundred verbatim
and those three answers are exact: the 29th, 95th and 100th smallest. The `rank_slack` field
reports the interval in items — `0.195` here — so you can see when a sketch is telling you it
has approximated something and when it has not.

`quantile_rank` is the exact inverse, and the direction the bound is actually stated in:

```python
runtime.execute("streaming.quantiles", "quantile_rank", [sk, 29.0])["result"]["value"]  # 0.29
```

`q = 0` and `q = 1` return the exact minimum and maximum, which are tracked separately from the
compactor stack precisely because compaction can discard them.

**Ask for many quantiles in one call.** `quantile_batch` builds the internal distribution once
and reads every quantile off it, where a hundred separate calls would build a hundred identical
distributions for the same answer. Each entry carries its own presence flag, so one
out-of-range `q` marks itself absent instead of failing the batch.

**Merging is within the stated bound, not exact,** and saying so is the point: compaction
discards items, so a merged summary is *a* summary of the concatenation rather than *the*
summary of it. When neither input ever compacted the merge is exact, and the total weight is
preserved to the item in every case.

## Drift and change points

`page_hinkley_scan` looks for a shift in the mean of a series and reports where:

```python
series = [0.0] * 5 + [4.0] * 5

v = runtime.execute("streaming.drift", "page_hinkley_scan",
                    [series, 0.0, 5.0])["result"]        # series, delta, threshold

v["detected"]       # True
v["change_index"]   # 6 — zero-based, and the FIRST crossing
v["statistic"]      # 12.912698...
```

`delta` is the change magnitude tolerated before the detector starts accumulating and
`threshold` is where it fires. Raise the threshold and the same series reports no detection,
with `change_index` at `-1` — which is never a valid position, so it cannot be used as one by
mistake. Test `detected` first.

The detector is five numbers, which is small enough to travel in a response. So
`page_hinkley_step` and `page_hinkley_resume` let a worker hold a stored detector, receive the
next chunk, and continue exactly where it left off — feeding chunks in order reproduces the
state a single pass over the concatenation would produce, scalar for scalar.

`ddm_scan` is the classification-error counterpart: it takes a stream of correct/incorrect
booleans and reports normal, warning or drift at every instant. Two behaviours are worth
knowing. A series shorter than 30 observations is reported **absent** rather than judged. And a
single error after a run of perfect predictions is level `0`, not drift — a run with no errors
has no standard error to compare against, and calling the first mistake a regime change would
fire on every model that has a good day.

## What every module refuses

Refusals are typed. The status codes in `360`–`379` each name a defect rather than returning a
bare number, and `stm_status_name` turns one into a phrase:

| Situation | Status |
| --- | --- |
| no observations, so no answer exists | `361` |
| a non-finite input | `362` |
| an element count that does not match the data | `363` |
| an accuracy parameter outside its range | `364`, `365`, `366`, `367` |
| the work this request would do exceeds the ceiling | `369` |
| a stored payload whose fields contradict each other | `371` |
| two summaries that cannot be combined | `372` |
| a quantile outside `[0, 1]` | `374` |
| a parameter outside its range | `377` |

Two of those deserve a note.

**The work ceiling is charged as a product, not a sum.** A request's cost is the number of
elementary steps it will perform — items times rows for a frequency ingest — and it is refused
before it runs when that product exceeds the ceiling. A summary's *memory* being bounded says
nothing about how long filling it takes, and a small payload that quietly implies minutes of
work is the failure this avoids.

**A stored payload is validated against itself.** Every summary you can hold, ship and hand
back is checked for the relations between its own fields — that its register array is the
length its precision implies, that its counter table is the size its dimensions imply, that its
level sizes account for exactly the items it carries — before anything reads it. Every one of
those returns status `371` and none of them can be caused to do anything else.

## Reproducibility

Every hash and every compaction coin comes from a counter-based generator at explicit
coordinates, seeded by you. Two runs on the same input with the same seed produce
bit-identical summaries; a different seed produces a different, equally valid one. There is no
process-global randomness anywhere in this package, so a result you got yesterday is a result
you can get again.

`stm_version` names the hashing and compaction rules as a string. Two summaries whose version
agrees were built by the same rules and may be merged, so a stored summary can be checked
before it is trusted.

## See also

* [Streaming Windows](streaming-windows.md) — windowed aggregates over the same stream
* [Data Quality](data-quality.md) — profiling and expectation checks on the source columns
* [Runtime Library Catalog](runtime-library-catalog.md) — every module and function
