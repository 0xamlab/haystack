from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TriggerConditionResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    source_id: str
    metric_hint: str
    threshold: float
    direction: str
    aggregation: str


class TriggerSummaryResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    trigger_id: str
    org_id: str
    name: str
    status: str
    condition: TriggerConditionResult
    description: str | None = None
    webhook_url: str | None = None
    execution_webhook_url: str | None = None
    auto_execute: bool = False
    created_at: datetime
    last_checked_at: datetime | None = None
    last_fired_at: datetime | None = None
    last_result_summary: str | None = None


class TriggerListResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    triggers: list[TriggerSummaryResult]
    count: int
    total: int
    page: int
    limit: int
    pages: int


class TriggerFireResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    trigger_id: str
    condition_met: bool
    fired: bool
    simulation_run_id: str | None = None
    recommended_action: str | None = None
    expected_value: float | None = None
    confidence: float | None = None
    fired_at: datetime | None = None
    execution_status: str | None = None
    message: str


class TriggerPauseResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    trigger_id: str
    status: str


class TriggerDeleteResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    trigger_id: str
    deleted: bool
