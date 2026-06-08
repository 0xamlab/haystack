from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class MeUserResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    id: str
    email: str
    name: str
    role: str
    email_verified: bool
    created_at: datetime


class MeOrgResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    id: str
    name: str
    slug: str
    plan: str
    status: str
    created_at: datetime


class MeResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    user: MeUserResult
    org: MeOrgResult


class TeamMemberResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    user_id: str
    name: str
    email: str
    role: str
    status: str
    last_active: datetime | None = None


class TeamListResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    members: list[TeamMemberResult]
    total: int
    page: int
    limit: int
    pages: int


class TeamInviteResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    message: str
    invite_id: str


class TeamRoleUpdateResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    message: str
    user_id: str


class TeamRemoveResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    removed: bool
    user_id: str


class AuditLogEntryResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    id: str
    timestamp: datetime
    actor_email: str
    action: str
    resource_type: str
    resource_id: str | None = None
    ip_address: str | None = None
    result: str
    content_hash: str | None = None
    metadata: dict[str, Any] | None = None


class AuditLogResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    entries: list[AuditLogEntryResult]
    total: int
    page: int
    limit: int
    pages: int


class ExecutionPolicyResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    org_id: str
    min_confidence: float
    risk_floor: float | None = None
    require_calibration: bool
    allow_reexecution: bool
    snapshot_id: str | None = None
    content_hash: str | None = None
    schema_revision: str | None = None
    revision: int | None = None
    previous_snapshot_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime


class ExecutionPolicySnapshotListResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    org_id: str
    data: list[ExecutionPolicyResult]
    total_snapshots: int


class DistributionInfoResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    name: str
    description: str
    required_params: list[str]
    optional_params: list[str]
    example: dict[str, object]


class DistributionListResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    distributions: list[DistributionInfoResult]
    total: int
    page: int
    limit: int
    pages: int


class TemplateInfoResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    id: str
    name: str
    category: str
    description: str
    example_request: dict[str, object]


class TemplateListResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    templates: list[TemplateInfoResult]
    total: int
    page: int
    limit: int
    pages: int


class BillingInfoResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    plan: str
    stripe_customer_id: str | None = None
    subscription_status: str | None = None
    current_period_end: datetime | None = None


class BillingSessionResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    url: str


class MeteringBatchResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    accepted: int
    billing_period: str


class CreditRefreshResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    credits_granted: int
    credits_issued_this_month: int
    monthly_limit: int
    monthly_remaining: int
    billing_period: str
    expires_at: float
    refresh_after: float
    server_time: float


class DeviceRegistrationResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    id: str
    org_id: str
    api_key_id: str
    device_id: str
    platform: str | None = None
    platform_version: str | None = None
    hostname_hash: str | None = None
    sdk_version: str | None = None
    status: str
    last_heartbeat_at: datetime | None = None
    heartbeat_count: int
    created_at: datetime
    updated_at: datetime


class DeviceListEntryResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    id: str
    device_id: str
    platform: str | None = None
    platform_version: str | None = None
    sdk_version: str | None = None
    status: str
    api_key_label: str | None = None
    api_key_prefix: str | None = None
    registered_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    heartbeat_count: int


class DeviceListResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    devices: list[DeviceListEntryResult]
    device_count: int
    total: int
    page: int
    limit: int
    pages: int
    device_limit: int
    plan: str


class DeviceRevokeResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    revoked: bool
    registration_id: str
