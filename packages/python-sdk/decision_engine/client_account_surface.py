from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .model_loader import validate_model as _validate_model
from .model_loader import validate_model_list as _validate_model_list

if TYPE_CHECKING:
    from .client_facade import DecisionEngineClient


def _require_api_key_prefix(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise TypeError(f"API key payload must be a JSON object, got {type(payload).__name__}.")
    key_prefix = payload.get("key_prefix")
    if not isinstance(key_prefix, str) or not key_prefix:
        raise ValueError(f"API key payload missing key_prefix: {payload!r}")
    return key_prefix


def _require_optional_device_limit(payload: Any) -> int | None:
    if not isinstance(payload, dict):
        raise TypeError(f"API key payload must be a JSON object, got {type(payload).__name__}.")
    device_limit = payload.get("device_limit")
    if device_limit is None:
        return None
    if not isinstance(device_limit, int) or device_limit < 0:
        raise ValueError(f"API key payload has invalid device_limit: {payload!r}")
    return device_limit


def _extract_api_key_list_items(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        items = data.get("api_keys")
        if isinstance(items, list):
            return items
    raise TypeError(
        f"API key list response must be a list or paginated object, got {type(data).__name__}."
    )


def _validate_api_key_list_payload(data: Any) -> list[Any]:
    items = _extract_api_key_list_items(data)
    for item in items:
        _require_api_key_prefix(item)
        _require_optional_device_limit(item)
        if isinstance(item, dict) and ("raw_key" in item or "key" in item):
            raise ValueError(f"API key list response leaked one-time secret material: {item!r}")
    return items


def _validate_api_key_create_payload(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise TypeError(
            f"API key create response must be a JSON object, got {type(data).__name__}."
        )
    key_prefix = _require_api_key_prefix(data)
    _require_optional_device_limit(data)
    raw_key = data.get("raw_key")
    if not isinstance(raw_key, str) or not raw_key or not raw_key.startswith(key_prefix):
        raise ValueError(f"API key create response missing raw_key: {data!r}")
    return data


def _request_model(
    client: DecisionEngineClient,
    method: str,
    path: str,
    model_name: str,
) -> Any:
    data = client._request(method, path)
    return _validate_model(model_name, data)


def _request_list_or_paginated_model(
    client: DecisionEngineClient,
    *,
    path: str,
    item_model_name: str,
    envelope_model_name: str,
    envelope_field: str,
) -> Any:
    data = client._request("GET", path)
    if isinstance(data, list):
        items = _validate_model_list(item_model_name, data)
        return _validate_model(
            envelope_model_name,
            {
                envelope_field: items,
                "total": len(items),
                "page": 1,
                "limit": len(items) or 1,
                "pages": 1,
            },
        )
    if isinstance(data, dict):
        return _validate_model(envelope_model_name, data)
    raise TypeError(
        f"{path} response must be a JSON list or object, got {type(data).__name__}."
    )


def _normalize_update_me_request(
    *,
    name: str | None = None,
    org_name: str | None = None,
) -> dict[str, str]:
    payload: dict[str, str] = {}
    if name is not None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string when provided.")
        payload["name"] = name.strip()
    if org_name is not None:
        if not isinstance(org_name, str) or not org_name.strip():
            raise ValueError("org_name must be a non-empty string when provided.")
        payload["org_name"] = org_name.strip()
    if not payload:
        raise ValueError("update_me() requires name and/or org_name.")
    return payload


def me(client: DecisionEngineClient) -> Any:
    return _request_model(client, "GET", "/v1/me", "MeResult")


def update_me(
    client: DecisionEngineClient,
    *,
    name: str | None = None,
    org_name: str | None = None,
) -> Any:
    data = client._request(
        "PATCH",
        "/v1/me",
        json=_normalize_update_me_request(name=name, org_name=org_name),
    )
    return _validate_model("MeResult", data)


def usage(client: DecisionEngineClient) -> Any:
    return _request_model(client, "GET", "/v1/usage", "UsageInfo")


def limits(client: DecisionEngineClient) -> dict[str, Any]:
    return client._request("GET", "/v1/limits")


def list_api_keys(client: DecisionEngineClient) -> Any:
    data = client._request("GET", "/v1/api-keys")
    return _validate_model_list("APIKeyInfo", _validate_api_key_list_payload(data))


def create_api_key(
    client: DecisionEngineClient,
    label: str | None = None,
    *,
    name: str | None = None,
    expires_at: datetime | str | None = None,
    device_limit: int | None = None,
) -> dict[str, Any]:
    resolved_label = label or name
    if not resolved_label:
        raise ValueError("create_api_key() requires label= or name=")
    payload: dict[str, Any] = {"label": resolved_label}
    if expires_at is not None:
        if isinstance(expires_at, datetime):
            normalized = (
                expires_at if expires_at.tzinfo is not None else expires_at.replace(tzinfo=UTC)
            )
            payload["expires_at"] = normalized.isoformat()
        elif isinstance(expires_at, str):
            payload["expires_at"] = expires_at
        else:
            raise TypeError("expires_at must be a datetime, ISO-8601 string, or None")
    if device_limit is not None:
        if not isinstance(device_limit, int):
            raise TypeError("device_limit must be an integer or None")
        if device_limit < 0:
            raise ValueError("device_limit must be greater than or equal to 0")
        payload["device_limit"] = device_limit
    return _validate_api_key_create_payload(client._request("POST", "/v1/api-keys", json=payload))


def revoke_api_key(client: DecisionEngineClient, key_id: str) -> dict[str, Any]:
    return client._request("DELETE", f"/v1/api-keys/{key_id}")


def distributions(client: DecisionEngineClient) -> Any:
    return _request_list_or_paginated_model(
        client,
        path="/v1/distributions",
        item_model_name="DistributionInfoResult",
        envelope_model_name="DistributionListResult",
        envelope_field="distributions",
    )


def templates(client: DecisionEngineClient) -> Any:
    return _request_list_or_paginated_model(
        client,
        path="/v1/templates",
        item_model_name="TemplateInfoResult",
        envelope_model_name="TemplateListResult",
        envelope_field="templates",
    )


def health(client: DecisionEngineClient) -> dict[str, Any]:
    return client._request("GET", "/v1/health")


def version(client: DecisionEngineClient) -> dict[str, Any]:
    return client._request("GET", "/v1/version")


__all__ = [
    "create_api_key",
    "distributions",
    "health",
    "limits",
    "list_api_keys",
    "me",
    "update_me",
    "revoke_api_key",
    "templates",
    "usage",
    "version",
]
