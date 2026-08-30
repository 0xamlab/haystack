---
icon: gauge-high
description: OS-course CPU scheduling algorithms and their metrics, stateless queue/backpressure/rate-limit scoring formulas, three independent token-bucket-family rate limiters, LLM-inference latency micro-optimizations, and ML-serving execution-planning heuristics for fusion, device placement, batching, and KV eviction.
---

# Scheduling and rate-limiting kernels

Five modules that share a queueing-and-timing vocabulary but split into three unrelated pairs once
you read the source. `scheduling_algo` is a real OS-course scheduler — First-Come-First-Served,
Shortest-Job-First, priority scheduling, and round-robin — each returning a full per-process
schedule (start/finish/wait times) plus the textbook metrics computed from it. `scheduler_ops`
looks related by name but does something else entirely: ten *stateless scalar formulas* for
scoring a live request queue — fair-queuing priority, backpressure, exponential backoff,
work-stealing, SLA headroom — meant to be called once per request inside a serving loop, not to
simulate a batch of jobs. `token_bucket` is a third, separate thing again: three independent
rate-limiter *structs* (token bucket, leaky bucket, sliding window) with real mutable state
threaded across calls via the SDK's `mutated_args` convention. `latency_optimizer` and
`execution_planner` are both about model-serving specifically, at two different scopes:
`latency_optimizer` is per-token, per-layer micro-optimizations inside one forward pass (early
exit, layer skipping, speculative-decoding gain, KV prefetch, output caching), while
`execution_planner` is the level above it — op fusion, roofline device placement, KV-cache
eviction priority, batching strategy, and adaptive batch sizing across a whole serving system.
None of the five is a database query planner or a general task-DAG scheduler, despite what a
couple of the names might suggest on their own.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# a request-rate limiter: 10-token bucket, refilling at 1 token/sec
tb = runtime.execute("token_bucket", "tb_create", [10.0, 1.0])["result"]
# {'capacity': 10.0, 'tokens': 10.0, 'refill_rate': 1.0, 'last_refill': 0.0}

step = runtime.execute("token_bucket", "tb_consume", [tb, 5.0, 0.0])["result"]
step["result"]                      # True -- 5.0 of 10.0 tokens were available
tb = step["mutated_args"]["bucket"]
tb["tokens"]                        # 5.0

step = runtime.execute("token_bucket", "tb_consume", [tb, 6.0, 0.0])["result"]
step["result"]                      # False -- only 5.0 available, 6.0 requested
tb = step["mutated_args"]["bucket"]
tb["tokens"]                        # 5.0 -- unchanged; a refused request never debits the bucket
```

## The modules

| Module | What it does |
| --- | --- |
| `scheduler_ops` | Stateless scoring formulas for a live execution queue: fair-queuing priority, WFQ credit, backpressure, token-bucket refill math, rate-limiter wait time, work-stealing, timeout escalation, pipeline utilization, SLA headroom, and exponential backoff |
| `scheduling_algo` | Real CPU scheduling algorithms — FCFS, SJF, priority scheduling, round-robin — each returning a full per-process schedule, plus the wait/turnaround/throughput/utilization/Gantt metrics computed from one |
| `latency_optimizer` | Per-token, per-layer latency micro-optimizations for LLM inference: early exit, adaptive depth, layer skipping, speculative-decoding gain, prefill/decode split latency, KV prefetch overlap, and output-cache benefit |
| `token_bucket` | Three independent rate-limiter primitives as real mutable state: a token bucket, a leaky bucket, and a sliding-window counter, each with create/mutate/query functions |
| `execution_planner` | Whole-request/whole-batch ML-serving planning: op-fusion scoring, roofline device placement, KV-cache eviction priority, batching strategy, global scheduling priority, weight prefetch benefit, graph-rewrite gain, memory-tier placement, pipeline depth, and adaptive batch sizing |

## `scheduling_algo`: FCFS, SJF, priority, and round-robin, with real per-process schedules

Every function takes processes as `List[List[Int]]`, one `[arrival_time, burst_time, priority]`
row per process. `fcfs`, `sjf`, and `priority_scheduling` return `[process_id, start_time,
finish_time, wait_time]` per process; `round_robin` returns the shorter `[process_id, finish_time,
wait_time]`, since round-robin has no single start time to report. The metrics functions
(`avg_wait_time`, `avg_turnaround`, `throughput`, `cpu_utilization`, `gantt_chart`) all consume
one of those result shapes.

```python
procs = [[0, 3, 2], [1, 2, 1], [2, 1, 3]]   # [arrival, burst, priority] per process

