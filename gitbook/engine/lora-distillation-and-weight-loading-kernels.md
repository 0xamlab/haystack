---
icon: puzzle-piece
description: Per-element LoRA/DoRA/prefix/prompt adapter math, sharded and quantized checkpoint-loading arithmetic, and classical distillation-column design equations (not neural-network knowledge distillation).
---

# Adapters, checkpoint loading, and distillation columns

Three small modules for the arithmetic around a trained model's weights rather than the weights
themselves: `lora_adapters` is the per-element math behind parameter-efficient fine-tuning — LoRA,
QLoRA, DoRA, prefix tuning, and prompt tuning all reduce to a handful of scalar formulas once you're
looking at one matrix element at a time. `weight_loader` is the bookkeeping arithmetic a checkpoint
loader needs before it can safely read a model off disk in pieces — shard byte offsets, safetensors
and GGUF header/block sizing, HuggingFace multi-file shard counts, lazy per-layer load ordering, and
a rolling checksum. `distillation` is exactly what its docstring says it is: distillation-column
design and vapor-liquid equilibrium — Fenske/Underwood/Gilliland stage counts, McCabe-Thiele
operating lines, Raoult's and Dalton's laws — a chemical/process-engineering module that shares a
name with, but has no relationship to, neural-network knowledge distillation (teacher-student
training). See the callout below.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# alpha=16, r=4 is a common LoRA config -> scaling = alpha/r
scaling = runtime.execute("lora_adapters", "adapter_scaling_factor", [16.0, 4.0])["result"]
scaling
# 4.0

