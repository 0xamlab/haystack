from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .async_client_model_surface_common import _request_model

if TYPE_CHECKING:
    from .async_client_facade import AsyncDecisionEngineClient


async def log_decision(
    client: AsyncDecisionEngineClient,
    request: dict[str, Any],
) -> Any:
    return await _request_model(
        client,
        "POST",
        "/v1/decisions",
        "DecisionLogResult",
        json_body=request,
    )


async def list_decisions(
    client: AsyncDecisionEngineClient,
    *,
    page: int | None = None,
    limit: int | None = None,
    page_size: int | None = None,
    with_outcome_only: bool | None = None,
) -> Any:
    params: dict[str, Any] = {}
    if page is not None:
        params["page"] = page
    if limit is not None:
        params["limit"] = limit
    if page_size is not None:
        params["page_size"] = page_size
    if with_outcome_only is not None:
        params["with_outcome_only"] = str(with_outcome_only).lower()
    data = await client._request("GET", "/v1/decisions", params=params or None)
    from .model_loader import validate_model as _validate_model

    return _validate_model("DecisionListResult", data)


async def get_decision(
    client: AsyncDecisionEngineClient,
    decision_id: str,
) -> Any:
    return await _request_model(
        client,
        "GET",
        f"/v1/decisions/{decision_id}",
        "DecisionLogResult",
    )


async def record_outcome(
    client: AsyncDecisionEngineClient,
    decision_id: str,
    *,
    actual_outcome: float,
    outcome_notes: str | None = None,
) -> Any:
    body: dict[str, Any] = {"actual_outcome": actual_outcome}
    if outcome_notes is not None:
        body["outcome_notes"] = outcome_notes
    return await _request_model(
        client,
        "PATCH",
        f"/v1/decisions/{decision_id}/outcome",
        "DecisionLogResult",
        json_body=body,
    )


async def execute_decision(
    client: AsyncDecisionEngineClient,
    decision_id: str,
    *,
    webhook_url: str,
    timeout_seconds: float = 10.0,
    force: bool = False,
    override_safety: bool = False,
    metadata: dict[str, Any] | None = None,
) -> Any:
    body: dict[str, Any] = {
        "webhook_url": webhook_url,
        "timeout_seconds": timeout_seconds,
        "force": force,
        "override_safety": override_safety,
    }
    if metadata is not None:
        body["metadata"] = metadata
    return await _request_model(
        client,
        "POST",
        f"/v1/decisions/{decision_id}/execute",
        "ExecutionReceiptResult",
        json_body=body,
    )


async def delete_decision(client: AsyncDecisionEngineClient, decision_id: str) -> dict[str, Any]:
    data = await client._request("DELETE", f"/v1/decisions/{decision_id}")
    if isinstance(data, dict):
        return data
    return {}


__all__ = [
    "delete_decision",
    "execute_decision",
    "get_decision",
    "list_decisions",
    "log_decision",
    "record_outcome",
]
