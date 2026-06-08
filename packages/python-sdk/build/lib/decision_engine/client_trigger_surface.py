from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .client_control_plane_surface import _coerce_pagination
from .model_loader import validate_model as _validate_model

if TYPE_CHECKING:
    from .client_facade import DecisionEngineClient


def _validate_trigger_id(trigger_id: str) -> str:
    if not isinstance(trigger_id, str) or not trigger_id.strip():
        raise ValueError("trigger_id must be a non-empty string.")
    return trigger_id.strip()


def _validate_trigger_direction(direction: Any) -> str:
    if not isinstance(direction, str):
        raise TypeError("condition.direction must be a string.")
    normalized = direction.strip()
    if normalized not in {"above", "below", "change"}:
        raise ValueError("condition.direction must be one of: above, below, change.")
    return normalized


def _validate_trigger_aggregation(aggregation: Any) -> str:
    if aggregation is None:
        return "sum"
    if not isinstance(aggregation, str):
        raise TypeError("condition.aggregation must be a string.")
    normalized = aggregation.strip()
    if normalized not in {"sum", "avg", "max", "min", "count"}:
        raise ValueError("condition.aggregation must be one of: sum, avg, max, min, count.")
    return normalized


def _validate_trigger_condition(condition: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(condition, dict):
        raise TypeError("condition must be a JSON object.")
    source_id = condition.get("source_id")
    metric_hint = condition.get("metric_hint")
    threshold = condition.get("threshold")
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError("condition.source_id must be a non-empty string.")
    if not isinstance(metric_hint, str) or not metric_hint.strip():
        raise ValueError("condition.metric_hint must be a non-empty string.")
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise TypeError("condition.threshold must be a number.")
    return {
        "source_id": source_id.strip(),
        "metric_hint": metric_hint.strip(),
        "threshold": float(threshold),
        "direction": _validate_trigger_direction(condition.get("direction")),
        "aggregation": _validate_trigger_aggregation(condition.get("aggregation")),
    }


def _validate_register_trigger_payload(
    *,
    name: str,
    condition: dict[str, Any],
    simulation_template: dict[str, Any],
    webhook_url: str | None = None,
    execution_webhook_url: str | None = None,
    auto_execute: bool = False,
    description: str | None = None,
) -> dict[str, Any]:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be a non-empty string.")
    if not isinstance(simulation_template, dict) or not simulation_template:
        raise ValueError("simulation_template must be a non-empty JSON object.")
    payload: dict[str, Any] = {
        "name": name.strip(),
        "condition": _validate_trigger_condition(condition),
        "simulation_template": simulation_template,
        "auto_execute": bool(auto_execute),
    }
    if webhook_url is not None:
        if not isinstance(webhook_url, str) or not webhook_url.strip():
            raise ValueError("webhook_url must be a non-empty string when provided.")
        payload["webhook_url"] = webhook_url.strip()
    if execution_webhook_url is not None:
        if not isinstance(execution_webhook_url, str) or not execution_webhook_url.strip():
            raise ValueError("execution_webhook_url must be a non-empty string when provided.")
        payload["execution_webhook_url"] = execution_webhook_url.strip()
    if description is not None:
        if not isinstance(description, str) or not description.strip():
            raise ValueError("description must be a non-empty string when provided.")
        payload["description"] = description.strip()
    return payload


def register_trigger(
    client: DecisionEngineClient,
    *,
    name: str,
    condition: dict[str, Any],
    simulation_template: dict[str, Any],
    webhook_url: str | None = None,
    execution_webhook_url: str | None = None,
    auto_execute: bool = False,
    description: str | None = None,
) -> Any:
    data = client._request(
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


def list_triggers(
    client: DecisionEngineClient,
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
    data = client._request("GET", "/v1/triggers", params=params or None)
    return _validate_model("TriggerListResult", data)


def fire_trigger(
    client: DecisionEngineClient,
    trigger_id: str,
    *,
    force: bool = False,
) -> Any:
    data = client._request(
        "POST",
        f"/v1/triggers/{_validate_trigger_id(trigger_id)}/fire",
        json={"force": force},
    )
    return _validate_model("TriggerFireResult", data)


def pause_trigger(
    client: DecisionEngineClient,
    trigger_id: str,
    *,
    paused: bool = True,
) -> Any:
    data = client._request(
        "PATCH",
        f"/v1/triggers/{_validate_trigger_id(trigger_id)}/pause",
        params={"paused": paused},
    )
    return _validate_model("TriggerPauseResult", data)


def delete_trigger(client: DecisionEngineClient, trigger_id: str) -> Any:
    normalized_trigger_id = _validate_trigger_id(trigger_id)
    data = client._request("DELETE", f"/v1/triggers/{normalized_trigger_id}")
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
