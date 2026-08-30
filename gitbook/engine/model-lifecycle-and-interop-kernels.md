---
icon: boxes-stacked
description: ABI version and layout arithmetic, safetensors/GGUF/ONNX/HuggingFace interop math, data/tensor/pipeline parallelism formulas, and checkpoint/quantization sizing, across four independent Float64 kernel modules.
---

# Model lifecycle and interop kernels

Four small modules for the arithmetic around a model artifact rather than the arithmetic inside
it: the layout and version-compatibility contract a checkpoint's bytes have to satisfy
(`model_abi`), the format-specific math for reading a model someone else produced
(`model_interop`, covering safetensors, GGUF, ONNX and HuggingFace configs), the communication and
memory formulas that describe splitting one model across many devices (`model_parallel`), and the
sizing/compression math around saving and shrinking a checkpoint (`model_serialization`). Every
function in all four modules takes and returns plain `Float64` — there is no tensor, buffer, or
struct type anywhere in this family, and no shared status-code vocabulary either: a degenerate
input gets a clamped or defaulted number back, never an error code.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("model_abi", "attention_head_dim", [4096.0, 32.0])["result"]
# 128.0 -- Llama-2-7B: 4096 hidden dim / 32 heads = 128 per head

runtime.execute("model_abi", "ffn_dim_from_model_dim", [4096.0, 8.0 / 3.0, 256.0])["result"]
# 11008.0 -- matches Llama-2-7B's real intermediate_size (4096 * 8/3, rounded up to a 256 multiple)
```

## The modules

| Module | What it does |
| --- | --- |
| `model_abi` | tensor-layout strides, dtype byte widths, NCHW/NHWC activation indexing, weight-shard byte offsets, and ABI version compatibility between a saved model and the running kernel |
| `model_interop` | safetensors tensor alignment, GGUF metadata sizing, ONNX per-op FLOPs, HuggingFace config/rope fields, checkpoint-version and tokenizer-vocab compatibility scores, and a perplexity helper for model-card quality proxies |
| `model_parallel` | data/tensor/pipeline parallelism math — gradient averaging, ring all-reduce volume, pipeline bubble fraction, layer-to-stage assignment, ZeRO-3 shard sizing, and comm/compute overlap ratios |
| `model_serialization` | checkpoint byte-size estimates, quantization bit widths, LoRA adapter parameter counts, pruning speedup, weight-sharing/sparsity ratios, and a rolling version-hash accumulator |

## Same division, two provenances

`model_abi.attention_head_dim(model_dim, n_heads)` and `model_interop.hf_config_head_dim(hidden_size,
num_attention_heads)` are the identical formula — `model_dim / n_heads`, falling back to `model_dim`
itself when `n_heads <= 0` — duplicated across the two modules rather than shared. That is
deliberate: `model_abi` speaks the runtime's own config fields, `model_interop` speaks a
HuggingFace `config.json`'s field names. The module boundary tracks which document produced the
number, not a different piece of arithmetic. `model_abi.model_config_head_count(model_dim,
head_dim)` is the same division run the other way (`model_dim / head_dim`, defaulting to `1.0`
when `head_dim <= 0`), so `attention_head_dim` and `model_config_head_count` invert each other:
`attention_head_dim(4096, 32) == 128` and `model_config_head_count(4096, 128) == 32`.

## Two RoPE-scaling formulas that are not interchangeable

Both modules have a function for stretching RoPE's base theta to a longer context, and they compute
genuinely different things. `model_abi.rope_theta_scale(base_theta, original_context,
target_context)` squares the context ratio — `base_theta * (target/original)^2` — despite its own
docstring citing the full NTK-aware exponent `dim / (dim - 2)`; the function never receives a `dim`
argument at all, so what actually ships is the fixed-quadratic approximation, not the per-dimension
NTK formula. `model_interop.hf_rope_theta_scale(base_theta, rope_scaling_factor)` is a flat multiply
by whatever factor a HuggingFace `rope_scaling` config supplies — no context-length ratio involved.
Doubling context from 4096 to 8192 and passing an equivalent factor of `2.0` to the other function
gives different answers:

```python
runtime.execute("model_abi", "rope_theta_scale", [10000.0, 4096.0, 8192.0])["result"]
# 40000.0 -- base * (8192/4096)^2 = base * 4

runtime.execute("model_interop", "hf_rope_theta_scale", [10000.0, 2.0])["result"]
# 20000.0 -- base * factor, no squaring
```

A caller who assumes these two are the same operation under different names will scale theta by 2x
too much or too little, depending on which one they meant to call.

## Worked examples — `model_abi`

`ffn_dim_from_model_dim` rounds the raw FFN size up to the next multiple of `round_to` — always the
*next* one, even when the raw value already lands exactly on a multiple:

```python
runtime.execute("model_abi", "ffn_dim_from_model_dim", [4096.0, 8.0 / 3.0, 256.0])["result"]
# 11008.0 -- Llama-2-7B's real intermediate_size

