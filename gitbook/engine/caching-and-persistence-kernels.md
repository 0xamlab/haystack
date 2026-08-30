---
icon: database
description: A TTL cache with hit-rate tracking, an in-memory table/query engine, a key-value store with snapshot/restore, and closed-form memory-sizing arithmetic for pools, allocators, and transformer training.
---

# Caching and persistence kernels

Four modules that share a "data shape" theme more than a mechanism: `cache` is a capacity- and
time-bounded key-value cache; `database` is a tiny in-memory table engine with the query
primitives (`where`, `sort`, `join`, `group by`) a caller would otherwise reach for a real database
to get; `persistence` is a plain key-value store plus a serialize/restore pair that gives a caller
something to actually write to disk; and `memory_system` is not any of those — it is closed-form
arithmetic for memory-hierarchy and ML-training-memory questions (pool fragmentation, slab waste,
cache-line padding, activation/gradient/optimizer memory, NUMA locality). None of the four calls
into any other, none of them touches a filesystem or a network socket, and none of them is the
KV-cache used by attention decoding — that pair (`kv_cache`, `paged_kv_cache`) lives on
[KV-cache and autoregressive generation kernels](kv-cache-and-autoregressive-generation-kernels.md)
and answers a different question (how much memory does *this attention layer's* K/V history cost)
than this page's `cache` module (a generic TTL key-value cache with no notion of attention, tokens,
or layers at all).

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# capacity=10 entries, ttl=5.0 seconds -- the exact shape of tests/mojo/test_wave26.mojo's cache suite
c = runtime.execute("cache", "create_ttl_cache", [10, 5.0])["result"]

# cache_put mutates `cache` by reference; the SDK boundary is stateless, so the updated
# struct comes back under mutated_args and has to be threaded into the next call
c = runtime.execute("cache", "cache_put", [c, 1, 42.0, 0.0])["result"]["mutated_args"]["cache"]

hit = runtime.execute("cache", "cache_get", [c, 1, 1.0])["result"]
hit["result"]              # 42.0 -- read at t=1.0, well inside the 5-second ttl
c = hit["mutated_args"]["cache"]

miss = runtime.execute("cache", "cache_get", [c, 1, 6.0])["result"]
miss["result"]              # -999999.0 -- the same key at t=6.0 has aged past expires_at=5.0
```

## The modules

| Module | What it does |
| --- | --- |
| `cache` | A capacity-bounded, time-to-live key-value cache: put/get with expiry, oldest-entry eviction on overflow, hit-rate tracking, and a no-side-effect containment check. |
| `database` | An in-memory, column-major table: create/insert, column selection, row filtering (`where`), aggregation (sum/mean/min/max/count), sorting, inner join, and group-by-aggregate. |
| `persistence` | An in-memory key-value store (parallel key/value lists) plus `snapshot`/`restore` to serialize its full contents to and from a plain nested list a caller can actually write out. |
| `memory_system` | Memory-hierarchy and ML-training-memory arithmetic: pool fragmentation, slab allocator waste, cache-line padding, strided-access penalty, activation/gradient/optimizer-state memory, peak memory, bandwidth utilization, and NUMA locality. |

## State crosses the SDK boundary as a value, not a handle

`cache_put`, `cache_get`, `cache_evict_expired`, and `cache_clear` all take `cache` as a mutable
reference in Mojo; `kv_put`, `kv_delete`, and `kv_clear` take `store` the same way; `table_insert_row`
takes `table` the same way. But `runtime.execute` is a stateless request/response call — there is no
server-side object the next call can find by handle. So the mutation crosses back as data: the
call's own return value goes under `result`, and the post-mutation struct goes under
`mutated_args.<param_name>` in that same response, exactly the pattern
[Exact numerics and graph kernels](exact-numerics-and-graph-kernels.md) documents for
`graph_add_edge`. `cache_get` is the one function in this family that does both at once — it has a
real return value (the looked-up `Float64`) *and* a mutated argument (the cache, because a lookup
updates `hits`/`misses`), so its response nests `result` and `mutated_args` side by side rather than
one replacing the other, as shown above. Read-only functions — `cache_size`, `cache_hit_rate`,
`cache_contains`, `kv_get`, `kv_contains`, `kv_size`, `kv_keys`, `kv_values`, every `table_*` lookup
except `table_insert_row` — take their struct by non-mutable reference and return a plain value with
no `mutated_args` key at all.

## `cache`: eviction is FIFO on survivors, not access-recency LRU

`cache.mojo`'s own docstring calls its overflow eviction "LRU-like," but tracing `cache_put`
shows something narrower: when the cache is full and a *new* key arrives, the function always
evicts `entries[0]` — the oldest entry that has not since been overwritten. Updating an *existing*
key's value with `cache_put`, or reading it with `cache_get`, never moves its position in the list.
So a key that is read constantly and one that is never read again are exactly as eligible for
eviction as each other, provided both were inserted at the same time — this is FIFO over the
surviving insertion order, not the recency-of-use tracking "LRU" implies. `test_wave26.mojo`'s
capacity test confirms the mechanism directly: filling a 3-entry cache with keys `1, 2, 3` and then
putting a 4th key evicts key `1` specifically (the oldest), regardless of the fact that key `2` was
never touched again either.

Expiry is a strict inequality: `cache_get` and `cache_contains` both check `expires_at > current_time`,
so an entry put at `t=0` with `ttl=5.0` is already expired at exactly `t=5.0`, not just after it —
the boundary instant counts as expired, not as the last valid instant. A miss and an expired hit
return the identical sentinel, `-999999.0`; `cache_hit_rate` counts both as misses (`hits /
(hits + misses)`, `0.0` with no lookups yet), so a caller cannot distinguish "never cached" from
"cached, but too late" by hit rate alone — only `cache_contains` (which does not touch the
counters) can answer that without perturbing the stats it would otherwise be measuring.

## `database`: an in-memory table, not a database engine

`database.mojo`'s own docstring is explicit about scope: it "replaces sqlalchemy core patterns,"
not a storage engine — there is no disk I/O, no transaction log, and no index. `Table` stores data
column-major (`data: List[List[Float64]]`, one inner list per column), and every operation is a
plain linear scan: `table_where` and `table_aggregate` are `O(n)`, `table_sort_by` is an insertion
sort (`O(n^2)` worst case, stable — a strict `>` comparison in the shift loop means equal values
never swap past each other), `table_join_inner` is a nested loop (`O(n * m)`, exact `Float64`
equality with no epsilon tolerance), and `table_group_aggregate` finds each row's group with a
linear scan of the groups seen so far (`O(n * g)` for `g` distinct groups). None of that is wrong
for the toy scale these kernels are built for, but it means "the caller has 10,000 rows and two
tables to join" is a very different cost than the identical call over 10 rows.

**`table_create`'s `n_rows` parameter is silently ignored.** Reading the body:

```mojo
def table_create(columns: List[String], n_rows: Int) -> Table:
    ...
    return Table(columns, 0, data)
