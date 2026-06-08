"""Add capability-plane persistence tables.

Revision ID: 0029
Revises: 0028
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def _provider_type_enum(*, create_type: bool) -> postgresql.ENUM:
    return postgresql.ENUM(
        "data_connector",
        "mcp_provider",
        "skill_pack",
        "native_tool_pack",
        "runtime_library_pack",
        name="capability_provider_type",
        create_type=create_type,
    )


def _capability_kind_enum(*, create_type: bool) -> postgresql.ENUM:
    return postgresql.ENUM(
        "dataset",
        "mcp_tool",
        "mcp_resource",
        "mcp_prompt",
        "skill",
        "native_tool",
        "runtime_library",
        name="capability_kind",
        create_type=create_type,
    )


def _execution_owner_enum(*, create_type: bool) -> postgresql.ENUM:
    return postgresql.ENUM(
        "algenta_managed",
        "client_managed",
        name="capability_execution_owner",
        create_type=create_type,
    )


def _binding_scope_enum(*, create_type: bool) -> postgresql.ENUM:
    return postgresql.ENUM(
        "user",
        "workspace",
        "organization",
        name="capability_binding_scope",
        create_type=create_type,
    )


def _binding_status_enum(*, create_type: bool) -> postgresql.ENUM:
    return postgresql.ENUM(
        "unconfigured",
        "authorizing",
        "ready",
        "degraded",
        "quarantined",
        name="capability_binding_status",
        create_type=create_type,
    )


def _authorization_session_status_enum(*, create_type: bool) -> postgresql.ENUM:
    return postgresql.ENUM(
        "pending",
        "completed",
        "cancelled",
        "expired",
        name="capability_authorization_session_status",
        create_type=create_type,
    )


def _execution_session_status_enum(*, create_type: bool) -> postgresql.ENUM:
    return postgresql.ENUM(
        "started",
        "succeeded",
        "failed",
        name="capability_execution_session_status",
        create_type=create_type,
    )


def upgrade() -> None:
    bind = op.get_bind()
    provider_type_enum = _provider_type_enum(create_type=True)
    capability_kind_enum = _capability_kind_enum(create_type=True)
    execution_owner_enum = _execution_owner_enum(create_type=True)
    binding_scope_enum = _binding_scope_enum(create_type=True)
    binding_status_enum = _binding_status_enum(create_type=True)
    authorization_session_status_enum = _authorization_session_status_enum(create_type=True)
    execution_session_status_enum = _execution_session_status_enum(create_type=True)
    provider_type_enum.create(bind, checkfirst=True)
    capability_kind_enum.create(bind, checkfirst=True)
    execution_owner_enum.create(bind, checkfirst=True)
    binding_scope_enum.create(bind, checkfirst=True)
    binding_status_enum.create(bind, checkfirst=True)
    authorization_session_status_enum.create(bind, checkfirst=True)
    execution_session_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "capability_providers",
        sa.Column("provider_id", sa.String(length=128), primary_key=True),
        sa.Column("provider_type", _provider_type_enum(create_type=False), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("docs_url", sa.String(length=2048), nullable=True),
        sa.Column("auth_schema_json", sa.JSON(), nullable=True),
        sa.Column("certification_summary_json", sa.JSON(), nullable=True),
        sa.Column("policy_summary_json", sa.JSON(), nullable=True),
        sa.Column("supported_execution_owners_json", sa.JSON(), nullable=True),
        sa.Column("install_metadata_json", sa.JSON(), nullable=True),
        sa.Column("customer_metadata_json", sa.JSON(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_capability_providers_provider_type",
        "capability_providers",
        ["provider_type"],
        unique=False,
    )

    op.create_table(
        "capability_provider_profiles",
        sa.Column("profile_id", sa.String(length=128), primary_key=True),
        sa.Column(
            "provider_id",
            sa.String(length=128),
            sa.ForeignKey("capability_providers.provider_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("auth_kind", sa.String(length=64), nullable=False, server_default="none"),
        sa.Column(
            "default_execution_owner",
            _execution_owner_enum(create_type=False),
            nullable=False,
        ),
        sa.Column(
            "binding_scope_default",
            _binding_scope_enum(create_type=False),
            nullable=False,
        ),
        sa.Column("supported_binding_scopes_json", sa.JSON(), nullable=True),
        sa.Column("profile_metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_capability_provider_profiles_provider_id",
        "capability_provider_profiles",
        ["provider_id"],
        unique=False,
    )

    op.create_table(
        "capability_bindings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "provider_id",
            sa.String(length=128),
            sa.ForeignKey("capability_providers.provider_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            sa.String(length=128),
            sa.ForeignKey("capability_provider_profiles.profile_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("binding_name", sa.String(length=255), nullable=False),
        sa.Column("scope", _binding_scope_enum(create_type=False), nullable=False),
        sa.Column("scope_ref", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            _binding_status_enum(create_type=False),
            nullable=False,
            server_default="unconfigured",
        ),
        sa.Column(
            "execution_owner",
            _execution_owner_enum(create_type=False),
            nullable=False,
        ),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("auth_state_json", sa.JSON(), nullable=True),
        sa.Column("customer_metadata_json", sa.JSON(), nullable=True),
        sa.Column("system_managed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_discovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quarantine_reason", sa.Text(), nullable=True),
        sa.Column("discovery_error_message", sa.Text(), nullable=True),
        sa.Column("test_error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_capability_bindings_id", "capability_bindings", ["id"], unique=False)
    op.create_index("ix_capability_bindings_org_id", "capability_bindings", ["org_id"], unique=False)
    op.create_index(
        "ix_capability_bindings_provider_id",
        "capability_bindings",
        ["provider_id"],
        unique=False,
    )
    op.create_index(
        "ix_capability_bindings_profile_id",
        "capability_bindings",
        ["profile_id"],
        unique=False,
    )

    op.create_table(
        "capability_snapshots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "binding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("capability_bindings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("manifest_hash", sa.String(length=128), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("discovery_metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_capability_snapshots_id", "capability_snapshots", ["id"], unique=False)
    op.create_index(
        "ix_capability_snapshots_binding_id",
        "capability_snapshots",
        ["binding_id"],
        unique=False,
    )
    op.create_index("ix_capability_snapshots_org_id", "capability_snapshots", ["org_id"], unique=False)
    op.create_index(
        "ix_capability_snapshots_manifest_hash",
        "capability_snapshots",
        ["manifest_hash"],
        unique=False,
    )

    op.create_table(
        "capability_routing_outcomes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_id", sa.String(length=128), nullable=False),
        sa.Column(
            "binding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("capability_bindings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("capability_id", sa.String(length=255), nullable=False),
        sa.Column("route_request_json", sa.JSON(), nullable=True),
        sa.Column("route_plan_json", sa.JSON(), nullable=True),
        sa.Column("result_status", sa.String(length=32), nullable=False, server_default="routed"),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("outcome_details_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_capability_routing_outcomes_id",
        "capability_routing_outcomes",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_capability_routing_outcomes_org_id",
        "capability_routing_outcomes",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        "ix_capability_routing_outcomes_provider_id",
        "capability_routing_outcomes",
        ["provider_id"],
        unique=False,
    )
    op.create_index(
        "ix_capability_routing_outcomes_binding_id",
        "capability_routing_outcomes",
        ["binding_id"],
        unique=False,
    )
    op.create_index(
        "ix_capability_routing_outcomes_capability_id",
        "capability_routing_outcomes",
        ["capability_id"],
        unique=False,
    )

    op.create_table(
        "capability_authorization_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_id", sa.String(length=128), nullable=False),
        sa.Column(
            "binding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("capability_bindings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_state_hash", sa.String(length=128), nullable=False, unique=True),
        sa.Column("authorize_url", sa.String(length=4096), nullable=False),
        sa.Column(
            "status",
            _authorization_session_status_enum(create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("request_payload_json", sa.JSON(), nullable=True),
        sa.Column("callback_payload_json", sa.JSON(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_capability_authorization_sessions_id",
        "capability_authorization_sessions",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_capability_authorization_sessions_org_id",
        "capability_authorization_sessions",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        "ix_capability_authorization_sessions_provider_id",
        "capability_authorization_sessions",
        ["provider_id"],
        unique=False,
    )
    op.create_index(
        "ix_capability_authorization_sessions_binding_id",
        "capability_authorization_sessions",
        ["binding_id"],
        unique=False,
    )

    op.create_table(
        "capability_execution_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_id", sa.String(length=128), nullable=False),
        sa.Column(
            "binding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("capability_bindings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("capability_id", sa.String(length=255), nullable=False),
        sa.Column(
            "execution_owner",
            _execution_owner_enum(create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            _execution_session_status_enum(create_type=False),
            nullable=False,
            server_default="started",
        ),
        sa.Column("request_id", sa.String(length=255), nullable=True),
        sa.Column("request_payload_json", sa.JSON(), nullable=True),
        sa.Column("response_payload_json", sa.JSON(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_capability_execution_sessions_id",
        "capability_execution_sessions",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_capability_execution_sessions_org_id",
        "capability_execution_sessions",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        "ix_capability_execution_sessions_provider_id",
        "capability_execution_sessions",
        ["provider_id"],
        unique=False,
    )
    op.create_index(
        "ix_capability_execution_sessions_binding_id",
        "capability_execution_sessions",
        ["binding_id"],
        unique=False,
    )
    op.create_index(
        "ix_capability_execution_sessions_capability_id",
        "capability_execution_sessions",
        ["capability_id"],
        unique=False,
    )
    op.create_index(
        "ix_capability_execution_sessions_request_id",
        "capability_execution_sessions",
        ["request_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_capability_execution_sessions_request_id", table_name="capability_execution_sessions")
    op.drop_index("ix_capability_execution_sessions_capability_id", table_name="capability_execution_sessions")
    op.drop_index("ix_capability_execution_sessions_binding_id", table_name="capability_execution_sessions")
    op.drop_index("ix_capability_execution_sessions_provider_id", table_name="capability_execution_sessions")
    op.drop_index("ix_capability_execution_sessions_org_id", table_name="capability_execution_sessions")
    op.drop_index("ix_capability_execution_sessions_id", table_name="capability_execution_sessions")
    op.drop_table("capability_execution_sessions")

    op.drop_index(
        "ix_capability_authorization_sessions_binding_id",
        table_name="capability_authorization_sessions",
    )
    op.drop_index(
        "ix_capability_authorization_sessions_provider_id",
        table_name="capability_authorization_sessions",
    )
    op.drop_index(
        "ix_capability_authorization_sessions_org_id",
        table_name="capability_authorization_sessions",
    )
    op.drop_index("ix_capability_authorization_sessions_id", table_name="capability_authorization_sessions")
    op.drop_table("capability_authorization_sessions")

    op.drop_index(
        "ix_capability_routing_outcomes_capability_id",
        table_name="capability_routing_outcomes",
    )
    op.drop_index(
        "ix_capability_routing_outcomes_binding_id",
        table_name="capability_routing_outcomes",
    )
    op.drop_index(
        "ix_capability_routing_outcomes_provider_id",
        table_name="capability_routing_outcomes",
    )
    op.drop_index("ix_capability_routing_outcomes_org_id", table_name="capability_routing_outcomes")
    op.drop_index("ix_capability_routing_outcomes_id", table_name="capability_routing_outcomes")
    op.drop_table("capability_routing_outcomes")

    op.drop_index("ix_capability_snapshots_manifest_hash", table_name="capability_snapshots")
    op.drop_index("ix_capability_snapshots_org_id", table_name="capability_snapshots")
    op.drop_index("ix_capability_snapshots_binding_id", table_name="capability_snapshots")
    op.drop_index("ix_capability_snapshots_id", table_name="capability_snapshots")
    op.drop_table("capability_snapshots")

    op.drop_index("ix_capability_bindings_profile_id", table_name="capability_bindings")
    op.drop_index("ix_capability_bindings_provider_id", table_name="capability_bindings")
    op.drop_index("ix_capability_bindings_org_id", table_name="capability_bindings")
    op.drop_index("ix_capability_bindings_id", table_name="capability_bindings")
    op.drop_table("capability_bindings")

    op.drop_index(
        "ix_capability_provider_profiles_provider_id",
        table_name="capability_provider_profiles",
    )
    op.drop_table("capability_provider_profiles")

    op.drop_index("ix_capability_providers_provider_type", table_name="capability_providers")
    op.drop_table("capability_providers")

    bind = op.get_bind()
    _execution_session_status_enum(create_type=True).drop(bind, checkfirst=True)
    _authorization_session_status_enum(create_type=True).drop(bind, checkfirst=True)
    _binding_status_enum(create_type=True).drop(bind, checkfirst=True)
    _binding_scope_enum(create_type=True).drop(bind, checkfirst=True)
    _execution_owner_enum(create_type=True).drop(bind, checkfirst=True)
    _capability_kind_enum(create_type=True).drop(bind, checkfirst=True)
    _provider_type_enum(create_type=True).drop(bind, checkfirst=True)