fcfs = runtime.execute("scheduling_algo", "fcfs", [procs])["result"]
# [[0, 0, 3, 0], [1, 3, 5, 2], [2, 5, 6, 3]]  -- [pid, start, finish, wait]

sjf = runtime.execute("scheduling_algo", "sjf", [procs])["result"]
[row[0] for row in sjf]
# [0, 2, 1] -- P0 runs first (only process arrived at t=0); once P1 and P2 have both
# arrived at t=3, P2 (burst=1) is shorter than P1 (burst=2) and runs next

rr = runtime.execute("scheduling_algo", "round_robin", [procs, 2])["result"]
# [[0, 6, 3], [1, 4, 1], [2, 5, 2]]  -- [pid, finish, wait], quantum = 2
```

Every FCFS start/finish/wait value and every SJF/priority ordering above is pinned by hand in
`tests/mojo/test_scheduling()` inside `tests/mojo/test_wave39.mojo` — not the auto-generated
smoke suite, a real hand-computed table. That test only asserts the round-robin result has three
rows with `finish > 0` and `wait >= 0`; the exact `[[0,6,3],[1,4,1],[2,5,2]]` above comes from
tracing the real `round_robin` loop in `mojo/engine/scheduling_algo.mojo` by hand (quantum-2 slices:
P0 runs 0→2, P1 and P2 arrive during that slice and queue behind it, P1 runs 2→4 and finishes,
P2 runs 4→5 and finishes, P0 finally finishes 5→6) and satisfies those weaker assertions.

{% hint style="warning" %}
**A real bug: `avg_turnaround` and `cpu_utilization` are silently wrong on round-robin results with
non-zero arrival times.** Both functions branch on row length to handle the two result shapes.
For the 4-column FCFS/SJF/priority shape the code is correct: `avg_turnaround` recovers
`arrival = start - wait` and sums `finish - arrival`; `cpu_utilization` sums `finish - start`
(the actual burst). But the 3-column round-robin branch takes a shortcut that only happens to be
right when every process arrives at `t=0`: `avg_turnaround` sums `finish` alone (no arrival
subtracted at all), and `cpu_utilization` sums `finish - wait`, which algebraically equals
`arrival + burst` — not `burst` — because `round_robin` defines
`wait = finish - arrival - burst`.

Run it on the round-robin result above (arrivals are `0, 1, 2`, not all zero):
`avg_turnaround` reports `(6 + 4 + 5) / 3 = 5.0`, but the real turnaround (`finish - arrival`) is
`((6-0) + (4-1) + (5-2)) / 3 = 4.0` — inflated by exactly the mean arrival time. `cpu_utilization`
against `total_time=6` reports `((6-3) + (4-1) + (5-2)) / 6 = 9 / 6 = 1.5` — over 100% utilization,
which is precisely the invariant the FCFS test in the very same file asserts can never happen
(`cpu_utilization should be <= 1.0`). The real utilization is `(3+2+1) / 6 = 1.0`. No existing test
calls either function on a round-robin result with a non-zero arrival time, which is presumably
why this has gone unnoticed.
{% endhint %}

## `scheduler_ops`: stateless scoring formulas for a live request queue

Every function is a pure `Float64 → Float64` formula — no struct, no stored state, meant to be
called fresh on every scheduling decision with whatever the caller already has on hand.

| Function | Formula |
| --- | --- |
| `priority_fair_score(priority, wait_time, base_priority_weight)` | `base_priority_weight * priority + wait_time` |
| `weighted_fair_queue_credit(current_credit, weight, tick)` | `current_credit + weight * tick` |
| `backpressure_load_factor(queue_depth, max_queue_depth)` | `queue_depth / max_queue_depth`, clamped to `[0, 1]`; `1.0` if `max_queue_depth <= 0` |
| `token_bucket_tokens(current_tokens, refill_rate, elapsed_ms, max_tokens)` | `min(max_tokens, current_tokens + refill_rate * elapsed_ms)` |
| `rate_limiter_wait_time(tokens_needed, current_tokens, refill_rate)` | `(tokens_needed - current_tokens) / refill_rate` if positive, else `0.0`; `1e9` if `refill_rate <= 0` |
| `work_stealing_threshold(local_queue_depth, remote_queue_depth, steal_ratio)` | `1.0` if `remote / local > steal_ratio` (or local is empty and remote isn't), else `0.0` |
| `request_timeout_score(elapsed_ms, timeout_ms, priority)` | `priority * (1 + urgency^2)`, `urgency = min(1, elapsed_ms / timeout_ms)` |
| `pipeline_stage_utilization(busy_time_ms, total_time_ms)` | `busy_time_ms / total_time_ms`, clamped to `[0, 1]` |
| `latency_sla_headroom(sla_budget_ms, elapsed_ms, remaining_stages, avg_stage_latency_ms)` | `(sla_budget_ms - elapsed_ms) - remaining_stages * avg_stage_latency_ms` |
| `exponential_backoff_delay(attempt, base_delay_ms, max_delay_ms, jitter)` | `min(base_delay_ms * 2^attempt, max_delay_ms) * (1 + jitter)` |

A worked chain for `work_stealing_threshold` at `steal_ratio = 2.0`: an idle local worker
(`local_queue_depth = 0`) with any remote backlog always steals (`1.0`); at
`local=2, remote=5`, the ratio `5/2 = 2.5` clears `2.0` and the worker steals; at
`local=3, remote=5`, the ratio `1.667` does not clear `2.0` and it doesn't. `exponential_backoff_delay(3, 100.0, 5000.0, 0.2)`
computes `100 * 2^3 = 800`ms, still under the `5000`ms ceiling, scaled by `1 + 0.2` jitter to
`960`ms for the fourth retry attempt (`attempt` is 0-indexed).

**This module's token-bucket math and SLA headroom are deliberately duplicated elsewhere, in a
different shape.** `token_bucket_tokens` and `rate_limiter_wait_time` re-derive the same refill
arithmetic as the `token_bucket` module's `TokenBucket` struct (`tokens = min(capacity, current +
rate * elapsed)`), but as plain functions over scalars — no struct is created, nothing is mutated,
nothing crosses the SDK boundary via `mutated_args`. A caller who already tracks
`current_tokens`/`last_refill` as ordinary fields (say, on a request object in the caller's own
language) can score a rate limit inline with one call; `token_bucket`'s struct-based API is for a
caller who wants the runtime itself to own that state. Note also that `token_bucket_tokens` only
returns the refreshed count — there is no accept/reject decision built in the way `tb_consume`
has one — which is exactly the gap `rate_limiter_wait_time` fills, answering "how long until
enough tokens exist" rather than "were there enough tokens." Separately, `latency_sla_headroom`
here is not the same formula as `cost_router.sla_headroom_score` documented in
[Mixture-of-experts and routing kernels](mixture-of-experts-and-routing-kernels.md):
`cost_router`'s version returns a normalized fraction, `(sla - predicted) / sla`, from a single
already-known latency prediction; this one returns an absolute millisecond figure that additionally
subtracts the estimated cost of whatever pipeline stages remain (`remaining_stages *
avg_stage_latency_ms`) instead of assuming one precomputed total.

## `token_bucket`: three independent rate limiters, as real mutable state

Unlike `scheduler_ops`, this module's three limiters are structs with lifecycle functions, and
mutation crosses the SDK boundary the same way it does for `graph.algorithms.graph_add_edge`
(see [Exact numerics and graph kernels](exact-numerics-and-graph-kernels.md)): a mutating call's
primary `result` carries its own return value, and the updated struct comes back separately under
that same response's `mutated_args`, keyed by the mutated parameter's name (`bucket`, `window`).

| Struct / functions | Behavior |
| --- | --- |
| `TokenBucket` — `tb_create`, `tb_consume`, `tb_refill`, `tb_available` | Refills continuously at `refill_rate` tokens/ms up to `capacity`; `tb_consume` refills first, then debits only if enough tokens exist, returning `False` (bucket untouched) otherwise |
| `LeakyBucket` — `lb_create`, `lb_add`, `lb_leak`, `lb_level` | Fills toward `capacity` as requests add to it, leaks at `leak_rate`/ms; `lb_add` leaks first, then refuses (`False`, bucket untouched) if the addition would overflow capacity |
| `SlidingWindow` — `sw_create`, `sw_allow`, `sw_count` | Records a timestamp per accepted request; `sw_allow` prunes timestamps older than `window_size` before checking against `max_requests` |

The token-bucket example at the top of this page is the first half of a real, hand-pinned sequence
in `tests/mojo/test_wave42.mojo` (assertions 56–62). The second half, for the leaky bucket and
sliding window, is equally exact:

```python
lb = runtime.execute("token_bucket", "lb_create", [10.0, 2.0])["result"]
lb["current"]                                                  # 0.0 -- leaky buckets start empty

