"""Capability-plane persistence models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, JSON, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin


def _enum_values(enum_cls: type[enum.StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


class ProviderType(enum.StrEnum):
    DATA_CONNECTOR = "data_connector"
    MCP_PROVIDER = "mcp_provider"
    SKILL_PACK = "skill_pack"
    NATIVE_TOOL_PACK = "native_tool_pack"
    RUNTIME_LIBRARY_PACK = "runtime_library_pack"


class CapabilityKind(enum.StrEnum):
    DATASET = "dataset"
    MCP_TOOL = "mcp_tool"
    MCP_RESOURCE = "mcp_resource"
    MCP_PROMPT = "mcp_prompt"
    SKILL = "skill"
    NATIVE_TOOL = "native_tool"
    RUNTIME_LIBRARY = "runtime_library"


class ImplementationKind(enum.StrEnum):
    CALLABLE = "callable"
    INSTRUCTION_ONLY = "instruction_only"
    HYBRID = "hybrid"


class ExecutionOwner(enum.StrEnum):
    ALGENTA_MANAGED = "algenta_managed"
    CLIENT_MANAGED = "client_managed"


class BindingScope(enum.StrEnum):
    USER = "user"
    WORKSPACE = "workspace"
    ORGANIZATION = "organization"


class BindingStatus(enum.StrEnum):
    UNCONFIGURED = "unconfigured"
    AUTHORIZING = "authorizing"
    READY = "ready"
    DEGRADED = "degraded"
    QUARANTINED = "quarantined"


class AuthorizationSessionStatus(enum.StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ExecutionSessionStatus(enum.StrEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CapabilityPlanLifecycleState(enum.StrEnum):
    """Lifecycle of one approval-gate for an ``approval_required=True`` capability.

    Mirrors DecisionService's proposed -> approved -> executed workflow (services/
    decision_service/service.py), but a single row plays both the "plan" and the "approval"
    role -- there is no revision/case concept here to justify DecisionService's separate
    Approval/ExecutionPlan tables. EXECUTING sits between APPROVED and EXECUTED so a
    concurrent double-execute is stopped by a compare-and-set on this column BEFORE the real
    side-effecting call runs, not after.
    """

    PROPOSED = "proposed"
    APPROVED = "approved"
    EXECUTING = "executing"
    EXECUTED = "executed"
    EXPIRED = "expired"


class CapabilityProvider(TimestampMixin, Base):
    __tablename__ = "capability_providers"

    provider_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    provider_type: Mapped[ProviderType] = mapped_column(
        Enum(
            ProviderType,
            name="capability_provider_type",
            values_callable=_enum_values,
        ),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    docs_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    auth_schema_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    certification_summary_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    policy_summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    supported_execution_owners_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    install_metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    customer_metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CapabilityProviderProfile(TimestampMixin, Base):
    __tablename__ = "capability_provider_profiles"

    profile_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    provider_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("capability_providers.provider_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_kind: Mapped[str] = mapped_column(String(64), nullable=False, default="none")
    default_execution_owner: Mapped[ExecutionOwner] = mapped_column(
        Enum(
            ExecutionOwner,
            name="capability_execution_owner",
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    binding_scope_default: Mapped[BindingScope] = mapped_column(
        Enum(
            BindingScope,
            name="capability_binding_scope",
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    supported_binding_scopes_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    profile_metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class CapabilityBinding(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "capability_bindings"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Workspace sub-tenant scope (set by a platform key via X-Workspace-Id). NULL =
    # org-wide / pre-migration. See services/workspace_scope.py + migration 0030.
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    provider_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("capability_providers.provider_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("capability_provider_profiles.profile_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    binding_name: Mapped[str] = mapped_column(String(255), nullable=False)
    scope: Mapped[BindingScope] = mapped_column(
        Enum(
            BindingScope,
            name="capability_binding_scope",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    )
    scope_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[BindingStatus] = mapped_column(
        Enum(
            BindingStatus,
            name="capability_binding_status",
            values_callable=_enum_values,
        ),
        nullable=False,
        default=BindingStatus.UNCONFIGURED,
    )
    execution_owner: Mapped[ExecutionOwner] = mapped_column(
        Enum(
            ExecutionOwner,
            name="capability_execution_owner",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    )
    config_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    auth_state_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    customer_metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    system_managed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_discovered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quarantine_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    discovery_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class CapabilitySnapshot(UUIDMixin, Base):
    __tablename__ = "capability_snapshots"

    binding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("capability_bindings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    manifest_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    discovery_metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CapabilityRoutingOutcome(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "capability_routing_outcomes"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    binding_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("capability_bindings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    capability_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    route_request_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    route_plan_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    result_status: Mapped[str] = mapped_column(String(32), nullable=False, default="routed")
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    score: Mapped[float | None] = mapped_column(nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    outcome_details_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class CapabilityAuthorizationSession(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "capability_authorization_sessions"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Sub-tenancy scope (durable form of the #4 fix): the session is independently
    # workspace-scoped, not only gated transitively via its binding. Nullable for legacy rows.
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    provider_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    binding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("capability_bindings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_state_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    authorize_url: Mapped[str] = mapped_column(String(4096), nullable=False)
    status: Mapped[AuthorizationSessionStatus] = mapped_column(
        Enum(
            AuthorizationSessionStatus,
            name="capability_authorization_session_status",
            values_callable=_enum_values,
        ),
        nullable=False,
        default=AuthorizationSessionStatus.PENDING,
    )
    request_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    callback_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CapabilityExecutionSession(UUIDMixin, Base):
    __tablename__ = "capability_execution_sessions"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    binding_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("capability_bindings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    capability_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    execution_owner: Mapped[ExecutionOwner] = mapped_column(
        Enum(
            ExecutionOwner,
            name="capability_execution_owner",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    )
    status: Mapped[ExecutionSessionStatus] = mapped_column(
        Enum(
            ExecutionSessionStatus,
            name="capability_execution_session_status",
            values_callable=_enum_values,
        ),
        nullable=False,
        default=ExecutionSessionStatus.STARTED,
    )
    request_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    request_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    response_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CapabilityExecutionPlan(UUIDMixin, TimestampMixin, Base):
    """A pending or decided approval-gate for one execute_capability_service call whose
    catalog entry has ``approval_required=True``.

    Created (PROPOSED) instead of executing when no prior approval is present; a separate,
    credentialed HTTP operation (never an MCP/LLM tool -- see routers/capabilities.py) flips
    it to APPROVED; a second call to execute_capability_service carrying this plan's id then
    performs the real execution. plan_hash + a single-use nonce bind the approval to the exact
    capability/binding/input that was proposed; manifest_hash is a staleness guard (if the
    capability's discovered manifest changes between propose and approve/execute, the plan is
    refused rather than silently authorizing a definition the approver never saw).
    """

    __tablename__ = "capability_execution_plans"
    __table_args__ = (
        # Idempotency keys are unique per org (when present) -- mirrors
        # uq_decision_approvals_org_idempotency exactly (see decision_aggregate.Approval).
        Index(
            "uq_capability_execution_plans_org_idempotency",
            "org_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    capability_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    provider_id: Mapped[str] = mapped_column(String(128), nullable=False)
    binding_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("capability_bindings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    execution_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("capability_execution_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    input_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True, doc="Frozen request input captured at propose time."
    )
    manifest_hash: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        doc="Capability manifest_hash snapshot at propose time (staleness guard).",
    )
    plan_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    nonce: Mapped[str] = mapped_column(
        String(64), nullable=False, doc="Single-use approval challenge issued at propose time."
    )
    nonce_consumed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    lifecycle_state: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=CapabilityPlanLifecycleState.PROPOSED.value,
        index=True,
    )
    approver_principal: Mapped[str | None] = mapped_column(String(256), nullable=True)
    required_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    receipt_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

