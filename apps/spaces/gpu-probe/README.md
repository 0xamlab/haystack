---
title: Algenta GPU probe
emoji: 🔬
colorFrom: gray
colorTo: green
sdk: docker
app_port: 7860
hardware: t4-small
suggested_hardware: t4-small
pinned: false
license: apache-2.0
short_description: "Qwen3-1.7B on Algenta CUDA kernels — parity probe"
tags:
  - kernels
  - mojo
  - cuda
  - llm
---

# Algenta GPU probe

Qwen3-1.7B decoded on an NVIDIA GPU by the compiled CUDA kernels published at
[thyn-ai/algenta-llm](https://huggingface.co/thyn-ai/algenta-llm), and checked token by token
against an independent reference. One fixed prompt, eight greedy tokens, the same token ids on
both sides or the index where they part. The same decode without Algenta — transformers on the
same GPU, float32 and float16 — sits beside it.

This Space is private and stays paused between runs. A run is one boot: it costs a few minutes
of `t4-small` time and leaves `run.json` behind.

## What it proves

- The Hub's GPU hardware meets the CUDA build's floor natively: NVIDIA driver 580 or later,
  a compute capability the build carries a library for (sm_75, sm_80, sm_89, sm_90).
- `kernels.get_kernel("thyn-ai/algenta-llm", backend="cuda")`, pinned to the published
  revision, resolves the `torch29-cxx11-cu128-x86_64-linux` variant, the native manifest
  declares the 6144 staging tier that admits Qwen3-1.7B, and the runtime loads the library the
  device's capability calls for.
- The Qwen3-1.7B snapshot converts to the f64 CUDA blob with
  `algenta.inference.prepare_model_checkpoint`, timed.
- `DecodeSession` produces eight greedy tokens for the prompt, with the session open time and
  each step's wall time.
- Plain transformers on the same GPU decodes the same prompt with the same greedy settings, in
  float32 (the precision of Algenta's resident weights) and in float16, each lane its own model
  load with a warm-up generate excluded; the page prints the two beside the Algenta lane —
  tokens, parity, load, time to first token, steady per-token time, tokens per second, device
  memory — every number measured in the same run, and a lane that cannot run says so with a
  code.
- transformers in float32 on the CPU produces the same eight token ids, or the page names the
  first divergent index and the reference's top-2 logit margin there.

## How the run is made

The probe runs at boot, one phase after another, each in its own process with a wall-clock
budget: `driver`, `kernel`, `convert`, `decode`, `baseline`, `reference`, then `record`.
`/health` is the live record of the run: the phase that is running, every phase's status, code
and time, and each fact once it has been measured. The page at `/` renders that record; a
number appears only after it was measured in this container, and a phase that cannot run says
so with a code. `/run.json` is the finished record with the evidence rows' fields and the
`baseline` block, written once every phase that decides the verdict is ok (a baseline that
could not run is recorded with its code, not as a stop).

The image bakes the kernel snapshot and the model snapshot at build time and boots with
`HF_HUB_OFFLINE=1`, so nothing downloads at boot. The 13.8 GB conversion happens on the Space's
disk during the `convert` phase and is reused while the Space stays up.

## Run it yourself

```sh
pip install kernels torch
python -c 'from kernels import get_kernel
k = get_kernel("thyn-ai/algenta-llm", version=1, backend="cuda", trust_remote_code=["thyn-ai/algenta-llm"])
print(k.__file__)'
```

Duplicate this Space on GPU hardware to run the full probe on your own account; the Dockerfile
carries every pin.

## Boundary

Space code is Apache-2.0. The kernels it loads are published under the Algenta Community
License 1.1; commercial plans at [algenta.ai/pricing](https://algenta.ai/pricing).
[Qwen/Qwen3-1.7B](https://huggingface.co/Qwen/Qwen3-1.7B) is Apache-2.0, by the Qwen team.
Documentation: [docs.algenta.ai](https://docs.algenta.ai). Questions and results:
[Discord](https://discord.gg/w8NDsph9an).