r = runtime.execute("token_bucket", "lb_add", [lb, 5.0, 0.0])["result"]
r["result"]; lb = r["mutated_args"]["bucket"]; lb["current"]   # True, then 5.0

r = runtime.execute("token_bucket", "lb_add", [lb, 6.0, 0.0])["result"]
r["result"]                                                    # False -- 5.0 + 6.0 = 11.0 > capacity 10.0

r = runtime.execute("token_bucket", "lb_add", [lb, 5.0, 0.0])["result"]
r["result"]; lb = r["mutated_args"]["bucket"]; lb["current"]   # True, then 10.0 -- exactly at capacity

r = runtime.execute("token_bucket", "lb_leak", [lb, 2.0])["result"]
lb = r["mutated_args"]["bucket"]; lb["current"]                # 6.0 -- 2 seconds x leak_rate 2.0

sw = runtime.execute("token_bucket", "sw_create", [10.0, 3])["result"]
for t in [1.0, 2.0, 3.0]:
    r = runtime.execute("token_bucket", "sw_allow", [sw, t])["result"]
    sw = r["mutated_args"]["window"]
    r["result"]                                                # True, True, True

r = runtime.execute("token_bucket", "sw_allow", [sw, 4.0])["result"]
sw = r["mutated_args"]["window"]
r["result"]                                                    # False -- 3 requests already in the last 10s

