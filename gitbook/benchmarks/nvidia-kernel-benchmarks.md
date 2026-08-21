---
icon: gauge-high
description: One portable FP32 kernel, unmodified, measured on NVIDIA T4, L4 and A100 — GEMM and saxpy with bit-exact validation; percentages are against spec-sheet peaks.
---

# NVIDIA kernel benchmarks

This page measures the **same portable kernel, unmodified, across three NVIDIA architectures** —
the portable GPU kernel layer whose run-verification sits in the
[GPU support matrix](../engine/gpu-support.md): identical code on different hardware, with
correctness asserted before any timing (worst-case oracle deltas of 0.0 on GEMM including
zero-padded ragged tiles; saxpy exact at n=65537, a size that is not a multiple of the kernel's
block size).

{% hint style="info" %}
**Configuration.** One unmodified portable validation kernel on all three GPUs. Percentages are
ratios against each chip's own spec-sheet peak, not against tuned vendor libraries.
{% endhint %}

## Results

FP32 GEMM (square, sizes 512-4096) and saxpy (64M elements), on T4, L4 and A100. Each cell in the
GEMM columns is *time / achieved GFLOPS*. Median of 3 timed runs after warmup; the timing wraps
only kernel enqueue + synchronize. The same unmodified portable 32x32 tile / 2x2-register kernel
runs on all three GPUs — nothing is retuned per chip.

| GPU (arch) | FP32 peak / mem BW | GEMM 512 | GEMM 1024 | GEMM 2048 | GEMM 4096 | %peak @4096 | saxpy 64M GB/s | %BW peak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A100-SXM4-40GB (sm_80) | 19.5 TF / 1555 GB/s | 0.756 ms / 354.8 GF | 4.753 ms / 451.9 GF | 34.898 ms / 492.3 GF | 211.56 ms / 649.6 GF | 3.3% | 1341.8 | 86.3% |
| L4 (sm_89) | 30.3 TF / 300 GB/s | 1.036 ms / 259.0 GF | 7.176 ms / 299.2 GF | 55.943 ms / 307.1 GF | 454.48 ms / 302.4 GF | 1.0% | 234.1 | 78.0% |
| T4 (sm_75) | 8.1 TF / 320 GB/s | 3.434 ms / 78.2 GF | 25.183 ms / 85.3 GF | 93.079 ms / 184.6 GF | 747.56 ms / 183.9 GF | 2.3% | 256.4 | 80.1% |

Peak values are the published spec-sheet figures (FP32 TFLOPS and memory bandwidth), so every
"%peak" column is a ratio against the chip's own ceiling, not against another GPU.

### Why the percent-of-peak is low

The kernel is the portable validation tile (32x32, 2x2 register block) compiled unmodified per
chip; no per-architecture tuning is applied, so percent-of-peak reflects the validation kernel.
Optimized NVIDIA kernels are measured against this baseline.

### Validation behind the table

Correctness gates the benchmarks: no timing is reported from a kernel that failed its oracle diff.

* **GEMM:** bit-exact against the CPU oracle — worst-case delta **0.0**, on both the 256^3 cube
  and the zero-padded ragged 100x140x84 shape (the tile-edge case a padded destination produces).
* **saxpy:** exact at n=65537 — deliberately not a multiple of the block size, so the tail path is
  what ran.

### Reading the numbers

* **GEMM orders A100 > L4 > T4 at every size.** Bandwidth ratios measured close to theory:
  A100/T4 5.3x measured vs 4.9x theoretical, A100/L4 5.7x measured vs 5.2x theoretical.
* **saxpy orders A100 > T4 > L4**, following the spec sheet: T4's 320 GB/s GDDR6 (256-bit)
  exceeds L4's 300 GB/s (192-bit). Both deliver ~79-86% of their own bandwidth peak.
* **T4's large-size numbers are at its power-limited steady clock**: 1215-1230 MHz of a 1590 MHz
  maximum, at 69 W of a 70 W board limit; L4 and A100 ran at max clocks under load. Clocks were
  sampled concurrently with the timed regions.

## Method

* **What is timed.** Kernel enqueue + synchronize only — no host-side conversion, no allocation,
  no framework. Median of 3 timed runs after warmup; medians, not minimums, because a best-of-N
  hides contention.
* **The kernel.** One portable FP32 32x32 tile / 2x2-register kernel, compiled once per chip from
  the same source, unmodified across all three GPUs.
* **Correctness.** Oracle diffs (above) run before any timing at each shape.
* **Environment.** NVIDIA driver 595.71.05 on all three machines, CUDA 13.2 reported, Ubuntu
  22.04 GCP spot VMs (spot capacity us-central1), mojo 1.0.0 / MAX 26.5.0 from the repo lock.

## Scope

* Percent-of-peak reflects the validation kernel, not a tuned-kernel ceiling.
* These are kernel-layer results. LLM-serving numbers are on
  [NVIDIA LLM throughput](nvidia-llm-throughput.md); lane-by-lane scope is on the
  [GPU support matrix](../engine/gpu-support.md).
* V100 (sm\_70) is rejected at compile time by the pinned toolchain; the CUDA floor is Turing —
  see [Unsupported architectures](../engine/gpu-support.md#unsupported-architectures).

## Reproduce

The compile gate is reproducible today, with no GPU, exactly as CI runs it:

```bash title="compile gate (no GPU needed)"
BUILD_VARIANT=cuda bash .github/scripts/build_runtime_linux_amd64.sh
```

The measurement itself needs a CUDA host (driver >= 580, per the
[GPU support requirements](../engine/gpu-support.md#requirements-proven-on-ubuntu-2204-gcp)) and a
runtime built with the CUDA knobs — `MOJO_BUILD_CUDA_GPU=1` and
`MOJO_BUILD_CUDA_TARGET` set to the fleet's architecture (`sm_75` / `sm_80` / `sm_89`). The
harness drives the portable GEMM and saxpy kernels through the same launch seam with the protocol
above: oracle diff first, then warmup, then median-of-3 timings wrapping enqueue + synchronize
only. The cross-GPU sweep uses the same kernel, protocol and knobs; a packaged sweep script
ships separately.

## Related

* [GPU support](../engine/gpu-support.md) — the matrix these numbers verify, lane by lane.
* [NVIDIA LLM throughput](nvidia-llm-throughput.md) — the CUDA-native LLM session raced on A100/L4.
* [Compute kernels](compute-kernels.md) — the Metal-side kernel measurements.
* [Prefill (token input) throughput](llm-prefill-throughput.md) — the production Metal path end to end.
* [Batched decode throughput](batched-decode-throughput.md) — batched serving on Metal.
* [Benchmarks](overview.md) — methodology.
