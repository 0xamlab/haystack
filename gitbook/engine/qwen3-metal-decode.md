---
icon: microchip
description: Greedy decode of Qwen3-0.6B-Base through the int8 Metal GPU kernel path — call surface, checkpoint preparation, refusals, verification.
---

# Qwen3 Metal decode

`metaldispatch.qwen3_decode` runs Qwen3-0.6B-Base end to end on Apple Silicon through the compiled
int8-weight Metal kernel path (`_MBQwen3I8AllSimd7`): prompt in, generated token ids out, one call.
One exact architecture and one hardware family, by construction — the kernels are compiled for this
shape. Measured throughput: [Decode throughput](../benchmarks/decode-throughput.md).

The model-agnostic door onto the same kernel family — any supported Qwen3-family shape, seeded
sampling, text in/text out — is `algenta.inference.decode`; see
[Run Qwen3-family models on Apple Silicon](../guides/run-qwen3-family-inference.md).

## Functions

| Function | What it does |
| --- | --- |
| `qwen3_i8_allsimd7_decode_flat(checkpoint_dir, max_new_tokens)` | Greedy-decodes the prompt already folded into the converted checkpoint's `manifest.json` through the GPU session (prefill, then per-token decode to the budget or end-of-text). Returns token ids, prefill/decode tok/s, and the per-token dispatch count. |
| `prepare_qwen3_checkpoint(checkpoint_dir, prompt_token_ids)` (SDK) | Converts a Hugging Face snapshot (`config.json` + `model.safetensors`) into the flat `manifest.json` + `weights.blob` pair the kernel reads, with the prompt folded in. |
| `qwen3_i8_allsimd7_decode(runtime, ...)` (SDK) | Python wrapper: converts when needed, calls the flat function through the bundled runtime, and maps engine statuses to named exceptions. |

```python
from algenta import MojoRuntime, qwen3_i8_allsimd7_decode

runtime = MojoRuntime(mode="local")
result = qwen3_i8_allsimd7_decode(
    runtime,
    checkpoint_dir="/path/to/Qwen3-0.6B-Base",   # your own downloaded HF snapshot
    prompt_token_ids=[785, 6722, 315, 9625, 374], # "The capital of France is"
    max_new_tokens=16,
)
result.token_ids                # prompt ids followed by generated ids
result.decode_tokens_per_sec
```

## Usage guidance

- **Checkpoint**: download the snapshot yourself (`huggingface_hub.snapshot_download` with
  `repo_id="Qwen/Qwen3-0.6B-Base"`); nothing here fetches from the network. Pass
  `converted_checkpoint_dir` after a one-time `prepare_qwen3_checkpoint()` to skip re-converting on
  repeated calls.
- **Tokens**: this path takes token ids. Tokenize with `algenta.load_tokenizer(checkpoint_dir)`
  (built in, no dependencies) or `transformers.AutoTokenizer` against the same directory.
- **One-shot shape**: one call opens the session, uploads weights, prefills, and decodes. There is
  no open/step/close surface; the weights load on every call.
- **Refusals are named, never silent**: a checkpoint of any other shape raises
  `UnsupportedCheckpointArchitectureError` naming every mismatched field before any GPU work; a
  worker built without `-D ALGENTA_GPU` returns `metaldispatch_shader_toolchain_absent`; a host
  without a Metal accelerator returns `metaldispatch_no_device`; missing files return
  `checkpoint_not_found`. A call that returns at all has generated tokens.

## Verification

- `prepare_qwen3_checkpoint` is checked byte-for-byte against the benchmark's own converter on a
  real checkpoint (`tests/test_qwen3_decode_checkpoint_conversion.py`).
- The GPU end-to-end path asserts the reference first token (374) and the reference continuation
  on the 256-token race prompt (`tests/test_inference_gpu_e2e.py`).
- Every decode step asserts its dispatch count against the generated budget; a mismatch is an
  error, not a result.

**Next:** the measured [decode throughput](../benchmarks/decode-throughput.md),
[batched decode](../benchmarks/batched-decode-throughput.md) for multi-request workloads, the
[model-agnostic guide](../guides/run-qwen3-family-inference.md), or the
[runtime library catalog](runtime-libraries.md) (same call over `POST /v1/libraries/execute`,
`module=metaldispatch.qwen3_decode`).
