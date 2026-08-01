---
icon: gauge-high
description: Quantized matrix-vector results — the fused NF4 path measured against expand-then-multiply, with correctness asserted against the reference kernel.
---

# Compute kernels

{% hint style="info" %}
**Baseline:** expand-then-multiply — the cost of the same computation without the fused path.
Correctness is asserted against the reference kernel before any timing is reported.
{% endhint %}

## Hardware

| Property | Value |
| --- | --- |
| Chip | Apple silicon, 16 physical cores |
| Precision measured | 64-bit floating point |

## Fused NF4 matrix-vector

A 4-bit weight is dequantized before it multiplies anything. The unfused path expands the
whole matrix and then calls a dense kernel. The fused path dequantizes inside the k-loop, so
the expanded matrix is never allocated.

| Path | Time | Peak intermediate allocation |
| --- | --- | --- |
| Fused NF4 GEMV | 0.42 ms | none |
| Expand, then multiply | 1.47 ms | 2 MB |

The fused path is 3.5x faster and does not allocate the expanded matrix. Expansion converts a
4-bit weight to a 64-bit value, so the intermediate is sixteen times the size of the weights
it is derived from.

**Correctness:** maximum elementwise difference against the reference kernel is 2.8e-14.

## Reproduce

```text title="benchmark"
mojo run benchmarks/mojo_benchmarks/bench_tensorx_and_gemm.mojo
```

The benchmark prints its own gate results. Gates check properties, not absolute times, which
vary by machine and load.

## See also

* [Benchmarks](overview.md)
* [Code retrieval quality](code-retrieval.md)
* [Runtime library catalog](../engine/runtime-library-catalog.md)
