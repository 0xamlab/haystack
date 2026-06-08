from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class DataSource(BaseModel):
    """
    A data source to map. Every format normalizes to list[dict] internally.

    Inline (no external dependency):
      `records`    — JSON array of objects (fastest)
      `csv`        — raw CSV text
      `json_str`   — raw JSON array/object text (nested JSON is auto-flattened)
      `url`        — HTTP(S) URL; format auto-detected from Content-Type / extension

    Binary files (base64-encoded for API transport):
      `excel_b64`  — Excel .xlsx file, base64-encoded
      `parquet_b64`— Parquet file, base64-encoded

    Connector config (routes through ConnectorRegistry):
      `connection` — dict with `type` + connector-specific keys:
        {"type": "sql",        "connection_string": "postgresql+asyncpg://...",
         "query": "SELECT ..."}
        {"type": "sql",        "connection_string": "sqlite+aiosqlite:///db.sqlite", "query": "..."}
        {"type": "rest_api",   "url": "https://...", "data_path": "data.items"}
        {"type": "s3",         "bucket": "my-bucket", "key": "data/sales.parquet"}
        {"type": "gcs",        "bucket": "my-bucket", "blob": "data/orders.csv"}
        {"type": "azure_blob", "connection_string": "DefaultEndpointsProtocol=...",
                               "container": "data", "blob": "sales.parquet"}
    """

    name: str = Field(
        ...,
        description="Label for this source (e.g., 'sales', 'orders')",
    )
    dataset_id: str | None = Field(
        None,
        description="Public dataset ID alias for a registered source.",
    )
    source_id: str | None = Field(
        None,
        description="Registered source ID; fastest path and avoids re-uploading data.",
    )
    records: list[dict[str, Any]] | None = Field(None, description="Inline JSON records")
    csv: str | None = Field(None, description="Raw CSV text")
    json_str: str | None = Field(
        None,
        description="Raw JSON array/object text (nested auto-flattened)",
    )
    url: str | None = Field(None, description="HTTP URL — format auto-detected")
    excel_b64: str | None = Field(None, description="Excel .xlsx file, base64-encoded")
    parquet_b64: str | None = Field(None, description="Parquet file, base64-encoded")
    connection: dict[str, Any] | None = Field(
        None,
        description="Connector config dict — see DataSource docstring for all types",
    )
    table: str | None = Field(None, description="Legacy field — use connection instead")

    @model_validator(mode="after")
    def _sync_registered_aliases(self) -> DataSource:
        if self.dataset_id and not self.source_id:
            self.source_id = self.dataset_id
        elif self.source_id and not self.dataset_id:
            self.dataset_id = self.source_id
        return self


class FieldMapping(BaseModel):
    source_field: str
    source: str
    target_field: str
    target: str
    confidence: float = Field(..., ge=0, le=1)
    reason: list[str]
    match_type: str


class SchemaField(BaseModel):
    name: str
    sources: list[str]
    distribution: str | None = None
    unit: str | None = None
    polarity: int | None = None
    sample_values: list[Any] = []


class MapRequest(BaseModel):
    """
    Drop in any data sources. Get back semantic field mappings and a unified schema.

    No configuration required. The engine auto-detects:
    - Which fields represent the same concept across sources
    - Distribution shapes for numeric fields
    - Polarity (revenue → positive, cost → negative)
    - Primary/foreign keys for joins
    - Confidence and reasoning for every mapping
    """

    sources: list[DataSource] = Field(
        ...,
        min_length=1,
        description="Data sources to map (CSV, JSON records, or table name)",
    )
    min_confidence: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for mappings (default: 0.5)",
    )
    include_statistics: bool = Field(
        True,
        description="Include value distribution statistics in response",
    )


class MapResponse(BaseModel):
    map_id: str
    sources_analyzed: int
    total_fields: int
    mappings: list[FieldMapping]
    unified_schema: list[SchemaField]
    join_keys: list[dict[str, Any]]
    derived_relationships: list[dict[str, Any]]
    simulation_ready: bool
    simulation_payload: dict[str, Any] | None
    deep_analysis_pending: bool = False
    latency_ms: float


class _LegacyQueryRequest(BaseModel):
    """
    Natural language query over one or more data sources.

    Examples:
      "total revenue by customer"
      "average cost per product"
      "count orders where amount > 1000"
      "top 10 customers by revenue"
    """

    query: str = Field(..., description="Natural language query")
    sources: list[DataSource] = Field(..., min_length=1, description="Data sources to query")
    limit: int = Field(100, ge=1, le=10000, description="Max rows to return")


class _LegacyQueryResponse(BaseModel):
    query: str
    result: list[dict[str, Any]]
    row_count: int
    query_plan: str
    metric_field: str | None
    group_field: str | None
    aggregation: str
    confidence: float
    latency_ms: float
