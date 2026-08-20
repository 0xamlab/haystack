---
icon: microchip
description: Which GPU backends Algenta runs on and how far each lane is verified — Metal run-verified end to end, CUDA run-verified for the portable kernel layer, ROCm not yet.
---

# GPU support

Algenta's GPU lanes are at different maturity stages. This page is the canonical matrix: what has
actually run on real hardware, what is compile-gated only, what the pinned toolchain refuses — and,
for each lane, exactly what the verification covers.

{% hint style="info" %}
**Scope honesty, up front.** "Run-verified" is always scoped to a lane. Metal is run-verified end
to end — the full LLM serving path included. NVIDIA CUDA is run-verified for the **portable GPU
kernel layer** on three real architectures; the flagship LLM serving path (batched-dispatch
sessions) is Metal-only today, and a CUDA-native session layer is the next engineering step. Do not
read a kernel-layer result as an LLM-serving result.
{% endhint %}

## The matrix

| Backend | Status | What has been verified |
| --- | --- | --- |
| Metal (Apple Silicon) | **RUN-verified — the production path today** | The full serving path: resident kernels, batched-dispatch sessions, prefill and decode — race-proven on real M-series hardware |
| NVIDIA CUDA | **RUN-verified for the portable kernel layer** | Bit-exact kernel runs on real T4 (sm_75), L4 (sm_89) and A100-40GB (sm_80) hardware; compile-gated in CI on every change |
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

* **No NVIDIA LLM serving yet.** The CUDA run-verification covers the portable kernel layer. The
  batched-dispatch session path — resident weights, prefill, decode — is Metal-only today; a
  CUDA-native session layer is the next engineering step.
* **No Volta.** sm_70 is a compile-time rejection, not a configuration choice.
* **No ROCm numbers.** Nothing has been measured there.

## Related

* [NVIDIA kernel benchmarks](../benchmarks/nvidia-kernel-benchmarks.md) — the measured CUDA numbers behind the matrix.
* [Metal LLM decode](qwen3-metal-decode.md) — the Metal serving entry point.
* [Prefill (token input) throughput](../benchmarks/llm-prefill-throughput.md) — Metal, compute-bound.
* [Batched decode throughput](../benchmarks/batched-decode-throughput.md) — Metal, batched serving.
* [Runtime libraries](runtime-libraries.md) — the surface the kernels are exposed through.
