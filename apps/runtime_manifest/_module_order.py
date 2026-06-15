"""Canonical LLM-runtime module rollout order.

Source of truth for the order in which the LLM runtime modules are rolled out /
reported in the runtime manifest. Kept as a dependency-free leaf module so it can
be imported by both the runtime-manifest builders (shipped in the prod images) and
the (dev-only) benchmark harness without dragging ``benchmarks/`` into production —
``benchmarks`` is not packaged into the api/worker/engine images, so importing this
value from there crashed the api on boot (ModuleNotFoundError: No module named
'benchmarks'). The benchmark now re-exports this tuple as ``TARGET_MODULES``.
"""

from __future__ import annotations

LLM_ROLLOUT_MODULE_ORDER = (
    "bpe_tokenizer",
    "text.tokenizer",
    "embeddings",
    "flash_attention",
    "sparse_attention",
    "transformer_attention",
    "transformer_blocks",
    "llm_sampling",
    "vector_similarity",
    "vector_search",
    "vector_kernels.ranker",
    "vector_kernels.table",
    "sparse_vector",
    "rlhf_dpo",
    "rerank_eval",
    "inference_cost_latency",
    "kv_cache",
    "paged_kv_cache",
    "continuous_batching",
    "inference_engine",
    "speculative_decoding",
    "generation_loop",
)