runtime.execute("model_abi", "ffn_dim_from_model_dim", [4096.0, 4.0, 256.0])["result"]
# 16640.0, not 16384.0 -- 4096*4 = 16384 is already an exact multiple of 256,
# but Int64(raw/round_to) + 1 always advances to the following multiple
```

`activation_layout_index` gives a different flat offset for the identical logical coordinate
depending on the layout flag — the entire reason the function exists:

```python
runtime.execute("model_abi", "activation_layout_index",
                [0.0, 2.0, 1.0, 3.0, 4.0, 5.0, 6.0, 0.0])["result"]
# 69.0 -- NCHW: n=0, c=2, h=1, w=3 over sizes c=4, h=5, w=6

runtime.execute("model_abi", "activation_layout_index",
                [0.0, 2.0, 1.0, 3.0, 4.0, 5.0, 6.0, 1.0])["result"]
# 38.0 -- same (n, c, h, w), NHWC instead of NCHW
```

Indexing a NCHW-trained activation buffer with the NHWC formula (or vice versa) does not error —
every index it produces is still in range, it just silently points at the wrong element.
`abi_version_compatible` turns a version-diff comparison into the same yes/no shape every guard in
this family uses:

```python
runtime.execute("model_abi", "abi_version_compatible", [1.0, 1.2, 0.5])["result"]
# 1.0 -- |1.2 - 1.0| = 0.2, under the 0.5 breaking threshold

runtime.execute("model_abi", "abi_version_compatible", [1.0, 2.0, 0.5])["result"]
# 0.0 -- |2.0 - 1.0| = 1.0, at or past the threshold
```

## Worked examples — `model_interop`

`safetensors_tensor_offset` pads a running byte offset up to the next alignment boundary, matching
the real safetensors format's 8-byte tensor alignment — and is a no-op when the offset is already
aligned:

```python
runtime.execute("model_interop", "safetensors_tensor_offset", [1000000.0, 8.0])["result"]
# 1000000.0 -- already a multiple of 8, no padding added

runtime.execute("model_interop", "safetensors_tensor_offset", [1000001.0, 8.0])["result"]
# 1000008.0 -- padded up by 7 bytes to the next 8-byte boundary
```

`onnx_node_flops` reproduces the standard `2·M·N·K` FLOP count for a matmul node:

```python
runtime.execute("model_interop", "onnx_node_flops", [1.0, 1.0, 4096.0, 4096.0, 4096.0])["result"]
# 137438953472.0 -- 2 * 4096^3, a single 4096x4096x4096 matmul, ~137.4 GFLOPs
```

`gguf_kv_metadata_size`'s own docstring documents the GGUF string encoding as `8 + len` (an 8-byte
length prefix plus the character bytes), but the code it ships computes `base + 8.0 * value_count`
— multiplying, not adding the fixed 8-byte prefix once. For a 21-byte key (`"general.architecture"`)
holding a 5-character string value, the true GGUF wire size is `25 + 8 + 5 = 38` bytes; the function
as written returns:

```python
runtime.execute("model_interop", "gguf_kv_metadata_size", [21.0, 2.0, 5.0])["result"]
# 65.0 -- (21 + 4) + 8*5, not the 38 bytes the function's own comment describes
```

Anything estimating real GGUF file sizes from this function's string branch will overcount; the
`int32`/`float32`/`bool` branches (`value_type` 0, 1, 3) match their documented per-value byte costs
exactly. `checkpoint_version_compat` decays smoothly rather than being a hard yes/no like
`abi_version_compatible`:

```python
runtime.execute("model_interop", "checkpoint_version_compat", [3.0, 3.0])["result"]  # 1.0 -- exact match
runtime.execute("model_interop", "checkpoint_version_compat", [3.0, 2.0])["result"]  # 0.5 -- 1/(1+1)
runtime.execute("model_interop", "checkpoint_version_compat", [3.0, 1.0])["result"]  # 0.3333333333333333 -- 1/(1+2)
```

`tokenizer_vocab_overlap` is a plain Jaccard index over vocab sizes and a shared-token count — a
Llama tokenizer (32,000 tokens) against a GPT-2 tokenizer (50,257 tokens) sharing a rough 5,000
tokens comes back low, quantifying why weights rarely port across tokenizer families without a
remap:

```python
runtime.execute("model_interop", "tokenizer_vocab_overlap", [32000.0, 50257.0, 5000.0])["result"]
# 0.06471905458405064
```

`model_card_perplexity` inverts the standard cross-entropy-to-perplexity relationship
(`exp(-mean log-likelihood)`); a mean log-likelihood of exactly `-ln(10)` per token comes back as a
perplexity of exactly 10:

```python
runtime.execute("model_interop", "model_card_perplexity", [-2302.585092994046, 1000.0])["result"]
# 10.000000000000007
```

## Worked examples — `model_parallel`

`tensor_parallel_split_dim` and `zero_stage3_param_bytes` are both a plain division by a device
count — one for a weight dimension, the other for parameter bytes:

```python
runtime.execute("model_parallel", "tensor_parallel_split_dim", [4096.0, 8.0])["result"]
# 512.0 -- 4096-wide projection split 8 ways under tensor parallelism

