# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DatasetInfo(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    dataset_id: str
    name: str | None = None
    source_id: str | None = None
    dataset_name: str
    status: str | None = None
    source_names: list[str] = Field(default_factory=list)
    source_name: str | None = None
    description: str | None = None
    connection_id: str | None = None
    connection_type: str | None = None
    provider: str | None = None
    visibility: str = "private"
    owner_user_id: str | None = None
    owner_key_id: str | None = None
    refreshable: bool = False
    row_count: int | None = None
    column_count: int | None = None
    columns: int | None = None
    roles_summary: dict[str, Any] = Field(default_factory=dict)
    discovery_labels: dict[str, Any] | None = None
    discovery_metadata: dict[str, Any] | None = None
    registered_at: datetime | None = None
    selection: dict[str, Any] | None = None


class DatasetListResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    datasets: list[DatasetInfo] = Field(default_factory=list)
    count: int
    total: int
    matched_total: int | None = None
    page: int
    limit: int
    pages: int


class DatasetSummaryResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    dataset_id: str
    name: str
    status: str
    source_names: list[str] = Field(default_factory=list)
    row_count: int | None = None
    column_count: int
    registered_at: datetime | None = None
    query_hints: list[dict[str, Any]] = Field(default_factory=list)


class DatasetDetailResult(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True, defer_build=True)

    dataset: DatasetInfo
    schema_payload: dict[str, Any] = Field(default_factory=dict, alias="schema")

    @property
    def schema(self) -> dict[str, Any]:
        return self.schema_payload


class DatasetDeleteResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    dataset_id: str
    status: str
    connection_deleted: bool = False


class DatasetConnectResult(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True, defer_build=True)

    status: str
    dataset_id: str | None = None
    source_id: str | None = None
    dataset_name: str | None = None
    schema_payload: dict[str, Any] | None = Field(default=None, alias="schema")
    schema_summary: dict[str, Any] | None = None
    connection_id: str | None = None
    connection_type: str | None = None
    provider: str | None = None
    labels: dict[str, Any] | None = None
    discovery: dict[str, Any] | None = None
    visibility: str | None = None
    selection: dict[str, Any] | None = None
    refreshable: bool | None = None
    latency_ms: float | None = None
    message: str | None = None
    choices: list[dict[str, Any]] | None = None

    @property
    def schema(self) -> dict[str, Any] | None:
        return self.schema_payload
