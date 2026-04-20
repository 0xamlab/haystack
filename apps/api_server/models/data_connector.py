"""DataConnector model — stores external data source configurations per org."""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin


class ConnectorType(str, enum.Enum):
    S3       = "s3"
    GCS      = "gcs"
    AZURE    = "azure"
    BIGQUERY = "bigquery"
    SNOWFLAKE = "snowflake"
    REDSHIFT = "redshift"
    POSTGRES = "postgres"
    SQLITE   = "sqlite"
    MYSQL    = "mysql"
    MSSQL    = "mssql"
    REST     = "rest"
    FILE     = "file"


class ConnectorStatus(str, enum.Enum):
    UNTESTED = "untested"
    LIVE     = "live"
    ERROR    = "error"


class ConnectorVisibility(str, enum.Enum):
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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    connector_type: Mapped[ConnectorType] = mapped_column(
        Enum(ConnectorType, name="connector_type",
             values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    # Config stored as encrypted JSON string in production; plaintext here for dev
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ConnectorStatus] = mapped_column(
        Enum(ConnectorStatus, name="connector_status",
             values_callable=lambda obj: [e.value for e in obj]),
        default=ConnectorStatus.UNTESTED,
        nullable=False,
    )
    last_tested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, default=ConnectorVisibility.PRIVATE.value)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    owner_key_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    def __repr__(self) -> str:
        return f"<DataConnector id={self.id} name={self.name} type={self.connector_type}>"
