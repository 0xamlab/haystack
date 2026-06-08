from __future__ import annotations

from dataclasses import asdict, dataclass, field
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


def _optional_string(data: dict[str, Any], key: str, context: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise TypeError(f"{context}.{key} must be a non-empty string.")
    return value


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


def _require_string_any(data: dict[str, Any], keys: tuple[str, ...], context: str) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    joined = "/".join(keys)
    raise TypeError(f"{context}.{joined} must include a non-empty string.")


def _require_number(data: dict[str, Any], key: str, context: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{context}.{key} must be a number.")
    return float(value)


def _require_integer(data: dict[str, Any], key: str, context: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{context}.{key} must be an integer.")
    return value


@dataclass(frozen=True)
class DeploymentRegionOutput:
    id: str
    name: str
    label: str | None = None
    location: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> DeploymentRegionOutput:
        context = "deployment_regions.providers.item.regions.item"
        data = coerce_payload_mapping(payload)
        name = _require_string_any(data, ("name", "label"), context)
        label = _optional_string(data, "label", context) or name
        return cls(
            id=_require_string(data, "id", context),
            name=name,
            label=label,
            location=_optional_string(data, "location", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class DeploymentProviderOutput:
    id: str
    name: str
    description: str
    icon: str
    regions: list[DeploymentRegionOutput] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> DeploymentProviderOutput:
        context = "deployment_regions.providers.item"
        data = coerce_payload_mapping(payload)
        raw_regions = data.get("regions") or []
        if not isinstance(raw_regions, list):
            raise TypeError(f"{context}.regions must be a list.")
        return cls(
            id=_require_string(data, "id", context),
            name=_require_string(data, "name", context),
            description=_require_string(data, "description", context),
            icon=_require_string(data, "icon", context),
            regions=[DeploymentRegionOutput.from_api(item) for item in raw_regions],
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class DeploymentRegionsOutput:
    providers: list[DeploymentProviderOutput] = field(default_factory=list)

    @classmethod
    def from_api(cls, payload: Any) -> DeploymentRegionsOutput:
        context = "deployment_regions"
        data = coerce_payload_mapping(payload)
        raw_providers = data.get("providers") or []
        if not isinstance(raw_providers, list):
            raise TypeError(f"{context}.providers must be a list.")
        return cls(
            providers=[DeploymentProviderOutput.from_api(item) for item in raw_providers],
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class DeploymentOutput:
    deployment_id: str
    org_id: str
    provider: str
    region: str
    status: str
    endpoint_url: str | None
    cost_usd_month: float
    billable_cost_usd_month: float
    billing_markup_pct: float
    created_at: str
    provisioned_at: str | None = None
    error_message: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> DeploymentOutput:
        context = "deployment"
        data = coerce_payload_mapping(payload)
        return cls(
            deployment_id=_require_identifier_text(data, "deployment_id", context),
            org_id=_require_identifier_text(data, "org_id", context),
            provider=_require_string(data, "provider", context),
            region=_require_string(data, "region", context),
            status=_require_string(data, "status", context),
            endpoint_url=_optional_string(data, "endpoint_url", context),
            cost_usd_month=_require_number(data, "cost_usd_month", context),
            billable_cost_usd_month=_require_number(data, "billable_cost_usd_month", context),
            billing_markup_pct=_require_number(data, "billing_markup_pct", context),
            created_at=_require_datetime_text(data, "created_at", context),
            provisioned_at=_optional_datetime_text(data, "provisioned_at", context),
            error_message=_optional_string(data, "error_message", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class DeploymentDeleteOutput:
    status: str
    deployment_id: str

    @classmethod
    def from_api(cls, payload: Any) -> DeploymentDeleteOutput:
        context = "deployment_delete"
        data = coerce_payload_mapping(payload)
        return cls(
            status=_require_string(data, "status", context),
            deployment_id=_require_identifier_text(data, "deployment_id", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class DeploymentCostOutput:
    deployment_id: str
    provider: str
    region: str
    year: int
    month: int
    cost_usd_month: float
    billable_cost_usd_month: float
    billing_markup_pct: float
    last_updated: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> DeploymentCostOutput:
        context = "deployment_cost"
        data = coerce_payload_mapping(payload)
        return cls(
            deployment_id=_require_identifier_text(data, "deployment_id", context),
            provider=_require_string(data, "provider", context),
            region=_require_string(data, "region", context),
            year=_require_integer(data, "year", context),
            month=_require_integer(data, "month", context),
            cost_usd_month=_require_number(data, "cost_usd_month", context),
            billable_cost_usd_month=_require_number(data, "billable_cost_usd_month", context),
            billing_markup_pct=_require_number(data, "billing_markup_pct", context),
            last_updated=_optional_datetime_text(data, "last_updated", context),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))
