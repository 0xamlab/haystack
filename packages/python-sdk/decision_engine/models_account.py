# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobStatus(BaseModel):
    """Job status returned by poll endpoint."""

    model_config = ConfigDict(extra="allow", defer_build=True)

    job_id: uuid.UUID
    run_id: uuid.UUID
    org_id: uuid.UUID
    status: str
    queue_name: str
    retry_count: int
    callback_url: str | None = None
    callback_status: str
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    ttl_expires_at: datetime | None = None
    poll_url: str


class JobSubmitResponse(BaseModel):
    """Returned immediately on async job submission."""

    model_config = ConfigDict(extra="allow", defer_build=True)

    job_id: uuid.UUID
    run_id: uuid.UUID
    status: str
    poll_url: str
    message: str = ""


class JobListResponse(BaseModel):
    """Paginated async job listing."""

    model_config = ConfigDict(extra="allow", defer_build=True)

    jobs: list[JobStatus]
    total: int
    page: int
    limit: int
    pages: int


class APIKeyInfo(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    id: uuid.UUID
    label: str
    key_prefix: str
    device_limit: int | None = None
    status: str
    created_at: datetime
    last_used_at: datetime | None = None
    expires_at: datetime | None = None


class UsageInfo(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    org_id: uuid.UUID
    billing_period: str
    simulations_run: int
    api_calls: int
    quota_limit: int
    quota_used_pct: float
