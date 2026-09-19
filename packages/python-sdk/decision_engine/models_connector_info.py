# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConnectorInfo(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    id: str
    name: str
    description: str | None = None
    connector_type: str
    status: str
    visibility: str
    last_tested_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime | None = None


__all__ = ["ConnectorInfo"]
