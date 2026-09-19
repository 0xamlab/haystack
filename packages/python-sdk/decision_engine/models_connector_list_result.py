# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .models_connector_info import ConnectorInfo


class ConnectorListResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    connectors: list[ConnectorInfo] = Field(default_factory=list)
    total: int
    page: int
    limit: int
    pages: int


__all__ = ["ConnectorListResult"]
