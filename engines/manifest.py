"""
engines/manifest.py — Algenta OS engine registry.

Maps each product-level engine to its constituent Mojo libraries,
API surface, and use cases.  Single source of truth — imported by
the API router, SDK, and CLI.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Engine:
    name: str
    slug: str                   # URL / API key  e.g. "decision"
    description: str
    api_path: str               # top-level route prefix
    mojo_libs: list[str]        # mojo/engine/*.mojo contributors
    use_cases: list[str]
    tier: str                   # "core" | "advanced" | "platform"


ENGINES: list[Engine] = [
    Engine(
        name="Decision Engine",
        slug="decision",
        description=(
            "Unified simulation + optimization + scoring + risk engine. "
            "Combines Monte Carlo, distributions, and ML-fusion for "
            "pricing, risk analysis, supply-chain, and routing decisions."
        ),
        api_path="/v1/decision",
        mojo_libs=[
            "engines_monte_carlo",
            "distributions",
            "decision_ml_fusion",
            "optimization_constrained",
            "multi_objective",
            "risk",
            "causal",
            "bayesian_inference",
            "scipy_optimize_ops",
            "stochastic",
        ],
        use_cases=["pricing", "risk analysis", "supply chain", "routing"],
        tier="core",
    ),
    Engine(
        name="Inference Engine",
        slug="inference",
        description=(
            "LLM and model inference runtime with paged KV cache, "
            "flash attention, speculative decoding, and generation control."
        ),
        api_path="/v1/inference",
        mojo_libs=[
            "transformer_attention",
            "kv_cache",
            "paged_kv_cache",
            "flash_attention",
            "generation_loop",
            "speculative_decoding",
            "fused_kernels",
            "continuous_batching",
            "quantization_stack",
            "positional_encoding",
        ],
        use_cases=["chat", "generation", "embeddings", "real-time inference"],
        tier="core",
    ),
    Engine(
        name="Agent Engine",
        slug="agent",
        description=(
            "Execution and reasoning engine for autonomous agents: "
            "tool calling, workflow DAGs, structured output, and memory."
        ),
        api_path="/v1/agent",
        mojo_libs=[
            "agent_runtime",
            "workflow_engine",
            "structured_output",
            "stateful_runtime",
            "hybrid_reasoning",
            "rlhf_dpo",
            "inference_security",
        ],
        use_cases=["automation", "copilots", "workflows", "orchestration"],
        tier="core",
    ),
    Engine(
        name="Retrieval Engine",
        slug="retrieval",
        description=(
            "Search and context engine combining dense vector search, "
            "BM25, cross-encoder reranking, and MMR diversity."
        ),
        api_path="/v1/retrieval",
        mojo_libs=[
            "vector_search",
            "rag_retrieval",
            "vector_similarity",
            "online_learning",
            "bpe_tokenizer",
        ],
        use_cases=["enterprise search", "knowledge systems", "copilots", "RAG"],
        tier="core",
    ),
    Engine(
        name="Optimization Engine",
        slug="optimize",
        description=(
            "Standalone optimization system: convex, constrained, "
            "multi-objective, gradient-based, and meta-heuristic solvers."
        ),
        api_path="/v1/optimize",
        mojo_libs=[
            "scipy_optimize_ops",
            "gradient_descent",
            "optimizer_full",
            "multi_objective",
            "linear_programming",
            "optimization_constrained",
            "optimization_meta",
            "convex",
        ],
        use_cases=["pricing optimization", "routing", "scheduling", "resource allocation"],
        tier="core",
    ),
    Engine(
        name="Serving Engine",
        slug="serving",
        description=(
            "Production serving runtime: continuous batching, scheduling, "
            "latency optimization, fault tolerance, and auto-scaling."
        ),
        api_path="/v1/serving",
        mojo_libs=[
            "continuous_batching",
            "scheduler_ops",
            "latency_optimizer",
            "fault_tolerance",
            "observability",
            "execution_planner",
            "memory_system",
        ],
        use_cases=["APIs", "real-time serving", "scaling", "production deployment"],
        tier="core",
    ),
    Engine(
        name="Training Engine",
        slug="training",
        description=(
            "Full ML training runtime: autograd, optimizers, distributed "
            "collectives, LoRA fine-tuning, RLHF/DPO, and training stability."
        ),
        api_path="/v1/training",
        mojo_libs=[
            "autograd_ops",
            "autograd_graph",
            "optimizer_full",
            "training_stability",
            "distributed_collectives",
            "lora_adapters",
            "rlhf_dpo",
            "data_pipeline",
            "model_parallel",
            "gpu_kernels",
        ],
        use_cases=["model training", "fine-tuning", "RLHF", "experimentation"],
        tier="advanced",
    ),
    Engine(
        name="Data Engine",
        slug="data",
        description=(
            "Data processing and feature system: ETL, feature engineering, "
            "streaming pipelines, deduplication, and quality filtering."
        ),
        api_path="/v1/data",
        mojo_libs=[
            "data_pipeline",
            "feature_engineering",
            "pandas_groupby",
            "numpy_ops",
            "data_feedback_loop",
            "evaluation_feedback",
        ],
        use_cases=["ETL", "feature pipelines", "analytics", "data quality"],
        tier="advanced",
    ),
    Engine(
        name="Model Engine",
        slug="model",
        description=(
            "Model lifecycle and interoperability: load, shard, adapt, "
            "and manage models across safetensors, GGUF, ONNX, and HF formats."
        ),
        api_path="/v1/model",
        mojo_libs=[
            "model_serialization",
            "model_interop",
            "model_abi",
            "weight_loader",
            "lora_adapters",
            "quantization_stack",
            "quantization",
            "bpe_tokenizer",
        ],
        use_cases=["loading models", "managing models", "adapting models", "format conversion"],
        tier="advanced",
    ),
    Engine(
        name="Cost Engine",
        slug="cost",
        description=(
            "AI compute cost optimizer: cost-aware routing, GPU/CPU placement, "
            "model tier selection, and SLA-budget tradeoffs."
        ),
        api_path="/v1/cost",
        mojo_libs=[
            "cost_router",
            "execution_planner",
            "model_router",
            "scheduler_ops",
            "observability",
        ],
        use_cases=["cost optimization", "routing workloads", "infra decisions", "FinOps"],
        tier="advanced",
    ),
    Engine(
        name="Security & Governance Engine",
        slug="security",
        description=(
            "Enterprise safety layer: prompt injection detection, PII filtering, "
            "output safety, differential privacy, RBAC, and audit logging."
        ),
        api_path="/v1/security",
        mojo_libs=[
            "security_governance",
            "inference_security",
            "privacy",
        ],
        use_cases=["compliance", "safe AI", "enterprise deployment", "audit"],
        tier="platform",
    ),
    Engine(
        name="Hybrid Intelligence Engine",
        slug="hybrid",
        description=(
            "Algenta's moat: ML prediction + physics simulation + "
            "optimization + symbolic rules unified into one reasoning system."
        ),
        api_path="/v1/hybrid",
        mojo_libs=[
            "hybrid_reasoning",
            "decision_ml_fusion",
            "scipy_optimize_ops",
            "bayesian_inference",
            "state_space_models",
            "causal",
            "stochastic",
            "simulation",
        ],
        use_cases=[
            "strategic decisions",
            "forecasting + optimization",
            "advanced analytics",
            "digital twins",
        ],
        tier="platform",
    ),
]

# ── Lookup helpers ──────────────────────────────────────────────────────────

ENGINES_BY_SLUG: dict[str, Engine] = {e.slug: e for e in ENGINES}
ENGINES_BY_TIER: dict[str, list[Engine]] = {}
for _e in ENGINES:
    ENGINES_BY_TIER.setdefault(_e.tier, []).append(_e)

# All Mojo libs referenced across engines (deduplicated)
ALL_ENGINE_LIBS: set[str] = {lib for e in ENGINES for lib in e.mojo_libs}
