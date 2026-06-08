from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .async_client_model_surface_common import _request_model

if TYPE_CHECKING:
    from .async_client_facade import AsyncDecisionEngineClient


async def plan_decision(
    client: AsyncDecisionEngineClient,
    request: dict[str, Any],
) -> Any:
    return await _request_model(
        client,
        "POST",
        "/v1/decisions/plan",
        "DecisionPlanResult",
        json_body=request,
    )


__all__ = ["plan_decision"]
