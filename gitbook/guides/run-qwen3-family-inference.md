---
icon: gauge-high
description: Run any supported Qwen3-family checkpoint on Apple Silicon through Algenta's model-agnostic SDK path — supported shapes, long context, and the quantized load cache.
---

# Run Qwen3-family models on Apple Silicon

By the end of this guide you will have installed Algenta, downloaded a Qwen3-family checkpoint of
your choice, and run real greedy inference through the model-agnostic Metal GPU kernel path —
one call, prompt token ids in, generated token ids out, on your own Apple Silicon machine.

This is the **model-agnostic** door onto the same race-verified kernels the
[Qwen3-0.6B-Base guide](run-qwen3-decode.md) uses: instead of one SDK function compiled for one
exact shape, `algenta.inference.decode()` accepts any model whose architecture the kernels support
and routes it to the model-agnostic entry point. Verified end to end on **Qwen3-0.6B-Base** and
**Qwen3-1.7B** with identical greedy output (first token matches an independent `transformers` CPU
reference on both).

## Requirements

* **Apple Silicon (M-series) Mac with Metal.** There is no CPU fallback and no support for other GPU vendors.
* **Python 3.14** — `pip install algenta` requires it.
* **A local Hugging Face checkpoint snapshot** (`config.json` + one or more `model*.safetensors`, single- or multi-shard). Downloaded by you, never by this call — for example `Qwen/Qwen3-0.6B-Base` or `Qwen/Qwen3-1.7B` (both Apache-2.0, ungated).
* **`numpy`**, to convert the checkpoint's published BF16 weights: `pip install "algenta[benchmark]"`.
* **A tokenizer for the checkpoint.** This path takes token ids in and token ids out — the examples below use `transformers`' `AutoTokenizer` against the same checkpoint directory.
* **A Metal-GPU build of the runtime worker.** The GPU worker binaries are produced by the repo's own build script (`scripts/build_mojo_binary.sh` with `MOJO_BUILD_METAL_GPU=1`); GPU packaging for the signed bundled runtime is on the roadmap.

## Supported models — and exactly what is refused

The kernels implement the **Qwen3 decoder family**: grouped-query attention with RMSNorm on Q/K,
tied embeddings, SiLU-gated FFN, RoPE, no attention bias. Any checkpoint matching those structural
invariants and the alignment gates runs; anything else raises `UnsupportedArchitectureError` naming
the exact mismatch, from `config.json` alone, before any conversion or GPU work:

| Gate | Requirement |
| --- | --- |
| GQA | `num_attention_heads % num_key_value_heads == 0` |
| Tile alignment | `hidden_size`, `intermediate_size`, and `num_attention_heads * head_dim` each divisible by 32 |
| Embeddings | `tie_word_embeddings` true |
| Bias | no attention bias |

One build serves one **staging tier**: the decode kernels' shared-memory staging is compiled to the
model's own `stage_needed = max(hidden_size, num_attention_heads * head_dim, intermediate_size)`.
Qwen3-0.6B-Base (3072) and Qwen3-1.7B (6144) are the two tiers with ready worker builds — a worker
built for one tier refuses a model that needs the other, by name, rather than running it wrong.

## Limitations

