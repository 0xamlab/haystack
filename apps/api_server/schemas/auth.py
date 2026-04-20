"""Auth and account schemas."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignUpRequest(BaseModel):
    model_config = ConfigDict(strict=False)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=255)


class LoginRequest(BaseModel):
    model_config = ConfigDict(strict=False)
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class APIKeyInfo(BaseModel):
    """API key info shown in list (never includes hash or raw key)."""
    id: uuid.UUID
    label: str
    key_prefix: str
    status: str
    created_at: datetime
    last_used_at: datetime | None = None


class APIKeyCreated(BaseModel):
    """Returned once at key creation — raw key shown here only."""
    id: uuid.UUID
    label: str
    key_prefix: str
    raw_key: str = Field(..., description="The full API key — shown ONCE, store it securely.")
    created_at: datetime


class CreateAPIKeyRequest(BaseModel):
    model_config = ConfigDict(strict=False)
    label: str = Field(..., min_length=1, max_length=255)
    expires_at: datetime | None = Field(default=None)


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


class LimitsResponse(BaseModel):
    plan: str
    max_simulations_per_month: int
    max_runs_per_simulation: int
    max_batch_items: int
    rate_limit_per_minute: int
    async_jobs_enabled: bool
    webhooks_enabled: bool


class DistributionInfo(BaseModel):
    name: str
    description: str
    required_params: list[str]
    optional_params: list[str]
    example: dict


class TemplateInfo(BaseModel):
    id: str
    name: str
    description: str
    category: str
    example_request: dict


class UpdateMeRequest(BaseModel):
    model_config = ConfigDict(strict=False)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    org_name: str | None = Field(default=None, min_length=1, max_length=255)
