from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from algenta.runtime_connector_model_common import coerce_payload_mapping, jsonable


@dataclass(frozen=True)
class ConnectorTestOutput:
    success: bool
    message: str
    latency_ms: int | None = None
    status: str | None = None
    error_type: str | None = None
    recoverable: bool | None = None

    @classmethod
    def from_api(cls, payload: Any) -> ConnectorTestOutput:
        data = coerce_payload_mapping(payload)
        return cls(
            success=bool(data["success"]),
            message=str(data["message"]),
            latency_ms=data.get("latency_ms"),
            status=data.get("status"),
            error_type=data.get("error_type"),
            recoverable=data.get("recoverable"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConnectorBrowseOutput:
    connector_type: str
    items: list[dict[str, Any]]
    total: int
    message: str
    labels: dict[str, Any] = field(default_factory=dict)
    discovery: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: Any) -> ConnectorBrowseOutput:
        data = coerce_payload_mapping(payload)
        return cls(
            connector_type=str(data["connector_type"]),
            items=list(data.get("items") or []),
            total=int(data["total"]),
            message=str(data["message"]),
            labels=dict(data.get("labels") or {}),
            discovery=dict(data.get("discovery") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))
