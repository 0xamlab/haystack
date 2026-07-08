"""algenta.client helpers — free functions used across the client mixins.

Extracted from packages/algenta-core/algenta/client.py during modularization.
"""
from __future__ import annotations

from typing import Any


def _sdk_payload_to_plain_data(payload: Any) -> Any:
    if isinstance(payload, list):
        return [_sdk_payload_to_plain_data(item) for item in payload]
    if isinstance(payload, tuple):
        return tuple(_sdk_payload_to_plain_data(item) for item in payload)
    if isinstance(payload, dict):
        return {
            str(key): _sdk_payload_to_plain_data(value)
            for key, value in payload.items()
        }
    model_dump = getattr(payload, "model_dump", None)
    if callable(model_dump):
        return model_dump()
    to_dict = getattr(payload, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return payload


def _cloud_get(path: str, api_key: str, base_url: str) -> dict[str, Any]:
    try:
        import httpx
    except ImportError:
        raise ImportError("Cloud mode requires: pip install algenta-core[cloud]") from None
    resp = httpx.get(
        f"{base_url}{path}",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
