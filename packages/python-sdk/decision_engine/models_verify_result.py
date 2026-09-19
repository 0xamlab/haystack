# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class VerifyResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    valid: bool
    errors: list[str]
    suggestions: list[str]
    resolved: dict[str, str]
    valid_dimensions: list[str] = Field(default_factory=list)
    valid_measures: list[str] = Field(default_factory=list)
    source_behavior: str = ""
    latency_ms: float
    verified: bool = False
    request_id: str | None = None
    schema_revision: str | None = None
    plan_hash: str | None = None
    verification_mode: str = "assist"
    rejection_reason: str | None = None
