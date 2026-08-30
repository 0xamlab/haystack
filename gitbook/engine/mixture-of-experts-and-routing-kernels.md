---
icon: route
description: Sparse mixture-of-experts math (gating, capacity, load-balance and z-loss) plus the separate, higher-level layer that routes a whole request to a model, precision, or backend by cost and latency.
---

# Mixture-of-experts and routing kernels

Five modules for two related but distinct decisions. `mixture_of_experts`, `moe_production`, and
`moe_routing` are the arithmetic *inside* one model's forward pass: given a token and a set of
experts, which experts does it go to, how much capacity does each expert get, and what penalizes a
gating network that sends every token to the same expert. `model_router` and `cost_router` are a
level up and outside any single model: given a whole request, which model, which precision, which
device, or which of a cascade of models serves it, traded off against cost and latency budgets. All
five take and return plain `Float64` scalars — no structs, no status-code vocabulary — which keeps
each function a single, checkable formula.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# 512 tokens over 8 experts, capacity_factor = 1.0 -- an exact division
runtime.execute("mixture_of_experts", "expert_capacity", [512.0, 8.0, 1.0])["result"]
# 65.0 -- not 64.0; expert_capacity always adds one full token of headroom, even
# when capacity_factor * n_tokens / n_experts already lands on a whole number

