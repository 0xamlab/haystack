---
icon: shield-halved
description: Scalar analytic formulas for multimodal fusion primitives, inference-serving capacity and latency estimates, per-request cost accounting, and prompt-injection/output-safety scoring.
---

# Multimodal and inference operations kernels

Four small modules that answer questions a serving stack asks around, rather than inside, the
tensor arithmetic of a forward pass: how many patches does this image break into, how much does
this request cost, how long will it wait in queue, and does this input look like a prompt
injection. None of the four take a `List[Float64]` buffer or a shape — every public function here
is scalar in, scalar (or a small fixed-size struct) out, which sets this family apart from `attnk`,
`tensorx`, and `llmk` elsewhere in this section: those operate on flat `[token][head][dim]` or
`(bytes, dims, rank, dtype)` buffers with real shapes; this family is a library of closed-form
estimates and heuristic scores that a caller plugs its own numbers into, one call per quantity,
never a buffer.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("multimodal", "image_patch_count", [224.0, 16.0])["result"]
# 196.0 — ViT-B/16 on a 224x224 image: a 14x14 grid of 16px patches

runtime.execute("inference_cost_latency", "request_cost_estimate",
                [1000, 500, 0.5, 1.5])["result"]
# 1.25 — 1000 prompt tokens @ $0.50/1k + 500 completion tokens @ $1.50/1k
```

## The modules

| Module | What it does |
| --- | --- |
| `multimodal` | image patch embedding/counting, mel-scale and STFT spectrogram math, audio feature normalization, CLIP-style cross-modal similarity, and a modality-fusion weight — the scalar building blocks a vision/audio front end composes into real tensors elsewhere |
| `inference_engine` | serving-loop metrics: padding masks, dynamic-batching priority, KV-cache hit ratio, latency-percentile and throughput estimates, continuous-batching capacity, and analytic prefill/decode time-per-token |
| `inference_cost_latency` | token-count estimation from character counts, KV-cache and attention FLOP sizing, prefill/decode latency, per-request USD cost, a cost/latency frontier score, batch efficiency, queueing delay, and speculative-decoding gain |
| `inference_security` | prompt-injection, jailbreak-pattern, adversarial-input, PII, data-leakage, output-toxicity and tool-call/sandboxed-execution trust scores — heuristic risk numbers computed from signals a caller already has (classifier logits, token counts, gate booleans), not a classifier itself |

## These are formulas, not kernels

Every function in all four modules takes `Float64` (or `Int`) scalars and returns a single
`Float64` (or `Int`) — `mojo/engine/multimodal.mojo`, `inference_engine.mojo`,
`inference_cost_latency.mojo`, and `inference_security.mojo` between them declare zero `List`
parameters. `image_patch_embed(pixel_value, weight, bias)` computes one element of a linear
projection (`pixel * weight + bias`); a caller wanting a whole patch embedding calls it once per
output element itself, the same way `tensorx.elementwise` decodes one buffer element at a time
except here there is no buffer, dtype tag, or shape underneath — just the one arithmetic
expression. This is a deliberate, narrower scope than `attnk`/`tensorx`/`llmk`: those own the actual
memory layout and iterate internally; this family owns the math and leaves iteration, batching, and
storage to the caller.

## Multimodal: scalar primitives for a vision/audio front end

`image_patch_count(image_size, patch_size)` is `(image_size / patch_size)²`. At the real ViT-B/16
resolution and patch size, `image_patch_count(224.0, 16.0)` gives `196.0` — the actual, well-known
14×14 = 196 patch count that model uses. `image_token_count` layers a compression factor on top for
models that downsample patches before they reach the LLM (LLaVA, Idefics-style connectors):

```python
runtime.execute("multimodal", "image_token_count", [224.0, 16.0, 1.0])["result"]
# 196.0 — compression_factor=1 is a no-op, tokens == patches