runtime.execute("lora_adapters", "lora_forward", [1.0, 0.02, 0.5, scaling])["result"]
# 0.04 -- one BAx element: x * a_row * b_col * scaling
```

## The modules

| Module | What it does |
| --- | --- |
| `lora_adapters` | LoRA/QLoRA/DoRA low-rank adapter forward pass and gradients, prefix-tuning key augmentation, and soft prompt-tuning embedding selection — the per-element arithmetic behind parameter-efficient fine-tuning |
| `weight_loader` | sharded and quantized checkpoint-loading arithmetic — safetensors header size, GGUF quantized block size, HuggingFace shard counts, shard byte offsets, lazy per-layer load priority, checkpoint hashing, and base/adapter weight interpolation |
| `distillation` | distillation-column design and vapor-liquid equilibrium: relative volatility, Fenske minimum stages, Underwood minimum reflux, Gilliland actual stages, McCabe-Thiele operating lines, Raoult's/Dalton's laws, Murphree stage efficiency, and condenser heat duty |

{% hint style="warning" %}
**`distillation` is a distillation *column*, not knowledge distillation.** The module's own
docstring is unambiguous: `"""Distillation / Separation Engineering Library. Provides functions for
distillation column design, vapor-liquid equilibrium, and separation process calculations."""`
(`mojo/engine/distillation.mojo:1-5`). Every one of its eleven functions —
`relative_volatility`, `fenske_min_stages`, `min_reflux_underwood`, `gilliland_stages`,
`mccabe_thiele_operating_line_enriching/stripping`, `boiling_point_elevation`,
`raoults_law_partial_pressure`, `daltons_law_total_pressure`, `stage_efficiency`,
`heat_duty_condenser` — is chemical/process engineering. There is no teacher model, no student
model, no logit temperature, and no KL-divergence loss anywhere in this file. If you came here
looking for model compression via teacher-student training, it is not implemented under this name
anywhere in the runtime contract.
{% endhint %}

## Adapters: LoRA, QLoRA, DoRA, prefix and prompt tuning

Every function in `lora_adapters` operates on one matrix element (or one scalar hyperparameter) at
a time — there is no matrix type here, the same flat-arithmetic convention used across this
runtime. `adapter_scaling_factor(alpha, rank)` computes LoRA's `α/r` scaling; a config of
`alpha=16, r=4` (`r=4` is on the smaller end of typical LoRA ranks, `alpha=4·r` a common heuristic)
gives `scaling = 4.0`. `lora_forward(x, a_row, b_col, scaling)` then computes one term of the
low-rank update `Δy = (xAB) × scale`: with `x=1.0`, `a_row=0.02`, `b_col=0.5`, and that same
`scaling=4.0`, it returns `0.04`. `lora_merge_weight(base_weight, lora_a, lora_b, scaling)` folds
that same delta into a base weight for deployment — `base=0.30` plus the same `lora_b × lora_a ×
scaling = 0.5 × 0.02 × 4.0 = 0.04` gives a merged weight of `0.34`; the delta term is identical to
`lora_forward`'s output when `x=1`, which is exactly the relationship the two functions have by
construction (`lora_forward` computes one `BAx` term, `lora_merge_weight` computes the same `BA`
term added directly onto the base weight instead of multiplied through an activation).

`qlora_dequant_forward(quantized_weight, quant_scale, zero_point, lora_delta)` is QLoRA's
dequantize-then-adapt step: `(q − zp) × scale + lora_delta`. With an INT4-range quantized value
`q=5.0`, `zero_point=8.0` (the unsigned 4-bit midpoint), `scale=0.02`, and the LoRA delta of `0.04`
computed above, the dequantized base is `(5 − 8) × 0.02 = −0.06`, and the effective forward weight
is `−0.06 + 0.04 = −0.02` — the frozen 4-bit base and the trainable adapter are two independent
number lines added together only at the end.

`dora_magnitude_scale(weight_norm, lora_delta_norm, magnitude_param)` implements DoRA's
weight-decomposition: it returns `magnitude_param / weight_norm`, the scale applied to the
*direction* `(W₀+ΔW)/‖W₀+ΔW‖` to reconstruct the decomposed weight `W = m × direction`. DoRA
initializes `m` to the pretrained weight's own norm, so at initialization — before any adapter
update exists — `weight_norm == magnitude_param` and the function returns `1.0`
(`dora_magnitude_scale(4.0, 0.4, 4.0) == 1.0`): the decomposition is a no-op until training moves
`m` away from that starting point. `lora_delta_norm` is accepted for reference but does not enter
this particular scale computation.

`prefix_tuning_key_aug(original_key, prefix_key, prefix_len, seq_len)` blends a trainable prefix key
into the real key sequence proportional to how much of the augmented sequence the prefix occupies:
`original_key + prefix_key × prefix_len / (seq_len + prefix_len)`. Ten prefix tokens in front of a
40-token sequence (`prefix_len=10, seq_len=40`) with `original_key=1.0, prefix_key=0.5` gives
`1.0 + 0.5 × 10/50 = 1.1`. `prompt_tuning_embed(token_embed, soft_prompt_embed, position, n_soft_tokens)`
is a pure selector, not a blend: for `position < n_soft_tokens` it returns `soft_prompt_embed`
outright, otherwise the real `token_embed` — a soft-prompt token position never mixes with a real
token embedding, it replaces it entirely at the reserved leading positions.

`adapter_param_efficiency(lora_params, total_params)` is the trainable-fraction ratio,
`lora_params / total_params`; a LoRA config touching `4,194,304` (4M) parameters of a 7-billion
parameter model gives `0.000599...`, about `0.06%` — the number a parameter-efficiency claim in a
LoRA paper or README is actually reporting. It guards `total_params <= 0.0` by returning `1.0`
(worst case: assume every parameter is trainable rather than divide by zero).

## Loading a checkpoint without reading all of it first

`weight_loader`'s ten functions are the arithmetic a sharded, lazily-loaded checkpoint reader needs
*before* it touches the tensor bytes: where a shard starts, how big a header or a quantized block
is, how many shards a HuggingFace index should declare, and which layer to fetch next.

`shard_offset_bytes(shard_id, params_per_shard, dtype_bytes)` is `shard_id × params_per_shard ×
dtype_bytes`: shard `2` of a checkpoint carrying `500,000,000` bf16 parameters per shard
(`dtype_bytes=2.0`) starts at byte `2,000,000,000`. `hf_model_index_shards(total_params,
max_shard_bytes, dtype_bytes)` computes how many such shards a `model.safetensors.index.json` needs
via `ceil(total_bytes / max_shard_bytes)`: a 7B-parameter model in bf16 (`14,000,000,000` bytes)
against the common 5 GB shard cap (`max_shard_bytes=5,000,000,000.0`) needs `3` shards. It guards
`max_shard_bytes <= 0.0` by returning `1.0` rather than dividing by zero.

`gguf_quantized_block_size(n_bits, block_size)` reproduces the real GGUF block-quantization byte
layout the function's own docstring states — `Q4_0: 18 bytes per 32 elements; Q8_0: 34 bytes per
32` — as `ceil(n_bits × block_size / 8) + 2` (the `+2` is one fp16 scale per block). Both cited
constants check out against the published GGUF format independent of this docstring: 32 packed
4-bit values is `32 × 4 / 8 = 16` bytes of data plus a 2-byte fp16 scale = `18`; 32 packed 8-bit
values is `32` bytes plus the same 2-byte scale = `34`. `safetensors_header_size(n_tensors,
avg_tensor_name_bytes)` is a JSON-header size estimate, `n_tensors × (avg_name_bytes + 64)`; a
291-tensor checkpoint (one norm/proj/embedding tensor set for a mid-size transformer) with an
average 40-byte tensor name comes to `291 × 104 = 30,264` estimated header bytes.

`lazy_load_priority(layer_id, total_layers, current_inference_layer)` ranks which not-yet-loaded
layer to fetch next during streaming inference: for a layer still ahead of the current decode
position, priority is `total_layers / (layers_ahead + 1)` — layer 10 with the decoder currently at
layer 6 in a 32-layer model (`ahead=4`) scores `32/5 = 6.4`. For a layer the decode position has
already passed, priority collapses to `1 / (layers_behind + 1)` — layer 3 already passed at layer 6
(`behind=3`) scores `1/4 = 0.25`, far below any not-yet-needed upcoming layer, since re-fetching a
layer decode has already consumed is the lowest-value thing a lazy loader could spend bandwidth on.

`partial_load_coverage(loaded_params, total_params)` is `loaded_params / total_params`, clamped to
`0.0` when `total_params <= 0.0` rather than dividing by zero — `4.5B` of `7B` parameters resident
gives `0.643`, 64.3% loaded. `weight_diff_norm(weight_new, weight_old)` returns one element's
squared difference, `(new − old)²`; per its own docstring the caller sums this across every
parameter and takes the square root outside the kernel to get the full L2 norm of a weight change —
for three elements moving by `+0.02, +0.01, +0.02` the three squared terms sum to `0.0009`, whose
square root, `0.03`, is the vector's L2 norm. `weight_hash_verify(accumulated_hash, weight, prime)`
is a rolling polynomial checksum, `hash × prime + round(weight × 10000)`: starting from `hash=0.0`
with `prime=31.0`, a first weight `0.12345678` quantizes to `1235` and the hash becomes `1235.0`;
folding in a second weight `−0.05123456` (quantizing to `−511`) carries it to `1235×31 − 511 =
37,774.0` — a corrupted byte anywhere in the checkpoint changes every subsequent hash value, which
is the property a verification checksum needs.

`adapter_merge_ratio(base_weight, adapter_weight, alpha)` computes a linear interpolation,
`(1−α)×base + α×adapter` — at `alpha=1.0` it is pure adapter (`0.34` for the `base=0.30,
adapter=0.34` pair above), at `alpha=0.5` it is the midpoint (`0.32`). This is a *different*
operation from `lora_adapters.lora_merge_weight` above despite both being called "merge": that
function reconstructs a merged weight from a low-rank `B×A` decomposition and a scaling factor;
this one linearly blends two already-materialized full weight tensors (a base checkpoint and a
fully fine-tuned or already-merged adapter checkpoint) — closer to a model-soup interpolation than
a LoRA merge. `checkpoint_resume_step(checkpoint_path_hash, step_encoded)` is, in the current
source, an identity function on its second argument — it returns `step_encoded` unchanged and does
not use `checkpoint_path_hash` in the computation; the hash is accepted as a parameter but the
step-extraction logic the docstring describes ("extract training step from checkpoint metadata")
is not yet expressed as anything beyond passing the already-decoded step through.

`weight_loader` and [bit-exact weight serialization](ml-serialization.md)'s `serialization_io`
solve adjacent but distinct problems: `serialization_io` guarantees a `Float64` array round-trips
through a string bit-for-bit — the value-encoding layer. `weight_loader` never touches a value's
bits; it computes the layout arithmetic around real on-disk formats (safetensors, GGUF, HuggingFace
sharded indices) — where a shard starts, how big a header or a quantized block is, which shard
count a multi-file index should declare. Neither module depends on the other in the runtime
contract; a real checkpoint pipeline would use `weight_loader`'s math to plan *where* to read and
`serialization_io`'s format for *how* the resident values themselves are persisted.

## A distillation column, worked end to end

Following the classic textbook path — relative volatility, minimum stages, minimum reflux, actual
stages, operating lines — for an idealized benzene/toluene-style separation (`alpha=2.5`, a
representative relative volatility for that system in this composition range):

```python
alpha, xd, xb, xf = 2.5, 0.95, 0.05, 0.5

