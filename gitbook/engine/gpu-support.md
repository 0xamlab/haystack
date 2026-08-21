---
icon: microchip
description: Which GPU backends Algenta runs on and how far each lane is verified — Metal end to end, CUDA kernel layer run-verified and LLM session race-verified on A100/L4, ROCm not yet.
---

# GPU support

Algenta's GPU lanes are at different maturity stages. This page is the canonical matrix: what has
actually run on real hardware, what is compile-gated only, what the pinned toolchain refuses — and,
for each lane, exactly what the verification covers.

{% hint style="info" %}
**Scope honesty, up front.** "Run-verified" is always scoped to a lane. Metal is run-verified end
to end — the full LLM serving path included, and it remains the production serving lane. NVIDIA
CUDA is run-verified for the **portable GPU kernel layer** on three real architectures, and the
CUDA-native resident LLM session has been **race-measured** on real A100 and L4 hardware (fixture
prefill 1.29x llama.cpp F16; decode 0.92x at the f32 bandwidth floor) — but it is not a shipped
serving path, and CI's CUDA lane stays compile-gated. Do not read a kernel-layer result as an
LLM-serving result, or a race measurement as a serving guarantee.
{% endhint %}

## The matrix

| Backend | Status | What has been verified |
| --- | --- | --- |
| Metal (Apple Silicon) | **RUN-verified — the production path today** | The full serving path: resident kernels, batched-dispatch sessions, prefill and decode — race-proven on real M-series hardware |
| NVIDIA CUDA | **RUN-verified for the portable kernel layer; LLM session race-measured** | Bit-exact kernel runs on real T4 (sm_75), L4 (sm_89) and A100-40GB (sm_80) hardware; the CUDA-native resident LLM session raced on A100/L4 (prefill 1.29x llama.cpp F16, decode 0.92x at its floor); compile-gated in CI on every change |
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

Bit-exact means bit-exact: worst-case oracle deltas of **0.0** on GEMM — including zero-padded
ragged tiles — and saxpy exact at n=65537, which is not a multiple of the kernel's block size. The
measured numbers, with full methodology, are on the
[NVIDIA kernel benchmarks](../benchmarks/nvidia-kernel-benchmarks.md) page.

The two-tier GPU gate is what scopes this lane: `-D ALGENTA_GPU` compiles in the **portable** GPU
kernels, while the Metal batched-dispatch machinery additionally requires `-D ALGENTA_METAL`. A
CUDA build therefore gets the portable kernels without the Metal-only session layer.

### LLM session layer (race-measured, not a shipped serving path)

Beyond the portable kernel layer, a **CUDA-native resident LLM session** now exists in-tree
(resident weights, v2 prefill GEMMs, CUDA-graph decode with split-K flash-decoding) and has been
raced head-to-head against llama.cpp on real A100 and L4 hardware under the campaign's frozen
discipline: fixture prefill **1.29x** llama.cpp F16 (a win), decode **0.92x / 0.87x** at the
measured f32 weight-streaming bandwidth floor (the f16/int8 arms that would close it are
toolchain-blocked). Every number is oracle-gated and stated with its caveats on the
[NVIDIA LLM throughput](../benchmarks/nvidia-llm-throughput.md) page. This is a race measurement on
spot hardware — the production SDK serving path remains Metal, and no GPU runs in CI.

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
**not yet verified**; treat it as not available until this table says otherwise.

## What is not claimed

* **No NVIDIA LLM *serving*.** The CUDA-native LLM session is race-measured on spot A100/L4
  hardware (see [NVIDIA LLM throughput](../benchmarks/nvidia-llm-throughput.md)), but the shipped
  SDK serving path is Metal-only, and CI's CUDA lane is a compile gate without GPUs.
* **No Volta.** sm_70 is a compile-time rejection, not a configuration choice.
* **No ROCm numbers.** Nothing has been measured there.

## Related

* [NVIDIA kernel benchmarks](../benchmarks/nvidia-kernel-benchmarks.md) — the measured CUDA numbers behind the matrix.
* [NVIDIA LLM throughput](../benchmarks/nvidia-llm-throughput.md) — the CUDA-native LLM session raced on A100/L4.
* [Metal LLM decode](qwen3-metal-decode.md) — the Metal serving entry point.
* [Prefill (token input) throughput](../benchmarks/llm-prefill-throughput.md) — Metal, compute-bound.
* [Batched decode throughput](../benchmarks/batched-decode-throughput.md) — Metal, batched serving.
* [Runtime libraries](runtime-libraries.md) — the surface the kernels are exposed through.