runtime.execute("model_parallel", "zero_stage3_param_bytes", [14000000000.0, 8.0])["result"]
# 1750000000.0 -- a 7B-parameter model in bf16 (14 GB) sharded 8 ways under ZeRO-3, 1.75 GB/device
```

`pipeline_bubble_fraction` shows why microbatch count matters more than stage count alone — the same
4 pipeline stages produce a very different bubble depending on how many microbatches fill them:

```python
runtime.execute("model_parallel", "pipeline_bubble_fraction", [4.0, 32.0])["result"]
# 0.08571428571428572 -- (4-1)/(32+4-1), ~8.6% bubble with 32 microbatches

runtime.execute("model_parallel", "pipeline_bubble_fraction", [4.0, 4.0])["result"]
# 0.42857142857142855 -- same 4 stages, only 4 microbatches, ~42.9% bubble
```

`gradient_all_reduce_bytes` and `communication_computation_ratio` chain together: the first gives a
ring all-reduce's communication volume, the second checks whether that volume is small enough to
hide behind compute.

```python
grad_bytes = runtime.execute("model_parallel", "gradient_all_reduce_bytes",
                             [7000000000.0, 2.0, 8.0])["result"]
grad_bytes
# 24500000000.0 -- ~24.5 GB per all-reduce: a 7B-parameter bf16 gradient, 8 workers, ring topology

runtime.execute("model_parallel", "communication_computation_ratio",
                [grad_bytes, 200.0, 500.0])["result"]
# 0.245 -- 122.5ms of comm time against a 500ms compute window: comm fits, overlap is feasible
```

`pipeline_stage_assignment` splits 32 layers evenly across 4 stages, and the boundary layers land
exactly where `floor(layer_id * n_stages / total_layers)` says they should:

```python
for layer_id in [0.0, 7.0, 8.0, 15.0, 16.0, 31.0]:
    runtime.execute("model_parallel", "pipeline_stage_assignment", [layer_id, 32.0, 4.0])["result"]
# 0.0, 0.0, 1.0, 1.0, 2.0, 3.0 -- layer 8 is the first layer of stage 1, layer 16 the first of stage 2
```

`ddp_sync_overhead` clamps at `1.0` rather than reporting an overhead above 100%, even when the
inputs describe an impossible measurement (gradient sync time exceeding the whole step it is part
of):

```python
runtime.execute("model_parallel", "ddp_sync_overhead", [122.5, 500.0])["result"]  # 0.245
runtime.execute("model_parallel", "ddp_sync_overhead", [600.0, 500.0])["result"]  # 1.0, clamped
```

The clamp hides a measurement error rather than surfacing it — a `600ms` sync inside a `500ms` step
is a bad input, not a real 120% overhead, and the function has no way to say so.

## Worked examples — `model_serialization`

`weight_quantization_bits` is a staircase onto standard hardware widths, not a continuous function —
several input precisions collapse onto the same bucket, and there is no 3-bit or 5-through-7-bit
bucket at all:

```python
for p in [1.0, 2.0, 3.0, 4.0, 5.0, 8.0, 9.0, 16.0, 17.0]:
    runtime.execute("model_serialization", "weight_quantization_bits", [p])["result"]
# 1.0, 2.0, 4.0, 4.0, 8.0, 8.0, 16.0, 16.0, 32.0
# -- precision 3 rounds up to the 4-bit bucket; 5 jumps straight to 8-bit
```

`checkpoint_size_estimate` matches the well-known "weights, or weights times three for Adam" rule of
thumb:

```python
runtime.execute("model_serialization", "checkpoint_size_estimate",
                [7000000000.0, 16.0, 0.0])["result"]
# 14000000000.0 -- a 7B-parameter model in bf16, weights only: 14 GB

runtime.execute("model_serialization", "checkpoint_size_estimate",
                [7000000000.0, 16.0, 1.0])["result"]
