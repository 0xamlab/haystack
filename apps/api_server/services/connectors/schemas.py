"""Pydantic schemas for the data connectors API."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ConnectorCreate(BaseModel):
    name: str
    connector_type: str
    description: str | None = None
    visibility: str | None = None
    config: dict[str, Any] | None = None


class ConnectorUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    visibility: str | None = None
    config: dict[str, Any] | None = None


class ConnectorResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    connector_type: str
    status: str
    visibility: str
    last_tested_at: datetime | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConnectorTestResult(BaseModel):
    success: bool
    message: str
    latency_ms: int | None = None


# ─── Connector type constants ─────────────────────────────────────────────────

VALID_TYPES = {
    "s3", "gcs", "azure", "bigquery", "snowflake", "redshift",
    "postgres", "postgresql", "sqlite", "mysql", "mssql", "rest", "rest_api", "file", "file_upload",
}

TYPE_NORMALIZE: dict[str, str] = {
    "postgresql":  "postgres",
    "rest_api":    "rest",
    "file_upload": "file",
}


def normalize_type(connector_type: str) -> str:
    """Normalize frontend connector type names to DB enum values."""
    normalized = connector_type.lower().replace("-", "_")
    return TYPE_NORMALIZE.get(normalized, normalized)
