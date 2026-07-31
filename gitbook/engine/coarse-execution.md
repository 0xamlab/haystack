---
icon: layer-group
description: Run many kernels — or a whole chain — in one call instead of one call each.
---

# Batched and chained execution

`execute(module, function, args)` carries exactly one kernel call. Frame overhead
dominates a small kernel, so N calls cost roughly N × that overhead even when the
maths is microseconds. Two coarse entry points remove it, without changing a single
kernel: both hand each step to the same dispatcher `execute` uses.

| Entry point | Use when | Cost |
| --- | --- | --- |
| `execute_batch` | many independent calls | one frame per shard |
| `pipeline` | each step consumes the previous one | one frame, intermediates stay in Mojo |
| `dataset_open` | one large input, many kernels | send it once, then O(1) per call |
| `stream_open` | a result too large for one frame | one frame per chunk you ask for |
| `budget` | a call must not run away | checked between items, returns partial work |

## Batched execution

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")
out = runtime.execute_batch([
    {"module": "stats", "function": "compute_mean", "args": [[1.0, 2.0, 3.0], 3]},
    {"module": "stats", "function": "median", "args": [[3.0, 1.0, 2.0], 3]},
    {"module": "stats", "function": "count_below_zero", "args": [[-1.0, 2.0], 2]},
])
out["ok"]                    # 3
out["results"][1]["result"]  # 2.0
```

Results come back in the order you supplied, each shaped like a single `execute()`
envelope — so one failing call does not sink its neighbours:

```python
out["results"][1]["success"]     # False
out["results"][1]["error_code"]  # e.g. "invalid_arguments"
```

Pass `partial_ok=False` to stop at the first failure; items never attempted report
`error_code == "not_executed"`, so you can always tell how far the batch got.

### The limit of per-item isolation

Isolation covers errors the runtime can *report*: an unknown module or function, a
wrong argument count, a contract violation, or a kernel that raises.

It does **not** cover a kernel that aborts the process. Many kernels take an
explicit element count and trust it — `stats.compute_mean(v, n)` loops `range(n)`
and indexes `v[i]` — so passing an `n` larger than the list triggers a bounds
assertion, and a Mojo assertion terminates the worker rather than raising something
catchable. When that happens the whole connection dies, taking every resident
dataset and cursor with it, and the caller sees a timeout rather than a per-item
error.

Two consequences worth planning around:

* Keep any count argument consistent with the list you pass. This is the caller's
  responsibility today; the runtime cannot check it generically, because nothing in
  the contract marks *which* integer parameter is a length.
* Always set a timeout. The SDK does this for you; a hand-rolled socket client
  must, or a worker abort looks like an indefinite hang.

Marking length parameters so the coarse layer can pre-validate them is exactly what
a per-function capability manifest would enable, and is tracked as future work.

## Chained execution

A batch keeps calls independent. When a step consumes the previous step's output, a
batch still round-trips it. A pipeline threads results **inside the worker**:

```python
from algenta.pipeline import PREV, Ref

plan = (
    runtime.pipeline()
    .kernel("stats", "sort_values", [[3.0, 1.0, 2.0], 3])
    .kernel("stats", "median", [Ref(0), 3])
    .kernel("stats", "compute_mean", [PREV, 1])
)
result = plan.execute()

