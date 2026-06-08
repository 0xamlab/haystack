from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .models_query_result import QueryResult


class QueryExecutionMetadata(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    request_id: str | None = None
    latency_ms: float | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    cache_hit: bool | None = None


class QueryWithMetadataResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    data: QueryResult
    metadata: QueryExecutionMetadata
    headers: dict[str, str] = Field(default_factory=dict)


class QueryBatchError(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class QueryBatchItemResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    key: str
    data: QueryResult | None = None
    metadata: QueryExecutionMetadata | None = None
    error: QueryBatchError | None = None


class QueryBatchResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    results: list[QueryBatchItemResult] = Field(default_factory=list)
    request_id: str | None = None


class QuerySqlReportResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int
    truncated: bool = False
    request_id: str | None = None
    latency_ms: float
