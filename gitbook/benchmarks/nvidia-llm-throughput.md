---
icon: gauge-high
description: Qwen3-0.6B-Base vs llama.cpp on NVIDIA A100 and L4 — fixture prefill won 1.29x with the v2 GEMM family; decode at 0.92x of F16, on the measured f32 bandwidth floor.
---

# NVIDIA LLM throughput

This page is the LLM-serving half of the NVIDIA story — the CUDA-native resident session
(resident weights, prefill, decode, CUDA-graph generation) raced head-to-head against
llama.cpp on two real GPUs, an A100-SXM4-40GB and an L4. The portable-kernel half lives on
[NVIDIA kernel benchmarks](nvidia-kernel-benchmarks.md); the lane-by-lane verification matrix
is [GPU support](../engine/gpu-support.md).

{% hint style="success" %}
**Prefill won.** On the A100, the v2 register-blocked / double-buffered GEMM family prefills the
256-token race fixture at **3,260 tok/s vs llama.cpp F16's 2,527 — 1.29x**, from a 0.19x starting
point one kernel generation earlier.
{% endhint %}

{% hint style="warning" %}
**Decode did not win — and the page says exactly why.** The final CUDA-graph + split-K decode arm
measures **329.8 / 318.9 tok/s vs llama.cpp F16's 356.9 / 366.6 = 0.92x / 0.87x**. The residual gap
is weight-format bandwidth, measured and diagnosed: algenta races Float32 weights (2.62 GB/token)
and sits at 86% of the f32 bandwidth floor; the f16/int8 arms that would halve the traffic are
built and oracle-verified but toolchain-blocked (below).
{% endhint %}

## Results — A100-SXM4-40GB

256-token fixture, greedy, f32 weights, 20 runs per cell, median, rel-IQR <= 5% (all PASS; final
decode medians carry 0.022% / 0.007%). llama.cpp pinned at 000547513f with GGML_CUDA, raced on the
same VM.

| Engine / format | Prefill tok/s (256) | Decode gen=64 | Decode gen=256 |
| --- | --- | --- | --- |
| **Algenta f32, v2 GEMMs** | **3,260** (IQR 0.039%) | 70.8 (per-dispatch) | 55.8 (per-dispatch) |
| **Algenta f32, v2 + CUDA-graph decode** | — | **329.8** | **318.9** |
| llama.cpp F16 | 2,527 | 356.9 | 366.6 |
| llama.cpp Q8_0 | 13,028 | 404.2 | 419.8 |

Head-to-head vs the F16 control: **prefill 1.29x (a win)**, decode 0.92x / 0.87x. The per-dispatch
row is the baseline path; the graph row is the campaign's final decode arm (4.6x over the 71.0
tok/s starting point: CUDA-graph capture/replay, warp-shuffle attention reduction, split-K
flash-decoding at N_SPLITS=32, plateau measured).

## Results — L4

Same fixture and discipline on g2-standard-8 (sm_89). llama-bench warm references: F16 pp256
7,555 / tg128 176.8; Q8_0 pp256 11,247 / tg128 277.4.

| Engine / format | Prefill tok/s (256) | Decode gen=64 | Decode gen=256 |
| --- | --- | --- | --- |
| Algenta f32, per-dispatch | 271.4 | 53.9 | 46.6 |
| Algenta f32, CUDA-graph decode | 262.1 | 98.1 | 97.2 |
| llama.cpp F16 | 2,165 (cold) | 171.3 | 172.6 |
| llama.cpp Q8_0 | 13,438 (cold) | 263.2 | 268.3 |

The L4 is the cleaner proof of what the decode gap is: algenta f32 streams 2.62 GB/token against
the L4's 300 GB/s — a ~114 tok/s floor — and measures 98 = **86% of its own f32 bandwidth floor**.
llama.cpp F16 streams 1.31 GB/token (floor ~229) and measures 171. The 0.57x ratio is the 2x
weight bytes, i.e. the format gap the blocked f16 arm would close — not a kernel-efficiency gap.

## What makes the prefill win

