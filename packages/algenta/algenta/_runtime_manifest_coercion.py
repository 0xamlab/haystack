"""Payload coercion + validation helpers.

Auto-extracted from runtime_model_manifest.py.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel

from algenta.runtime_model_common import jsonable

from algenta._runtime_manifest_enums import EnumT


def _normalize_manifest_payload_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return {
            key: _normalize_manifest_payload_value(item)
            for key, item in value.__dict__.items()
            if not key.startswith("_")
        }
    if isinstance(value, Mapping):
        return {
            jsonable(key): _normalize_manifest_payload_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize_manifest_payload_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_normalize_manifest_payload_value(item) for item in value)
    return value


def coerce_payload_mapping(payload: Any) -> dict[str, Any]:
    if isinstance(payload, BaseModel):
        normalized = _normalize_manifest_payload_value(payload)
        if isinstance(normalized, Mapping):
            return dict(normalized)
    model_dump = getattr(payload, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, Mapping):
            return {
                jsonable(key): _normalize_manifest_payload_value(item)
                for key, item in dumped.items()
            }
    if isinstance(payload, Mapping):
        return {
            jsonable(key): _normalize_manifest_payload_value(item)
            for key, item in payload.items()
        }
    payload_dict = getattr(payload, "__dict__", None)
    if isinstance(payload_dict, dict):
        return {
            jsonable(key): _normalize_manifest_payload_value(item)
            for key, item in payload_dict.items()
        }
    return dict(_normalize_manifest_payload_value(payload))


def _coerce_enum(value: Any, enum_cls: type[EnumT], field_name: str | None = None) -> EnumT:
    if isinstance(value, enum_cls):
        return value
    candidate = value.value if isinstance(value, Enum) else str(value)
    try:
        return enum_cls(candidate)
    except ValueError as exc:
        if field_name:
            raise ValueError(
                f"{field_name}: {value!r} is not a valid {enum_cls.__name__}"
            ) from exc
        raise


def _coerce_optional_enum(
    value: Any,
    enum_cls: type[EnumT],
    field_name: str | None = None,
) -> EnumT | None:
    if value is None:
        return None
    return _coerce_enum(value, enum_cls, field_name)


def _coerce_enum_list(
    values: Any,
    enum_cls: type[EnumT],
    field_name: str | None = None,
) -> list[EnumT]:
    if values is None:
        return []
    if not isinstance(values, list):
        if field_name:
            raise ValueError(f"{field_name} must be a list.")
        raise ValueError(f"{enum_cls.__name__} values must be a list.")
    coerced: list[EnumT] = []
    for index, item in enumerate(values):
        item_field = None if field_name is None else f"{field_name}.{index}"
        coerced.append(_coerce_enum(item, enum_cls, item_field))
    return coerced


def _coerce_enum_mapping(
    values: Any,
    key_enum_cls: type[EnumT],
    value_coercer: Any,
    field_name: str,
) -> dict[EnumT, Any]:
    if values is None:
        return {}
    if not isinstance(values, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")
    coerced: dict[EnumT, Any] = {}
    for raw_key, raw_value in values.items():
        key = _coerce_enum(raw_key, key_enum_cls, f"{field_name}.{raw_key}.[key]")
        coerced[key] = value_coercer(raw_value, key)
    return coerced


def _normalized_manifest_runtime_value(value: object) -> str:
    if isinstance(value, Enum):
        return value.value
    return str(value)


def _ensure_unique_manifest_values(
    values: list[Any],
    field_name: str,
    *,
    value_selector: Any | None = None,
) -> list[Any]:
    selector = value_selector or (lambda item: item)
    seen: set[str] = set()
    duplicates: list[str] = []
    for entry in values:
        normalized = _normalized_manifest_runtime_value(selector(entry))
        if normalized in seen and normalized not in duplicates:
            duplicates.append(normalized)
        seen.add(normalized)
    if duplicates:
        duplicate_text = ", ".join(duplicates)
        raise ValueError(f"{field_name} must be unique; duplicate entries: {duplicate_text}")
    return values


def _count_manifest_values(values: list[Any]) -> dict[Any, int]:
    counts: dict[Any, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _require_manifest_field(data: dict[str, Any], key: str, context: str) -> Any:
    if key not in data:
        raise ValueError(f"{context}.{key} is required.")
    return data[key]


def _require_manifest_string_value(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")
    return value


def _require_manifest_integer_value(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")
    return value


def _require_manifest_float_value(value: Any, field_name: str) -> float:
    if not isinstance(value, float):
        raise ValueError(f"{field_name} must be a float.")
    return value


def _require_manifest_boolean_value(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")
    return value


def _require_manifest_string(data: dict[str, Any], key: str, context: str) -> str:
    return _require_manifest_string_value(
        _require_manifest_field(data, key, context),
        f"{context}.{key}",
    )


def _require_manifest_integer(data: dict[str, Any], key: str, context: str) -> int:
    return _require_manifest_integer_value(
        _require_manifest_field(data, key, context),
        f"{context}.{key}",
    )


def _require_manifest_float(data: dict[str, Any], key: str, context: str) -> float:
    return _require_manifest_float_value(
        _require_manifest_field(data, key, context),
        f"{context}.{key}",
    )


def _require_manifest_boolean(data: dict[str, Any], key: str, context: str) -> bool:
    return _require_manifest_boolean_value(
        _require_manifest_field(data, key, context),
        f"{context}.{key}",
    )


def _optional_manifest_float(data: dict[str, Any], key: str, context: str) -> float | None:
    if data.get(key) is None:
        return None
    return _require_manifest_float(data, key, context)


def _optional_manifest_string(data: dict[str, Any], key: str, context: str) -> str | None:
    if data.get(key) is None:
        return None
    return _require_manifest_string(data, key, context)


def _optional_manifest_string_list(
    data: dict[str, Any],
    key: str,
    context: str,
) -> list[str]:
    values = data.get(key)
    if values is None:
        return []
    field_name = f"{context}.{key}"
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list.")
    return [
        _require_manifest_string_value(item, f"{field_name}.{index}")
        for index, item in enumerate(values)
    ]