```

Every table starts at `0` rows no matter what `n_rows` is passed — there is no pre-sizing effect,
and no error either. `tests/mojo/test_wave59.mojo` only ever calls `table_create(cols, 0)`, so the
parameter's dead weight never shows up in the pinned suite; a caller passing `table_create(cols,
100)` expecting 100 empty/zero rows gets the same empty table as `table_create(cols, 0)`.

**`table_where`'s `op` and `table_aggregate`'s `agg` both use the integer range 0-4 for unrelated
things.** `table_where`: `0`=eq, `1`=gt, `2`=lt, `3`=gte, `4`=lte. `table_aggregate`: `0`=sum,
`1`=mean, `2`=min, `3`=max, `4`=count. Passing an aggregate code where a filter op is expected (or
the reverse) is a silent behavior change, not an error — both parameters are a plain `Int`, and
there is no shared enum between the two functions.

A grounded worked example, straight out of `test_wave59.mojo`'s 5-row table (`group` column values
`1, 1, 2, 2, 1` against `value`s `10, 20, 30, 5, 15`): `table_group_aggregate(t, group_col=2,
agg_col=1, agg=0)` (sum) returns group `1 -> 45.0` (`10+20+15`) and group `2 -> 35.0` (`30+5`);
`agg=1` (mean) returns `1 -> 15.0` and `2 -> 17.5`. `table_sort_by(t, 1, ascending=True)` on the same
table returns row indices `[3, 0, 4, 1, 2]` — row 3's `value=5` sorts first, row 2's `value=30`
sorts last.

`database` is not the backend behind [Columnar queries](columnar-queries.md)'s `runtime.query`
plan API either — that page's `Query(...).run(...)` compiles a filter/group/sort *plan* and routes
it through whichever module shard is installed (its examples use `routing_module="stats"`); this
page's `table_*` functions are a lower-level, uncompiled API a caller drives one call at a time,
threading `mutated_args` between an insert and the next read the same way `cache` does.

## `persistence`: what it actually persists

Despite the name, and despite the docstring's own framing ("replaces shelve/dbm"), `persistence.mojo`
does no disk I/O of its own. `KVStore` is an in-memory struct — parallel `keys`/`values` lists plus
a `size` counter — and every one of its operations (`kv_put`, `kv_get`, `kv_delete`, `kv_clear`,
...) only ever touches those in-process lists. What the module actually contributes is the *shape*
of state a caller can hand to real storage: `snapshot(store)` flattens the whole store to a plain
`List[List[Float64]]` (`[[key_as_float, value], ...]`), and `restore(data)` rebuilds a `KVStore`
from that same shape — writing the snapshot to a file, a socket, or anywhere durable is entirely the
caller's job, not this module's.

Two real edge cases fall out of that shape. `snapshot` casts every integer key to `Float64`
(`Float64(store.keys[i])`); `Float64` can only represent integers exactly up to `2^53`
(`9,007,199,254,740,992`), so a `KVStore` keyed past that magnitude loses precision on a
snapshot/restore round trip — not a concern at realistic key ranges, but a real, silent ceiling for
anyone keying by, say, a raw 64-bit hash. And `kv_delete` removes an entry by swapping it with the
*last* element and popping (`O(1)`, no shifting), so `kv_keys`/`kv_values` order is insertion order
only until the first delete — after that, order reflects deletion history, not insertion history.

`test_wave57.mojo` pins the full round trip by hand: `kv_put` three keys (`1->10.0, 2->20.0,
3->30.0`), `snapshot` them to 3 pairs, `restore` into a fresh store, and confirm `kv_get` on the
restored store returns the same three values — the one hand-verified guarantee this module makes is
that round trip, not durability itself.

`kv_get` and `kv_contains` do **not** mutate `store` (no hit/miss counters exist in this module at
all) — a real difference from `cache`, where even a read-only-looking `cache_get` updates
`hits`/`misses` on every call. A `KVStore` has no eviction, no TTL, and no capacity limit; it grows
until `kv_clear` or `kv_delete` shrinks it.

## `memory_system`: memory-hierarchy and training-memory arithmetic — not agent memory, not a cache

The name is the one genuine surprise in this family. `memory_system.mojo` is neither a computer's
RAM-management code nor an AI-agent's conversational/long-term "memory" concept — its own docstring
states the actual scope plainly: "Memory pooling, tensor layout, and activation checkpointing math."
Every function is a closed-form estimator, not a live allocator or a cache: `pool_fragmentation_ratio`,
`slab_alloc_waste`, and `cache_line_padding_bytes` model allocator waste; `strided_access_penalty` and
`numa_locality_score` model access-pattern cost; `activation_memory_bytes`, `gradient_memory_bytes`,
`optimizer_state_bytes`, and `peak_memory_estimate` size a transformer training step's memory
footprint; `memory_bandwidth_utilization` is a plain ratio. None of these ten functions takes or
returns a struct — every argument and result is a bare `Float64`.

| Function | Formula (from source) |
| --- | --- |
| `pool_fragmentation_ratio(allocated, used)` | `(allocated - used) / allocated`, clamped at `0.0`; `0.0` if `allocated <= 0`. |
| `slab_alloc_waste(object_size, slab_size)` | `slab_size - floor(slab_size / object_size) * object_size`. |
| `cache_line_padding_bytes(struct_size, cache_line)` | `cache_line - (struct_size mod cache_line)`, or `0.0` if already aligned. |
| `strided_access_penalty(stride_bytes, cache_line)` | `stride_bytes / cache_line`, floored at `1.0` (never below "no penalty"). |
| `activation_memory_bytes(batch, seq_len, d_model, n_layers, dtype_bytes)` | `batch * seq_len * d_model * n_layers * 2 * dtype_bytes` (the `2` is input + output activations per layer). |
| `gradient_memory_bytes(n_parameters, dtype_bytes)` | `n_parameters * dtype_bytes`. |
| `optimizer_state_bytes(n_parameters, optimizer_type)` | `n_parameters * multiplier * 4.0`, `multiplier` = `0` (SGD), `1` (momentum), or `2` (Adam/AdamW) by `optimizer_type` \>= 1/2/3. |
| `peak_memory_estimate(weights, activations, gradients, optimizer)` | Plain sum of the four. |
| `memory_bandwidth_utilization(actual_gbs, peak_gbs)` | `actual / peak`, capped at `1.0`; `0.0` if `peak <= 0`. |
| `numa_locality_score(local, remote, remote_penalty)` | `local / (local + remote * remote_penalty)`; `1.0` if the total is `0`. |

**`optimizer_state_bytes` always assumes 4-byte (FP32) optimizer state — it has no `dtype_bytes`
parameter at all**, unlike `gradient_memory_bytes` and `activation_memory_bytes`, which both take
one. A caller modeling 8-bit optimizer state (bitsandbytes-style) cannot express that through this
function; it reports the FP32 figure regardless of what is actually deployed. And there is no
"weight memory" function in this module — `peak_memory_estimate` takes `model_weights_bytes` as a
plain pre-computed argument, even though the underlying formula would be identical to
`gradient_memory_bytes`'s (`n_parameters * dtype_bytes`, just at the weights' own dtype rather than
the gradient's).

**A worked training-memory chain**, every number computed from the formulas above and independently
re-checkable: a 7B-parameter model, bf16 weights (2 bytes), FP32 gradients (4 bytes), Adam optimizer,
batch size 8, sequence length 2048, `d_model` 4096, 32 layers.

- `activation_memory_bytes(8, 2048, 4096, 32, 2)` = `8 * 2048 * 4096 * 32 * 2 * 2` = `8,589,934,592`
  bytes (exactly `2^33`, ~8.0 GiB).
- `gradient_memory_bytes(7e9, 4)` = `28,000,000,000` bytes (~26.1 GiB).
- `optimizer_state_bytes(7e9, 3)` = `7e9 * 2 * 4` = `56,000,000,000` bytes (~52.1 GiB — Adam's `m`
  and `v` moments, both FP32).
- Weight memory (not a function in this module, same shape as `gradient_memory_bytes` at bf16):
  `7e9 * 2` = `14,000,000,000` bytes (~13.0 GiB).
- `peak_memory_estimate(14_000_000_000, 8_589_934_592, 28_000_000_000, 56_000_000_000)` =
  `106,589,934,592` bytes, ~99.3 GiB — already past what a single 80 GB accelerator holds, before
  counting any framework or CUDA-context overhead, which is exactly the kind of back-of-envelope
  question this module exists to answer without spinning up a training run to find out the hard way.

`pool_fragmentation_ratio(1e9, 6e8) = 0.4`, `slab_alloc_waste(48, 4096) = 16.0` (4096 / 48 fits `85`
whole objects, wasting `4096 - 85*48 = 16` bytes per slab), `cache_line_padding_bytes(100, 64) =
28.0` (a 100-byte struct needs 28 bytes of padding to reach the next 64-byte boundary), and
`numa_locality_score(900, 100, 3) = 0.75` (900 local accesses against 100 remote ones penalized 3x,
i.e. weighted as 300) — all four hand-traced directly against the source above, not run through the
kernel.

This module's `cache_line_padding_bytes` and `strided_access_penalty` reference "cache line" as a
hardware concept (CPU/GPU memory-alignment granularity); that is unrelated to this same page's
`cache` module, which is a software TTL key-value cache with no notion of bytes, alignment, or
hardware at all. `mojo/engine/structs/lru_cache.mojo` (a `String`-keyed LRU cache with real
recency-based eviction) is a different, internal struct file, not a `runtime_library_contract.json`
module in its own right — it is not reachable through `runtime.execute` and is out of scope for
this page.

## Verification notes

`cache` and `persistence` each have a real, hand-written pinned suite: `tests/mojo/test_wave26.mojo`
("Data Pipeline, Advanced Caching, Differential Privacy") drives `cache` through capacity eviction,
expiry, hit-rate, and clear with concrete key/value/timestamp triples; `tests/mojo/test_wave57.mojo`
("Persistence, Constrained Optimization, Random Forest") drives `persistence` through put/get/delete/
snapshot/restore. `database` has its own dedicated hand-written suite in
`tests/mojo/test_wave59.mojo` ("Database Operations, Reinforcement Learning, Astronomy"), covering
create, insert, select, all three comparison operators, every aggregate, sort direction, inner join,
and group-by. `mojo/tests/libs/test_cache.mojo`, `test_persistence.mojo`, and (there is no
`test_database.mojo` in that directory at all) the auto-generated smoke tests that do exist for
these three only call `create_ttl_cache`/`kv_create` once each and check the call doesn't throw —
the wave tests above are the real coverage. `memory_system` has no hand-written wave-test suite
anywhere in this corpus; `mojo/tests/libs/test_memory_system.mojo` is auto-generated and checks only
that each function returns a finite number at the literal input `0.5` (or `0.5` repeated). The
worked chain in this page's `memory_system` section was computed independently from the formulas in
`mojo/engine/memory_system.mojo` and can be re-derived from that source directly.

**Next:** see the attention-specific KV cache this page's `cache` module is not, on
[KV-cache and autoregressive generation kernels](kv-cache-and-autoregressive-generation-kernels.md),
or browse the [Runtime library catalog](runtime-library-catalog.md) for every module and function.
