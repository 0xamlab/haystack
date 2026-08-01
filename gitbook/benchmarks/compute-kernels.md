---
icon: microchip
description: Quantized matrix-vector results — the fused NF4 path against expanding weights first, with the memory it never allocates.
---

# Compute kernels

Results for the dense and quantized matrix kernels that sit under the runtime's numeric surface. Each claim below names its baseline, states the property being gated, and reports the correctness check that ran with it.

{% hint style="info" %}
**Baseline:** Algenta's previous implementation. These are regression figures, not a comparison with another library.
{% endhint %}

## Hardware

| Property | Value |
| --- | --- |
| Chip | Apple silicon, 16 physical cores |
| Vector width | 2 lanes at 64-bit, 4 at 32-bit, 8 at 16-bit |
| Precision measured | 64-bit floating point |

Results are reported for this configuration only. Other chip generations and memory configurations are published separately as they are measured, never averaged into a single figure.

## Quantized matrix-vector

The 4-bit quantized path reconstructs each weight inside the reduction loop rather than expanding the whole matrix first. The comparison is against expanding it first and then multiplying — the obvious implementation, and the one this kernel exists to avoid.

| Approach | Time | Peak extra memory |
| --- | --- | --- |
| Fused reconstruction | 0.42 ms | one block |
| Expand, then multiply | 1.47 ms | full expanded matrix |
| **Ratio** | **3.5x** | |

At the measured size the expanded matrix is 2 MB that the fused path never allocates. The saving grows with the model: expansion turns a 4-bit weight into a 64-bit one, so the expanded form is sixteen times the size of what was stored.

Two things make the fused path faster rather than merely smaller, and both were found by measurement rather than design:

* **One division per block, not per weight.** Locating a weight's scale requires an integer division. Doing it per weight cost more than the memory traffic the whole approach exists to reduce; hoisting it to once per block is what turned a loss into a win.
* **The scale multiplies once per block.** Accumulating the block first and scaling the partial sum removes a multiply per weight.

**Correctness:** compared against the expand-then-multiply path element by element, within a tolerance built from each result's own magnitude and the length of the reduction that produced it. Maximum observed difference: **2.8e-14**, against a tolerance several orders of magnitude larger. The difference is non-zero because hoisting the scale re-associates the arithmetic; it is one unit in the last place, not a behavioural change.

## Quantization throughput

| Elements | Cost per element |
| --- | --- |
| 4,096 | 80.3 |
| 16,384 | 36.1 |
| 65,536 | 31.8 |

The gated property is that cost per element does not grow with size — a quantizer that rescanned the whole input for each block would. It falls here, which is fixed setup cost being amortised across more elements.

## Reproducing these numbers

Every table on this page comes from one command:

```text title="benchmark"
mojo run benchmarks/mojo_benchmarks/bench_tensorx_and_gemm.mojo
```

The benchmark prints its own gate results. It fails on the properties described above — not on absolute times, which vary by machine, thermal state and concurrent load. If you reproduce it, expect the ratios to move and the shapes to hold.

## Reading these results honestly

{% hint style="warning" %}
These are **kernel-level** measurements. A kernel-level ratio is not an end-to-end ratio, and this page does not claim one. How much a faster kernel moves a complete workload depends entirely on what fraction of that workload the kernel occupies — a kernel that is ten times faster but accounts for a tenth of total time moves the total by well under half.
{% endhint %}

End-to-end results are published separately, measured end to end, when they exist.

## What was withdrawn from this page

The dense floating-point GEMM figures are gone. Two defects, pointing the same way:

* The baseline was `linalg.mat_mul`, which the benchmark source itself calls "the frozen naive
  kernel" — a naive triple loop. A cache-hostile baseline inflates a ratio.
* Every timing was a **single call**. Eight timing sites, no repetition, no minimum over runs, on
  a machine whose load the page never reported.

So the largest number on the page carried the weakest sampling on it. They return when they are
measured against NumPy on Accelerate, with a minimum over repetitions and the load recorded.

## Related

* [Benchmarks](overview.md) — the rules every published number follows.
* [Runtime libraries](../engine/runtime-libraries.md) — how these kernels are called.
* [Runtime library catalog](../engine/runtime-library-catalog.md) — the full module and function list.
