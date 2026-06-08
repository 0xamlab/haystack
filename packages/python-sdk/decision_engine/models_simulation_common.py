from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MetricsSummary(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    expected_value: float
    median: float
    std_deviation: float
    variance: float
    probability_of_loss: float
    var_95: float | None = None
    cvar_95: float | None = None


class PercentileSummary(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    p5: float
    p25: float
    p50: float
    p75: float
    p95: float


class RunMetadata(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    mode: str
    seed: int | None = None
    billing_units: int
    engine_version: str


__all__ = ["MetricsSummary", "PercentileSummary", "RunMetadata"]
