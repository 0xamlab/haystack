"""
Decision Engine Python SDK

Usage:
    from decision_engine import DecisionEngineClient

    client = DecisionEngineClient(api_key="de_live_...")
    result = client.simulate(
        mode="auto",
        scenario={
            "variables": {"revenue": {"low": 80000, "high": 200000}},
            "objective": "maximize_net_value",
        },
    )
    print(result.recommended_action, result.confidence)
"""
from .async_client import AsyncDecisionEngineClient
from .client import DecisionEngineClient
from .exceptions import (
    AuthenticationError,
    DecisionEngineError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from .models import (
    APIKeyInfo,
    BatchItemResult,
    BatchResult,
    DecisionEnvelope,
    ExplainResult,
    JobStatus,
    JobSubmitResponse,
    MetricsSummary,
    PercentileSummary,
    QueryCandidate,
    QueryResult,
    ResolvedPlan,
    ResolveResult,
    SourceRegistrationResult,
    UsageInfo,
    VerifyResult,
)

__version__ = "1.0.0"
__all__ = [
    "DecisionEngineClient",
    "AsyncDecisionEngineClient",
    "DecisionEnvelope",
    "QueryCandidate",
    "QueryResult",
    "ResolvedPlan",
    "ResolveResult",
    "VerifyResult",
    "SourceRegistrationResult",
    "ExplainResult",
    "MetricsSummary",
    "PercentileSummary",
    "JobStatus",
    "JobSubmitResponse",
    "UsageInfo",
    "APIKeyInfo",
    "BatchResult",
    "BatchItemResult",
    "DecisionEngineError",
    "AuthenticationError",
    "RateLimitError",
    "ValidationError",
    "ServerError",
    "NotFoundError",
]
