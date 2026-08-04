---
icon: gauge-high
description: How Algenta measures and publishes performance — what each benchmark claims, the baseline it is measured against, and the rules every published number follows.
---

# Benchmarks

Every result in this section includes its baseline, hardware description, and reproduction command.

This section is the index. Each benchmark family has its own page with its own claims, baselines and results, so results can be added without rewriting what is already here.

## Published families

<table data-view="cards">
<thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Compute kernels</strong></td><td>Dense and quantized matrix kernels, measured against the engine's own prior implementations.</td><td><a href="compute-kernels.md">compute-kernels.md</a></td></tr>
<tr><td><strong>Least-squares accuracy</strong></td><td>Correct digits on the NIST StRD linear-regression suite, against fourteen numpy, scipy and statsmodels arms on the same data.</td><td><a href="least-squares-accuracy.md">least-squares-accuracy.md</a></td></tr>
<tr><td><strong>Forecasting on the joint axis</strong></td><td>Accuracy and latency together on all 100,000 M4 series, against statsforecast 2.1.1 at matched parallelism.</td><td><a href="forecasting-joint-axis.md">forecasting-joint-axis.md</a></td></tr>
<tr><td><strong>FinQA exact execution</strong></td><td>Execution accuracy on all 8,281 real FinQA gold programs, against three real naive-reimplementation arms on the same programs.</td><td><a href="finqa-exact-execution.md">finqa-exact-execution.md</a></td></tr>
<tr><td><strong>LLM tool-calling uplift</strong></td><td>gpt-5-mini answering 16 real numeric questions with and without Algenta's tool-calling access to its own compiled engine.</td><td><a href="llm-tool-calling-uplift.md">llm-tool-calling-uplift.md</a></td></tr>
</tbody>
</table>

More families are added here as they are measured. A family appears above only once it has published numbers and a reproduction command — never as a placeholder.

## The rules every number follows

A result appears in this section only if it meets all of the following conditions.

{% hint style="info" %}
**Measured against the strongest available baseline, not the weakest.** A speedup over an unoptimised reference is an implementation detail. A speedup over the best thing a reader could otherwise use is a result. Each page names its baseline explicitly, and a page whose only baseline is an earlier Algenta implementation says so in its first line rather than presenting the ratio as competitive.
{% endhint %}

* **The baseline is named and versioned.** "Faster" is meaningless without saying "than what". Where the comparison is against Algenta's own earlier implementation, the page says so plainly rather than implying an external comparison.
* **Correctness is asserted alongside every timing.** A faster wrong answer is not a result. Every kernel benchmark diffs its output against a reference implementation and reports the difference.
* **Properties are gated, absolute times are not.** Nanoseconds vary by machine, thermal state and load. What must hold is the *shape* — cost per unit of work staying flat as the problem grows, for example. Absolute numbers are printed for tracking and are explicitly not a contract.
* **Hardware is reported, never averaged.** Results are published per chip generation and per memory configuration. A single headline number across different hardware hides the only thing a reader needs.
* **Measured after warm-up.** First-call costs — page faults on a fresh buffer, a thread pool spinning up — belong to neither implementation.
* **Reproducible.** Every page carries the command that produced its table.

## What is not published here

* Single-number claims of the form "N times faster", with no shape, no baseline and no hardware.
* A self-comparison presented as a competitive one. Where Algenta is measured against its own earlier implementation, the page says so — and where a tuned vendor library is faster, the page says that too rather than omitting the comparison.
* A timing taken on a machine that was busy. Benchmarks in this engine check `hot ≤ warm ≤ cold` and a sample-dispersion bound before reporting; a run that fails either is published as invalid with no ratio, because a contended sample and a real regression look identical on the page.
* A kernel-level speedup restated as an end-to-end one. A kernel result may be published as a kernel result; it becomes an end-to-end claim only when an end-to-end run demonstrates it.
* Results from a configuration a reader cannot reproduce.

## Related

* [Compute kernels](compute-kernels.md) — dense and quantized matrix kernel results.
* [Attention](attention.md) — tiled attention memory, rotary embedding, and block-size invariance.
* [Normalization](normalization.md) — RMSNorm and LayerNorm, and the price of a safe variance.
* [Feed-forward](feed-forward.md) — gated activations, the two GELU conventions, and embedding cost.
* [Forecasting on the joint axis](forecasting-joint-axis.md) — M4 accuracy and latency measured together against statsforecast 2.1.1.
* [LLM tool-calling uplift](llm-tool-calling-uplift.md) — an LLM answering the same questions with and without access to this engine.
* [Runtime libraries](../engine/runtime-libraries.md) — the surface these kernels are exposed through.
* [Runtime library catalog](../engine/runtime-library-catalog.md) — every module and function the runtime exposes.
