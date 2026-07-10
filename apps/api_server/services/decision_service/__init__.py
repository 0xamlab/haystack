"""Decision Service — orchestrates the governed decision workflow over the aggregate.

Build order 4: the API-only Decision workflow —
    create_or_update_decision → run_decision_analysis (async) → get_result / inspect_evidence
      → propose_action_plan → approve (separately authenticated) → execute_approved_plan
      → record_outcome → refresh_decision

The service is deliberately persistence-agnostic: it drives a :class:`DecisionRepository`
(in-memory for DB-free unit tests; SQLAlchemy-backed for the app) and executes a governed
Decision Pack (:mod:`apps.api_server.decision_packs`). The LM never generates numbers here —
the pack's deterministic model + solver do.
"""

from __future__ import annotations

from .records import (
    ApprovalRecord,
    DecisionCaseRecord,
    EvidenceRecord,
    ExecutionPlanRecord,
    OutcomeRecord,
    RecommendationRecord,
    RevisionRecord,
    RunRecord,
)
from .repository import DecisionRepository, InMemoryDecisionRepository
from .service import DecisionService, DecisionServiceError

__all__ = [
    "DecisionService",
    "DecisionServiceError",
    "DecisionRepository",
    "InMemoryDecisionRepository",
    "DecisionCaseRecord",
    "RevisionRecord",
    "EvidenceRecord",
    "RunRecord",
    "RecommendationRecord",
    "ExecutionPlanRecord",
    "ApprovalRecord",
    "OutcomeRecord",
]