* **Tokens in, tokens out.** There is no BPE tokenizer or detokenizer in this path yet — bring token ids (for example from `transformers.AutoTokenizer`). A native tokenizer is the next roadmap item.
* **Greedy decode only.** Every generated token is the argmax. No temperature, top-p/top-k, penalties, or seeds.
* **One call, start to finish.** One call prefills the prompt and decodes to `max_new_tokens` or end-of-text; there is no open session to step across calls.
* **Weights load per call — with a cache.** Each call loads the weights, but the first call on a converted checkpoint writes `weights_i8.cache` (the exact quantized device bytes, 8x smaller than the converted blob); later calls restore it and skip re-quantization entirely. See [The quantized load cache](#the-quantized-load-cache).

## Convert once, decode many times

`prepare_model_checkpoint()` reads the checkpoint's own `config.json` for the shape, handles single-
or multi-shard safetensors, pre-transposes the GEMM weights the kernels expect, and writes the flat
`manifest.json` + `weights.blob` pair the kernel reads. `decode()` converts for you when you omit
`converted_checkpoint_dir`; converting once and reusing is the intended shape.

```python
from algenta import MojoRuntime
from algenta.inference import decode, prepare_model_checkpoint

# 1. Convert once (multi-shard checkpoints handled automatically).
converted = prepare_model_checkpoint(
    checkpoint_dir="./qwen3-1.7b",
    prompt_token_ids=[785, 6722, 315, 9625, 374],  # "The capital of France is"
    out_dir="./qwen3-1.7b-converted",
)

# 2. Decode through the runtime (reuse the conversion on every later call).
runtime = MojoRuntime(mode="local")
result = decode(
    runtime,
    checkpoint_dir="./qwen3-1.7b",
    prompt_token_ids=[785, 6722, 315, 9625, 374],
    max_new_tokens=16,
    converted_checkpoint_dir=converted,
)
print(result.token_ids[result.n_prompt:])      # generated token ids
print(result.prefill_tokens_per_sec, result.decode_tokens_per_sec)
```

To tokenize a real prompt first:

```python
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("./qwen3-1.7b")
prompt_token_ids = tokenizer("The capital of France is")["input_ids"]
```

## Long context

The engine sizes its own context as `max(512, n_prompt + max_new_tokens)`, auto-raised whenever a
call needs more, up to a 65,536 safety ceiling — prompts and generations far past the historical 512
default just work. Verified: a 256-token prompt + 300 new tokens (556 total) and deep soaks of 2,048
new tokens on 0.6B / 1,024 on 1.7B, every token checked against the reference.

`max_ctx` on `decode()` is a **caller-side guard**, not an override: a value below
`n_prompt + max_new_tokens` is refused before any work happens; a larger value is accepted but
cannot change a one-shot run, because nothing inside a single call can consume context beyond what
the prompt + generation uses.

## The quantized load cache

The first `decode()` on a converted checkpoint writes `weights_i8.cache` next to the manifest — the
exact post-quantization device bytes (int8 weights + per-row scales, ~1 byte/param against the flat
blob's 8). Every later call on that checkpoint restores the cache instead of re-reading the full
blob and re-running quantization. Measured on M4 Max:

| Model | Converted blob | Cache | Cold call | Cached call |
| --- | --- | --- | --- | --- |
| Qwen3-0.6B-Base | 4.77 GB | 0.598 GB | 4.87 s | 1.57 s (3.10x) |
| Qwen3-1.7B | 13.76 GB | 1.724 GB | 10.98 s | 5.70 s (1.93x) |

Cached and cold calls produce **byte-identical greedy sequences** — the cache is the very bytes the
GPU kernels read. The validity gate is magic + dims + SHA-256 of `manifest.json` + exact length:
any mismatch falls back to the full path and rewrites a fresh cache. A cache written for one
checkpoint never passes another's gate.

## Refusals, by name

`decode()` never returns a plausible-looking wrong answer for a mismatch it can detect — it raises:

| Error | Meaning |
| --- | --- |
| `UnsupportedArchitectureError` | The checkpoint's architecture is outside the supported family/gates (message names every problem found). |
| `InferenceError("checkpoint_not_found")` | Missing `config.json`, safetensors shard, tensor, or converted pair. |
| `InferenceError("invalid_arguments")` | Empty/invalid prompt ids, `max_new_tokens < 1`, or `max_ctx` below the call's need. |
| `InferenceError("metaldispatch_...")` | The engine refused by status: no Metal device, GPU build absent, context past the ceiling, and so on — the status name is always the `code`. |

## Next steps

{% content-ref url="../benchmarks/llm-inference-overview.md" %}
[llm-inference-overview.md](../benchmarks/llm-inference-overview.md)
{% endcontent-ref %}

{% content-ref url="run-qwen3-decode.md" %}
[run-qwen3-decode.md](run-qwen3-decode.md)
{% endcontent-ref %}

{% content-ref url="../benchmarks/llm-prefill-throughput.md" %}
[llm-prefill-throughput.md](../benchmarks/llm-prefill-throughput.md)
{% endcontent-ref %}