result["result"]     # the final node's output
result["results"]    # every node's output, in order
result["lineage"]    # [{"index": 0, "module": "stats", "function": "sort_values", "ok": true}, ...]
result["plan_hash"]  # stable 64-hex identity of the plan
```

`Ref(i)` is node *i*'s output; `PREV` is the node immediately before. References
must point backwards — a forward or self reference is rejected before anything
executes, so you never get a half-run plan.

`plan_hash` is SHA-256 over the node list with references intact and no results
mixed in. The same plan hashes identically across runs and machines, which makes it
usable as a cache key or a provenance record: it identifies the computation, not the
data.

Pipelines are fail-fast, because later nodes usually consume earlier ones and
continuing past a failure just produces more failures. The error names where it
stopped:

```python
result["error_code"]    # "pipeline_node_failed"
result["failed_index"]  # 1
result["node_response"] # the failing node's own envelope
```

Pass `continue_on_error=True` in the node list form (`runtime.run_pipeline`) to
attempt every node regardless.

## Resident datasets

Batching and pipelines both address per-*call* cost. Neither helps when the input
itself is large: every call that needs a 100k-row array re-ships and re-parses it. A
resident dataset is sent once and then addressed by handle, so per-call payload
becomes O(1) in rows rather than O(rows) — a larger effect than batching can reach,
and with no FFI or protocol change.

```text title="dataset handle"
{"type":"dataset_open","name":"sales","value":[...]}  -> {"handle":"ds_1","bytes":...}
{"type":"dataset_list"}                               -> {"datasets":[...],"bytes":...}
{"type":"dataset_close","handle":"ds_1"}              -> {"closed":true}
```

Reference one from any batch item or pipeline node with `"@ds_1"`, alongside the
pipeline's own `"$0"` node references. An unknown handle is an error rather than a
silent null, so a typo fails instead of feeding a kernel nothing.

Handles live for the connection and are **never reused** after a close, so a stale
reference fails with `dataset_not_found` rather than reading whatever took its
place. Residency is capped per connection; opening past the cap fails with
`dataset_capacity_exceeded` rather than evicting — silent eviction would turn a
handle you still hold into a confusing not-found far from the cause.

## Streaming a large result

A session makes a large input cheap to reference; a cursor does the same for a large
output. The caller asks for the next chunk when it is ready, which is backpressure
with no extra machinery — your next call *is* the credit. Stopping early is free:
close the cursor and the remainder is never encoded.

```text title="streaming a resident dataset"
{"type":"stream_open","handle":"ds_1","chunk_rows":1000}
  -> {"cursor":"st_1","total":100000,"remaining":100000}
{"type":"stream_next","cursor":"st_1"}
  -> {"chunk":[...],"rows":1000,"position":1000,"remaining":99000,"done":false}
{"type":"stream_close","cursor":"st_1"}
```

Loop until `done`. A cursor stores only a handle and a position, so it costs a few
bytes whatever the dataset size, and `max_rows` can override the chunk size for a
single pull (clamped to a ceiling, so it cannot be used to demand everything at
once). Closing the dataset mid-stream makes the next pull fail with
`dataset_not_found` rather than returning stale rows.

## Execution budgets

Any coarse request may carry a budget. Every field is optional; absent or
non-positive means unlimited.

```json
{"type": "batch_execute", "requests": [], "budget": {"deadline_ms": 250, "max_ops": 100, "max_result_bytes": 1048576}}
```

Exceeding one returns a typed envelope naming the dimension **and the work already
completed** — asking for 250 ms of work gets you the 250 ms of work, not just an
error:

```python
out["error_code"]  # "budget_exceeded"
out["exceeded"]    # "deadline_ms"
out["partial"]     # results for the items that ran
out["consumed"]    # {"elapsed_ms": ..., "ops": ..., "result_bytes": ...}
```

Budgets are checked *between* items, never mid-kernel. The worker's server loop
reads frames sequentially, so while a kernel computes nothing is reading the socket
— an out-of-band cancel frame would sit in the buffer until the work it meant to
stop had already finished. The budget therefore travels with the request, and
`deadline_ms` is a duration from when the worker began, so no clock synchronisation
is needed.

## Shard routing

The runtime ships as module-routed shards, and a worker only contains its own
shard's modules.

* `execute_batch` groups your calls by owning worker and sends one frame per group,
  then reassembles into your original order. A batch over related modules is one
  frame; in the worst case it degrades to one frame per shard, never worse than
  unbatched.
* `pipeline` needs every node in one worker, so a plan spanning shards raises
  `PipelineShardError` naming which modules sit where. It refuses rather than
  half-executing, since a partly-run DAG is worse than a clear error.

Keep a plan within one module group — the normal case when the installed runtime is
filtered to what your workflow needs.

## Measured effect

`benchmarks/bench_runtime_batch.py`, single shard, median of 9 reps, local bundled
runtime:

Independent calls — `benchmarks/bench_runtime_batch.py`, single shard, median of 9
reps:

| Calls | One at a time | Batched | Speedup | Frames |
| --- | --- | --- | --- | --- |
| 1 | 0.21 ms | 0.27 ms | 0.77× | 1 → 1 |
| 4 | 0.73 ms | 0.41 ms | 1.8× | 4 → 1 |
| 16 | 2.62 ms | 0.81 ms | 3.3× | 16 → 1 |
| 64 | 10.85 ms | 2.04 ms | 5.3× | 64 → 1 |
| 256 | 45.84 ms | 7.31 ms | 6.3× | 256 → 1 |

Batching a *single* call is slightly **slower** — the envelope costs more than it
saves. The win starts around four calls and settles near 6× as per-call cost drops
from ~0.18 ms to ~0.03 ms.

Chained calls — `benchmarks/bench_runtime_pipeline.py`, a genuinely dependent chain
where each step consumes the previous one:

| Depth | Threaded via Python | Pipeline | Speedup | Frames |
| --- | --- | --- | --- | --- |
| 2 | 0.51 ms | 0.33 ms | 1.5× | 2 → 1 |
| 4 | 0.71 ms | 0.38 ms | 1.9× | 4 → 1 |
| 8 | 1.64 ms | 0.43 ms | 3.8× | 8 → 1 |
| 16 | 2.82 ms | 0.60 ms | 4.7× | 16 → 1 |

Isolating the transport, 64 calls cost 14.7 ms as separate frames versus 1.42 ms in
one frame — a 10.4× reduction. End-to-end lands lower because argument marshalling
(~0.007 ms/call) and the kernels themselves are unaffected by batching.

Resident input — `benchmarks/bench_runtime_session.py`, 8 calls over the same array,
inlined in every call versus referenced by handle:

| rows | inline | resident | speedup | inline request bytes | resident |
| --- | --- | --- | --- | --- | --- |
| 100 | 3.03 ms | 1.35 ms | 2.3× | 5,214 | 574 |
| 1,000 | 14.64 ms | 2.56 ms | 5.7× | 47,646 | 582 |
| 10,000 | 107.87 ms | 18.05 ms | 6.0× | 472,222 | 590 |
| 50,000 | 555.19 ms | 89.44 ms | 6.2× | 2,359,254 | 590 |

The right-hand columns are the mechanism: resident request size stays **flat at
~590 bytes** while the inline form grows to 2.36 MB. That is what "O(1) in rows"
means concretely, and why this effect keeps widening with dataset size where
batching's does not.

Resident *time* still grows with rows, because the kernel work grows — a mean over
50,000 values is genuinely more arithmetic. Only the payload is constant.

Reproduce with:

```bash
make bench-runtime-batch
make bench-runtime-pipeline
make bench-runtime-session
```

## Next

* [Runtime libraries](runtime-libraries.md) — the single-call surface these build on
* [Runtime library catalog](runtime-library-catalog.md) — every module and function
* [Engine health & verification](health.md) — confirm the local runtime is live