* **Register-blocked, double-buffered v2 GEMMs** (`residentk/kernels_prefill_f32_v2.mojo`): a
  4x4 accumulator block on a 64x64 output tile (16 FMAs per 8 shared loads per k-step, 2:1 vs the
  first generation's 1:1), one barrier per k-step serving both pipeline directions, exactly one
  128-bit `float4` load per thread per tile, and bank-conflict-aware shared layouts.
* **Kernel sweep:** layer GEMM sum 9,550 us -> 968 us (9.9x); the wide roles reach 29-38% of the
  A100's 19.5 TFLOP/s FP32 SIMT peak.
* **Bit-exact by construction:** v2 vs the oracle-verified first generation is max-diff 0.0 on
  every role, ragged m_rows included — same k-ascending accumulation order.
* **The arithmetic ceiling is measured, not assumed:** an FMA-chain probe with an ncu
  executed-FFMA hardware witness puts f32 SIMD at 17.6 TFLOP/s = 90% of nominal peak, so the
  remaining gap is shared-memory traffic and grid fill, not arithmetic.

## Why decode stops at 0.92x — stated plainly

* **Only Float32 vector loads stream at HBM speed** in the pinned Mojo 1.0.0 / MAX 26.5 CUDA
  backend. The probe battery (committed under `benchmarks/llm_smoke/nvidia_race/`) measured f16
  loads at 4-7% of peak, int8 at 1-1.6%, even Int32 SIMD at ~2% — every sub-f32 load path is
  scalarized. The built-and-oracle-verified f16 session therefore measured 3x *slower* than f32.
* **No tensor-core surface is routeable from Mojo user code** on this toolchain (15 compile
  probes: no mma/tma module, no inline-asm escape hatch), so llama.cpp's warm FP16-tensor-core
  prefill has no counterpart here.
* Both gaps are **upstream of this repo**; the f16 session stays in-tree, race-ready for the day
  the backend load paths are fixed.

## Method

* **Checkpoint / prompt.** `Qwen/Qwen3-0.6B-Base`, real Hugging Face checkpoint; the fixed
  256-token race fixture; greedy (temperature 0).
* **Opponent.** llama.cpp pinned at 000547513f, built with GGML_CUDA, raced on the same VM;
  fixture prefill via `llama-completion -no-cnv`, warm references via llama-bench.
* **Statistics.** 20 runs per cell, median, rel-IQR <= 5%; a 16/16 greedy-token oracle passed
  before any number counted; and the stale-binary rule — after building an optimization arm, the
  bench number must demonstrably move over baseline before it is trusted (the oracle alone cannot
  catch a no-op build).
* **Hardware.** GCP spot VMs: a2-highgpu-1g (A100-SXM4-40GB) and g2-standard-8 (L4), driver
  595.71.05, Ubuntu 22.04, mojo 1.0.0 / MAX 26.5.0. Clocks sampled concurrently with the timed
  regions; no throttle involvement in any number.

## What is not claimed

* **No warm-vs-warm prefill win.** Each `llama-completion` fixture prefill is that process's
  first; the warm-vs-warm view is llama-bench (F16 pp256 = 14,101 tok/s on FP16 tensor cores —
  algenta's 3,260 is 0.23x of that). The 1.29x is the like-for-like fixture race, stated with the
  asymmetry carried, not hidden.
* **No Q8_0 win.** Quantized formats halve weight traffic; the CUDA quantized arms are
  toolchain-blocked (above), so the Q8_0 rows (13,028 prefill / 404-420 decode) lead and are
  reported as-is.
* **No decode win.** 0.92x / 0.87x vs F16 is the result, at a measured floor — not a win and not
  presented as one.
* **One checkpoint.** Qwen3-0.6B-Base; the session derives shapes from the checkpoint's dims but
  the race numbers are this model's.
* **Not a shipped serving path.** The CUDA-native session is race-verified on spot hardware; the
  production SDK serving path remains Metal, and CI's CUDA lane is compile-gated (no GPU on the
  builder). See [GPU support](../engine/gpu-support.md).

## Related

* [NVIDIA kernel benchmarks](nvidia-kernel-benchmarks.md) — the portable-kernel layer on T4/L4/A100.
* [GPU support](../engine/gpu-support.md) — the verification matrix.
* [Prefill (token input) throughput](llm-prefill-throughput.md) — the Metal prefill race.
* [Decode throughput](decode-throughput.md) — the Metal single-stream race.
* [LLM inference overview](llm-inference-overview.md) — prefill + decode together on Apple silicon.
* [Benchmarks](overview.md) — methodology and what is not published.
