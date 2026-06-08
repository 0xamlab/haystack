from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from algenta.runtime_model_common import coerce_payload_mapping, jsonable


def _require_string(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _require_identifier_text(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if isinstance(value, UUID):
        return str(value)
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _require_integer(data: dict[str, Any], key: str, context: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{context}.{key} must be an integer.")
    return value


def _require_non_negative_integer(data: dict[str, Any], key: str, context: str) -> int:
    value = _require_integer(data, key, context)
    if value < 0:
        raise TypeError(f"{context}.{key} must be greater than or equal to 0.")
    return value


def _optional_non_negative_integer(
    data: dict[str, Any],
    key: str,
    context: str,
) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TypeError(f"{context}.{key} must be an integer greater than or equal to 0.")
    return value


def _require_number(data: dict[str, Any], key: str, context: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{context}.{key} must be a number.")
    return float(value)


def _require_datetime_text(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if isinstance(value, datetime):
        return value.isoformat()
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


def _optional_datetime_text(data: dict[str, Any], key: str, context: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


@dataclass(frozen=True)
class UsageOutput:
    org_id: str
    billing_period: str
    simulations_run: int
    api_calls: int
    quota_limit: int
    quota_used_pct: float

    @classmethod
    def from_api(cls, payload: Any) -> UsageOutput:
        context = "usage"
        data = coerce_payload_mapping(payload)
        return cls(
            org_id=_require_identifier_text(data, "org_id", context),
            billing_period=_require_string(data, "billing_period", context),
            simulations_run=_require_integer(data, "simulations_run", context),
            api_calls=_require_integer(data, "api_calls", context),
            quota_limit=_require_integer(data, "quota_limit", context),
            quota_used_pct=_require_number(data, "quota_used_pct", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class APIKeyInfoOutput:
    id: str
    label: str
    key_prefix: str
    device_limit: int | None
    status: str
    created_at: str
    last_used_at: str | None = None
    expires_at: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> APIKeyInfoOutput:
        context = "api_keys.item"
        data = coerce_payload_mapping(payload)
        return cls(
            id=_require_identifier_text(data, "id", context),
            label=_require_string(data, "label", context),
            key_prefix=_require_string(data, "key_prefix", context),
            device_limit=_optional_non_negative_integer(data, "device_limit", context),
            status=_require_string(data, "status", context),
            created_at=_require_datetime_text(data, "created_at", context),
            last_used_at=_optional_datetime_text(data, "last_used_at", context),
            expires_at=_optional_datetime_text(data, "expires_at", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class APIKeyCreatedOutput:
    id: str
    label: str
    key_prefix: str
    device_limit: int | None
    raw_key: str
    created_at: str
    expires_at: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> APIKeyCreatedOutput:
        context = "api_key_created"
        data = coerce_payload_mapping(payload)
        key_prefix = _require_string(data, "key_prefix", context)
        raw_key = _require_string(data, "raw_key", context)
        if not raw_key.startswith(key_prefix):
            raise TypeError(f"{context}.raw_key must start with key_prefix.")
        return cls(
            id=_require_identifier_text(data, "id", context),
            label=_require_string(data, "label", context),
            key_prefix=key_prefix,
            device_limit=_optional_non_negative_integer(data, "device_limit", context),
            raw_key=raw_key,
            created_at=_require_datetime_text(data, "created_at", context),
            expires_at=_optional_datetime_text(data, "expires_at", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))
