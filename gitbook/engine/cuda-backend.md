---
icon: microchip
description: Run the CUDA backend — availability, NVIDIA driver and architecture requirements, the callable entry points, determinism gates, verified model shapes, and the TypeScript SDK path.
---

# CUDA backend

The CUDA backend runs Algenta's resident LLM session on NVIDIA GPUs: tensor-core prefill, fused
attention, and CUDA-graph decode over the same declared checkpoint facts as every other backend.
It is hardware-verified on H200 and H100 (sm\_90), A100 (sm\_80), L4 (sm\_89) and T4 (sm\_75).
Apple Metal remains the default serve path in the shipped SDK; the full backend matrix is
[GPU support](gpu-support.md).

## Availability

| Surface | Artifact | Status |
| --- | --- | --- |
| Python facade and CLI | `algenta` on PyPI | Published |
| Native runtime, macOS arm64 and linux-x86\_64 | `algenta-runtime-native` on PyPI | Published |
| Native runtime, CUDA shards | `algenta-runtime-native-linux-x86_64-cuda`, built by the `build-linux-cuda` CI job | Ships with the next runtime release |
| TypeScript client | `algenta-sdk` on npm | Published. Backend-agnostic — see [TypeScript SDK](#typescript-sdk) |

The CUDA runtime is a build variant of `algenta-runtime-native` for linux-x86\_64: the same
package and platform tag, with the accelerator shards compiled
`-D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_90`. It publishes with the next runtime
release, gated on the hardware verification recorded on this page. The install line does not
change:

```bash title="install on Linux x86_64 with an NVIDIA GPU"
python3.14 -m venv .venv
source .venv/bin/activate
pip install algenta
algenta runtime doctor
```

`pip install algenta` resolves the pinned `algenta-runtime-native` wheel for the platform and
verifies it against its signed manifest before execution; it fails closed on a mismatch. Python
3.14 is required.

## Hardware requirements

| Item | Requirement |
| --- | --- |
| GPU architecture | sm\_52, sm\_60/61, sm\_75, sm\_80, sm\_86, sm\_87, sm\_89, sm\_90(a), sm\_100(a), sm\_110, sm\_120(a), sm\_121 — the pinned toolchain's supported range |
| Excluded architecture | sm\_70 (V100 / Volta) — rejected at compile time by the pinned toolchain |
| NVIDIA driver | >= 580, validated at 580.173.02 and 595.71.05 |
| Operating system | Linux x86\_64, glibc >= 2.35 (`manylinux_2_35_x86_64`) |
| Toolchain | The repo's pinned Mojo toolchain (mojo 1.0.0 / MAX 26.5.0), resolved from the lockfile |
| Compile target | `sm_90` by default; override with `MOJO_BUILD_CUDA_TARGET` |
| Link step | clang |
| Headless hosts | `ubuntu-drivers install --gpgpu` installs the driver without `nvidia-smi`; install the matching `nvidia-utils-<ver>-server` package for it |

Per-GPU compile target:

| GPU | `MOJO_BUILD_CUDA_TARGET` |
| --- | --- |
| T4 | `sm_75` |
| A100 | `sm_80` |
| L4 | `sm_89` |
| H100, H200 | `sm_90` |

### Memory

| Checkpoint | Measured footprint |
| --- | --- |
| Qwen3-0.6B-Base, packed-int8 (1.58 B/weight), 32 sequences in flight | 5,038 MiB on A100, 4,804 MiB on L4 |
| Qwen2.5-7B-Instruct, f16 prefill twins staged once at session open | +13.05 GB, one time, ~71 ms |
| Gemma-3-27B-it, f16 resident weights | 54 GB residency |

Footprints are measured on the hardware in [Verified shapes](#verified-shapes) and reported with
their methodology on [NVIDIA LLM serving](../benchmarks/nvidia-llm-serving.md) and
[NVIDIA LLM throughput](../benchmarks/nvidia-llm-throughput.md).

## Entry points

The CUDA lane is driven through the backend-scoped entries below. Each takes the same declared
checkpoint facts; `backend="cuda"` selects the CUDA fact gates and the CUDA kernel set.

### Conformance verdict

`scripts/algenta_conform.py` returns the verdict for any checkpoint before any weights are
converted or any GPU work is done:

```bash title="CUDA verdict for a local checkpoint"
python3 scripts/algenta_conform.py /path/to/model-dir --backend cuda
python3 scripts/algenta_conform.py /path/to/model-dir --backend cuda --json verdict.json
python3 scripts/algenta_conform.py --table
```

Exit codes: `0` supported, `3` supported pending the tensor probe, `2` refused with typed
refusals, `1` unusable input. A refusal names the exact fact, its value, and the supported range.
The declared fact ranges, the per-family kernel sets, and the onboarded-checkpoint table are on
[Model support matrix](model-support-matrix.md).

### Checkpoint conversion

`prepare_model_checkpoint()` validates the architecture and writes the `manifest.json` +
`weights.blob` pair the resident kernels read:

```python title="convert a checkpoint for the CUDA backend"
from algenta import prepare_model_checkpoint

prompt_ids = [785, 6722, 315, 9625, 374]   # "The capital of France is"

prepare_model_checkpoint(
    "/path/to/model-dir",     # a local Hugging Face snapshot directory
    prompt_ids,
    out_dir="/tmp/model-cuda",
    weights_dtype="f32",      # exact for BF16-origin checkpoints, half the disk of f64
    backend="cuda",           # applies the CUDA fact gates to the tensor probe
)
```

The q/k/v projection-bias fact is the gate that differs by backend: the CUDA paths apply biases,
so a checkpoint carrying them converts for CUDA and is refused for Metal. Conversion is
prompt-independent — one conversion serves every prompt length.

### Throughput battery

The fact-driven battery drives the CUDA resident door across prefill shapes with no per-model
harness:

```bash title="sweep prefill shapes on the CUDA backend"
python3 scripts/algenta_bench.py cuda /path/to/model --driver "./conform_generate_cuda_<tier>" --shapes 256,1024 --gen 64
```

`--driver` (or `ALGENTA_CONFORM_CUDA_DRIVER`) points at the resident binary built for the
checkpoint's staging tier. Each cell reports single-stream time-to-first-token and decode rate as
a median over `--runs`.

### Kernel contract

The CUDA kernels that ship are published as a ratcheted inventory — 142 kernels across the
`gemma3` and `qwen3/llama` families, at staging tiers 3072, 6144, 8192 and 18944 elements:

```python title="query the shipped CUDA kernel inventory"
from algenta import engine_kernels

gemma3 = engine_kernels(backend="cuda", family="gemma3")
for kernel in gemma3:
    kernel.name, kernel.role, kernel.module, kernel.families
```

The full table is [Kernel inventory](kernel-inventory.md). These kernels take device pointers,
which do not cross a JSON frame, so they are declared rather than callable; the callable compiled
functions are the [Runtime libraries](runtime-libraries.md) surface.

### Serve entry

A serve entry that selects the CUDA backend ships with the next runtime release, published with
its own grammar. The contract that decides what a CUDA build runs is published now:
[Model support matrix](model-support-matrix.md) for the fact ranges and typed refusals,
[Kernel inventory](kernel-inventory.md) for the kernel set, and
[Runtime libraries](runtime-libraries.md) for the authenticated HTTP surface.

## Determinism

| Gate | Requirement |
| --- | --- |
| Greedy continuation vs the fp32 CPU oracle | 16/16 and 64/64 tokens identical, on every build, before any measurement is recorded |
| Repeat runs | Bit-identical across fresh driver processes: 6/6 identical-prompt rounds on A100 and L4 |
| Concurrent serving | 8/8 concurrent token identity on every shipped build |
| Cross-engine identity | Five chat prompts, token-identical against the reference engines serving the same checkpoint |
| Scope certification | The measured default configuration is certified full-scope against the oracle at 256, 1024, 550 and 4096 tokens |

Greedy decoding is temperature 0 with `repetition_penalty` pinned at 1.0 against the oracle.
A build that fails a gate is not measured.

## Verified shapes

Prompt shapes and hardware per checkpoint. Throughput tables and their methodology are published
on the linked pages.

| Checkpoint | Family | GPU | Shapes measured | Numbers |
| --- | --- | --- | --- | --- |
| `google/gemma-3-27b-it` | gemma3 | H200 (sm\_90) | Prefill 256, 1024, RAG-4096 | [NVIDIA LLM throughput](../benchmarks/nvidia-llm-throughput.md) |
| `google/gemma-3-27b-it` | gemma3 | H100 80GB HBM3 (sm\_90) | TTFT 160, 256, 550; open-loop C=50; closed-loop batch C=50 | [NVIDIA LLM serving](../benchmarks/nvidia-llm-serving.md) |
| `Qwen/Qwen2.5-7B-Instruct` | qwen3/llama | A100-SXM4-40GB (sm\_80) | Prefill 256, 1024, RAG-4096; 256-token server TTFT; decode gen=256 | [NVIDIA LLM throughput](../benchmarks/nvidia-llm-throughput.md) |
| `Qwen/Qwen3-0.6B-Base` | qwen3/llama | A100-SXM4-40GB (sm\_80), H100 (sm\_90), L4 (sm\_89) | Prefill 256; decode gen=64 and gen=256; batch B=32; concurrent C=8, 16, 32; cold start | [NVIDIA LLM serving](../benchmarks/nvidia-llm-serving.md) |
| Portable kernel layer | any | T4 (sm\_75), L4 (sm\_89), A100 (sm\_80) | Bit-exact against the CPU oracle, worst-case GEMM delta 0.0 | [NVIDIA kernel benchmarks](../benchmarks/nvidia-kernel-benchmarks.md) |

Staging tier per onboarded checkpoint — Qwen2.5-7B-Instruct and Mistral-7B-Instruct-v0.3 at
STAGE\_18944, Llama-3.2-1B and Llama-3.2-3B at STAGE\_8192 — is tabled on
[Model support matrix](model-support-matrix.md).

## TypeScript SDK

The TypeScript client published to npm as `algenta-sdk` is backend-agnostic: it speaks HTTP to a
base URL, and which backend serves a request is a property of the deployment, not of the client.
There is no CUDA-specific client build and no CUDA-specific code path — point `baseUrl` at the
engine serving on CUDA and the same `client.chatCompletions()`, `client.streamChatCompletions()`,
`client.embeddings()` and `client.rerank()` calls reach it unchanged. See
[TypeScript SDK](../sdk/typescript.md) for configuration and
[LLM & model discovery](../sdk/typescript/llm.md) for the call surface.

## Notes

* Metal is the default serve path in the shipped SDK. The CUDA backend is hardware-verified on the
  GPUs tabled above; its runtime wheel publishes with the next runtime release.
* CI compiles and links the CUDA lane on every change (`build-linux-cuda`, default target
  `sm_90`) on a builder with no CUDA toolkit and no GPU. Hardware verification runs on the GPUs in
  [Verified shapes](#verified-shapes).
* There is no CPU fallback. A host with no NVIDIA accelerator exits non-zero naming the missing
  accelerator, and a build compiled without `-D ALGENTA_GPU -D ALGENTA_CUDA` exits non-zero naming
  the missing build flags.
* The architecture preflight runs before any GPU work and returns a named `residentk` status;
  a checkpoint whose staged vectors exceed every tier of the backend is refused naming the value
  and the tiers.
* Build flags: `-D ALGENTA_GPU` compiles the portable GPU kernels; `-D ALGENTA_METAL` additionally
  compiles the Metal serving path.

## Related

* [GPU support](gpu-support.md) — the backend support matrix and requirements.
* [Model support matrix](model-support-matrix.md) — declared fact ranges and the conform CLI.
* [Kernel inventory](kernel-inventory.md) — the published CUDA and Metal kernel tables.
* [NVIDIA LLM throughput](../benchmarks/nvidia-llm-throughput.md) — prefill and decode measurements.
* [NVIDIA LLM serving](../benchmarks/nvidia-llm-serving.md) — concurrency, cold start, VRAM, determinism.
* [NVIDIA kernel benchmarks](../benchmarks/nvidia-kernel-benchmarks.md) — the portable-kernel layer.
* [Runtime libraries](runtime-libraries.md) — the callable compiled-function surface.
