from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any


def coerce_payload_mapping(payload: Any) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    if isinstance(payload, Mapping):
        return dict(payload)
    payload_dict = getattr(payload, "__dict__", None)
    if isinstance(payload_dict, dict):
        return dict(payload_dict)
    return dict(payload)


def jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    return value
