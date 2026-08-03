---
icon: bolt
description: Decode tokens per second for Qwen3-0.6B-Base on Apple silicon — Algenta ahead of real, installed mlx-lm and llama.cpp on every one of 14 interleaved rounds, not just the median.
---

# Decode throughput

Autoregressive decoding generates one token at a time, and the steady-state rate once the prompt
has been processed — tokens per second — is the cost a live deployment pays on every request. This
page measures that rate for one real checkpoint against two real, independently-implemented,
installed alternatives on the same machine, run back to back: mlx-lm, Apple's own MLX-based
generation library, and llama.cpp, measured in both its GPU and CPU-only configurations.

{% hint style="success" %}
**Across 14 interleaved rounds, with the run order alternated every round, Algenta's decode
throughput was ahead of mlx-lm in every single round — not just on the median.** Median 326.81
tok/s against mlx-lm's 310.27 (14 of 14 rounds, ratio range 1.0026x-1.1257x). Both llama.cpp
configurations were beaten in all 14 rounds too.
{% endhint %}

## Results

Decode-only tokens per second on `Qwen/Qwen3-0.6B-Base`, 16 greedy-decoded tokens from a single
fixed prompt, 14 interleaved rounds:

| Arm | Compute | Median tok/s | Range across 14 rounds |
| --- | --- | --- | --- |
| **Algenta** | GPU (Metal) | **326.81** | 312.32 - 336.67 |
| mlx-lm 0.31.3 | GPU (Metal) | 310.27 | 292.18 - 318.20 |
| llama.cpp (build 10210), `-ngl 99` | GPU (Metal) | 253.97 | 234.21 - 265.48 |
| llama.cpp (build 10210), `-ngl 0` | CPU | 15.19 | 1.83 - 45.33 |

**Every round, not just the median.** mlx-lm is the closer of the two real opponents on this
checkpoint, so it is the one that decides the claim:

| Round | Algenta | mlx-lm | Ratio |
| --- | --- | --- | --- |
| 1 | 312.32 | 292.99 | 1.0660 |
| 2 | 328.92 | 292.18 | 1.1257 |
| 3 | 326.02 | 315.74 | 1.0326 |
| 4 | 336.67 | 315.96 | 1.0655 |
| 5 | 332.68 | 318.20 | 1.0455 |
| 6 | 319.44 | 312.61 | 1.0219 |
| 7 | 316.29 | 315.46 | 1.0026 |
| 8 | 327.51 | 316.36 | 1.0353 |
| 9 | 324.73 | 305.96 | 1.0614 |
| 10 | 334.97 | 302.66 | 1.1068 |
| 11 | 331.36 | 317.48 | 1.0437 |
| 12 | 326.10 | 307.93 | 1.0590 |
| 13 | 322.13 | 307.86 | 1.0464 |
| 14 | 327.99 | 306.23 | 1.0711 |

**14 of 14 rounds, ratio range 1.0026x (round 7, the closest) to 1.1257x (round 2, the widest). No
round in this race saw mlx-lm ahead.**

Against llama.cpp the margin is wider and equally consistent: 14 of 14 rounds against its GPU
configuration (ratio range 1.180x-1.430x), and 14 of 14 against its CPU-only configuration (ratio
range 7.16x-176.03x, computed round by round from the same raw data).

### Correctness

A faster wrong answer is not a result. Every arm's generated token ids were checked position by
position against an independent `transformers`-CPU reference. All three engines — Algenta,
llama.cpp, and mlx-lm — produced token-identical output on every round checked, in every
configuration: `[12095, 13, 576, 6722, 315, 9856, 374, 19846, 13, 576, 6722, 315, 15344, 374,
21718, 13]`, i.e. "Paris. The capital of Germany is Berlin. The capital of Italy is Rome." No arm
diverged from any other in any round checked.

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
* **Interleaving.** 14 rounds. All engines run back to back within a round, and the run order is
  alternated every round (forward, then reversed, then forward again, ...) so no engine is always
  measured first or last.
* **Load.** This is a shared machine. The 1-minute load average was sampled before and after every
  round and stayed in the 10.65-17.45 range throughout — busy, not idle, and disclosed rather than
  rerun until quiet.
* **Hardware.** Apple M4 Max, 16 physical cores (12 performance + 4 efficiency). Algenta and both
  GPU-mode opponents share the same integrated GPU, via Apple's Metal.

## What is not claimed

* **One checkpoint, one prompt, one decode length.** This page measures Qwen3-0.6B-Base, a single
  5-token prompt, and 16 decoded tokens. It is not a throughput claim across other model sizes,
  other prompts, longer contexts, or batched/concurrent serving.
* **Not a claim about prefill, training, or fine-tuning.** Only steady-state decode is measured.
  Prompt processing and any non-decode workload are out of scope.
* **Not a claim about every serving framework.** mlx-lm and llama.cpp are the two real, installed
  alternatives measured on this page. Other serving stacks are not part of this comparison.
* **Not a claim about future versions.** mlx-lm 0.31.3 and llama.cpp build 10210 are the versions
  installed and measured for this page. Neither project's own future releases are addressed here.
* **The margin is not uniform.** The narrowest round against mlx-lm (1.0026x) is reported alongside
  the widest (1.1257x) rather than only the favorable end of the range.

## Related

* [Benchmarks](overview.md) — methodology and what is not published.
* [Feed-forward](feed-forward.md) — gated activations and embedding cost.
* [Attention](attention.md) — tiled attention memory and rotary embedding cost.
* [Qwen3-0.6B-Base decode (Apple Silicon, Metal)](../engine/qwen3-metal-decode.md) — call this
  kernel path yourself, from Python, against your own checkpoint.
* [Run Qwen3-0.6B-Base decode on Apple Silicon](../guides/run-qwen3-decode.md) — a step-by-step
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
and prompt, with Metal/GPU support enabled. A packaged, single-command external script that also
drives Algenta's side of the race, alternates the interleave order, and verifies every arm's output
against a `transformers` reference is not yet published as part of this repository's public
tooling. Until that script ships, this page's numbers are reproducible in shape — real installs,
same checkpoint, same prompt, decode-only timing, interleaved rounds — rather than via one
copy-pasteable end-to-end command.
