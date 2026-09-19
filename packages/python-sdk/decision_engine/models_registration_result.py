# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SourceRegistrationResult(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True, defer_build=True)

    source_id: str | None = None
    dataset_id: str | None = None
    name: str | None = None
    dataset_name: str | None = None
    status: str
    ingest_mode: str | None = None
    source_schema: dict[str, Any] | None = Field(default=None, alias="schema")
    planner_cache_hit: bool | None = None
    planner_schema_revision: str | None = None
    planner_prewarm_ms: float | None = None
    latency_ms: float | None = None
    row_count: int | None = None
