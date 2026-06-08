from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from algenta.runtime_model_common import coerce_payload_mapping, jsonable
from algenta.runtime_model_query_output import QueryOutput


@dataclass(frozen=True)
class QueryExecutionMetadata:
    request_id: str | None = None
    latency_ms: float | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    cache_hit: bool | None = None

    @classmethod
    def from_api(cls, payload: Any) -> QueryExecutionMetadata:
        data = coerce_payload_mapping(payload)
        return cls(
            request_id=data.get("request_id"),
            latency_ms=data.get("latency_ms"),
            tokens_in=data.get("tokens_in"),
            tokens_out=data.get("tokens_out"),
            cost_usd=data.get("cost_usd"),
            cache_hit=data.get("cache_hit"),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class QueryWithMetadataOutput:
    data: QueryOutput
    metadata: QueryExecutionMetadata
    headers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: Any) -> QueryWithMetadataOutput:
        data = coerce_payload_mapping(payload)
        return cls(
            data=QueryOutput.from_api(data["data"]),
            metadata=QueryExecutionMetadata.from_api(data.get("metadata") or {}),
            headers={
                str(key): str(value) for key, value in dict(data.get("headers") or {}).items()
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class QueryBatchError:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: Any) -> QueryBatchError:
        data = coerce_payload_mapping(payload)
        return cls(
            code=str(data["code"]),
            message=str(data["message"]),
            details=dict(data.get("details") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class QueryBatchItemOutput:
    key: str
    data: QueryOutput | None = None
    metadata: QueryExecutionMetadata | None = None
    error: QueryBatchError | None = None

    @classmethod
    def from_api(cls, payload: Any) -> QueryBatchItemOutput:
        data = coerce_payload_mapping(payload)
        item_data = data.get("data")
        metadata = data.get("metadata")
        error = data.get("error")
        return cls(
            key=str(data["key"]),
            data=QueryOutput.from_api(item_data) if item_data is not None else None,
            metadata=QueryExecutionMetadata.from_api(metadata) if metadata is not None else None,
            error=QueryBatchError.from_api(error) if error is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class QueryBatchOutput:
    results: list[QueryBatchItemOutput] = field(default_factory=list)
    request_id: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> QueryBatchOutput:
        data = coerce_payload_mapping(payload)
        return cls(
            results=[QueryBatchItemOutput.from_api(item) for item in data.get("results") or []],
            request_id=data.get("request_id"),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class QuerySqlReportOutput:
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    request_id: str | None = None
    latency_ms: float = 0.0

    @classmethod
    def from_api(cls, payload: Any) -> QuerySqlReportOutput:
        data = coerce_payload_mapping(payload)
        return cls(
            columns=[str(column) for column in data.get("columns") or []],
            rows=[dict(row) for row in data.get("rows") or []],
            row_count=int(data.get("row_count", 0)),
            truncated=bool(data.get("truncated", False)),
            request_id=data.get("request_id"),
            latency_ms=float(data.get("latency_ms", 0.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))