runtime.execute("multimodal", "image_token_count", [224.0, 16.0, 4.0])["result"]
# 49.0 — 196 / 4 == 49.0 exactly
```

The division is rounded via `Int64(n_patches / compression_factor + 0.5)` — add one half, then
truncate — which rounds half up rather than Python's banker's rounding, though it agrees with
ordinary rounding away from a `.5` boundary.

`vision_attention_scale(head_dim)` is the familiar `1/√d_head` scaling: at `head_dim = 64.0` (a real
ViT-B head width) it returns `0.125`. `spectrogram_mel_freq(hz)` implements the standard mel-scale
formula (`2595 · log10(1 + hz/700)`) via natural log divided by `ln(10) = 2.302585093`, hand-coded
because there is no `log10` in `std.math` here; `spectrogram_mel_freq(1000.0)` returns
`999.9855371396244` — 1000 Hz mapping to (within floating-point roundoff of) 1000 mel is the textbook
reference point for this formula, not a coincidence.

`cross_modal_similarity(vision_embed, text_embed, vision_norm, text_norm, temperature)` computes
`(vision_embed * text_embed) / (vision_norm * text_norm * temperature)` — the CLIP-style
temperature-scaled cosine similarity, but for a **single element pair**, not a full embedding
vector. Calling this once per dimension and summing the results is not the same as computing a real
cosine similarity: the norm product and temperature would then be divided out once per dimension
instead of once for the whole vector. A caller building a full cross-modal similarity needs to sum
the raw `vision_embed_i * text_embed_i` products across dimensions first, and divide by
`vision_norm * text_norm * temperature` exactly once at the end — this function is the per-element
term, not a drop-in per-dimension accumulator.

{% hint style="warning" %}
**`multimodal_fusion_weight`'s `n_modalities` parameter has no effect.** The docstring says the
formula is "confidence × relevance / (sum across modalities)" and describes `n_modalities` as a
baseline for uniform weighting, but the source's `if n_modalities <= 0.0` branch and its `else`
branch return the exact same expression, `modality_confidence * modality_relevance` — there is no
division by modality count anywhere in the function body. Passing `n_modalities=0` or
`n_modalities=100` produces an identical result for the same confidence/relevance pair; a caller who
wants actual normalization across modalities has to do it themselves after collecting every
modality's raw weight.
{% endhint %}

## Inference engine: serving-loop metrics

These are the per-decision numbers a scheduler or capacity planner reads off, each independent of
the others. `dynamic_batching_priority(wait_time, sequence_length, sla_deadline)` is
`(wait_time / sequence_length) × (1 / sla_deadline)` — at `wait_time=200`, `sequence_length=100`,
`sla_deadline=50` (ms) that is `2.0 × 0.02 = 0.04` — except when `sla_deadline <= 0` (already past
its deadline) or `sequence_length <= 0`, in which case it returns the raw `wait_time` unmultiplied
rather than dividing by (or by the reciprocal of) zero.

`continuous_batching_capacity(gpu_memory_bytes, kv_cache_per_token_bytes, model_weights_bytes)` is
`(gpu_memory - model_weights) / kv_cache_per_token`. At `gpu_memory_bytes=80e9` (an 80GB
accelerator), `model_weights_bytes=14e9` (a 14GB model), `kv_cache_per_token_bytes=1e5` (100KB per
token), capacity comes out to `660000.0` tokens of concurrent KV-cache headroom.

`prefill_time_estimate` and `decode_time_per_token` both use the same FLOP model — `2 × n_layers ×
d_model² × 4` per token (the constant 4 stands in for attention + FFN's four big matmuls) — scaled
by `n_tokens` for prefill and left per-token for decode:

```python
# n_layers=28, d_model=1024 (Qwen3-0.6B-Base's real shape), flops_per_second=1e12 (1 TFLOP/s)
runtime.execute("inference_engine", "prefill_time_estimate", [512.0, 28.0, 1024.0, 1e12])["result"]
# 120.259084288 — ms to prefill a 512-token prompt at that assumed throughput

