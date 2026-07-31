---
icon: gauge-high
description: How Algenta measures and publishes performance — what each benchmark claims, the baseline it is measured against, and the rules every published number follows.
---

# Benchmarks

Algenta publishes performance the same way it publishes everything else: with the configuration attached. A number without a baseline, a hardware description and a reproduction command is marketing, not measurement.

This section is the index. Each benchmark family has its own page with its own claims, baselines and results, so results can be added without rewriting what is already here.

## Published families

<table data-view="cards">
<thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Compute kernels</strong></td><td>Dense and quantized matrix kernels, measured against the engine's own prior implementations.</td><td><a href="compute-kernels.md">compute-kernels.md</a></td></tr>
</tbody>
</table>

More families are added here as they are measured. A family appears above only once it has published numbers and a reproduction command — never as a placeholder.

## The rules every number follows

These are not aspirations. They are the conditions a result has to meet before it appears on any page in this section.

{% hint style="info" %}
**Measured against the strongest available baseline, not the weakest.** A speedup over an unoptimised reference is an implementation detail. A speedup over the best thing a reader could otherwise use is a result. Each page names its baseline explicitly.
{% endhint %}

* **The baseline is named and versioned.** "Faster" is meaningless without saying "than what". Where the comparison is against Algenta's own earlier implementation, the page says so plainly rather than implying an external comparison.
* **Correctness is asserted alongside every timing.** A faster wrong answer is not a result. Every kernel benchmark diffs its output against a reference implementation and reports the difference.
* **Properties are gated, absolute times are not.** Nanoseconds vary by machine, thermal state and load. What must hold is the *shape* — cost per unit of work staying flat as the problem grows, for example. Absolute numbers are printed for tracking and are explicitly not a contract.
* **Hardware is reported, never averaged.** Results are published per chip generation and per memory configuration. A single headline number across different hardware hides the only thing a reader needs.
* **Measured after warm-up.** First-call costs — page faults on a fresh buffer, a thread pool spinning up — belong to neither implementation.
* **Reproducible.** Every page carries the command that produced its table.

## What is not published here

* Single-number claims of the form "N times faster", with no shape, no baseline and no hardware.
* A kernel-level speedup restated as an end-to-end one. A kernel result may be published as a kernel result; it becomes an end-to-end claim only when an end-to-end run demonstrates it.
* Results from a configuration a reader cannot reproduce.

## Related

* [Compute kernels](compute-kernels.md) — dense and quantized matrix kernel results.
* [Runtime libraries](../engine/runtime-libraries.md) — the surface these kernels are exposed through.
* [Runtime library catalog](../engine/runtime-library-catalog.md) — every module and function the runtime exposes.
