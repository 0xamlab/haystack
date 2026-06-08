from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConnectorTestInfo(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    success: bool
    message: str
    latency_ms: int | None = None
    status: str | None = None
    error_type: str | None = None
    recoverable: bool | None = None


class ConnectorBrowseResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    connector_type: str
    items: list[dict[str, Any]] = Field(default_factory=list)
    total: int
    message: str
    labels: dict[str, Any] = Field(default_factory=dict)
    discovery: dict[str, Any] = Field(default_factory=dict)
