---
icon: microchip
description: Greedy-decode Qwen3-0.6B-Base with a real Metal GPU kernel path from Python — one model shape, one hardware family, stated precisely so nothing here overclaims.
---

# Qwen3-0.6B-Base decode (Apple Silicon, Metal)

This is a narrow, real capability, not a general LLM-serving surface: greedy (argmax) decode for
**exactly one checkpoint shape — Qwen3-0.6B-Base** — on **Apple Silicon with Metal**, through a
compiled int8-weight GPU kernel path. See [Decode throughput](../benchmarks/decode-throughput.md)
for the measured result this kernel produces (ahead of installed mlx-lm and llama.cpp on this
checkpoint, every round of 14). This page is about calling it yourself, not about the race.

Everything runs inside the compiled runtime that ships with the SDK. There is nothing to start and
nothing to install separately beyond the checkpoint itself.

```python
from algenta import MojoRuntime, qwen3_i8_allsimd7_decode

runtime = MojoRuntime(mode="local")

result = qwen3_i8_allsimd7_decode(
    runtime,
    checkpoint_dir="/path/to/your/Qwen3-0.6B-Base",   # your own downloaded HF snapshot
    prompt_token_ids=[785, 6722, 315, 9625, 374],       # "The capital of France is"
    max_new_tokens=16,
)

result.token_ids                # [785, 6722, ..., 12095, 13, 576, ...]
result.decode_tokens_per_sec    # steady-state decode rate on this run
```

## What this refuses, and why it refuses rather than guesses

`_MBQwen3I8AllSimd7`'s kernels were compiled for one exact architecture. Running them against a
different shape would not raise a numeric error — it would silently produce the wrong answer, so
every mismatch is refused by name instead:

| Situation | What happens |
| --- | --- |
| A checkpoint that is not Qwen3-0.6B-Base's exact shape | `UnsupportedCheckpointArchitectureError`, naming every mismatched field, before any conversion or GPU work starts. |
| A worker binary built without `-D ALGENTA_GPU` | `Qwen3DecodeError` with code `metaldispatch_shader_toolchain_absent`. |
| A host with no Metal accelerator | `Qwen3DecodeError` with code `metaldispatch_no_device`. |
| `checkpoint_dir` missing `config.json` / `model.safetensors` | `Qwen3DecodeError` with code `checkpoint_not_found`. |

None of these return an empty result or a plausible-looking wrong answer. An empty `token_ids` is
never a valid response to a call that raised — if the call did not raise, generation happened.

## Getting a checkpoint onto disk

This function does not download anything — that stays your own, explicit, network-dependent step,
the same way it is for every other checkpoint this project's own benchmarks use:

```python
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="Qwen/Qwen3-0.6B-Base",
    local_dir="/path/to/your/Qwen3-0.6B-Base",
    allow_patterns=["*.json", "*.safetensors", "tokenizer*", "vocab*", "merges*"],
)
```

`qwen3_i8_allsimd7_decode()` reads that directory directly — pass wherever you put it, not a fixed
path. It converts the checkpoint's own `config.json` + `model.safetensors` into the flat format the
kernel reads on every call by default; pass `converted_checkpoint_dir` (after calling
`prepare_checkpoint()` once yourself) to skip re-converting across repeated calls against the same
checkpoint.

## Tokens in, tokens out — this is not a chat API

`prompt_token_ids` is a list of integers, not a string. Tokenize with the checkpoint's own
tokenizer — this module does not carry a second, un-audited tokenizer implementation:

```python
from transformers import AutoTokenizer

tok = AutoTokenizer.from_pretrained("/path/to/your/Qwen3-0.6B-Base")
prompt_token_ids = tok("The capital of France is", return_tensors=None)["input_ids"]
```

## Why one call, not a session you open and step

Every existing driver for this kernel path — including the benchmark this page's throughput number
comes from — opens a session, prefills the prompt, decodes greedily to a token budget or an
end-of-text token, and exits, all within one call. There is no design here for stepping a session
token-by-token across separate calls, so `qwen3_i8_allsimd7_decode()` does not offer one: it matches
what this kernel path actually does rather than an aspirational streaming API.

## What this page does not claim

* **One model.** Qwen3-0.6B-Base's exact architecture only — not other Qwen3 sizes, not other model
  families. A different shape raises rather than runs.
* **One hardware family.** Apple Silicon with Metal. There is no CPU fallback here — a host without
  a Metal accelerator, or a worker built without `-D ALGENTA_GPU`, gets a named refusal, never a
  slower silent substitute.
* **Greedy decode only.** Argmax at every step. No sampling, no beam search, no repetition penalty.
* **Not a chat template, not a tokenizer.** Bring your own token ids in, get token ids out.

## Related

* [Decode throughput](../benchmarks/decode-throughput.md) — the measured race this kernel path won.
* [Runtime libraries](runtime-libraries.md) — the same call also reaches this over
  `POST /v1/libraries/execute` with `module=metaldispatch.qwen3_decode`,
  `function=qwen3_i8_allsimd7_decode_flat`.
* [Retrieval](retrieval.md) — another local-runtime capability with the same "raise, never guess"
  discipline for a missing backend.