r = runtime.execute("token_bucket", "sw_allow", [sw, 12.0])["result"]
sw = r["mutated_args"]["window"]
r["result"]                                                    # True -- by t=12 the window's cutoff is t=2,
                                                                # which has already pruned the 1.0 and 2.0
                                                                # timestamps, leaving room

runtime.execute("token_bucket", "sw_count", [sw, 12.0])["result"]
# 2 -- only 3.0 and the just-recorded 12.0 are still > cutoff (12 - 10 = 2)
```

`_sw_prune`'s cutoff comparison is strict (`timestamps[i] > cutoff`), so a request at exactly the
window boundary is dropped, not kept — the window is a half-open `(current_time - window_size,
current_time]`. `tb_available` and `lb_level` both read the struct's stored field directly, without
applying the passage of time first — calling either right after constructing a bucket with an old
timestamp still baked in will report a stale count until the next `tb_refill`/`lb_leak` call.

## `latency_optimizer`: per-token, per-layer LLM-inference micro-optimizations

| Function | Formula |
| --- | --- |
| `early_exit_confidence(intermediate_logit_entropy, exit_threshold, layer_depth_fraction)` | `(exit_threshold - entropy) * layer_depth_fraction` |
| `adaptive_depth_score(token_difficulty, available_compute_budget, full_model_compute)` | `token_difficulty * (budget / full_compute)`, clamped to `1.0`; `1.0` if `full_compute <= 0` |
| `prefill_decode_split_latency(prefill_tokens, decode_tokens, prefill_throughput_tps, decode_throughput_tps)` | `prefill_tokens / prefill_tps + decode_tokens / decode_tps` |
| `async_speculation_gain(accepted_tokens, total_speculated, speculation_overhead)` | `accepted_tokens - speculation_overhead * total_speculated` |
| `token_streaming_headroom(buffer_tokens, generation_rate_tps, consumption_rate_tps)` | See below — not a single clean formula |
| `layer_skip_quality_cost(layer_importance_score, n_skipped_layers, model_depth)` | `importance * (skipped / depth)^2` |
| `partial_forward_savings(full_forward_flops, partial_forward_flops, quality_degradation, quality_threshold)` | `full - partial` if `degradation <= threshold`, else `0.0` |
| `kv_prefetch_overlap(decode_step_latency_ms, kv_load_latency_ms)` | `(decode_step - kv_load) / decode_step`, clamped to `[0, 1]`; `0.0` if the prefetch doesn't finish in time |
| `attention_skip_score(layer_attention_entropy, skip_entropy_threshold, positional_importance)` | `(skip_threshold - entropy) * positional_importance` |
| `output_caching_hit_benefit(cache_hit_rate, full_generation_latency_ms, cache_lookup_latency_ms)` | `hit_rate * (full_latency - lookup_latency)` |

A few worked numbers against the real formulas: `adaptive_depth_score(0.8, 50.0, 100.0) = 0.8 *
0.5 = 0.4` — a difficult token (`0.8`) gets 40% of the model's depth when only half the compute
budget remains. `kv_prefetch_overlap(10.0, 6.0) = 4/10 = 0.4` — a 6ms KV-block prefetch hides 40%
of a 10ms decode step; `kv_prefetch_overlap(10.0, 12.0) = 0.0`, since a prefetch slower than the
step it's supposed to hide behind can't overlap at all. `layer_skip_quality_cost(0.6, 4.0, 32.0) =
0.6 * (4/32)^2 = 0.6 * 0.015625 = 0.009375` — the squared skip-fraction term means skipping a few
layers is nearly free but the cost accelerates as more are skipped. `output_caching_hit_benefit(0.3,
800.0, 5.0) = 0.3 * 795 = 238.5`ms — the *expected* per-request savings averaged over hits and
misses, not the savings on a cache hit alone (which would be `795`ms).

{% hint style="info" %}
**`token_streaming_headroom` is two different formulas glued together by a sign check, and the
growing-buffer branch mixes units.** When the buffer is draining (`generation_rate_tps <=
consumption_rate_tps`), the function returns `buffer_tokens / consumption_rate_tps` — a clean
"seconds until empty," e.g. `token_streaming_headroom(50.0, 20.0, 25.0) = 50 / 25 = 2.0` seconds
of headroom before the stream starves. But when the buffer is growing
(`generation_rate_tps > consumption_rate_tps`), the function returns `buffer_tokens /
consumption_rate_tps + net_rate` — literally adding a tokens/second rate onto a seconds figure.
`token_streaming_headroom(50.0, 30.0, 20.0) = 50/20 + 10 = 12.5`. That number is what the real
source computes and returns, but it is not dimensionally a "seconds of headroom" figure the way
the draining branch's is; treat it as an opaque, larger-is-safer score in the growing case rather
than a literal time budget.
{% endhint %}

## `execution_planner`: whole-request and whole-batch ML-serving planning, not a query optimizer

**Scope check.** The hint for this page raised query/task-plan optimization as something to
verify; reading `mojo/engine/execution_planner.mojo` directly rules that out. Every one of its ten
functions plans one model's forward pass on serving hardware — there is no SQL, no relational
operator, and no generic DAG-of-tasks abstraction anywhere in the module. `scheduling_priority_score`
is the only function whose name suggests general-purpose scheduling, and its formula
(`urgency * request_value / estimated_compute_ms`) is about ranking inference requests by
value-per-millisecond, not about ordering nodes in an arbitrary task graph.

| Function | Formula |
| --- | --- |
| `fusion_opportunity_score(op_a_flops, op_b_flops, memory_traffic_saved)` | `memory_traffic_saved / (op_a_flops + op_b_flops)` |
| `device_placement_score(op_arithmetic_intensity, device_ridge_point, device_peak_flops)` | `min(1, intensity / ridge_point) * peak_flops` (roofline model) |
| `kv_policy_eviction_priority(last_access_step, current_step, attention_score, seq_remaining)` | `attention_score * seq_remaining / (current_step - last_access_step + 1)` |
| `batching_strategy_score(request_latency_budget_ms, current_batch_size, throughput_gain_per_request, latency_cost_per_request)` | `throughput_gain - latency_cost / budget`; `-1.0` if `latency_cost >= budget` |
| `scheduling_priority_score(queue_wait_ms, sla_budget_ms, request_value, estimated_compute_ms)` | `((queue_wait_ms + 1) / sla_budget_ms) * request_value / estimated_compute_ms` |
| `prefetch_benefit_estimate(weight_bytes, bandwidth_bytes_per_ms, compute_ms_until_needed)` | `(compute_gap - load_time) / compute_gap`, clamped to `[0, 1]` |
| `graph_rewrite_gain(original_flops, rewritten_flops, original_memory, rewritten_memory, flop_weight)` | `flop_weight * (1 - rewritten/original flops) + (1 - flop_weight) * (1 - rewritten/original memory)` |
| `memory_placement_affinity(access_frequency, tensor_bytes, tier_bandwidth, tier_capacity)` | `access_frequency * tier_bandwidth / (tensor_bytes * tier_capacity)` |
| `pipeline_depth_optimal(stage_latency_ms, bubble_fraction, n_microbatches)` | `(1 - bubble_fraction) * n_microbatches / stage_latency_ms` |
| `adaptive_batch_size(current_batch, gpu_utilization, target_utilization, max_batch, adjust_rate)` | `current_batch + adjust_rate * (target - observed) * current_batch`, clamped to `[1, max_batch]` |

Worked chain: an op pair with `op_a_flops=1e6, op_b_flops=2e6, memory_traffic_saved=5e5` scores
`fusion_opportunity_score = 5e5 / 3e6 = 0.1667`. A KV block last touched at step 10 (`current_step
= 15`, `attention_score = 0.8`, `seq_remaining = 50`) has `kv_policy_eviction_priority = 0.8 * 50 /
(15 - 10 + 1) = 40 / 6 = 6.667` — keep it, since a lower number is evicted first. One more request
against a 100ms SLA with `throughput_gain_per_request = 0.2` and `latency_cost_per_request = 15`ms
scores `batching_strategy_score = 0.2 - 15/100 = 0.05` (worth batching); the same call with a
120ms cost against the same 100ms budget short-circuits straight to `-1.0` (`latency_cost_per_request
>= request_latency_budget_ms`), never reaching the arithmetic. `adaptive_batch_size(32.0, 0.5, 0.8,
256.0, 0.5)` computes `error = 0.3`, `new_batch = 32 + 0.5 * 0.3 * 32 = 36.8` — a damped step
toward the target utilization rather than a jump straight to it.

**Relationship to `scheduler_ops.priority_fair_score`.** `scheduling_priority_score` is this
module's closest analog to `scheduler_ops.priority_fair_score`, and the two answer different
questions: `priority_fair_score` adds a linear age bonus to a caller-supplied priority number for a
single dequeue-ordering decision (`base_weight * priority + wait_time`); `scheduling_priority_score`
divides business value by estimated compute cost to get a value-per-millisecond figure, weighted by
how much of the SLA budget has already elapsed. A queue could use either, or both in sequence — one
answers "who's waited long enough," the other "what's the most valuable thing to run per unit of
compute."

## Verification

`scheduling_algo` and `token_bucket` both have real, hand-written pinned assertions:
`tests/mojo/test_wave39.mojo`'s `test_scheduling()` for FCFS/SJF/priority-scheduling start, finish,
and wait times, and `tests/mojo/test_wave42.mojo`'s `test_token_bucket()` /
`test_leaky_bucket()` / `test_sliding_window()` for every token-bucket, leaky-bucket, and
sliding-window transition shown above. `scheduler_ops`, `latency_optimizer`, and
`execution_planner` have only the auto-generated smoke suites in `mojo/tests/libs/` — each calls
every function once with literal `0.5` arguments and checks the result is finite, with no pinned
numeric value. Every worked number for those three modules above was hand-derived directly from
the formulas in `mojo/engine/scheduler_ops.mojo`, `latency_optimizer.mojo`, and
`execution_planner.mojo`, and independently verified before being written down here.

**Next:** see [Mixture-of-experts and routing kernels](mixture-of-experts-and-routing-kernels.md)
for `cost_router`'s request-level SLA and latency-budget formulas, or
[KV cache and autoregressive generation kernels](kv-cache-and-autoregressive-generation-kernels.md)
for `continuous_batching`'s admission-control and preemption scoring, which sits next to
`scheduler_ops` and `execution_planner` in a real serving loop.