runtime.execute("inference_engine", "decode_time_per_token", [28.0, 1024.0, 1e12])["result"]
# 0.234881024 — ms per generated token, i.e. ~4257.5 tok/s theoretical peak at 1 TFLOP/s
```

`latency_percentile_estimate(mean_latency, std_latency, percentile)` computes `z = -log(1 -
percentile) × 1.2816` and returns `mean + z × std` for `0 < percentile < 1`; the source's own
comment marks this `# approximation` — the `z` it computes is not the standard normal inverse CDF
(`z_{0.99} ≈ 2.326`), it grows from a log-based tail heuristic instead (`z_{0.99} ≈ 5.902` here), so
a mean=100ms/std=20ms server reports an estimated p99 of `218.04` ms under this formula — useful as
a fast, deterministic proxy, not a substitute for a real percentile computed from sampled latencies.
`percentile <= 0` returns the bare mean; `percentile >= 1` returns `mean + 5 × std`, both without
touching the log.

## Cost and latency accounting

`inference_cost_latency` is the arithmetic layer for turning token counts, throughput, and pricing
into dollars and milliseconds. `kv_cache_bytes(batch_size, sequence_length, num_layers, hidden_size,
bytes_per_element)` is `batch × seq × layers × hidden × bytes_per_element × 2` (the trailing `×2`
accounts for both K and V):

```python
# batch=1, sequence_length=2048, num_layers=28, hidden_size=1024, bytes_per_element=2 (fp16)
runtime.execute("inference_cost_latency", "kv_cache_bytes", [1, 2048, 28, 1024, 2])["result"]
# 234881024.0 bytes == exactly 224.0 MiB
```

`hidden_size` here is whatever the caller passes for the KV projection width — the formula does not
distinguish a model's full `d_model` from a smaller grouped-query-attention KV width, so a caller
modeling a GQA checkpoint must pass the actual K/V dimension (`num_kv_heads × head_dim`), not
`d_model`, or the estimate overcounts.

`attention_flops(batch_size, sequence_length, num_layers, num_heads, head_dim)` is `4 × batch ×
layers × heads × seq² × head_dim` — quadratic in sequence length, the standard closed-form count for
dense (non-flash) self-attention's QKᵀ and softmax·V matmuls:

```python
# batch=1, sequence_length=2048, num_layers=28, num_heads=16, head_dim=64
runtime.execute("inference_cost_latency", "attention_flops", [1, 2048, 28, 16, 64])["result"]
# 481036337152.0 -- 481.04 GFLOP for one forward pass at this shape
```

`prompt_token_estimate`/`completion_token_estimate` are the same ceiling-division helper
(`ceil(char_count / chars_per_token)`) under two names — `prompt_token_estimate(1001, 4.0)` returns
`251` (`1001 / 4.0 = 250.25`, rounded up), not `250`. `request_cost_estimate` combines a completed
token count with per-1k pricing:

```python
runtime.execute("inference_cost_latency", "request_cost_estimate",
                [1000, 500, 0.5, 1.5])["result"]
# 1.25 -- (1000 * 0.5 + 500 * 1.5) / 1000

runtime.execute("inference_cost_latency", "speculative_decode_gain_estimate",
                [0.7, 4, 50.0, 200.0])["result"]
# 1.2727272727272725 -- 70% draft-token acceptance, 4 draft tokens/step,
# base model at 50 tok/s, draft model at 200 tok/s: a real net speedup, not just the raw 4x draft rate
```

