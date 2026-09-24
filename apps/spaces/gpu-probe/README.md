---
title: Algenta GPU probe
emoji: 🔬
colorFrom: gray
colorTo: green
sdk: docker
app_port: 7860
hardware: l4x1
suggested_hardware: l4x1
pinned: false
license: apache-2.0
short_description: "Qwen3-0.6B-Base: the published CUDA race, live on an L4"
tags:
  - kernels
  - mojo
  - cuda
  - llm
---

# Algenta GPU probe

The published single-stream race, run live on one NVIDIA L4: the CUDA engine that ships in
Algenta's runtime wheel against llama.cpp built with GGML_CUDA at the benchmark pages' pinned
commit, on Qwen3-0.6B-Base, the same 256-token prompt, 64 greedy tokens, one warm-up excluded
and the median of three timed runs, exactly the shape of the published L4 cell. The published
figures of that cell are printed beneath the measured ones, marked as published, with a link to
the page they come from. Two secondary rows run beside the race on the same GPU with the same
prompt: the compiled CUDA kernels published at
[thyn-ai/algenta-llm](https://huggingface.co/thyn-ai/algenta-llm) on their f32 parity path, and
plain transformers in float32 and float16. Every lane's tokens are checked against a
transformers float32 CPU reference, the first 16 as the published oracle and all 64.

This Space is private and stays paused between runs. A run is one boot: it costs some minutes of
`l4x1` time and leaves `run.json` behind.

## What it measures

- Lane A, the shipped engine: `conform_generate_cuda` from the installed `algenta-runtime-native`
  wheel, located the way `algenta serve` locates it, run as the published battery runs it
  (`<checkpoint> --max-new 64 --prompt-len 256`). Its signed manifest names its compile target
  and build; the probe prints them and refuses to launch an engine whose target cannot load on
  the device, with a code that says so. When the Space variable `ALGENTA_CUDA_ENGINE` names the
  packed-int8 captured-graph driver of the published cells (`qwen3_p3_graph_cuda`, built for
  the L4's sm_89 and shipped beside the app), lane A runs that driver instead, through its own
  protocol: its gate battery first (a 16-token oracle, 3 x 128 steps of graph-vs-per-dispatch
  token identity, an engagement check), then gen=64 and gen=256 in one process; the page names
  the engine's build and the campaign prompt fixture the whole run then uses.
- Lane B, the published opponent: `llama-server -ngl 99` on the F16 GGUF converted from the same
  snapshot at image build, the same 256 ids sent as tokens, greedy; llama.cpp's own timings
  (`predicted_per_second`, `prompt_per_second`) are the figures.
- Lane C, the Hub kernels: `kernels.get_kernel("thyn-ai/algenta-llm", backend="cuda")` at the
  published revision, the `DecodeSession` over the same f64 blob, one warm-up session excluded,
  three timed sessions.
- Lane D, the naive stack: transformers `generate` on the same GPU in float32 and float16, each
  its own model load, one warm-up generate excluded, three timed generates.
- The reference: transformers float32 greedy on the CPU, the same ids, with each step's top-2
  logit margin, so a divergence names the index and how close the call was.

A lane that cannot run says so with a code (`engine_target_mismatch`, `llama_server_failed`,
`baseline_oom`, ...) and the other lanes still run; the record is written when the driver, the
conversion and the reference are ok.

## How the run is made

The probe runs at boot, one phase after another, each in its own process with a wall-clock
budget: `driver`, `kernel`, `convert`, `engine`, `llama`, `decode`, `baseline`, `reference`,
then `record`. `/health` is the live record: the phase that is running, every phase's status,
code and time, and each fact once it has been measured. The page at `/` renders that record; a
number appears only after it was measured in this container, and a lane that cannot run says so
with a code. `/run.json` is the finished record with the evidence rows' fields.

The image builds llama.cpp in a builder stage, bakes the kernel snapshot, the model snapshot and
the F16 GGUF at build time and boots with `HF_HUB_OFFLINE=1`, so nothing downloads at boot. The
f64 conversion (about 4.8 GB) happens on the Space's disk during the `convert` phase and serves
lanes A and C.

## Run it yourself

```sh
pip install algenta kernels torch
python -c 'from algenta.serve.engine import resolve_engine
print(resolve_engine("cuda"))'
python -c 'from kernels import get_kernel
k = get_kernel("thyn-ai/algenta-llm", version=1, backend="cuda", trust_remote_code=["thyn-ai/algenta-llm"])
print(k.__file__)'
```

Duplicate this Space on GPU hardware to run the full race on your own account; the Dockerfile
carries every pin.

## Boundary

Space code is Apache-2.0. The kernels it loads are published under the Algenta Community
License 1.1; commercial plans at [algenta.ai/pricing](https://algenta.ai/pricing).
[Qwen/Qwen3-0.6B-Base](https://huggingface.co/Qwen/Qwen3-0.6B-Base) is Apache-2.0, by the Qwen
team; llama.cpp is MIT, by the ggml authors. Documentation:
[docs.algenta.ai](https://docs.algenta.ai). Questions and results:
[Discord](https://discord.gg/w8NDsph9an).
