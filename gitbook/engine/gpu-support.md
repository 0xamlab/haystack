---
icon: microchip
description: GPU backend support matrix — Metal (default serve path), NVIDIA CUDA (hardware-verified kernel layer and LLM session), ROCm status, and per-lane requirements.
---

# GPU support

Metal is the default serve path in the shipped SDK. NVIDIA CUDA runs the portable kernel layer and
the resident LLM session, hardware-verified on the GPUs tabled below; its runtime wheel publishes
with the next runtime release. AMD ROCm is not verified. Install, requirements, entry points and
the verified-shape table for the NVIDIA lane are on [CUDA backend](cuda-backend.md).

## Support matrix

| Backend | Status | Verification |
| --- | --- | --- |
| Metal (Apple Silicon) | Supported. Default serve path in the shipped SDK | Full serving path on M-series hardware: resident kernels, batched dispatch, prefill, decode |
| NVIDIA CUDA | Supported. Hardware-verified kernel layer and LLM session; runtime wheel publishes with the next release | Kernels bit-exact on T4 (sm\_75), L4 (sm\_89), A100 (sm\_80); LLM session measured on A100 (sm\_80), L4 (sm\_89), H100 and H200 (sm\_90) |
| AMD ROCm | Not verified | Compile gate in progress |
| V100 / Volta (sm\_70) | Not supported | Compile-time constraint of the pinned toolchain |

## MAX hardware compatibility

The engine runs on the Modular MAX runtime; MAX's hardware compatibility matrix (vendor
documentation, max.modular.com/packages) lists, for NVIDIA, driver >= 580 with B200 tested
for serving and B300, B100, DGX Spark, H200, H100, L4, L40, A100, A10, A1000, RTX 50XX,
RTX 40XX, RTX 30XX, Jetson Orin/Thor, T4 and RTX 20XX known compatible for development;
for AMD, ROCm >= 6.3.3 (MI355X requires ROCm >= 7.0) with MI355X, MI300X and MI325X tested
for serving and MI250X plus the Radeon RX/RDNA families known compatible for development.

Algenta's own verification within that matrix: LLM session measured on A100, L4, H100 and H200
(this page); kernel layer bit-exact on T4, L4 and A100; B200 (sm\_100) and the AMD
compile gate are being exercised and land here as they clear.

## Metal (Apple Silicon)

Metal runs the full serving path: resident kernels, batched dispatch, prefill and decode.
Measured throughput:

* [Prefill (token input) throughput](../benchmarks/llm-prefill-throughput.md)
* [Decode throughput](../benchmarks/decode-throughput.md)
* [Batched decode throughput](../benchmarks/batched-decode-throughput.md)
* [Metal LLM decode](qwen3-metal-decode.md) — the SDK entry point

## NVIDIA CUDA

Install, hardware requirements, the callable entry points, the determinism gates and the
per-checkpoint verified-shape table are on [CUDA backend](cuda-backend.md).

### Kernel layer

The portable GPU kernels compile to PTX via the NVPTX backend and run bit-exact against the CPU
oracle on T4, L4 and A100 (worst-case GEMM delta 0.0 including zero-padded ragged tiles; saxpy
exact at n=65537). Measured numbers and methodology:
[NVIDIA kernel benchmarks](../benchmarks/nvidia-kernel-benchmarks.md).

Build flags: `-D ALGENTA_GPU` compiles the portable GPU kernels; `-D ALGENTA_METAL` additionally
compiles the Metal serving path. A CUDA build contains the portable kernels without the Metal
session layer.

### LLM session

The CUDA-native resident session (v2 prefill GEMMs, CUDA-graph decode with split-K
flash-decoding) is measured against llama.cpp on A100, L4 and H100: prefill 3,260 vs
2,527 tok/s (F16); decode 427.1 / 408.7 vs 356.9 / 366.6 (F16) on the A100 and 656.1 /
622.3 vs 468.3 / 525.0 (F16) on the H100 with packed-int8 weights. The same session family
carries the larger checkpoints: Qwen2.5-7B-Instruct prefill, decode and server TTFT on A100, and
Gemma-3-27B-it prefill on H200 with its serving cells on H100. Numbers and methodology:
[NVIDIA LLM throughput](../benchmarks/nvidia-llm-throughput.md) and
[NVIDIA LLM serving](../benchmarks/nvidia-llm-serving.md). Per-checkpoint shapes and hardware:
[CUDA backend](cuda-backend.md#verified-shapes).

### Compile gate in CI

The `build-linux-cuda` job compiles and links the CUDA lane on every change, without a CUDA
toolkit or GPU on the builder; it produces the
`algenta-runtime-native-linux-x86_64-cuda` artifact. Hardware verification runs on the GPUs in
the support matrix above. Default target is `sm_90`; override `MOJO_BUILD_CUDA_TARGET`:

| Fleet GPU | `MOJO_BUILD_CUDA_TARGET` |
| --- | --- |
| T4 | `sm_75` |
| A100 | `sm_80` |
| L4 | `sm_89` |
| H100, H200 | `sm_90` |

### Requirements

* NVIDIA driver >= 580 (validated at 580.173.02 and 595.71.05).
* clang for the external link step.
* The repo's pinned Mojo toolchain (mojo 1.0.0 / MAX 26.5.0), resolved from the lockfile.
* `ubuntu-drivers install --gpgpu` installs the headless driver without `nvidia-smi`; install
  the matching `nvidia-utils-<ver>-server` package for it.
* Direct `mojo` invocations outside the managed environment need
  `MODULAR_HOME=<env>/share/max`.

## Unsupported architectures

The pinned toolchain (mojo 1.0.0 / MAX 26.5.0) rejects sm\_70 at compile time:

```text title="compile error"
oss/modular/mojo/stdlib/std/gpu/host/info.mojo:2145:5: note: constraint failed: GPU architecture 'sm_70' is not supported.
```

The constraint is enforced in the Mojo stdlib before the PTX assembler runs;
`MODULAR_NVPTX_COMPILER_PATH` swaps only the downstream `ptxas` binary and does not change the
outcome (verified). Supported range: sm\_52, 60/61, 75, 80, 86, 87, 89, 90(a), 100(a), 110,
120(a), 121. This matches Modular's baseline (Turing and newer).

## AMD ROCm

MAX bundles `_miopen`/`_rocblas`; the compile gate is in progress. Nothing has run on ROCm
hardware.

## Notes

* Metal is the default serve path in the shipped SDK. The CUDA backend is hardware-verified on the
  GPUs above and its runtime wheel publishes with the next runtime release; CI compiles and links
  the CUDA lane on a builder with no GPU.
* Install, requirements, entry points and the verified-shape table for the NVIDIA lane:
  [CUDA backend](cuda-backend.md).

## Related

* [CUDA backend](cuda-backend.md)
* [NVIDIA kernel benchmarks](../benchmarks/nvidia-kernel-benchmarks.md)
* [NVIDIA LLM throughput](../benchmarks/nvidia-llm-throughput.md)
* [NVIDIA LLM serving](../benchmarks/nvidia-llm-serving.md)
* [Metal LLM decode](qwen3-metal-decode.md)
* [Prefill (token input) throughput](../benchmarks/llm-prefill-throughput.md)
* [Batched decode throughput](../benchmarks/batched-decode-throughput.md)
* [Runtime libraries](runtime-libraries.md)
