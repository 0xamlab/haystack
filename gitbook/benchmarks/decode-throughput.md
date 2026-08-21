---
icon: bolt
description: Decode tokens per second for Qwen3-0.6B-Base on Apple silicon — 324.8 tok/s median vs mlx-lm 281.6 and llama.cpp 254.0, interleaved order-rotated rounds on the same machine.
---

# Decode throughput

Autoregressive decoding generates one token at a time, and the steady-state rate once the prompt
has been processed — tokens per second — is the cost a live deployment pays on every request. This
page measures that rate for one real checkpoint against two real, independently-implemented,
installed alternatives on the same machine, run back to back: mlx-lm, Apple's own MLX-based
generation library, and llama.cpp, measured in both its GPU and CPU-only configurations.

{% hint style="info" %}
**Medians over interleaved, order-rotated rounds:** Algenta 324.82 tok/s; mlx-lm 281.58 (Algenta
ahead in 19 of 20 rounds); llama.cpp GPU 253.97 and CPU 15.19 (ahead in all 14 rounds).
{% endhint %}

## Try it yourself, in 5 lines

Once you have the checkpoint on disk and a tokenizer for it (see [Get the checkpoint](../guides/run-qwen3-decode.md#get-the-checkpoint) for the one-time download), decoding is one call:

```python title="decode_quickstart.py"
from algenta import MojoRuntime, qwen3_i8_allsimd7_decode

runtime = MojoRuntime(mode="local")
result = qwen3_i8_allsimd7_decode(
    runtime, checkpoint_dir="./qwen3-0.6b-base",
    prompt_token_ids=prompt_token_ids, max_new_tokens=16,
)
print(result.decode_tokens_per_sec)
```

No server to start, no sidecar to manage — the compiled Metal kernel path ships inside the
`algenta` package itself. [Run local LLM decode](../guides/run-qwen3-decode.md)
is the complete version of this: install, tokenize your own prompt, and the full table of
typed errors this call raises by name (never a silent wrong answer) instead of returning one.

## Results

Decode-only tokens per second on `Qwen/Qwen3-0.6B-Base`, 16 greedy-decoded tokens from a single
fixed prompt. mlx-lm and llama.cpp were measured in separate interleaved sessions (20 rounds and
14 rounds respectively) rather than one shared session, so each opponent's row reports its own
session's round count rather than a single mixed number:

| Arm | Compute | Rounds | Median tok/s | Range |
| --- | --- | --- | --- | --- |
| **Algenta** (vs mlx-lm session) | GPU (Metal) | 20 | **324.82** | 312.43 - 331.42 |
| mlx-lm 0.31.3 | GPU (Metal) | 20 | 281.58 | 244.38 - 314.81 |
| llama.cpp (build 10210), `-ngl 99` | GPU (Metal) | 14 | 253.97 | 234.21 - 265.48 |
| llama.cpp (build 10210), `-ngl 0` | CPU | 14 | 15.19 | 1.83 - 45.33 |

### vs mlx-lm — 20 interleaved rounds

Full round-by-round breakdown, including the one round mlx-lm led:

| Round | Algenta | mlx-lm | Ratio |
| --- | --- | --- | --- |
| 1 | 324.59 | 283.78 | 1.1438 |
| 2 | 323.24 | 261.29 | 1.2371 |
| 3 | 321.83 | 289.28 | 1.1125 |
| 4 | 326.02 | 271.65 | 1.2001 |
| 5 | 330.76 | 279.75 | 1.1823 |
| 6 | 323.45 | 314.06 | 1.0299 |
| 7 | 323.35 | 283.61 | 1.1401 |
| 8 | 312.43 | 314.81 | 0.9924 |
| 9 | 327.21 | 270.52 | 1.2095 |
| 10 | 328.59 | 278.43 | 1.1801 |
| 11 | 321.95 | 276.60 | 1.1639 |
| 12 | 321.77 | 268.24 | 1.1996 |
| 13 | 325.06 | 302.64 | 1.0741 |
| 14 | 325.66 | 276.82 | 1.1764 |
| 15 | 322.28 | 283.41 | 1.1371 |
| 16 | 327.22 | 291.79 | 1.1214 |
| 17 | 331.42 | 283.90 | 1.1674 |
| 18 | 320.10 | 244.38 | 1.3098 |
| 19 | 326.98 | 301.74 | 1.0836 |
| 20 | 328.35 | 265.55 | 1.2365 |

Algenta led in 19 of 20 rounds (ratio range 1.0299x-1.3098x); mlx-lm led round 8 at 0.9924x.

### vs llama.cpp — 14 interleaved rounds

Against llama.cpp the margin is wider and, in this measurement, uniform: 14 of 14 rounds against
its GPU configuration (ratio range 1.180x-1.430x), and 14 of 14 against its CPU-only configuration
(ratio range 7.16x-176.03x, computed round by round from the same raw data).

### Correctness

Every arm's generated token ids were checked position by position against an independent
`transformers`-CPU reference, in both measurement sessions. All
three engines — Algenta, llama.cpp, and mlx-lm — produced token-identical output on every round
checked, in every configuration: `[12095, 13, 576, 6722, 315, 9856, 374, 19846, 13, 576, 6722, 315,
15344, 374, 21718, 13]`, i.e. "Paris. The capital of Germany is Berlin. The capital of Italy is
Rome." No arm diverged from any other in any round checked.

## Method

* **Checkpoint.** `Qwen/Qwen3-0.6B-Base` (Apache-2.0, ungated), a real Hugging Face checkpoint
  downloaded unmodified, published as BF16 safetensors.
* **Prompt and decode length.** One fixed prompt, `"The capital of France is"` (5 tokens), 16
  greedy-decoded tokens (temperature 0 / argmax) per round — the only decoding strategy directly
  comparable across three independently-implemented engines without a matched random-number
  stream.
* **What is timed.** Decode-only wall time: from the first generated token to the last, excluding
  weight load and prompt prefill.
* **Opponents.** mlx-lm 0.31.3 (MLX 0.32.0, running on the Apple GPU device) and llama.cpp build
  10210 (Homebrew, Metal support built in), measured in both its GPU (`-ngl 99`) and CPU-only
  (`-ngl 0`) configurations. Both are real installs on the same machine as Algenta, not simulated
  or estimated.
* **Interleaving.** The mlx-lm session ran 20 rounds; the llama.cpp session ran 14. All engines
  measured together in a session run back to back within each round, with the run order rotated
  every round so no engine is always measured first or last.
* **Load.** Shared machine. The 1-minute load average was sampled before and after every round:
  10.65-17.45 during the llama.cpp session, 4.0-5.6 during the mlx-lm session; reported as
  measured.
* **Hardware.** Apple M4 Max, 16 physical cores (12 performance + 4 efficiency). Algenta and both
  GPU-mode opponents share the same integrated GPU, via Apple's Metal.

## Scope

* Qwen3-0.6B-Base, one 5-token prompt, 16 decoded tokens. Other model sizes, prompts and context
  lengths are separate measurements; concurrent serving is
  [Batched decode throughput](batched-decode-throughput.md).
* Steady-state decode only; prefill is on [Prefill throughput](llm-prefill-throughput.md).
* Opponents are the installed mlx-lm 0.31.3 and llama.cpp build 10210; other serving stacks and
  future versions are not covered.
* Per-round ratios are reported in full (tables above), including the round mlx-lm led.

## Related

* [LLM inference overview](llm-inference-overview.md) — prefill + decode together.
* [Prefill (token input) throughput](llm-prefill-throughput.md) — the token-input half of inference.
* [Batched decode throughput](batched-decode-throughput.md) — continuous batching for many sequences.
* [Benchmarks](overview.md) — methodology.
* [Feed-forward](feed-forward.md) — gated activations and embedding cost.
* [Attention](attention.md) — tiled attention memory and rotary embedding cost.
* [Metal LLM decode](../engine/qwen3-metal-decode.md) — call this
  kernel path yourself, from Python, against your own checkpoint.
* [GPU support](../engine/gpu-support.md) — the lane-by-lane verification
  matrix behind these Metal results.
* [Run local LLM decode](../guides/run-qwen3-decode.md) — a step-by-step
  guide: install, get the checkpoint, tokenize a prompt, and run a decode end to end.

## Reproduce

The environment side of this benchmark is publicly reproducible — the same real checkpoint and the
same two real opponents, installed the normal way:

```bash
pip install mlx-lm
brew install llama.cpp
python3 -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='Qwen/Qwen3-0.6B-Base')"
```

Both opponents are then run with their own standard generation entry points against that checkpoint
and prompt, with Metal/GPU support enabled. The packaged end-to-end driver (Algenta side,
interleave rotation, per-arm `transformers` verification) ships separately; the protocol is real
installs, same checkpoint, same prompt, decode-only timing, interleaved rounds.
