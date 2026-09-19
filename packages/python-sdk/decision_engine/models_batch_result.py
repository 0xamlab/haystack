# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .models_decision_envelope import DecisionEnvelope


class BatchItemResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    index: int
    success: bool
    envelope: DecisionEnvelope | None = None
    error: str | None = None


class BatchResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    total: int
    succeeded: int
    failed: int
    results: list[BatchItemResult]