`speculative_decode_gain_estimate` compares two durations for producing the same accepted tokens:
`accepted = acceptance_rate × draft_tokens_per_step` tokens would have cost `accepted /
base_decode_tps` seconds generated one at a time; generating them speculatively costs
`draft_tokens_per_step / draft_decode_tps` (running the draft model once) plus `(draft_tokens_per_step
- accepted) / base_decode_tps` (the target model re-verifying, which also covers the rejected
tokens' wasted draft work). The ratio of the first to the second is the reported gain — `1.27x`
above, well under the `4x` a caller might naively expect from "the draft model is 4x faster," because
acceptance is well below 100% and the target model still re-verifies every draft token regardless of
whether it accepts it.

{% hint style="info" %}
**`quantized_inference_speedup`'s `fp32_flops` parameter is declared but never read.** The function
signature is `quantized_inference_speedup(fp32_flops, int8_throughput_ratio,
memory_bandwidth_ratio)` and the docstring frames it as "speedup over FP32," but the body is exactly
`min(int8_throughput_ratio, memory_bandwidth_ratio)` — `fp32_flops` does not appear anywhere in the
function. Passing any value for it, including `0.0` or a negative number, changes nothing about the
result; the function is really "the tighter of two already-relative ratios," independent of the raw
FP32 throughput a caller happens to supply.
{% endhint %}

## Inference security: heuristic risk scores

Every function in `inference_security` takes signals a caller is assumed to already have — a
classifier logit, a token count, a 0/1 gate result — and combines them with one fixed formula; none
of them run a classifier or inspect text themselves. Two different concerns share the identical
"AND via multiplication" shape: `tool_call_validation_score(arg_type_match, arg_range_valid,
permission_granted, rate_limit_ok)` and `sandboxed_exec_trust_score(tool_signature_valid,
execution_timeout_ok, resource_limit_ok, output_schema_valid)` both multiply four inputs together,
so all four must be `1.0` for the product to be `1.0` and any single `0.0` gate zeroes the whole
score. Neither function validates that its inputs are actually binary — passing `0.5` for a
"partially granted" permission silently produces a fractional score (`0.5` instead of a hard reject),
rather than refusing a non-boolean input.

```python
runtime.execute("inference_security", "tool_call_validation_score", [1.0, 1.0, 0.0, 1.0])["result"]
# 0.0 -- permission_granted=0 zeroes the whole gate regardless of the other three
```

`prompt_injection_score(instruction_override_tokens, system_prompt_distance,
role_switch_probability)` is `override_tokens × role_switch_prob / (system_prompt_distance + 1)` —
the `+ 1` keeps a zero-distance input (text identical to the system prompt) from dividing by zero:

```python
runtime.execute("inference_security", "prompt_injection_score", [3.0, 0.2, 0.8])["result"]
# 2.0000000000000004 -- 3 override-looking tokens, a role-switch probability of 0.8,
# and a small (0.2) semantic distance from the system prompt
```

`rate_limit_violation_score(requests_in_window, rate_limit, window_fraction_elapsed)` projects the
in-window request count forward to a full window (`requests / (window_fraction_elapsed + 1e-6)`,
the `1e-6` guarding a window that just opened) and reports how far over `rate_limit` that projection
sits:

```python
runtime.execute("inference_security", "rate_limit_violation_score", [80.0, 100.0, 0.5])["result"]
# 0.5999968000063999 -- 80 requests at the halfway point of the window projects to ~160 by
# the end of it, 60% over a limit of 100

runtime.execute("inference_security", "rate_limit_violation_score", [80.0, 0.0, 0.5])["result"]
# 1.0 -- rate_limit <= 0 (no limit configured) is treated as an immediate, maximal violation,
# a fail-closed default rather than a divide-by-zero or a silent "no limit means no violation"
```

`adversarial_input_score(input_perplexity, baseline_perplexity, perturbation_budget)` turns a
perplexity spike into a suspicion score: `(input_perplexity / baseline_perplexity - 1) × (1 +
perturbation_budget)`. An input three times as perplexing as the domain baseline, evaluated against
a known epsilon budget of `0.1`, scores `2.2`:

```python
runtime.execute("inference_security", "adversarial_input_score", [45.0, 15.0, 0.1])["result"]
# 2.2
```

`token_level_safety_score`, `output_toxicity_estimate`, `pii_token_risk`, `data_leakage_risk_score`,
and `jailbreak_pattern_score` follow the same pattern — a fixed closed-form combination of
caller-supplied signals, worked by hand against the source in the Verification section below.

## Edge-case and refusal behavior

* **Every division guard returns a defined sentinel, never lets a `NaN`/`inf` through.**
  `kv_cache_hit_ratio`, `throughput_tokens_per_sec`, `speculative_decode_accept_rate`,
  `continuous_batching_capacity`, `prefill_time_estimate`/`decode_time_per_token`,
  `prefill_latency_estimate`/`decode_latency_estimate`, `batch_efficiency_estimate`,
  `queue_delay_estimate`, `speculative_decode_gain_estimate`, and `adversarial_input_score` all check
  their denominator (or a proxy for it) against zero first and return `0.0` rather than dividing.
* **A "no limit configured" state is treated as a violation, not silently permitted.**
  `rate_limit_violation_score` returns `1.0` — maximal severity — the moment `rate_limit <= 0`,
  rather than treating an unset limit as "nothing to violate."
* **`inference_cost_latency`'s integer inputs are clamped, never allowed negative.** Every `Int`
  parameter across the module (`batch_size`, `sequence_length`, token counts, and so on) is passed
  through `_clamp_non_negative_int`/`_clamp_non_negative_float` before use, so a caller's negative
  count is silently floored to zero rather than propagating a negative FLOP count or byte size.
* **`batch_efficiency_estimate` clamps its ratio at `1.0`.** A batch larger than the declared
  saturation size (`batch_size=128, saturation_batch_size=64`) reports `1.0`, not `2.0` — the
  function communicates "at or past saturation," not how far past.

## Relationship to the LLM decode kernels

This family does not overlap in function names or purpose with [LLM inference
kernels](llm-inference-kernels.md) (`llmk`) or [Metal LLM decode](qwen3-metal-decode.md)
(`metaldispatch`). Those two families compute the actual arithmetic of a decode step — real
KV-cache buffers, real matrix-vector products, real greedy argmax over real logits — verified by
running that arithmetic and checking it against a reference implementation. `inference_engine` and
`inference_cost_latency` estimate the *cost* of running that arithmetic (how many milliseconds, how
many dollars, how much KV memory) from closed-form models a caller can evaluate before ever running
a decode step, and neither imports nor calls into `llmk` or `metaldispatch`. `prefill_time_estimate`
and `attention_flops`, for instance, model the same prefill phase `llmk`/`metaldispatch` actually
execute, but as an independent analytic guess rather than a measurement of that execution. Likewise,
`inference_security`'s risk scores operate on signals (logits, token counts, gate results) that would
typically come from running a classifier alongside a real decode loop — this module is the scoring
formula, not the classifier or the loop itself.

## Verification

All four of this page's test files — `mojo/tests/libs/test_multimodal.mojo`,
`test_inference_engine.mojo`, `test_inference_cost_latency.mojo`, and `test_inference_security.mojo`
— are auto-generated coverage smoke tests: each calls every public function once with a shared
fixture (mostly `0.5` for `Float64` arguments) and asserts only that the result is finite
(`not isnan(x) and not isinf(x)`), printing a pass/fail count. None of the four pin a specific
numeric output, so the worked examples throughout
this page were computed independently, by hand, from the real formulas in `mojo/engine/multimodal.mojo`,
`inference_engine.mojo`, `inference_cost_latency.mojo`, and `inference_security.mojo` — every number
shown can be reproduced by re-running the same arithmetic, and several were deliberately chosen
against real-world reference points (ViT-B/16's 196 patches, 1000 Hz ≈ 1000 mel, Qwen3-0.6B-Base's
28-layer/1024-hidden shape) as an independent cross-check that the formula matches its documented
intent, not just that it runs.

**Next:** [LLM inference kernels](llm-inference-kernels.md) for the real decode-step arithmetic this
family estimates the cost of, or the [Runtime library catalog](runtime-library-catalog.md) for every
module and function.
