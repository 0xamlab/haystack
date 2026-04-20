"""
engines/bundles.py — Use-case bundles manifest.

A bundle groups Algenta engines and Mojo libraries into a focused,
domain-specific experience. Users install the bundle for their use case,
get drop-in API compatibility, and discover the platform naturally.

Distribution tiers:
  algenta-core      — local only, no API key, pure Python
  algenta-finance   — financial modeling bundle
  algenta-ml        — ML/AI engineering bundle
  algenta-ai        — GenAI + agent bundle
  algenta-ops       — infrastructure + operations bundle
  algenta-sdk       — full hosted API SDK
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Bundle:
    slug: str
    name: str
    description: str
    install: str                       # pip install command
    engines: list[str]                 # engine slugs from manifest.py
    mojo_libs: list[str]               # key Mojo libraries
    replaces: list[str]                # libraries this bundle can replace
    entry_points: list[str]            # primary API functions
    use_cases: list[str]
    tier: str                          # "local" | "developer" | "pro" | "enterprise"

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "install": self.install,
            "engines": self.engines,
            "mojo_libs": self.mojo_libs,
            "replaces": self.replaces,
            "entry_points": self.entry_points,
            "use_cases": self.use_cases,
            "tier": self.tier,
        }


BUNDLES: list[Bundle] = [

    Bundle(
        slug="algenta-core",
        name="Algenta Core",
        description=(
            "Local simulation, optimization, and decision-making. "
            "Zero dependencies. No API key. Works offline. "
            "The entry point to the Algenta ecosystem."
        ),
        install="pip install algenta-core",
        engines=["decision", "optimize"],
        mojo_libs=[
            "monte_carlo", "probability_distributions", "risk_engine",
            "optimization_core", "statistics",
        ],
        replaces=["scipy.stats", "random", "statistics"],
        entry_points=[
            "algenta.simulate.risk()",
            "algenta.decision.analyze()",
            "algenta.optimize.maximize()",
            "algenta.forecast.predict()",
        ],
        use_cases=[
            "Quick risk assessment",
            "Local prototyping",
            "Teaching and demos",
            "Offline computation",
        ],
        tier="local",
    ),

    Bundle(
        slug="algenta-finance",
        name="Algenta Finance",
        description=(
            "Financial modeling, risk quantification, portfolio optimization, "
            "and credit scoring. Drop-in replacement for QuantLib patterns "
            "and manual Monte Carlo loops."
        ),
        install="pip install algenta-finance",
        engines=["decision", "optimize", "retrieval"],
        mojo_libs=[
            "monte_carlo", "probability_distributions", "risk_engine",
            "option_pricing", "portfolio_optimizer", "credit_risk",
            "fixed_income", "value_at_risk", "scenario_generator",
            "financial_ratios",
        ],
        replaces=["QuantLib", "scipy.stats", "numpy (for finance)"],
        entry_points=[
            "algenta.finance.option_price()",
            "algenta.finance.portfolio_risk()",
            "algenta.finance.credit_score()",
            "algenta.finance.var(confidence=0.95)",
        ],
        use_cases=[
            "Options pricing (Black-Scholes, Monte Carlo)",
            "Portfolio VaR and CVaR",
            "Credit risk scoring",
            "Revenue forecasting with confidence intervals",
            "Investment scenario analysis",
        ],
        tier="developer",
    ),

    Bundle(
        slug="algenta-ml",
        name="Algenta ML",
        description=(
            "ML training, scoring, and feature engineering — faster than scikit-learn "
            "and PyTorch for tabular workloads. Includes model evaluation, "
            "hyperparameter search, and dataset utilities."
        ),
        install="pip install algenta-ml",
        engines=["training", "data", "model", "optimize"],
        mojo_libs=[
            "gradient_descent", "neural_net_forward", "attention_mechanism",
            "feature_engineering", "cross_validation", "hyperparameter_search",
            "regularization", "loss_functions", "activation_functions",
            "batch_normalization",
        ],
        replaces=["scikit-learn (scoring + feature eng)", "pandas (feature pipelines)"],
        entry_points=[
            "algenta.ml.train(model, data)",
            "algenta.ml.score(model, features)",
            "algenta.ml.features.engineer(df)",
            "algenta.ml.search_hyperparams(model, space)",
        ],
        use_cases=[
            "Tabular ML training and scoring",
            "Feature engineering pipelines",
            "Hyperparameter optimization",
            "Model evaluation and cross-validation",
            "A/B test analysis",
        ],
        tier="pro",
    ),

    Bundle(
        slug="algenta-ai",
        name="Algenta AI",
        description=(
            "LLM inference, agent workflows, RAG pipelines, and structured output. "
            "Drop-in replacement for LangChain, vLLM, and FAISS patterns. "
            "Runs your models 100× faster with the Algenta Inference Engine."
        ),
        install="pip install algenta-ai",
        engines=["inference", "agent", "retrieval", "serving"],
        mojo_libs=[
            "flash_attention", "kv_cache", "speculative_decoding",
            "continuous_batching", "vector_search", "bm25_retrieval",
            "reranking", "structured_output", "tool_calling",
            "session_memory",
        ],
        replaces=["vLLM", "LangChain", "LangGraph", "FAISS", "Weaviate (basic)"],
        entry_points=[
            "algenta.ai.infer(model, prompt)",
            "algenta.ai.agent.run(task, tools)",
            "algenta.ai.retrieve(query, docs)",
            "algenta.ai.rag(query, collection)",
        ],
        use_cases=[
            "LLM inference with KV caching",
            "AI agent orchestration",
            "RAG pipeline construction",
            "Semantic search and reranking",
            "Structured output extraction",
        ],
        tier="pro",
    ),

    Bundle(
        slug="algenta-ops",
        name="Algenta Ops",
        description=(
            "Infrastructure optimization, capacity planning, SLA modeling, "
            "and cost routing. Used by MLOps and DevOps teams to reduce "
            "GPU spend and hit latency targets."
        ),
        install="pip install algenta-ops",
        engines=["cost", "serving", "optimize", "decision"],
        mojo_libs=[
            "execution_planner", "cost_router", "latency_optimizer",
            "workflow_engine", "model_router", "stateful_runtime",
            "scheduling_priority", "batch_strategy", "gpu_placement",
            "sla_modeling",
        ],
        replaces=["Airflow (routing logic)", "Ray (scheduling)", "manual cost logic"],
        entry_points=[
            "algenta.ops.route(request, budget)",
            "algenta.ops.plan_capacity(load_forecast)",
            "algenta.ops.optimize_cost(workload)",
            "algenta.ops.sla_risk(latency_p99, target)",
        ],
        use_cases=[
            "GPU vs CPU routing decisions",
            "Batch vs real-time scheduling",
            "Latency budget optimization",
            "Infrastructure cost modeling",
            "Capacity planning for ML inference",
        ],
        tier="pro",
    ),

]

BUNDLES_BY_SLUG: dict[str, Bundle] = {b.slug: b for b in BUNDLES}


def get_bundle(slug: str) -> Bundle | None:
    return BUNDLES_BY_SLUG.get(slug)


def list_bundles(tier: str | None = None) -> list[Bundle]:
    if tier:
        return [b for b in BUNDLES if b.tier == tier]
    return BUNDLES
