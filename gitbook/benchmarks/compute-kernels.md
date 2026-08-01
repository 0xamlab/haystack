---
icon: microchip
description: Dense and quantized matrix kernel results — blocked GEMM and NF4 quantized matrix-vector, measured against the engine's own prior implementations with correctness asserted alongside every timing.
---

# Compute kernels

Results for the dense and quantized matrix kernels that sit under the runtime's numeric surface. Each claim below names its baseline, states the property being gated, and reports the correctness check that ran with it.

{% hint style="warning" %}
**Read the baseline before reading the numbers.** Everything on this page compares Algenta against **Algenta's own earlier implementation**. These are portability and regression figures — the engine got faster at something it already did — and they are **not** a claim about any other library.

For dense floating-point matrix multiply specifically, a tuned vendor library is the right tool and is faster than this kernel. Measured on the same Apple silicon host, a vendor GPU path reaches roughly twice the throughput of Algenta's Metal matrix kernel. Algenta's dense matrix kernels exist to be **portable, dependency-free and correct on shapes a vendor path does not cover** — not to win a dense-GEMM contest, and no number here should be quoted as if they did.

Where Algenta's kernels do lead is stated on the other pages in this section, and it is mostly **memory rather than throughput**: attention with a working set that does not grow with context, and a loss layer that never materialises the logit tensor. Those are the numbers worth quoting.
{% endhint %}

## Hardware

| Property | Value |
| --- | --- |
| Chip | Apple silicon, 16 physical cores |
| Vector width | 2 lanes at 64-bit, 4 at 32-bit, 8 at 16-bit |
| Precision measured | 64-bit floating point |

Results are reported for this configuration only. Other chip generations and memory configurations are published separately as they are measured, never averaged into a single figure.

## Dense matrix multiply

A cache-blocked kernel with vectorised inner loops, distributed across physical cores, compared against the engine's earlier single-threaded implementation on identical inputs. **This is a self-comparison, not a competitive one** — see the note above.

| Size | Blocked | Prior implementation | Ratio | Cost per operation |
| --- | --- | --- | --- | --- |
| 64 | 0.10 ms | 0.67 ms | 6.6x | 0.193 |
| 128 | 0.69 ms | 5.60 ms | 8.2x | 0.163 |
| 256 | 0.86 ms | 44.1 ms | 51.4x | 0.026 |
| 512 | 9.16 ms | 396 ms | 43.3x | 0.034 |

**The gated property is the last column, not the ratio.** Cost per operation must not grow as the problem grows — a kernel whose per-operation cost rises with size is losing its working set from cache, and a single-size measurement cannot see that. Here it *falls* by roughly 5.7x from the smallest to the largest size, which is the blocking doing its job.

The ratio widens with size for the same reason it should: the prior implementation walks one operand against the grain of memory, so it degrades once that operand stops fitting in cache, while the blocked kernel keeps its working set resident.

**Correctness:** every result is compared element by element against the prior implementation. Maximum observed difference across all sizes: **zero**. The two are not required to agree bit-for-bit — a blocked kernel sums in a different order, and floating-point addition is not associative — so the check is against a per-element tolerance derived from the magnitude of the element being judged. It happens to land exact at these sizes.

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

## Related

* [Benchmarks](overview.md) — the rules every published number follows.
* [Runtime libraries](../engine/runtime-libraries.md) — how these kernels are called.
* [Runtime library catalog](../engine/runtime-library-catalog.md) — the full module and function list.
