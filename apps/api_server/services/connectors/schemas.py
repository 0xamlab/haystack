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


class ConnectorPreviewRequest(BaseModel):
    connector_type: str
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
    status: str | None = None
    error_type: str | None = None
    recoverable: bool | None = None


# ─── Connector type constants ─────────────────────────────────────────────────

VALID_TYPES = {
    "s3",
    "gcs",
    "azure",
    "clickhouse",
    "bigquery",
    "snowflake",
    "redshift",
    "postgres",
    "postgresql",
    "sqlite",
    "mysql",
    "mssql",
    "oracle",
    "neo4j",
    "redis",
    "elastic",
    "elasticsearch",
    "rest",
    "rest_api",
    "file",
    "file_upload",
    "github_repo",
    "gitlab_repo",
    "bitbucket_repo",
    "local_repo",
    "repo_archive",
}

TYPE_NORMALIZE: dict[str, str] = {
    "postgresql": "postgres",
    "click_house": "clickhouse",
    "redis_cache": "redis",
    "elastic": "elasticsearch",
    "rest_api": "rest",
    "file_upload": "file",
    "github": "github_repo",
    "github_repository": "github_repo",
    "gitlab": "gitlab_repo",
    "gitlab_repository": "gitlab_repo",
    "bitbucket": "bitbucket_repo",
    "bitbucket_repository": "bitbucket_repo",
    "local_repository": "local_repo",
    "archive_repository": "repo_archive",
}


def normalize_type(connector_type: str) -> str:
    """Normalize frontend connector type names to DB enum values."""
    normalized = connector_type.lower().replace("-", "_")
    return TYPE_NORMALIZE.get(normalized, normalized)
