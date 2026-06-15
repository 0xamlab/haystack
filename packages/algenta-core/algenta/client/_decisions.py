"""_DecisionsMixin for the CodnaClient class.

Extracted from packages/algenta-core/algenta/client.py during modularization.
"""
from __future__ import annotations

from typing import Any

from algenta.client._helpers import _sdk_payload_to_plain_data, _cloud_get  # noqa: F401


class _DecisionsMixin:
    def log_decision(self, request: dict[str, Any]) -> Any:
        return self._sdk_client().log_decision(request)

    def list_decisions(
        self,
        *,
        page: int | None = None,
        limit: int | None = None,
        page_size: int | None = None,
        with_outcome_only: bool | None = None,
    ) -> Any:
        return self._sdk_client().list_decisions(
            page=page,
            limit=limit,
            page_size=page_size,
            with_outcome_only=with_outcome_only,
        )

    def get_decision(self, decision_id: str) -> Any:
        return self._sdk_client().get_decision(decision_id)

    def record_outcome(
        self,
        decision_id: str,
        *,
        actual_outcome: float,
        outcome_notes: str | None = None,
    ) -> Any:
        return self._sdk_client().record_outcome(
            decision_id,
            actual_outcome=actual_outcome,
            outcome_notes=outcome_notes,
        )

    def execute_decision(
        self,
        decision_id: str,
        *,
        webhook_url: str,
        timeout_seconds: float = 10.0,
        force: bool = False,
        override_safety: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        return self._sdk_client().execute_decision(
            decision_id,
            webhook_url=webhook_url,
            timeout_seconds=timeout_seconds,
            force=force,
            override_safety=override_safety,
            metadata=metadata,
        )

    def delete_decision(self, decision_id: str) -> Any:
        return self._sdk_client().delete_decision(decision_id)

    def plan_decision(self, request: dict[str, Any]) -> Any:
        return self._sdk_client().plan_decision(request)

