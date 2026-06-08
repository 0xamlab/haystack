from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Literal, cast

from apps.api_server.services.connectors.tester import ConnectorTestOutcome
from apps.api_server.services.connectors.tester_common import FailureType


@dataclass(frozen=True)
class ConnectorBrowsePreviewOutcome:
    items: list[dict[str, Any]]
    message: str
    discovery: dict[str, Any]
    labels: dict[str, Any]


def copy_browse_outcome(outcome: ConnectorBrowsePreviewOutcome) -> ConnectorBrowsePreviewOutcome:
    return ConnectorBrowsePreviewOutcome(
        items=copy.deepcopy(outcome.items),
        message=outcome.message,
        discovery=copy.deepcopy(outcome.discovery),
        labels=copy.deepcopy(outcome.labels),
    )


def serialize_test_outcome(outcome: ConnectorTestOutcome) -> dict[str, Any]:
    return {
        "success": outcome.success,
        "message": outcome.message,
        "latency_ms": outcome.latency_ms,
        "status": outcome.status,
        "error_type": outcome.error_type,
        "recoverable": outcome.recoverable,
    }


def deserialize_test_outcome(payload: dict[str, Any]) -> ConnectorTestOutcome:
    status_raw = str(payload["status"])
    status: Literal["live", "error"] = "live" if status_raw == "live" else "error"
    error_type_raw = payload.get("error_type")
    error_type = None if error_type_raw is None else cast(FailureType, str(error_type_raw))
    return ConnectorTestOutcome(
        success=bool(payload["success"]),
        message=str(payload["message"]),
        latency_ms=int(payload["latency_ms"]),
        status=status,
        error_type=error_type,
        recoverable=(
            None if payload.get("recoverable") is None else bool(payload.get("recoverable"))
        ),
    )


def serialize_browse_outcome(outcome: ConnectorBrowsePreviewOutcome) -> dict[str, Any]:
    return {
        "items": outcome.items,
        "message": outcome.message,
        "discovery": outcome.discovery,
        "labels": outcome.labels,
    }


def deserialize_browse_outcome(payload: dict[str, Any]) -> ConnectorBrowsePreviewOutcome:
    return ConnectorBrowsePreviewOutcome(
        items=copy.deepcopy(list(payload["items"])),
        message=str(payload["message"]),
        discovery=copy.deepcopy(dict(payload["discovery"])),
        labels=copy.deepcopy(dict(payload["labels"])),
    )


__all__ = ["ConnectorBrowsePreviewOutcome"]
