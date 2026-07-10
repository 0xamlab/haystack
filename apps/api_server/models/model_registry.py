"""Minimal model registry — governed ``ModelArtifact`` / ``ModelVersion`` entities.

The Decision Service's outputs must never reference an *ungoverned* model-version string.
Every ``AnalysisRun`` points at an immutable ``ModelVersion`` that pins the exact input/output
schema, units, validity ranges, calibration status, limitations, and golden-test result of the
model that produced it. This is the Phase-1 slice; the full governance workflow (review queues,
challenger models, promotion, drift reporting, retirement) is Phase 2.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin
from apps.api_server.models._mixins import OrgWorkspaceScopedMixin


class ValidationStatus(StrEnum):
    draft = "draft"
    validated = "validated"
    retired = "retired"


class ModelArtifact(UUIDMixin, TimestampMixin, OrgWorkspaceScopedMixin, Base):
    """A logical model identity (the family a versioned model belongs to)."""

    __tablename__ = "model_artifacts"

    key: Mapped[str] = mapped_column(
        String(256), nullable=False, index=True, doc="Stable model key, e.g. '<pack>.outcome_model'"
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    owner: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<ModelArtifact id={self.id} key={self.key!r}>"


class ModelVersion(UUIDMixin, TimestampMixin, OrgWorkspaceScopedMixin, Base):
    """An IMMUTABLE version of a model. Never update a row — publish a new version.

    ``version_ref`` (e.g. ``'<pack>.outcome_model@v0.1.0'``) is the value ``AnalysisRun`` and
    result payloads carry, so a decision is always reproducible against a governed definition.
    """

    __tablename__ = "model_versions"

    artifact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    version_ref: Mapped[str] = mapped_column(
        String(256), nullable=False, index=True, doc="Fully-qualified '<key>@<version>' reference"
    )
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    pack_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True, doc="Decision Pack this version is compatible with"
    )

    input_schema: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    output_schema: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    units: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    validity_ranges: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    assumption_defaults: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    calibration_dataset_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    calibration_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="uncalibrated", doc="uncalibrated | calibrated"
    )
    validation_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ValidationStatus.draft.value, index=True
    )
    known_limitations: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    golden_test_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    effective_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True, doc="Integrity hash of the governed definition"
    )

    def __repr__(self) -> str:
        return f"<ModelVersion {self.id} ref={self.version_ref!r} status={self.validation_status}>"
