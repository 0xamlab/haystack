---
icon: diagram-project
description: Feed-forward and embedding kernel results — gated activation cost across three variants, the two GELU conventions and why they are not interchangeable, and embedding scatter cost.
---

# Feed-forward

Results for the gated feed-forward activations and the token embedding, forward and backward.

## Hardware

| Property | Value |
| --- | --- |
| Chip | Apple silicon, 16 physical cores |
| Precision measured | 64-bit floating point |

Results are reported for this configuration only. Other chip generations and memory configurations are published separately as they are measured, never averaged into a single figure.

## Gated activation cost

Measured over roughly one million elements:

| Activation | Total | Cost per element |
| --- | --- | --- |
| SwiGLU | 1.48 ms | 1.41 ns |
| GEGLU, tanh form | 2.78 ms | 2.65 ns |
| GEGLU, error-function form | 4.40 ms | 4.19 ns |

Cost per element across a 64x range of buffer sizes changes by **0.11x** — it falls, for the same reason it falls in the normalization kernels: the fixed cost of distributing work amortises over more elements. The gate is only that it does not rise.

| Direction | Time | Ratio |
| --- | --- | --- |
| Forward | 1.48 ms | — |
| Backward | 3.10 ms | 2.09x |

**Gradients are checked against finite differences, and the check is shown to be capable of failing.** The gate derivative of SwiGLU has a product-rule term that a careless derivation drops, leaving the derivative of a different function. Recomputing without it moves the gradient by **0.197**, far outside tolerance — so the check has teeth rather than merely passing.

## Two GELU conventions, and why the slower one exists

The error-function form costs **1.58x** the tanh form. That looks like a straightforward accuracy-for-speed trade, and it is not one.

These are treated as **different activations** by the model ecosystem. A model configuration naming `gelu` means the error-function form; configurations naming `gelu_new` or `gelu_pytorch_tanh` mean the tanh form. Measured across the range where activations actually operate, the two differ by up to **4.7e-4** — worst around an input of 2.7.

That gap is far too small to notice in any single output and far too large to ignore across a whole model. A checkpoint trained under one convention and served under the other does not fail. It produces fluent text that is quietly worse, which reads as a disappointing model rather than a configuration error.

**So Algenta does not choose for you.** The convention is an explicit parameter with no default, because defaulting would be correct for roughly half of published checkpoints and silently wrong for the rest. The difference between the two is also reported as a number, so a team deciding whether a checkpoint can be served under the other convention gets a measurement rather than an assurance.

{% hint style="warning" %}
The error-function form is accurate to about 2e-8, limited by the underlying error-function routine rather than by the kernel. It is named for the convention it implements, not described as exact. That is five orders of magnitude closer to the convention than the tanh form, which is what makes the distinction worth having — it is not a claim of bit-for-bit parity with any other framework.
{% endhint %}

`mlpk.activation`'s `mlp_gelu_agreement(lo, hi, samples)` is that measurement, callable
directly rather than read off this page:

{% tabs %}
{% tab title="Python" %}
```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

r = runtime.execute("mlpk.activation", "mlp_gelu_agreement", [-6.0, 6.0, 4801])["result"]
r["max_abs_delta"]      # 0.0004732056909777732 — the 4.7e-4 figure above
r["argmax_input"]       # 2.7 — where the two conventions disagree most
r["within_tolerance"]   # False — expected: these are different activations, not two roundings of one
```
{% endtab %}

{% tab title="TypeScript" %}
```ts
import { MojoRuntime } from "algenta-sdk";

const runtime = new MojoRuntime();

const { result } = await runtime.execute("mlpk.activation", "mlp_gelu_agreement", [
  -6.0, 6.0, 4801,
]) as { result: { max_abs_delta: number; argmax_input: number; within_tolerance: boolean } };

result.max_abs_delta;      // 0.0004732056909777732 — the 4.7e-4 figure above
result.argmax_input;       // 2.7 — where the two conventions disagree most
result.within_tolerance;   // false — expected: these are different activations, not two roundings of one
```
{% endtab %}
{% endtabs %}

The gated activation itself is `gated_ffn_fwd_flat(value, gate, n_tok, d_ff, kind)`, with
`kind` `0` for SwiGLU, `1` for the tanh GEGLU and `2` for the erf GEGLU measured above.

## Embedding

| Operation | Time |
| --- | --- |
| Gather 1,024 rows of 256 values | 0.51 ms |
| Scatter gradient into a 32,768 × 256 table | 10.1 ms |

The gradient costs **19.6x** the lookup, and the reason is visible in the shapes: the batch touched **1,024 of 32,768** rows, but the gradient is dense across all of them. The cost is set by the vocabulary, not by the batch.

That is the argument for a sparse gradient representation, quantified rather than asserted. It is deferred rather than dismissed — returning a sparse result today would push the conversion onto every caller for no saving, because nothing downstream consumes one yet.

**Reproducibility:** several tokens in a batch commonly map to the same vocabulary row, so the gradient accumulation has genuine write conflicts. Algenta splits that accumulation by column rather than by token, so every row sums in token order no matter how many cores run it. The result is **bit-identical** to a single-threaded reference across 4,096 tokens.

**Bounds:** a token identifier equal to the vocabulary size — the classic off-by-one — is rejected rather than clamped. A clamped identifier trains the wrong row and the run completes successfully, which is worse than an error.

## What is not claimed

* Any comparison against a third-party feed-forward implementation.
* That these figures represent the product's throughput at lower precision. Every number here is 64-bit; these kernels are limited by memory bandwidth, so a narrower numeric format is most of the remaining headroom.

## Related

* [Benchmarks](overview.md) — methodology and what is not published.
* [Normalization](normalization.md) — the other half of a transformer block.
* [Attention](attention.md) — attention kernel results.
* [Decode throughput](decode-throughput.md) — these kernels measured end to end, against real installed mlx-lm and llama.cpp.
* [Runtime library catalog](../engine/runtime-library-catalog.md) — every module and function, including `mlpk.activation` and `mlpk.embedding` above.
