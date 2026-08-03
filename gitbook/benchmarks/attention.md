---
icon: layer-group
description: Attention kernel results — tiled attention memory against sequence length, rotary embedding cost, and the correctness checks that ran alongside every timing.
---

# Attention

Results for the attention kernels: tiled attention, rotary position embedding, and the masks that go with them. Every number below names the property being gated and the correctness check that ran with it.

{% hint style="info" %}
**The headline claim on this page is about memory, not speed.** A tiled attention kernel exists so that a long context never allocates the full score matrix. At short sequence lengths it is not meaningfully faster than the direct form, and this page says so rather than selecting a size where it looks better.
{% endhint %}

## Hardware

| Property | Value |
| --- | --- |
| Chip | Apple silicon, 16 physical cores |
| Precision measured | 64-bit floating point |
| Attention shape | Grouped-query, multiple query heads sharing each key/value head |

Results are reported for this configuration only. Other chip generations and memory configurations are published separately as they are measured, never averaged into a single figure.

## Working set against context length

The direct form of attention builds a score matrix of `sequence × sequence` values per head. The tiled form never holds more than one block of it. Measured at a fixed block size:

| Sequence | Tiled working set | Direct working set | Ratio |
| --- | --- | --- | --- |
| 64 | 32,768 bytes | 32,768 bytes | 1x |
| 128 | 32,768 bytes | 131,072 bytes | 4x |
| 256 | 32,768 bytes | 524,288 bytes | 16x |

**The gated property is that the tiled column does not move.** It is constant because the block size is held constant for this measurement; the ratio grows quadratically because the direct form does. Extrapolated to a 32,768-token context the direct form would need roughly **8.6 GB** for what the tiled form holds in 262,144 bytes.

That extrapolation is arithmetic on the shape, not a measurement, and is labelled as such.

**Cost per cell** across the same range grows by **0.97x** — that is, it does not grow. The gate is that it stays under 3x, because a tiled kernel that recomputes more than it saves would show up here as rising per-cell cost.

## Correctness of the tiled form

The tiled kernel is only useful if it agrees with the direct one. Both were run on identical inputs:

| Quantity | Maximum difference |
| --- | --- |
| Attention output | 2.4e-14 |
| Log-sum-exp per row | 1.5e-13 |

The log-sum-exp is checked as well as the output because it is the more sensitive of the two: it depends on every score in a row, where the output is a weighted average in which errors can cancel.

**Block-size invariance:** the same input processed in 9,216 small blocks and in 192 large ones produces **bit-identical** output. A tiled kernel whose answer depends on its block size is not usable for reproducible training, so this is asserted rather than assumed.

## Rotary position embedding

| Positions | Cost per cell |
| --- | --- |
| 256 | 15.6 ns |
| 1,024 | 14.8 ns |
| 4,096 | 17.3 ns |

Per-cell cost grows **1.11x** across a 16x increase in positions, against a gate of 3x.

**Correctness:** a rotation is its own inverse when applied backwards, so the check is a round trip rather than a table of expected values. Maximum error after applying and un-applying: **3.3e-16**. That single property catches a wrong dimension pairing, a wrong sign and a wrong table index at once — three faults that each produce a model which runs and is quietly wrong.

## A note on two conventions

Position embeddings can be extended to longer contexts under more than one convention, and they disagree — extending a 2,048-position model to 8,192 gives a scaling factor of either 160,000 or 40,000 depending on which is used. Both appear in real model configurations.

Algenta does not pick one silently. The convention is selected explicitly, and the difference between the two is reported as a number rather than resolved behind the caller's back. A model loaded under the wrong convention does not fail; it produces fluent text that degrades as the context grows, which reads as a disappointing model rather than a configuration error.

`attnk.rope`'s `rope_theta_agreement(base, original_context, target_context)` is exactly that
report, callable directly:

{% tabs %}
{% tab title="Python" %}
```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

r = runtime.execute("attnk.rope", "rope_theta_agreement", [10000.0, 2048.0, 8192.0])["result"]
r["squared_convention"]   # 160000.0
r["linear_convention"]    # 40000.0
r["ratio"]                 # 4.0
r["agree"]                 # False — a real 4x disagreement, not rounding noise
```
{% endtab %}

{% tab title="TypeScript" %}
```ts
import { MojoRuntime } from "algenta-sdk";

const runtime = new MojoRuntime();

const { result } = await runtime.execute("attnk.rope", "rope_theta_agreement", [
  10000.0, 2048.0, 8192.0,
]) as { result: { squared_convention: number; linear_convention: number; ratio: number; agree: boolean } };

result.squared_convention;   // 160000.0
result.linear_convention;    // 40000.0
result.ratio;                 // 4.0
result.agree;                 // false — a real 4x disagreement, not rounding noise
```
{% endtab %}
{% endtabs %}

## What is not claimed

* That tiled attention is faster than direct attention at short sequence lengths. Measured at a size where both fit in cache, the two are within 2% of each other, and that is reported above rather than omitted.
* Any comparison against a third-party attention implementation. These are Algenta's own kernels measured against Algenta's own direct form.

## Related

* [Benchmarks](overview.md) — methodology and what is not published.
* [Compute kernels](compute-kernels.md) — the matrix kernels attention is built on.
* [Normalization](normalization.md) — the layer norms that surround attention in a transformer block.
* [Decode throughput](decode-throughput.md) — this kernel measured end to end, against real installed mlx-lm and llama.cpp.
* [Runtime library catalog](../engine/runtime-library-catalog.md) — every module and function, including `attnk.rope`, `attnk.flash`, `attnk.sdpa` and `attnk.mask` above.
