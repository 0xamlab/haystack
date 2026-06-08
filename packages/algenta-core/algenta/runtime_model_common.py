from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any

from pydantic import BaseModel


def _normalize_payload_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return {
            key: _normalize_payload_value(item)
            for key, item in value.__dict__.items()
            if not key.startswith("_")
        }
    if isinstance(value, Mapping):
        return {
            jsonable(key): _normalize_payload_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_payload_value(item) for item in value]
    return value


def coerce_payload_mapping(payload: Any) -> dict[str, Any]:
    if isinstance(payload, BaseModel):
        normalized = _normalize_payload_value(payload)
        if isinstance(normalized, Mapping):
            return dict(normalized)
    model_dump = getattr(payload, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, Mapping):
            return {
                jsonable(key): _normalize_payload_value(item)
                for key, item in dumped.items()
            }
    if isinstance(payload, Mapping):
        return {jsonable(key): _normalize_payload_value(item) for key, item in payload.items()}
    payload_dict = getattr(payload, "__dict__", None)
    if isinstance(payload_dict, dict):
        return {
            jsonable(key): _normalize_payload_value(item)
            for key, item in payload_dict.items()
        }
    return dict(_normalize_payload_value(payload))


def jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, dict):
        return {jsonable(key): jsonable(item) for key, item in value.items()}
    return value
