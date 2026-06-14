"""Auth and account schemas."""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field, field_validator


class SignUpRequest(BaseModel):
    model_config = ConfigDict(strict=False)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=255)


class LoginRequest(BaseModel):
    model_config = ConfigDict(strict=False)
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(strict=False)
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(strict=False)
    token: str = Field(..., min_length=1)
    new_password: str = Field(
        ...,
        validation_alias=AliasChoices("new_password", "password"),
        min_length=8,
        max_length=128,
    )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = Field(default="bearer")  # noqa: S105 - protocol constant, not a secret
    expires_in: int


class APIKeyInfo(BaseModel):
    """API key info shown in list (never includes hash or raw key)."""

    id: uuid.UUID
    label: str
    key_prefix: str
    device_limit: int = Field(
        ...,
        ge=0,
        description=(
            "Max registered devices for this key on the local runtime path. "
            "0 preserves the plan's unlimited or no-local-runtime behavior."
        ),
    )
    status: str
    created_at: datetime
    last_used_at: datetime | None = None
    expires_at: datetime | None = None


class APIKeyCreated(BaseModel):
    """Returned once at key creation — raw key shown here only."""

    id: uuid.UUID
    label: str
    key_prefix: str
    device_limit: int = Field(
        ...,
        ge=0,
        description=(
            "Max registered devices for this key on the local runtime path. "
            "0 preserves the plan's unlimited or no-local-runtime behavior."
        ),
    )
    raw_key: str = Field(..., description="The full API key — shown ONCE, store it securely.")
    created_at: datetime
    expires_at: datetime | None = None


class CreateAPIKeyRequest(BaseModel):
    model_config = ConfigDict(strict=False)
    label: str = Field(..., min_length=1, max_length=255)
    expires_at: datetime | None = Field(default=None)
    device_limit: int | None = Field(default=None, ge=0)

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        if normalized <= datetime.now(UTC):
            raise ValueError("expires_at must be in the future.")
        return normalized


class OrgInfo(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan: str
    status: str
    created_at: datetime


class UserInfo(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    role: str
    email_verified: bool
    created_at: datetime


class MeResponse(BaseModel):
    user: UserInfo
    org: OrgInfo


class SignUpResponse(BaseModel):
    user: UserInfo
    org: OrgInfo
    api_key: APIKeyCreated
    message: str = "Account created successfully. Your API key is shown once — store it securely."


class UsageResponse(BaseModel):
    org_id: uuid.UUID
    billing_period: str
    simulations_run: int
    api_calls: int
    quota_limit: int
    quota_used_pct: float
    # Managed-LLM pass-through spend this period (D3). Dollars spent on the platform's pooled
    # provider key; 0 cap = unlimited / org not on managed (BYOK + self-host never accrue here).
    managed_llm_spend_usd_month: float = 0.0
    managed_llm_cap_usd_month: int = 0
    # Repository-intelligence object-store footprint (live S3 sum; 0 off-S3). storage_gb_limit 0 =
    # unlimited. Limit ENFORCEMENT is opt-in (ALGENTA_ENFORCE_STORAGE_CAP); this is informational.
    storage_bytes_used: int = 0
    storage_gb_limit: int = 0


class LimitsResponse(BaseModel):
    plan: str
    max_simulations_per_month: int
    max_runs_per_simulation: int
    max_batch_items: int
    rate_limit_per_minute: int
    async_jobs_enabled: bool
    webhooks_enabled: bool
    # Free-tier cost caps (Wave 2; 0 = unlimited). concurrent_jobs is enforced on async job submit;
    # storage_gb + llm_spend_cap_usd_month are advertised here, enforced once their backends land.
    concurrent_jobs: int = 0
    storage_gb: int = 0
    llm_spend_cap_usd_month: int = 0


class DistributionInfo(BaseModel):
    name: str
    description: str
    required_params: list[str]
    optional_params: list[str]
    example: dict[str, Any]


class TemplateInfo(BaseModel):
    id: str
    name: str
    description: str
    category: str
    example_request: dict[str, Any]


class UpdateMeRequest(BaseModel):
    model_config = ConfigDict(strict=False)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    org_name: str | None = Field(default=None, min_length=1, max_length=255)