runtime.execute("distillation", "fenske_min_stages", [xd, xb, alpha])["result"]
# 6.426866226495531 -- minimum stages at total reflux

rmin = runtime.execute("distillation", "min_reflux_underwood", [alpha, xd, xf, 1.0])["result"]
rmin
# 1.25

r = runtime.execute("distillation", "actual_reflux", [rmin, 1.3])["result"]
r
# 1.625 -- 1.3x Rmin, inside the typical 1.2-1.5x design range the docstring calls out

runtime.execute("distillation", "gilliland_stages", [6.426866226495531, rmin, r])["result"]
# 11.531622151520981 -- actual stages via the Gilliland correlation
```

`relative_volatility(y1, x1) = (y/(1−y))/(x/(1−x))` guards both mole fractions to the open interval
`(0, 1)`, returning `0.0` outside it rather than a division blowup — `relative_volatility(0.8, 0.5)
== 4.0`. `fenske_min_stages` guards `alpha <= 1.0` (no separation is possible at or below unity
relative volatility) and both compositions outside `(0, 1)`, also returning `0.0`.
`min_reflux_underwood` guards `alpha` within `1e-15` of `1.0`, where its own denominator would
otherwise blow up. `gilliland_stages` clamps its intermediate ratio `(R−Rmin)/(R+1)` into `[0, 1]`
before raising it to a fractional power, so a caller passing `R < Rmin` (an infeasible design, more
separation demanded than the reflux can deliver) gets a defined answer rather than a domain error
from the fractional exponent.

`mccabe_thiele_operating_line_enriching(r, xd, x) = (R/(R+1))·x + xd/(R+1)`: with `r=2.0, xd=0.9` at
`x=0.5`, `y = 0.6333`. Its stripping-section counterpart takes a feed-quality ratio directly rather
than deriving it from `q`: with the same `r=2.0`, `xb=0.1`, `f_ratio=1.2`, at the same `x=0.5`, `y =
0.5267`. Both guard `R+1 == 0`, an unreachable operating point (reflux ratio `−1`), by returning
`0.0`. `stage_efficiency` (Murphree) is `(y_actual − y_in)/(y_eq − y_in) × 100`; an actual vapor
composition of `0.65` against an equilibrium value of `0.8` and an inlet of `0.5` scores `50%`
efficiency, guarding a near-zero denominator the same way the reflux and Fenske functions do.
`boiling_point_elevation`, `raoults_law_partial_pressure`, `daltons_law_total_pressure`, and
`heat_duty_condenser` are unguarded closed-form physical-chemistry relations —
`raoults_law_partial_pressure(0.4, 100.0) == 40.0`, `daltons_law_total_pressure(40.0, 60.0) ==
100.0`, and `heat_duty_condenser(100.0, 30000.0) == 3,000,000.0` (100 mol/hr vapor at 30 kJ/mol
latent heat is a 3 MJ/hr condenser duty).

## Verification

`mojo/tests/libs/test_lora_adapters.mojo`, `test_weight_loader.mojo`, and `test_distillation.mojo`
are all auto-generated smoke suites, not hand-verified numeric test files: each calls every public
function exactly once with a fixed input (`0.5` for every `Float64` argument, or another fixed
constant for a handful of functions) and asserts only that the result is finite
(`not isnan(x) and not isinf(x)`) — there are no pinned expected values to lift a worked example
from, and the header comment in each file says as much (`"auto-generated tests for <module>"`).

Every numeric result in this page was instead computed independently in plain Python from the
formulas as written in the real `.mojo` source (`mojo/engine/lora_adapters.mojo`,
`weight_loader.mojo`, `distillation.mojo`), not copied from any test assertion. Two of those
computed values check against an external, source-independent fact rather than only against
themselves: the GGUF `Q4_0`/`Q8_0` block sizes (`18`, `34` bytes) match the published GGUF
quantized-block byte layout (32 packed values plus one fp16 scale), and the Fenske/Underwood/
Gilliland/McCabe-Thiele chain above reproduces the standard textbook sequence for a binary
distillation design at the stated relative volatility and compositions.

**Next:** see the bit-exact byte-level counterpart to `weight_loader`'s layout arithmetic in
[bit-exact weight serialization](ml-serialization.md), or the checkpoint fact-checking a loaded
model is validated against in the [model support matrix](model-support-matrix.md).