# 42000000000.0 -- same model with Adam optimizer state included: 3x, 42 GB
```

`lora_parameter_count` is where the efficiency argument for LoRA becomes a concrete number: a
rank-8 adapter over 4 target modules on a 4096-wide model is a tiny fraction of the 7B base model it
adapts.

```python
runtime.execute("model_serialization", "lora_parameter_count", [4096.0, 8.0, 4.0])["result"]
# 262144.0 -- 2 * 4096 * 8 * 4; roughly 0.0037% of a 7B-parameter base model
```

`pruning_sparsity_speedup` scales the ideal `1/(1-sparsity)` memory-bound speedup by how much of the
workload is actually memory-bound — the same sparsity level gives a much smaller realized speedup
than the ideal figure alone would suggest:

```python
runtime.execute("model_serialization", "pruning_sparsity_speedup", [0.5, 0.8])["result"]
# 1.7999968000064 -- 50% sparsity, 80% memory-bound workload
runtime.execute("model_serialization", "pruning_sparsity_speedup", [0.9, 0.8])["result"]
# 8.199920000799994 -- 90% sparsity, same 80% memory-bound fraction
```

`version_hash_component` truncates a weight value to three decimal places (`Int64(param_value *
1000.0)`) before folding it into a rolling-hash accumulator step — two weights differing only past
the third decimal place contribute an identical component:

```python
runtime.execute("model_serialization", "version_hash_component", [0.123456, 5.0, 31.0])["result"]
# 278.0 -- index*prime + Int64(0.123456*1000) = 5*31 + 123
```

## No status vocabulary, no structs

Unlike `attnk`, `tensorx`, or `llmk`, none of these four modules define a struct or a shared
status-code range — the runtime contract lists zero structs for all four (`model_abi`,
`model_interop`, `model_parallel`, `model_serialization` each report `"structs": []`). Every
function is a bare `Float64`-in/`Float64`-out arithmetic helper, and every guard against a
degenerate input (`world_size <= 0`, `total_layers <= 0`, `weight_norm <= 0`, an unrecognized
`op_type` or `value_type` code) returns a plain defaulted or clamped number rather than an error
sentinel. A caller that wants to detect "this input was nonsensical" has to notice the fallback
value itself — there is no `TX_ERR_*`-style code anywhere in this family to check instead.

## A unit mismatch worth watching

`model_abi.dtype_byte_width` returns **bytes** per element (fp16 → `2.0`); `model_serialization
.checkpoint_size_estimate` expects `dtype_bits` in **bits** (fp16 → `16.0`). Feeding one function's
output straight into the other without multiplying by 8 silently understates a checkpoint size by
8x — there is nothing in either signature that stops a `Float64` meant as bytes from being accepted
as bits.

## Distinct from `serialization_io`

[Bit-exact weight serialization](ml-serialization.md) documents `serialization_io`, a completely
different module: it round-trips named `Float64` arrays to a versioned string with bit-exact
fidelity, for the classical-stats namespace's own weight persistence. It shares zero functions with
`model_serialization` — `weights_to_string`, `weights_from_string`, and `string_checksum` are the
whole of its public API. `model_serialization` never serializes an actual weight value; it estimates
byte sizes, parameter counts, and compression ratios *about* a model's weights (`checkpoint_size_estimate`,
`lora_parameter_count`, `weight_sharing_ratio`) without ever writing one out. The "serialization" in
each name refers to a different problem: one is a wire format, the other is a sizing calculator.

## Verification

All four `mojo/tests/libs/test_model_*.mojo` files behind this page
(`test_model_abi.mojo`, `test_model_interop.mojo`, `test_model_parallel.mojo`,
`test_model_serialization.mojo`) are auto-generated coverage smoke tests: each calls every function
in its module exactly once, with every argument fixed at `0.5`, and checks only that the result is
finite — none pin a specific numeric output, and none exercise the multi-branch behavior (dtype
codes, `op_type`/`value_type` dispatch, layout flags, clamping) that the worked examples above
depend on. Every number in this page was hand-traced against the real formulas in
`mojo/engine/model_abi.mojo`, `model_interop.mojo`, `model_parallel.mojo`, and
`model_serialization.mojo`, and is reproducible by re-running the same arithmetic — including the
`gguf_kv_metadata_size` and `ffn_dim_from_model_dim` results that diverge from what each function's
own docstring describes.

**Next:** see how a checkpoint's derived facts (including this family's own head-dim and RoPE
fields) gate real model support in the [model support matrix](model-support-matrix.md), or how a
loaded checkpoint's tensors actually run a decode step in [LLM inference kernels](llm-inference-kernels.md).
