#!/usr/bin/env python3
"""Generate scripts/hf_kernel_filters.json — the Hub layout table (one repo per module filter).

Reuses the catalogue categories (scripts/docs/gen_runtime_library_reference.py::CATEGORY_RULES)
and the runtime inventory (apps.runtime.mojo_inventory.discover_runtime_library_modules) so the
table can never drift from the modules the runtime actually dispatches. "General & domain modules"
is split alphabetically into chunks of at most --general-chunk modules. Every executable module
lands in exactly one filter (checked). Modules in --quarantine go to `algenta-host-interop`
(status pending-stage-2) so coverage stays complete while their in-process viability is decided.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "docs"))

GPU_BEARING_PREFIXES = ("residentk.", "metaldispatch.", "accel.", "attnk.", "gemm.", "llmk.", "normk.", "lossk.", "mlpk.", "tensorx.")

SLUGS = {
    "Vision & imaging": ("algenta-vision", "Image, vision and pixel kernels"),
    "LLM & attention": ("algenta-llm", "LLM, attention, RoPE, embedding and KV-cache kernels"),
    "Machine learning": ("algenta-ml", "Machine-learning kernels: activations, gradients, optimizers, losses, layers"),
    "Tensors & linear algebra": ("algenta-tensors", "Tensor, linear-algebra, BLAS and decomposition kernels"),
    "Statistics & probability": ("algenta-stats", "Statistics, probability, hypothesis testing, regression and sampling kernels"),
    "Signal & audio": ("algenta-signal", "Signal, FFT, audio and spectral kernels"),
    "Cryptography & hashing": ("algenta-crypto", "Cryptography and hashing kernels"),
    "Text & language": ("algenta-text", "Text and language kernels"),
    "Graph & automata": ("algenta-graph", "Graph, network and automata kernels"),
    "Serialization & data": ("algenta-serialization", "Serialization and data-format kernels"),
    "Bits, numbers & time": ("algenta-bits-time", "Bit, number and time kernels"),
    "Geometry & spatial": ("algenta-geometry", "Geometry and spatial kernels"),
    "Networking & systems": ("algenta-networking", "Networking and systems kernels"),
    "Finance & business": ("algenta-finance", "Finance and business kernels"),
}

# The card's first call: a real computation with a legible result, never an enum lookup.
CARD_EXAMPLES = {
    "algenta-stats": ["ab_testing", "z_test_proportions", [50, 1000, 65, 1000]],
    "algenta-llm": ["embeddings", "cosine_similarity", [[1.0, 0.0], [1.0, 1.0]]],
    "algenta-ml": ["activations", "gelu", [1.0]],
}
CARD_EXAMPLE_NOTES = {"algenta-stats": "z statistic, p-value"}

# One line per module on the card, written for someone who has never seen the engine. Modules
# without an entry fall back to the first sentence of their Mojo docstring (cleaned); a family is
# published only when every module reads well, so add entries here as families are released.
MODULE_DESCRIPTIONS = {
    "ab_testing": "A/B testing: two-proportion z-test, power, sample size, sequential tests",
    "bayesian": "Bayesian inference: Beta, Normal and Poisson posteriors, credible intervals, Bayes factors",
    "distribution_fit": "Distribution fitting",
    "distributions": "Samplers for 27 probability distributions",
    "forecasting.interval": "Prediction bands from backtest residuals",
    "hypothesis": "Nonparametric tests: Mann-Whitney, Wilcoxon, Kruskal-Wallis, Fisher exact, sign test",
    "interval": "Interval arithmetic",
    "ml.naive_bayes": "Gaussian naive Bayes classifier",
    "probability": "Probability: Bayes' rule, combinatorics, PMFs, entropy, KL divergence",
    "regression": "Regression: simple and multiple OLS, ridge, polynomial features, fit metrics",
    "regression_tree": "Regression trees (CART)",
    "sampling": "Quasi-random sampling: Halton, Sobol-like, Latin hypercube, stratified",
    "scipy_stats_ops": "Distribution PDF, CDF and PPF",
    "stat_tests": "Hypothesis tests: t-tests, Kolmogorov-Smirnov, Pearson, Spearman",
    "stats": "Descriptive statistics, quantiles and sorting",
    "stats_bootstrap": "Bootstrap statistics",
    "timeseries_stats": "Time-series statistics: autocorrelation, ADF, smoothing, rolling windows",
    "accel.contract": "Status codes and backend selection for accelerator kernels",
    "accel.device": "Accelerator detection for this host",
    "accel.gemm_metal": "Threadgroup-tiled GEMM on the GPU",
    "attnk.backward": "Gradients of scaled dot-product attention",
    "attnk.contract": "Status codes and work budget for attention kernels",
    "attnk.flash": "Tiled attention with online softmax",
    "attnk.mask": "Attention masks as additive bias: causal, sliding-window, padding, packed",
    "attnk.rope": "Rotary position embedding: frequency tables and application",
    "attnk.sdpa": "Scaled dot-product attention, materialized reference",
    "attnk.tiled": "Blockwise online-softmax attention over flat buffers, with grouped-query attention",
    "bpe_tokenizer": "BPE and SentencePiece tokenization primitives",
    "causal_inference.propensity": "Propensity scores, overlap diagnostics, inverse-probability weighting, matching",
    "embeddings": "Vector embeddings: similarity, distance, centroids, nearest neighbours",
    "flash_attention": "Blockwise memory-efficient attention math",
    "gemm.blocked": "Cache-blocked SIMD GEMM and GEMV over flat row-major buffers",
    "gemm.contract": "Status codes, dimension check and work budget for GEMM",
    "gemm.quantized": "Matmul with dequantization fused into the k-loop",
    "kv_cache": "KV-cache memory math and incremental decoding",
    "llm_sampling": "Token sampling: temperature, top-k, top-p, min-p, penalties, beam scores",
    "llmk.contract": "Status codes and shape check for the LLM kernels",
    "llmk.gemv_fast": "Parallel matrix-vector multiply for the transposed decode shape",
    "llmk.generate": "Autoregressive decode primitives: greedy argmax, KV-cache append",
    "llmk.residual": "Elementwise add of two flat buffers",
    "lossk.contract": "Status codes and work budget for training objectives",
    "lossk.cross_entropy": "Fused projection and cross-entropy, chunked",
    "metaldispatch.contract": "Status codes for the Metal dispatch layer",
    "metaldispatch.qwen3_decode": "Int8 Metal GPU decode for Qwen3-family checkpoints",
    "metaldispatch.qwen3_prefill_decode": "Batched-prefill Metal GPU decode for Qwen3-family checkpoints",
    "metaldispatch.session_prefill_policy": "Resolved execution plan for a resident decode session",
    "mlpk.activation": "Gated feed-forward activations, forward and backward",
    "mlpk.contract": "Status codes, work budget and the GELU convention for feed-forward kernels",
    "mlpk.embedding": "Token embedding lookup and its scatter-add gradient",
    "mlpk.gated_ffn": "Fused gated feed-forward activations over flat buffers",
    "normk.contract": "Status codes and work budget for normalization kernels",
    "normk.layernorm": "LayerNorm, forward and backward, over flat row-major buffers",
    "normk.rmsnorm": "RMSNorm, forward and backward, over flat row-major buffers",
    "paged_kv_cache": "Paged KV cache: virtualization, compaction, prefix sharing",
    "propensity": "Propensity score matching: scores, calipers, balance checks, matched estimates",
    "residentk.contract": "Status codes, shape check and dispatch budget for resident sessions",
    "residentk.probe": "Whether this host can hold a resident GPU decode session",
    "sparse_attention": "Sparse, local and long-context attention variants",
    "tensorx.buffer": "Byte buffers tagged with a dtype and a shape",
    "tensorx.contract": "Status codes, finiteness predicate and shape check for tensors",
    "tensorx.dtype": "Dtype tags, limits, accumulation policy and round-trip",
    "tensorx.elementwise": "Add, subtract, multiply, divide and cast over dtype-tagged buffers, with broadcasting",
    "tensorx.pack": "Blockwise low-bit quantization: int4 and int8 grids, NF4 codebook, nibble packing",
    "tensorx.reduce": "Sum, mean, min, max, variance and standard deviation over dtype-tagged buffers",
    "tensorx.shape": "N-dimensional shapes, row-major strides and broadcasting",
    "text.tokenizer": "Text tokenization: words, sentences, n-grams, stop words, stemming",
    "token_bucket": "Rate limiting: token bucket, leaky bucket, sliding window",
    "transformer_attention": "Transformer attention calculations",
    "transformer_blocks": "Transformer block primitives: attention heads, feed-forward, residual, norms",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default=str(ROOT / "scripts" / "hf_kernel_filters.json"))
    ap.add_argument("--general-chunk", type=int, default=100)
    ap.add_argument("--quarantine", nargs="*", default=["env"])
    a = ap.parse_args()
    from apps.runtime.mojo_inventory import discover_runtime_library_modules  # noqa: E402
    from gen_runtime_library_reference import categorize  # noqa: E402

    modules = sorted(m.import_path for m in discover_runtime_library_modules(executable_only=True))
    by_cat: dict[str, list[str]] = {}
    quarantine = [m for m in modules if m in set(a.quarantine)]
    for m in modules:
        if m in quarantine:
            continue
        # GPU-bearing engine packages (the session modules through which the 199 residentk /
        # metaldispatch kernels are reached, plus the accelerator kernel layers) are pinned to the
        # LLM family so the metal/cuda variants have one home; CATEGORY_RULES would scatter them
        # into the alphabetical general chunks.
        if m.startswith(GPU_BEARING_PREFIXES):
            by_cat.setdefault("LLM & attention", []).append(m)
            continue
        by_cat.setdefault(categorize(m), []).append(m)
    filters: dict[str, dict] = {}
    for cat, mods in sorted(by_cat.items()):
        if cat in SLUGS:
            slug, summary = SLUGS[cat]
            filters[slug] = {"title": cat, "summary": summary, "modules": mods}
        else:  # General & domain modules -> alphabetical chunks
            chunks = [mods[i : i + a.general_chunk] for i in range(0, len(mods), a.general_chunk)]
            for i, chunk in enumerate(chunks):
                slug = f"algenta-general-{chr(ord('a') + i)}"
                filters[slug] = {"title": f"{cat} ({chunk[0]} .. {chunk[-1]})", "summary": "General and domain kernels, alphabetical chunk", "modules": chunk}
    if quarantine:
        filters["algenta-host-interop"] = {"title": "Host-interpreter interop modules (not shipped in v1)", "summary": "Every function needs the host Python bridge and SIGSEGVs in-process (Stage 2, RQ-G); served by the algenta runtime worker instead", "modules": quarantine, "status": "excluded-v1"}
    for slug, f in filters.items():
        f.setdefault("status", "planned")
        if slug in CARD_EXAMPLES:
            f["card_example"] = CARD_EXAMPLES[slug]
        if slug in CARD_EXAMPLE_NOTES:
            f["card_example_note"] = CARD_EXAMPLE_NOTES[slug]
        descriptions = {m: MODULE_DESCRIPTIONS[m] for m in f["modules"] if m in MODULE_DESCRIPTIONS}
        if descriptions:
            f["module_descriptions"] = descriptions
        f["excluded_functions"] = ["datetime.now_epoch"] if "datetime" in f["modules"] else []
        f["request_types"] = ["library_execute"]
        if slug == "algenta-llm":
            f["request_types"] = ["library_execute", "dataset_open", "dataset_close", "dataset_list", "batch_execute", "pipeline_execute", "query_execute", "stream_open", "stream_next", "stream_close", "qwen3_decode_open", "qwen3_decode_next", "qwen3_decode_close"]
        f["required_engine_implementations"] = []
        f["backends"] = ["cpu", "metal", "cuda"] if slug == "algenta-llm" else ["cpu"]
        if slug == "algenta-llm":
            f["required_engine_implementations"] = ["residentk", "metaldispatch"]
            f["gpu_variants_status"] = "pending-stage-2b"
        f["module_count"] = len(f["modules"])
    covered = [m for f in filters.values() for m in f["modules"]]
    assert sorted(covered) == modules and len(covered) == len(set(covered)), "every module must land in exactly one filter"
    out = {"schema": 1, "source": "apps.runtime.mojo_inventory.discover_runtime_library_modules(executable_only=True) x gen_runtime_library_reference.categorize", "module_count": len(modules), "filters": filters}
    Path(a.output).write_text(json.dumps(out, indent=2) + "\n")
    for slug, f in filters.items():
        print(f"{slug:26} {f['module_count']:4}  {f['title']}")
    print(f"total modules {len(modules)} in {len(filters)} filters -> {a.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
