from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .client_trigger_surface import (
    _validate_register_trigger_payload,
    _validate_trigger_id,
)
from .client_control_plane_surface import _coerce_pagination
from .model_loader import validate_model as _validate_model

if TYPE_CHECKING:
    from .async_client_facade import AsyncDecisionEngineClient


async def register_trigger(
    client: AsyncDecisionEngineClient,
    *,
    name: str,
    condition: dict[str, Any],
    simulation_template: dict[str, Any],
    webhook_url: str | None = None,
    execution_webhook_url: str | None = None,
    auto_execute: bool = False,
    description: str | None = None,
) -> Any:
    data = await client._request(
        "POST",
        "/v1/triggers",
        json=_validate_register_trigger_payload(
            name=name,
            condition=condition,
            simulation_template=simulation_template,
            webhook_url=webhook_url,
            execution_webhook_url=execution_webhook_url,
            auto_execute=auto_execute,
            description=description,
        ),
    )
    return _validate_model("TriggerSummaryResult", data)


async def list_triggers(
    client: AsyncDecisionEngineClient,
    *,
    status: str = "all",
    page: int | None = None,
    limit: int | None = None,
) -> Any:
    if not isinstance(status, str) or status not in {"active", "paused", "all"}:
        raise ValueError("status must be one of: active, paused, all.")
    params = _coerce_pagination(page=page, limit=limit)
    if status != "all":
        params["status"] = status
    data = await client._request("GET", "/v1/triggers", params=params or None)
    return _validate_model("TriggerListResult", data)


async def fire_trigger(
    client: AsyncDecisionEngineClient,
    trigger_id: str,
    *,
    force: bool = False,
) -> Any:
    data = await client._request(
        "POST",
        f"/v1/triggers/{_validate_trigger_id(trigger_id)}/fire",
        json={"force": force},
    )
    return _validate_model("TriggerFireResult", data)


async def pause_trigger(
    client: AsyncDecisionEngineClient,
    trigger_id: str,
    *,
    paused: bool = True,
) -> Any:
    data = await client._request(
        "PATCH",
        f"/v1/triggers/{_validate_trigger_id(trigger_id)}/pause",
        params={"paused": paused},
    )
    return _validate_model("TriggerPauseResult", data)


async def delete_trigger(client: AsyncDecisionEngineClient, trigger_id: str) -> Any:
    normalized_trigger_id = _validate_trigger_id(trigger_id)
    data = await client._request("DELETE", f"/v1/triggers/{normalized_trigger_id}")
    if not isinstance(data, dict):
        raise TypeError(
            f"Trigger delete response must be a JSON object, got {type(data).__name__}."
        )
    return _validate_model(
        "TriggerDeleteResult",
        {"trigger_id": normalized_trigger_id, "deleted": True, **data},
    )


__all__ = [
    "delete_trigger",
    "fire_trigger",
    "list_triggers",
    "pause_trigger",
    "register_trigger",
]
