---
icon: arrows-rotate
description: Getting the same answer twice — chunk-invariant reductions, one canonical spelling for every float, and a replay manifest that says whether two runs were really the same run.
---

# Reproducibility

"Did I get the same answer?" has three separate failure modes, and they need three separate answers. A result can differ because the arithmetic was grouped differently, because the *text* of the number differs while the number does not, or because the two runs were not actually comparable in the first place.

## Chunk-invariant reductions

Floating-point addition is not associative, so a sum that divides its work differently returns a different number for identical input. Measured on one array: **11 different chunkings produced 8 distinct `Float64` results.**

`determinism.reduce_det` fixes the tree shape from the element count alone, so the grouping cannot vary:

| Function | Answers |
| --- | --- |
| `det_sum(a, n)` | sum, with a fixed reduction tree |
| `det_sum_chunked(a, n, chunk)` | the same sum, computed in chunks — and the same bits |
| `det_mean(a, n)` | mean over the same tree |
| `det_dot(a, b, n)` | dot product |
| `det_sum_squares(a, n)` | sum of squares |
| `det_tree_depth(n)` | the tree depth for a count, so the shape is inspectable |
| `reduction_shape_id()` | identifies the shape itself, so a change to it is visible |

Every one returns a `DetReduction`, which reports **absence** distinctly from zero: a rejected input has no answer, while the sum of an empty array is `0` and is present.

{% hint style="info" %}
**Invariance and accuracy are different properties, and no single reduction has both.** The compensated `neumaier` path recovers exact answers where the fixed tree cannot — and is itself *not* chunk-invariant. Choosing a reduction means choosing which property the job needs. Both are measured, and the cases where each one fails are asserted in the kernel's own suite.
{% endhint %}

## One canonical spelling for a float

Two runs can produce the identical `Float64` and still disagree, because the same number has many correct decimal spellings and different languages pick different ones. `canonical.float_repr` picks exactly one:

| Function | Answers |
| --- | --- |
| `canonical_float(v)` | the one canonical decimal text for `v` |
| `float_text(v)` | the text plus whether the round trip and shortest-ness were *proved*, not assumed |
| `round_trips(v, text)` | whether that text names `v` and no other double |
| `canonical_float_texts(values)` | the same, elementwise |
| `float_class(v)` / `float_class_name(code)` | finite, NaN, +Inf or -Inf as a code and a name |
| `hash_aligned_float(v)` | the spelling to use when the value is about to be **hashed** |

Two deliberate decisions worth knowing before relying on this:

* **Non-finite values render as `null`, never as a number.** JSON has no NaN or infinity, and emitting a bare `nan` token produces a document that strict parsers reject. The NaN/`+Inf`/`-Inf` distinction is preserved in `float_class` instead of being smuggled into the value.
* **`-0.0` keeps its sign in text, and loses it for hashing.** Text has to be bit-faithful; hashing has to be equality-faithful, and `-0.0 == 0.0`. `hash_aligned_float` is the single named place those two policies meet, so the trap — text equality is not a proxy for hash equality — has one home rather than being rediscovered.

## Replay manifests

The third failure mode is comparing two runs that were never comparable. `determinism.manifest` records what a run *was*, and answers whether two of them match:

| Function | Answers |
| --- | --- |
| `manifest_build(...)` | a manifest from a run's declared inputs |
| `manifest_digest(m)` | its digest, over the canonical encoding |
| `manifest_same_run(a, b)` | whether two runs are the same run |
| `manifest_field_names()` / `manifest_derived_field_names()` | which fields are declared, and which are derived from them |
| `manifest_perturb_field(m, field)` | a copy with one field changed — so a caller can check that the digest actually notices |

`manifest_perturb_field` exists for testing the digest rather than trusting it: if changing a field does not change the digest, that field is not really covered.

## What this does not do

* It does not make an existing kernel deterministic. Kernels that draw on process-global randomness are declared as such rather than silently changed; the reproducible equivalents are separate functions.
* It does not make two different *machines* agree on a transcendental function. The guarantee here is about grouping and spelling, not about libm.
* It does not version your data. A manifest says two runs declared the same inputs; it cannot tell you the file behind a path was rewritten.

## Related

* [Columnar queries](columnar-queries.md) — the query surface that shares the canonical encoding.
* [Batched and chained execution](coarse-execution.md) — plan hashes, which are built on the canonical form described here.
* [Declared capabilities](capabilities.md) — how a kernel declares determinism and seed requirements.