# perfectly uniform routing over 8 experts: every expert gets 1/8 of the tokens
# and the router assigns every expert a mean probability of 1/8
term = runtime.execute("mixture_of_experts", "load_balance_loss", [0.125, 0.125, 8.0])["result"]
term * 8   # sum the per-expert term over all 8 experts -> 1.0, the loss's own minimum
```

## The modules

| Module | What it does |
| --- | --- |
| `mixture_of_experts` | Core sparse-MoE formulas: top-k gate scoring, expert load fraction, the Switch Transformer load-balance loss, router z-loss, expert capacity with a buffer, token dispatch weight, routing entropy, Soft-MoE slot scoring, expert utilization, and the final gated FFN combination. |
| `moe_production` | Running MoE at multi-device scale: token drop fraction under capacity overflow, load imbalance, all-to-all communication efficiency, token-expert affinity, an overflow penalty term, per-device expert-shard memory, normalized routing entropy, the straight-through router gradient, activation sparsity, and an adaptive capacity-factor controller. |
| `moe_routing` | Named gating-network variants from the MoE literature: noisy top-k (Shazeer et al.), Switch Transformer's top-1 softmax, expert-parallel device placement, GShard's smooth top-2 gate, expert dropout, jitter noise, a warmup schedule for the auxiliary-loss coefficient, expert-choice routing, cosine-similarity routing, and per-expert capacity for heterogeneous hardware. |
| `model_router` | Request-level routing across whole models or endpoints: capability/context-window matching, load scoring, fallback triggering, ensemble weighting, retrieval-vs-generation stage selection, quality/cost utility, routing-decision confidence, latency-tier assignment, model-freshness decay, and shadow/canary traffic sizing. |
| `cost_router` | Cost-aware infrastructure routing: per-request cost estimation, a latency/cost Pareto tradeoff score, GPU-vs-CPU and quantized-vs-full-precision routing, batch-vs-immediate serving, MoE-vs-dense model selection, small-then-large cascade savings, remaining budget, SLA headroom, and cost per output token. |

## Two different granularities sharing one page

`mixture_of_experts`, `moe_production`, and `moe_routing` all operate at the *token* level, inside
a single model's forward pass — every function in these three modules takes gate logits, expert
counts, or per-token capacities as arguments. `model_router` and `cost_router` operate at the
*request* level, across a fleet of models, precisions, or devices, and neither one imports or is
imported by any of the three MoE modules; `cost_router.moe_vs_dense_routing` is the one function
that mentions MoE at all from that side, and it treats "route to an MoE model" as a single external
choice — the same kind of decision as GPU-vs-CPU or quantized-vs-full-precision — rather than
implementing any token-to-expert dispatch itself. Grepping the rest of `gitbook/` for these five
module names turns up nothing outside the machine-generated
[Runtime library catalog](runtime-library-catalog.md), so there is no existing page these formulas
duplicate. The nearest sibling in spirit is [LLM inference kernels](llm-inference-kernels.md), which
documents the decode-loop primitives (`llmk.generate`, `llmk.gemv_fast`) a real decode step calls —
but that page's worked model is Qwen3-0.6B-Base, a **dense** model, so its forward pass never calls
any of the five modules here; a decode loop running an MoE checkpoint would sit between the two
pages, calling `llmk`'s residual-add and KV-cache primitives once per layer and `mixture_of_experts`
/`moe_production` once per layer per token to pick and weight that layer's experts.

## `mixture_of_experts`: gating, capacity, and the two auxiliary losses

| Function | What it does |
| --- | --- |
| `topk_gate_score(logit, temperature)` | Divides a raw gate logit by `temperature` before softmax; `temperature <= 0` is refused by returning the logit unscaled rather than dividing by zero. |
| `expert_load_fraction(tokens_to_expert, total_tokens)` | `tokens_to_expert / total_tokens`; `0.0` if `total_tokens <= 0`. |
| `load_balance_loss(router_prob, load_fraction, n_experts)` | One term of the Switch Transformer auxiliary loss, `n_experts * f_i * P_i` — the caller sums this over all experts. |
| `router_z_loss(logit, n_tokens)` | Returns `exp(logit)` to accumulate into a log-sum-exp; the caller squares `log(sum)` and divides by `n_tokens` itself. |
| `expert_capacity(n_tokens, n_experts, capacity_factor)` | `floor(capacity_factor * n_tokens / n_experts) + 1` — always at least one token of headroom above the raw ratio. |
| `token_dispatch_weight(gate_prob, is_selected)` | `gate_prob` if `is_selected >= 0.5`, else `0.0`. |
| `sparse_gate_entropy(probs_sum_log, n_experts)` | `-Σ(p·log p) / log(n_experts)`, normalized so a uniform distribution scores `1.0`. |
| `soft_moe_slot_score(query_dot_phi, n_slots)` | `exp(query_dot_phi) / n_slots`, the unnormalized Soft-MoE slot dispatch weight. |
| `expert_utilization(active_tokens, capacity)` | `active_tokens / capacity`, capped at `1.0` on overflow. |
| `moe_ffn_output(expert_output, gate_weight)` | `gate_weight * expert_output` — one term of the gated sum of expert outputs. |

**`expert_capacity` is not `ceil`.** Reading `expert_capacity`'s body directly:
`Float64(Int64(capacity_factor * n_tokens / n_experts + 1.0))` truncates towards zero, so the result
is always `floor(cap) + 1`. For a non-integer `cap` that equals `ceil(cap)` — 1000 tokens over 8
experts at `capacity_factor = 1.25` gives `cap = 156.25`, and `expert_capacity(1000, 8, 1.25)` returns
`157`, matching `ceil(156.25)`. But when `cap` lands on a whole number the two diverge: 512 tokens
over 8 experts at `capacity_factor = 1.0` gives `cap = 64.0` exactly, and the function still returns
`65`, not `64` — a full extra token of buffer that a plain ceiling would not add. A caller sizing a
capacity buffer off this function's return, rather than re-deriving the ceiling itself, gets that
extra slot for free.

**Uniform routing is the minimum of `load_balance_loss`, by construction.** If routing is perfectly
uniform across `n` experts, both `load_fraction` and `router_prob` equal `1/n` for every expert, so
each term is `n * (1/n) * (1/n) = 1/n`, and summing `n` equal terms gives exactly `1.0` — which is
why the formula multiplies by `n_experts` at all: it is the normalizer that pins the loss's floor at
`1.0` regardless of how many experts there are, so the same threshold means the same thing at 8
experts or 64.

**`sparse_gate_entropy` hits its ceiling of `1.0` the same way.** Over 4 experts routed uniformly
(`p_i = 0.25` each), `Σ p·log(p) = 4 * 0.25 * ln(0.25) = -1.386294...`, and
`sparse_gate_entropy(-1.386294, 4) = 1.386294 / ln(4) = 1.0` — `ln(4) = 1.386294...` exactly cancels
it, because normalized entropy is built to read `1.0` at maximum spread regardless of expert count,
the same normalization trick `load_balance_loss` uses.

**`router_z_loss` only returns half the formula.** Its own docstring is explicit that this function
computes `exp(logit)` for one expert and nothing past that — the caller sums those values across
experts, takes `log`, squares it, and divides by `n_tokens`. Two logits of `0.0` each give
`exp(0.0) = 1.0` per call; summed, `log(2.0)^2 = 0.480453`; divided by, say, `n_tokens = 100`, the
final z-loss is `0.00480453`. `n_tokens` itself never touches this function's arithmetic beyond a
`<= 0.0` guard that returns `0.0` — the normalization it names happens entirely at the call site.

## `moe_production`: dispatch, imbalance, and an adaptive controller

| Function | What it does |
| --- | --- |
| `token_drop_fraction(tokens_to_expert, expert_capacity)` | `(tokens - capacity) / tokens` if over capacity, else `0.0`. |
| `expert_load_imbalance(max_load, mean_load)` | `max_load / mean_load`; `1.0` (perfectly balanced) if `mean_load <= 0`. |
| `communication_efficiency_moe(useful_bytes, total_bytes)` | `useful_bytes / total_bytes`, capped at `1.0`; `1.0` if `total_bytes <= 0`. |
| `expert_affinity_score(token_embedding, expert_centroid, history_weight)` | `token * centroid + history_weight`. |
| `capacity_overflow_penalty(tokens_routed, capacity, penalty_factor)` | `max(0, tokens - capacity)^2 * penalty_factor`. |
| `expert_shard_memory_bytes(expert_ffn_params, n_experts_per_device, dtype_bytes)` | `params * n_experts_per_device * dtype_bytes`. |
| `routing_entropy_balance(router_probs_entropy, max_entropy)` | `entropy / max_entropy`; `1.0` if `max_entropy <= 0`. |
| `gradient_through_router(upstream_grad, gate_prob)` | `upstream_grad * gate_prob` — straight-through estimator for a discrete routing decision. |
| `expert_activation_sparsity(active_experts, total_experts)` | `active_experts / total_experts`; `1.0` if `total_experts <= 0`. |
| `dynamic_capacity_factor(target_drop_rate, current_drop_rate, current_factor, adjust_rate)` | `current_factor + adjust_rate * (current_drop_rate - target_drop_rate)` — a proportional controller step. |

A production-scale worked chain: 200 tokens routed to one expert against a capacity of 160 —
`token_drop_fraction(200, 160) = 40 / 200 = 0.2` (a fifth of that expert's tokens are dropped this
batch), and `capacity_overflow_penalty(200, 160, 0.001) = 40^2 * 0.001 = 1.6`, an auxiliary loss term
that grows quadratically in the overflow rather than linearly, so a badly imbalanced batch is
penalized far more than a mildly imbalanced one. `expert_load_imbalance(200, 100)` for that same
expert against a mean load of 100 across the layer reports `2.0` — double its fair share.

`dynamic_capacity_factor` is the controller that would respond to that: if the layer's target drop
rate is `0.01` and it is currently observing `0.05` (dropping five times too much), a controller
running at `current_factor = 1.25`, `adjust_rate = 0.1` computes `1.25 + 0.1 * (0.05 - 0.01) = 1.254`
— a small step toward more headroom, not a jump straight to the deficit, since `adjust_rate` damps
the correction. If the layer is instead under-utilizing (`current_drop_rate = 0.002`, below the
`0.01` target), the same call shrinks the factor to `1.2492`, trimming buffer capacity back down.

`expert_shard_memory_bytes` is a plain multiply with no guard at all — a realistic Mixtral-scale
input, `expert_shard_memory_bytes(176_000_000, 8, 2)` (176M params per expert FFN, 8 experts on one
device, bf16 at 2 bytes/param), returns `2,816,000,000` bytes, about 2.8 GiB, before any activation
or optimizer-state memory is counted.

## `moe_routing`: named gating variants from the literature

| Function | What it does |
| --- | --- |
| `noisy_top_k_gate(logit, noise, epsilon)` | `logit + noise * softplus(epsilon)` (Shazeer et al. 2017) — tunable Gaussian noise added before softmax. |
| `switch_transformer_gate(logit, max_logit, sum_exp)` | `exp(logit - max_logit) / sum_exp` — numerically-stable top-1 softmax; `0.0` if `sum_exp <= 0`. |
| `expert_parallel_shard_id(expert_id, n_devices)` | `expert_id mod n_devices` — which device hosts this expert. |
| `gshard_gate_weight(gate_score, threshold, is_top1)` | For the primary expert, `gate_score`; for the secondary, `1 - gate_score` if it clears `threshold`, else `0.0` (GShard's smooth top-2). |
| `expert_dropout_mask(expert_id, dropout_rate, random_val)` | `0.0` (dropped) if `random_val < dropout_rate`, else `1.0` (active). |
| `combined_jitter_noise(base_logit, noise_std, noise_sample)` | `base_logit * (1 + noise_std * noise_sample)` — multiplicative training-time exploration noise. |
| `aux_loss_coefficient(step, warmup_steps, target_coeff)` | `target_coeff * min(1, step / warmup_steps)` — linear warmup. |
| `expert_choice_gate(token_score, capacity, n_tokens)` | `round(capacity * n_tokens)` — the number of tokens this expert selects; `token_score` is accepted but not used by this particular return value. |
| `cosine_router_score(token_dot_expert, token_norm, expert_norm)` | `(token · expert) / (‖token‖ * ‖expert‖)`; `0.0` if either norm is zero. |
| `heterogeneous_expert_capacity(base_capacity, expert_speed_ratio)` | `base_capacity * expert_speed_ratio` — a faster device's expert gets proportionally more capacity. |

`switch_transformer_gate(2.0, 3.0, 5.0)` — a logit of `2.0` against a row maximum of `3.0` and a
precomputed `Σ exp(logit_i - max)` of `5.0` — returns `exp(-1.0) / 5.0 = 0.0735759`, the same
max-subtraction stability trick every softmax implementation in this codebase uses. `gshard_gate_weight`
is not symmetric between the two positions it names: called as the primary expert
(`gshard_gate_weight(0.7, 0.3, 1.0) = 0.7`) it passes the gate score straight through, but called as
the secondary expert with the same score above threshold
(`gshard_gate_weight(0.4, 0.3, 0.0) = 1.0 - 0.4 = 0.6`) it returns the *complement* of the score, and
below threshold (`gshard_gate_weight(0.2, 0.3, 0.0) = 0.0`) the secondary expert is dropped entirely
— reading the weight for the wrong slot without checking `is_top1` produces a plausible-looking
number that is the wrong one.

**`expert_choice_gate`'s `token_score` argument doesn't reach this function's own return.** The
formula it implements — `Float64(Int64(capacity * n_tokens + 0.5))`, a round-half-up — only touches
`capacity` and `n_tokens`; `token_score` is present in the signature (matching the docstring's
framing of "affinity score of token for this expert") but plays no part in the number this call
produces. That is consistent with the docstring's own description of the return as "effective
capacity" — the per-expert token budget — rather than a per-token accept/reject decision; the
ranking of individual tokens against that budget, using this same score, is left to the caller.
`expert_choice_gate(anything, 0.125, 1000) = round(125.0) = 125` regardless of what `token_score` is.

## `model_router` and `cost_router`: choosing across models and backends, not across experts

| Function | What it does |
| --- | --- |
| `capability_match_score(request_task_embedding, model_task_embedding, model_max_context, request_context_len)` | Task-similarity product, clamped at `0`, times a hard `0`/`1` context-window gate. |
| `model_load_score(active_requests, max_capacity, queue_depth)` | `(active + queue) / max_capacity`; `1.0` if `max_capacity <= 0`. |
| `fallback_trigger_score(primary_error_rate, primary_latency_p99, sla_latency_ms, error_threshold)` | Sum of normalized error and latency overshoot; positive triggers fallback. |
| `ensemble_weight(model_accuracy, model_latency_ms, latency_budget_ms, total_model_accuracy)` | Accuracy share of the ensemble, zeroed out if the model misses the latency budget. |
| `hybrid_pipeline_stage_score(retrieval_relevance, generation_confidence, use_retrieval_threshold)` | `(retrieval_relevance - generation_confidence) - threshold`; positive routes to retrieval. |
| `model_selection_utility(model_quality, model_cost, user_quality_weight)` | `w*quality - (1-w)*cost`. |
| `routing_uncertainty(top_model_score, second_model_score)` | Normalized margin between the top two candidates; `0.0` if both scores are non-positive. |
| `latency_tier_assignment(request_latency_budget_ms, tier_interactive_ms, tier_batch_ms)` | `0` (interactive), `1` (standard), or `2` (batch), by threshold. |
| `model_freshness_score(model_training_step, current_step, decay_half_life_steps)` | `exp(-staleness * ln(2) / half_life)`; exponential decay, `1.0` if never stale. |
| `shadow_routing_fraction(shadow_experiment_budget, total_traffic, statistical_power_needed)` | The traffic fraction needed for statistical power, capped at the experiment budget. |
| `request_cost_estimate(input_tokens, output_tokens, cost_per_input_token, cost_per_output_token)` | Linear cost model, input and output tokens priced separately. |
| `latency_cost_tradeoff(predicted_latency_ms, latency_budget_ms, predicted_cost, cost_budget)` | `1 - 0.5*(latency_ratio + cost_ratio)` — `1.0` is perfect, negative is infeasible. |
| `gpu_vs_cpu_routing_score(model_flops, gpu_flops, cpu_flops, gpu_cost_per_ms, cpu_cost_per_ms)` | `cpu_time*cpu_cost - gpu_time*gpu_cost`; positive prefers GPU. |
| `batch_vs_single_decision(wait_time_ms, batch_throughput_gain, latency_budget_ms, queue_depth)` | Batching benefit scaled by remaining slack and `log(queue_depth + 2)`; a fixed `-1.0` if there is no slack to wait in. |
| `quantized_vs_full_routing(request_quality_requirement, quantization_quality_loss, speedup_factor, cost_reduction)` | `(speedup - 1) + cost_reduction` if quality survives quantization, else a fixed `-1.0`. |
| `moe_vs_dense_routing(sequence_length, active_expert_fraction, moe_communication_overhead, dense_flop_ratio)` | Whether MoE's FLOP advantage survives its communication overhead, scaled by `log(sequence_length + 1)`. |
| `cascade_model_routing(small_model_confidence, confidence_threshold, small_model_cost, large_model_cost)` | Expected cost saving from a small-then-large cascade versus always calling the large model. |
| `budget_remaining_fraction(total_budget, spent_budget)` | `(total - spent) / total`, clamped to `[0, 1]`. |
| `sla_headroom_score(predicted_latency_ms, sla_latency_ms)` | `(sla - predicted) / sla`; negative means the SLA is at risk. |
| `cost_per_output_token(total_cost, n_output_tokens)` | `total_cost / n_output_tokens`; `total_cost` unchanged if there are no output tokens. |

**`capability_match_score` is a hard gate, not a graceful discount.** A request needing 16,384 tokens
of context against a model whose `model_max_context` is 8,192 scores `0.0` no matter how well the
task embeddings align — `context_ok` is a `1.0`/`0.0` step function multiplied straight into the
score, so there is no partial credit for a model that is almost, but not quite, big enough.

**`cascade_model_routing` prices a wrong small-model answer as a total loss, not a partial one.** If
the small model's confidence (`0.7`) falls below the acceptance threshold (`0.85`), `accept_prob` is
`0.0` and the cascade cost becomes `small_model_cost + large_model_cost` — both calls are paid for,
because the cascade tried the small model first and then had to fall back. At
`small_model_cost = 0.001`, `large_model_cost = 0.02`, that is `0.021`, which is *more* than the
`0.02` an always-large policy would have cost, so `cascade_model_routing(0.7, 0.85, 0.001, 0.02)`
returns `-0.001` — a cascade that guesses wrong often enough is a net loss versus never cascading at
all, not merely a smaller win. When the small model clears the bar instead
(`cascade_model_routing(0.92, 0.85, 0.001, 0.02) = 0.019`), the cascade keeps nearly the entire
`large_model_cost` as savings.

**Two functions return a fixed `-1.0` sentinel for "infeasible," rather than a naturally scaled
negative number.** `batch_vs_single_decision` returns exactly `-1.0` when there is no latency slack
left to wait in (`latency_budget_ms <= wait_time_ms`), and `quantized_vs_full_routing` returns
exactly `-1.0` when quantization would drop quality below the request's floor
(`1 - quantization_quality_loss < request_quality_requirement`) — in both cases regardless of how far
past the limit the inputs are. A caller comparing routing scores across candidates needs to treat
`-1.0` from either function as a refusal marker, not average it in as if it were one point on a
continuous scale.

**`moe_vs_dense_routing` is the one place this pair touches MoE, and only as an external choice.**
At `sequence_length = 999`, `active_expert_fraction = 0.25` (one of four experts active per token),
`moe_communication_overhead = 0.25`, and `dense_flop_ratio = 8.0` (a dense model would cost 8x the
FLOPs of MoE's active fraction), `moe_efficiency = 0.25 / 1.25 = 0.2`, `moe_advantage = 8.0 * 0.2 =
1.6`, and the final score is `(1.6 - 1.0) * log(1000) = 0.6 * 6.907755 = 4.144653` — positive, MoE
preferred. Nothing here dispatches a token to an expert; it is a single scalar comparing two whole
model architectures for one request shape.

## No status-code vocabulary in this family

Unlike `attnk`, `tensorx`, `normk`, `mlpk`, and `llmk` — each of which owns a numbered status-code
range and returns a code alongside (or instead of) a value — none of these five modules define one.
Every guard clause returns a plain sentinel `Float64` directly: `0.0` for "no load," `1.0` for
"perfectly balanced" or "fully fresh," a fixed `-1.0` for "infeasible" in `cost_router`. There is no
`*_status_name` lookup function and no shared error-code range reserved for this family in
`mojo_inventory.py`'s status ledger. That is a real, load-bearing difference from the other kernel
families documented in this corpus, not an omission in this page: every one of these functions
already returns a single number by design, so a second return value carrying a status code would be
the whole interface, and the sentinel convention above does the same job with one value instead of
two.

## Verification

The five `mojo/tests/libs/test_*.mojo` files behind this family (`test_mixture_of_experts.mojo`,
`test_moe_production.mojo`, `test_moe_routing.mojo`, `test_model_router.mojo`,
`test_cost_router.mojo`) are auto-generated coverage smoke tests: each calls every function once
with the literal argument `0.5` (or `0.5`/`0.5`/`0.5`/`0.5` for four-argument functions) and checks
only that the result is finite — they do not pin any specific numeric output. The worked examples
above were hand-traced against the real formulas in `mojo/engine/mixture_of_experts.mojo`,
`moe_production.mojo`, `moe_routing.mojo`, `model_router.mojo`, and `cost_router.mojo`, and every
number given can be reproduced by re-running the same arithmetic.

**Next:** see the dense-model decode loop these formulas sit beside in
[LLM inference kernels](llm-inference-kernels.md), or browse the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
