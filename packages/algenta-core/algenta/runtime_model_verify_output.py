from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from algenta.runtime_model_common import coerce_payload_mapping


@dataclass(frozen=True)
class VerifyOutput:
    valid: bool
    errors: list[str]
    suggestions: list[str]
    resolved: dict[str, str]
    latency_ms: float
    verified: bool = False
    request_id: str | None = None
    schema_revision: str | None = None
    plan_hash: str | None = None
    verification_mode: str = "assist"
    rejection_reason: str | None = None
    valid_dimensions: list[str] = field(default_factory=list)
    valid_measures: list[str] = field(default_factory=list)
    source_behavior: str = ""

    @classmethod
    def from_api(cls, payload: Any) -> VerifyOutput:
        data = coerce_payload_mapping(payload)
        return cls(
            valid=data["valid"],
            errors=data.get("errors") or [],
            suggestions=data.get("suggestions") or [],
            resolved=data.get("resolved") or {},
            latency_ms=data["latency_ms"],
            verified=data.get("verified", False),
            request_id=data.get("request_id"),
            schema_revision=data.get("schema_revision"),
            plan_hash=data.get("plan_hash"),
            verification_mode=data.get("verification_mode", "assist"),
            rejection_reason=data.get("rejection_reason"),
            valid_dimensions=data.get("valid_dimensions") or [],
            valid_measures=data.get("valid_measures") or [],
            source_behavior=data.get("source_behavior", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
