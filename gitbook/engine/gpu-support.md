---
icon: microchip
description: GPU backend support matrix — Metal (production serving), NVIDIA CUDA (kernel layer and LLM session benchmarks), ROCm status, and per-lane requirements.
---

# GPU support

Algenta serves on Apple Metal. NVIDIA CUDA runs the portable kernel layer and the LLM session
benchmarks. AMD ROCm is not verified.

## Support matrix

| Backend | Status | Verification |
| --- | --- | --- |
| Metal (Apple Silicon) | Supported. Production serving path | Full serving path on M-series hardware: resident kernels, batched dispatch, prefill, decode |
| NVIDIA CUDA | Kernel layer supported. LLM session benchmarked | Kernels bit-exact on T4 (sm\_75), L4 (sm\_89), A100 (sm\_80); LLM session benchmarked on A100 and L4 |
| AMD ROCm | Not verified | Compile gate in progress |
| V100 / Volta (sm\_70) | Not supported | Compile-time constraint of the pinned toolchain |

## Metal (Apple Silicon)

Metal runs the full serving path: resident kernels, batched dispatch, prefill and decode.
Measured throughput:

* [Prefill (token input) throughput](../benchmarks/llm-prefill-throughput.md)
* [Decode throughput](../benchmarks/decode-throughput.md)
* [Batched decode throughput](../benchmarks/batched-decode-throughput.md)
* [Metal LLM decode](qwen3-metal-decode.md) — the SDK entry point

## NVIDIA CUDA

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
flash-decoding) is benchmarked against llama.cpp on A100 and L4: prefill 3,260 vs 2,527 tok/s
(F16); decode 329.8 / 318.9 vs 356.9 / 366.6. Numbers and methodology:
[NVIDIA LLM throughput](../benchmarks/nvidia-llm-throughput.md).

### Compile gate in CI

The `build-linux-cuda` job compiles and links the CUDA lane on every change, without a CUDA
toolkit or GPU on the builder. Default target is `sm_90`; override `MOJO_BUILD_CUDA_TARGET`:

| Fleet GPU | `MOJO_BUILD_CUDA_TARGET` |
| --- | --- |
| T4 | `sm_75` |
| A100 | `sm_80` |
| L4 | `sm_89` |

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

* The shipped SDK serving path is Metal. The CUDA LLM session is benchmark-verified on the
  hardware above; CI runs no GPU.

## Related

* [NVIDIA kernel benchmarks](../benchmarks/nvidia-kernel-benchmarks.md)
* [NVIDIA LLM throughput](../benchmarks/nvidia-llm-throughput.md)
* [Metal LLM decode](qwen3-metal-decode.md)
* [Prefill (token input) throughput](../benchmarks/llm-prefill-throughput.md)
* [Batched decode throughput](../benchmarks/batched-decode-throughput.md)
* [Runtime libraries](runtime-libraries.md)
