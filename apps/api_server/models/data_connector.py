"""DataConnector model — stores external data source configurations per org."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin


class ConnectorType(enum.StrEnum):
    S3 = "s3"
    GCS = "gcs"
    AZURE = "azure"
    CLICKHOUSE = "clickhouse"
    ELASTICSEARCH = "elasticsearch"
    BIGQUERY = "bigquery"
    SNOWFLAKE = "snowflake"
    REDSHIFT = "redshift"
    POSTGRES = "postgres"
    SQLITE = "sqlite"
    MYSQL = "mysql"
    MSSQL = "mssql"
    NEO4J = "neo4j"
    REDIS = "redis"
    REST = "rest"
    FILE = "file"
    GITHUB_REPO = "github_repo"
    GITLAB_REPO = "gitlab_repo"
    BITBUCKET_REPO = "bitbucket_repo"
    LOCAL_REPO = "local_repo"
    REPO_ARCHIVE = "repo_archive"


class ConnectorStatus(enum.StrEnum):
    UNTESTED = "untested"
    LIVE = "live"
    ERROR = "error"


class ConnectorVisibility(enum.StrEnum):
    PRIVATE = "private"
    SHARED = "shared"


class DataConnector(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "data_connectors"

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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    connector_type: Mapped[ConnectorType] = mapped_column(
        Enum(
            ConnectorType, name="connector_type", values_callable=lambda obj: [e.value for e in obj]
        ),
        nullable=False,
    )
    # Config stored as envelope-encrypted JSON (AES-256-GCM, AAD=org) when
    # ALGENTA_CONFIG_ENCRYPTION_KEY is set; legacy/dev rows may be plaintext.
    # See services/config_crypto.py.
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Deterministic SHA-256 of the canonical plaintext config — encryption-safe
    # dedupe key for create-or-reuse (ciphertext is non-deterministic).
    config_fingerprint: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ConnectorStatus] = mapped_column(
        Enum(
            ConnectorStatus,
            name="connector_status",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=ConnectorStatus.UNTESTED,
        nullable=False,
    )
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=ConnectorVisibility.PRIVATE.value,
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    owner_key_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<DataConnector id={self.id} name={self.name} type={self.connector_type}>"
