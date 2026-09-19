# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DeploymentRegionResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    id: str
    name: str
    label: str | None = None
    location: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_name_aliases(cls, value):
        if isinstance(value, dict):
            normalized = dict(value)
            label = normalized.get("label")
            name = normalized.get("name")
            if (not isinstance(name, str) or not name) and isinstance(label, str) and label:
                normalized["name"] = label
            if (not isinstance(label, str) or not label) and isinstance(name, str) and name:
                normalized["label"] = name
            return normalized
        return value


class DeploymentProviderResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    id: str
    name: str
    description: str
    icon: str
    regions: list[DeploymentRegionResult] = Field(default_factory=list)


class DeploymentRegionsResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    providers: list[DeploymentProviderResult] = Field(default_factory=list)


class DeploymentResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    deployment_id: str
    org_id: str
    provider: str
    region: str
    status: str
    endpoint_url: str | None = None
    cost_usd_month: float
    billable_cost_usd_month: float
    billing_markup_pct: float
    created_at: datetime
    provisioned_at: datetime | None = None
    error_message: str | None = None


class DeploymentDeleteResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    status: str
    deployment_id: str


class DeploymentCostResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    deployment_id: str
    provider: str
    region: str
    year: int
    month: int
    cost_usd_month: float
    billable_cost_usd_month: float
    billing_markup_pct: float
    last_updated: datetime | None = None
