from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from algenta.runtime_model_common import coerce_payload_mapping


@dataclass(frozen=True)
class SourceRegistration:
    source_id: str | None
    dataset_id: str | None
    name: str | None
    status: str
    ingest_mode: str | None = None
    source_schema: dict[str, Any] | None = None
    planner_cache_hit: bool | None = None
    planner_schema_revision: str | None = None
    planner_prewarm_ms: float | None = None
    latency_ms: float | None = None
    row_count: int | None = None
    # Local registrations infer coarse per-field types ({name, type} with type in
    # number/string/boolean/date/unknown). Optional and additive; also mirrored
    # under source_schema["typed_fields"].
    typed_fields: list[dict[str, str]] | None = None

    @property
    def dataset_name(self) -> str | None:
        return self.name

    @classmethod
    def from_api(cls, payload: Any) -> SourceRegistration:
        data = coerce_payload_mapping(payload)
        return cls(
            source_id=data.get("source_id"),
            dataset_id=data.get("dataset_id"),
            name=data.get("name") or data.get("dataset_name"),
            status=data["status"],
            ingest_mode=data.get("ingest_mode"),
            source_schema=data.get("source_schema") or data.get("schema"),
            planner_cache_hit=data.get("planner_cache_hit"),
            planner_schema_revision=data.get("planner_schema_revision"),
            planner_prewarm_ms=data.get("planner_prewarm_ms"),
            latency_ms=data.get("latency_ms"),
            row_count=_registration_row_count(data),
            typed_fields=_registration_typed_fields(data),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _registration_row_count(data: dict[str, Any]) -> int | None:
    direct_row_count = data.get("row_count")
    if isinstance(direct_row_count, int):
        return direct_row_count
    source_schema = data.get("source_schema") or data.get("schema")
    if isinstance(source_schema, dict):
        schema_row_count = source_schema.get("row_count")
        if isinstance(schema_row_count, int):
            return schema_row_count
    return None


def _registration_typed_fields(data: dict[str, Any]) -> list[dict[str, str]] | None:
    direct_typed_fields = data.get("typed_fields")
    if isinstance(direct_typed_fields, list):
        return direct_typed_fields
    source_schema = data.get("source_schema") or data.get("schema")
    if isinstance(source_schema, dict):
        schema_typed_fields = source_schema.get("typed_fields")
        if isinstance(schema_typed_fields, list):
            return schema_typed_fields
    return None
