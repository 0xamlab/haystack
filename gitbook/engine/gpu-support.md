---
icon: microchip
description: Which GPU backends Algenta runs on and how far each lane is verified — Metal end to end, CUDA kernel layer run-verified and LLM session race-verified on A100/L4, ROCm not yet.
---

# GPU support

Algenta's GPU lanes are at different maturity stages. This page is the canonical matrix: what has
actually run on real hardware, what is compile-gated only, what the pinned toolchain refuses — and,
for each lane, exactly what the verification covers.

{% hint style="info" %}
**Scope.** Verification is per-lane. Metal is run-verified end to end — the full LLM serving
path included — and is the production serving lane. NVIDIA CUDA is run-verified for the
**portable GPU kernel layer** on three architectures, and the CUDA-native resident LLM session
is benchmark-verified on A100 and L4. The CI CUDA lane is compile-gated.
{% endhint %}

## The matrix

| Backend | Status | What has been verified |
| --- | --- | --- |
| Metal (Apple Silicon) | **RUN-verified — the production path today** | The full serving path: resident kernels, batched-dispatch sessions, prefill and decode — race-proven on real M-series hardware |
| NVIDIA CUDA | **RUN-verified for the portable kernel layer; LLM session benchmarked** | Bit-exact kernel runs on real T4 (sm_75), L4 (sm_89) and A100-40GB (sm_80) hardware; the CUDA-native resident LLM session benchmarked on A100/L4 (prefill 3,260 vs llama.cpp F16 2,527 tok/s; decode 329.8 vs 356.9); compile-gated in CI on every change |
| V100 / Volta (sm_70) | **Unsupported** | The pinned toolchain hard-rejects sm_70 at compile time — see [Unsupported architectures](#unsupported-architectures) |
| AMD ROCm | **Compile-gate in progress** | Not verified — see [AMD ROCm](#amd-rocm) |

## Metal (Apple Silicon)

Metal is the lane Algenta serves from today. Resident kernels, batched dispatch, and both halves of
LLM inference have run on real M-series hardware and are measured publicly:

* [Prefill (token input) throughput](../benchmarks/llm-prefill-throughput.md) — the compute-bound half.
* [Decode throughput](../benchmarks/decode-throughput.md) and [Batched decode throughput](../benchmarks/batched-decode-throughput.md) — the memory-bound half, single-stream and batched.
* [Metal LLM decode](qwen3-metal-decode.md) — the entry point itself.

## NVIDIA CUDA

The portable GPU kernel layer has **run-verified bit-exact** on three real NVIDIA architectures:

| GPU | Architecture | Validation |
| --- | --- | --- |
| A100-SXM4-40GB | sm_80 (Ampere) | Bit-exact against the CPU oracle |
| L4 | sm_89 (Ada Lovelace) | Bit-exact against the CPU oracle |
| T4 | sm_75 (Turing) | Bit-exact against the CPU oracle |

Worst-case oracle deltas are **0.0** on GEMM — including zero-padded ragged tiles — and saxpy is
exact at n=65537, which is not a multiple of the kernel's block size. The measured numbers, with
full methodology, are on the [NVIDIA kernel benchmarks](../benchmarks/nvidia-kernel-benchmarks.md)
page.

The two-tier GPU gate is what scopes this lane: `-D ALGENTA_GPU` compiles in the **portable** GPU
kernels, while the Metal batched-dispatch machinery additionally requires `-D ALGENTA_METAL`. A
CUDA build therefore gets the portable kernels without the Metal-only session layer.

### LLM session layer

A **CUDA-native resident LLM session** (resident weights, v2 prefill GEMMs, CUDA-graph decode
with split-K flash-decoding) is in-tree and benchmarked against llama.cpp on A100 and L4:
prefill 3,260 vs 2,527 tok/s (F16), decode 329.8 / 318.9 vs 356.9 / 366.6, with decode bounded by
fp32 weight-streaming bandwidth on the pinned toolchain. Numbers and methodology:
[NVIDIA LLM throughput](../benchmarks/nvidia-llm-throughput.md). The shipped SDK serving path is
Metal; CI runs no GPU.

### Compile gate in CI

The `build-linux-cuda` job (in the runtime build workflow) re-proves on every run that the CUDA
lane still compiles and links — with no CUDA toolkit and no GPU on the builder: the NVPTX backend
ships inside the pinned mojo toolchain. The lane targets `sm_90` by default; override
`MOJO_BUILD_CUDA_TARGET` for your deployment fleet:

| Fleet GPU | `MOJO_BUILD_CUDA_TARGET` |
| --- | --- |
| T4 | `sm_75` |
| A100 | `sm_80` |
| L4 | `sm_89` |

### Requirements (proven on Ubuntu 22.04, GCP)

* **NVIDIA driver >= 580.** Validated at 580.173.02 and 595.71.05.
* **clang** for the external link step, and the repo's pinned Mojo toolchain resolved from the
  lockfile (mojo 1.0.0 / MAX 26.5.0).
* **Install recipe notes.** `ubuntu-drivers install --gpgpu` installs the driver but the headless
  meta package ships **without** `nvidia-smi` — install the matching `nvidia-utils-<ver>-server`
  package explicitly to get it.
* **`MODULAR_HOME` for direct `mojo` invocations.** When invoking `mojo` outside the repo's
  managed environment, point `MODULAR_HOME` at the environment's `share/max` directory
  (for example `MODULAR_HOME=<env>/share/max`, where `<env>` is the environment root).

## Unsupported architectures

**V100 / Volta (sm_70) is unsupported by the pinned toolchain** — mojo 1.0.0 / MAX 26.5.0
hard-rejects it at compile time with a constraint error:

```text title="compile error"
oss/modular/mojo/stdlib/std/gpu/host/info.mojo:2145:5: note: constraint failed: GPU architecture 'sm_70' is not supported.
```

This matches Modular's official baseline (Turing sm_75 and newer — RTX 20-series/T4, Ampere,
Hopper). The documented `MODULAR_NVPTX_COMPILER_PATH` workaround does **not** change this — it was
tested: compiling the same kernel with `--target-accelerator sm_70` produces the identical error
with and without the variable set. The constraint is enforced inside Mojo's own stdlib at compile
time, before any PTX assembler is invoked; the env var only swaps the downstream `ptxas` binary
and cannot override std's architecture allowlist. The supported range on this toolchain is
sm_52, 60/61, 75, 80, 86, 87, 89, 90(a), 100(a), 110, 120(a), 121. The floor of the CUDA lane is
therefore **Turing** — a V100 is not a validation gap, it is a toolchain constraint.

## AMD ROCm

The compile gate is in progress — MAX bundles `_miopen`/`_rocblas` — but nothing has run. ROCm is
**not yet verified**.

## Scope notes

* The CUDA-native LLM session is benchmark-verified on A100/L4
  ([NVIDIA LLM throughput](../benchmarks/nvidia-llm-throughput.md)); the shipped SDK serving path
  is Metal-only, and the CI CUDA lane is a compile gate without GPUs.
* sm_70 is a compile-time rejection, not a configuration choice.
* ROCm has no measured numbers.

## Related

* [NVIDIA kernel benchmarks](../benchmarks/nvidia-kernel-benchmarks.md) — the measured CUDA numbers behind the matrix.
* [NVIDIA LLM throughput](../benchmarks/nvidia-llm-throughput.md) — the CUDA-native LLM session raced on A100/L4.
* [Metal LLM decode](qwen3-metal-decode.md) — the Metal serving entry point.
* [Prefill (token input) throughput](../benchmarks/llm-prefill-throughput.md) — Metal, compute-bound.
* [Batched decode throughput](../benchmarks/batched-decode-throughput.md) — Metal, batched serving.
* [Runtime libraries](runtime-libraries.md) — the surface the kernels are exposed through.
