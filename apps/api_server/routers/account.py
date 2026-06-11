"""
Account endpoints:
  GET    /v1/me              — current user + org info
  PATCH  /v1/me              — update current user and/or org name
  GET    /v1/usage           — usage summary for billing period
  GET    /v1/limits          — plan-based limits
  GET    /v1/templates       — built-in simulation templates
  GET    /v1/distributions   — supported distribution types
  GET    /v1/api-keys        — list API keys
  POST   /v1/api-keys        — create new API key
  DELETE /v1/api-keys/{id}   — revoke API key
"""

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_current_org, get_redis
from apps.api_server.middleware.rbac import require_role
from apps.api_server.models.api_key import APIKey, APIKeyStatus
from apps.api_server.models.organization import Organization
from apps.api_server.models.usage_record import UsageRecord
from apps.api_server.models.user import User
from apps.api_server.pagination import paginate_sequence
from apps.api_server.schemas.auth import (
    APIKeyCreated,
    APIKeyInfo,
    CreateAPIKeyRequest,
    DistributionInfo,
    LimitsResponse,
    MeResponse,
    OrgInfo,
    TemplateInfo,
    UpdateMeRequest,
    UsageResponse,
    UserInfo,
)
from apps.api_server.services.auth_service import (
    AuthContext,
    generate_api_key,
    invalidate_api_key_cache,
    is_api_key_expired,
)
from apps.api_server.services.workspace_scope import workspace_scope_clauses
from apps.api_server.services.plan_limits import (
    effective_device_limit,
    validate_api_key_device_limit,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Account"])


def _api_key_info_device_limit(auth: AuthContext, api_key: APIKey) -> int:
    plan = auth.get("plan")
    if plan is None:
        organization = getattr(api_key, "organization", None)
        organization_plan = getattr(organization, "plan", None)
        if organization_plan is not None:
            plan = getattr(organization_plan, "value", organization_plan)
    stored_limit = getattr(api_key, "device_limit", None)
    if plan is None:
        return stored_limit if isinstance(stored_limit, int) else 0
    return effective_device_limit(
        plan,
        stored_limit if isinstance(stored_limit, int) else None,
    )


class DistributionListResponse(BaseModel):
    distributions: list[DistributionInfo]
    total: int
    page: int
    limit: int
    pages: int


class TemplateListResponse(BaseModel):
    templates: list[TemplateInfo]
    total: int
    page: int
    limit: int
    pages: int


class APIKeyListResponse(BaseModel):
    api_keys: list[APIKeyInfo]
    total: int
    page: int
    limit: int
    pages: int


# Plan → quota mapping
_PLAN_QUOTAS: dict[str, dict[str, int | bool]] = {
    "free": {
        "simulations": 500,
        "max_runs": 10_000,
        "max_batch": 10,
        "rate": 60,
        "async": False,
        "webhooks": False,
    },
    "developer": {
        "simulations": 10_000,
        "max_runs": 100_000,
        "max_batch": 10,
        "rate": 300,
        "async": True,
        "webhooks": True,
    },
    "pro": {
        "simulations": 100_000,
        "max_runs": 1_000_000,
        "max_batch": 100,
        "rate": 1_000,
        "async": True,
        "webhooks": True,
    },
    "enterprise": {
        "simulations": 0,
        "max_runs": 1_000_000,
        "max_batch": 100,
        "rate": 10_000,
        "async": True,
        "webhooks": True,
    },
}


@router.get("/v1/me", response_model=MeResponse, summary="Get current user and org info")
async def me(
    auth: AuthContext = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    user_result = await db.execute(
        select(User)
        .join(Organization, User.org_id == Organization.id)
        .where(User.org_id == auth["org_id"])
        .order_by(User.created_at)
        .limit(1)
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "user_not_found", "message": "User not found."}},
        )

    org_result = await db.execute(select(Organization).where(Organization.id == auth["org_id"]))
    org = org_result.scalar_one_or_none()
    if org is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "org_not_found", "message": "Organization not found."}},
        )

    return MeResponse(
        user=UserInfo(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role.value,
            email_verified=user.email_verified,
            created_at=user.created_at,
        ),
        org=OrgInfo(
            id=org.id,
            name=org.name,
            slug=org.slug,
            plan=org.plan.value,
            status=org.status.value,
            created_at=org.created_at,
        ),
    )


@router.patch("/v1/me", response_model=MeResponse, summary="Update current user and/or org name")
async def update_me(
    payload: UpdateMeRequest,
    auth: AuthContext = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    user_result = await db.execute(
        select(User).where(User.org_id == auth["org_id"]).order_by(User.created_at).limit(1)
    )
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "user_not_found", "message": "User not found."}},
        )

    org_result = await db.execute(select(Organization).where(Organization.id == auth["org_id"]))
    org = org_result.scalar_one_or_none()
    if org is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "org_not_found", "message": "Organization not found."}},
        )

    if payload.name is not None:
        user.name = payload.name

    if payload.org_name is not None:
        org.name = payload.org_name

    await db.flush()
    logger.info(
        "me_updated",
        org_id=str(auth["org_id"]),
        name_updated=payload.name is not None,
        org_name_updated=payload.org_name is not None,
    )

    return MeResponse(
        user=UserInfo(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role.value,
            email_verified=user.email_verified,
            created_at=user.created_at,
        ),
        org=OrgInfo(
            id=org.id,
            name=org.name,
            slug=org.slug,
            plan=org.plan.value,
            status=org.status.value,
            created_at=org.created_at,
        ),
    )


@router.get(
    "/v1/usage",
    response_model=UsageResponse,
    summary="Get usage summary for current billing period",
)
async def usage(
    auth: AuthContext = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
) -> UsageResponse:
    now = datetime.now(UTC)
    billing_period = now.strftime("%Y-%m")

    # Count from usage_records (accurate billing count — only successful calls)
    count_result = await db.execute(
        select(func.count(UsageRecord.id))
        .where(*workspace_scope_clauses(UsageRecord, auth))
        .where(UsageRecord.billing_period == billing_period)
    )
    sim_count = count_result.scalar_one() or 0

    plan = auth["plan"]
    quota = _PLAN_QUOTAS.get(plan, _PLAN_QUOTAS["free"])
    limit = quota["simulations"]
    used_pct = round((sim_count / limit * 100), 1) if limit > 0 else 0.0

    return UsageResponse(
        org_id=auth["org_id"],
        billing_period=billing_period,
        simulations_run=sim_count,
        api_calls=sim_count,
        quota_limit=limit,
        quota_used_pct=used_pct,
    )


@router.get(
    "/v1/limits",
    response_model=LimitsResponse,
    summary="Get rate limits and quotas for current plan",
)
async def limits(auth: AuthContext = Depends(get_current_org)) -> LimitsResponse:
    plan = auth["plan"]
    quota = _PLAN_QUOTAS.get(plan, _PLAN_QUOTAS["free"])
    return LimitsResponse(
        plan=plan,
        max_simulations_per_month=int(quota["simulations"]),
        max_runs_per_simulation=int(quota["max_runs"]),
        max_batch_items=int(quota["max_batch"]),
        rate_limit_per_minute=int(quota["rate"]),
        async_jobs_enabled=bool(quota["async"]),
        webhooks_enabled=bool(quota["webhooks"]),
    )


@router.get(
    "/v1/distributions",
    response_model=list[DistributionInfo] | DistributionListResponse,
    summary="List supported distribution types",
)
async def distributions(
    auth: AuthContext = Depends(get_current_org),
    page: int | None = Query(default=None, ge=1),
    limit: int | None = Query(default=None, ge=1, le=200),
) -> list[DistributionInfo] | DistributionListResponse:
    entries = [
        DistributionInfo(
            name="normal",
            description="Normal (Gaussian) distribution — symmetric bell curve.",
            required_params=["mean", "std"],
            optional_params=[],
            example={"mean": 100000, "std": 20000},
        ),
        DistributionInfo(
            name="uniform",
            description="Uniform distribution — equal probability between low and high.",
            required_params=["low", "high"],
            optional_params=[],
            example={"low": 50000, "high": 150000},
        ),
        DistributionInfo(
            name="triangular",
            description="Triangular distribution — peak at mode between low and high.",
            required_params=["low", "mode", "high"],
            optional_params=[],
            example={"low": 50000, "mode": 100000, "high": 200000},
        ),
        DistributionInfo(
            name="lognormal",
            description="Log-normal distribution — always positive, right-skewed.",
            required_params=["mean", "std"],
            optional_params=[],
            example={"mean": 11.5, "std": 0.4},
        ),
        DistributionInfo(
            name="fixed",
            description="Fixed value — no randomness. Useful for known constants.",
            required_params=["value"],
            optional_params=[],
            example={"value": 50000},
        ),
    ]
    if page is None and limit is None:
        return entries
    envelope = paginate_sequence(entries, page=page or 1, limit=limit or 25)
    return DistributionListResponse(
        distributions=envelope.items,
        total=envelope.total,
        page=envelope.page,
        limit=envelope.limit,
        pages=envelope.pages,
    )


@router.get(
    "/v1/templates",
    response_model=list[TemplateInfo] | TemplateListResponse,
    summary="List built-in simulation templates",
)
async def templates(
    auth: AuthContext = Depends(get_current_org),
    page: int | None = Query(default=None, ge=1),
    limit: int | None = Query(default=None, ge=1, le=200),
) -> list[TemplateInfo] | TemplateListResponse:
    entries = [
        TemplateInfo(
            id="product-launch",
            name="Product Launch Decision",
            category="business",
            description="Compare launch vs no-launch with revenue and cost uncertainty.",
            example_request={
                "mode": "auto",
                "scenario": {
                    "name": "Product launch",
                    "variables": {
                        "revenue": {"low": 80000, "high": 300000},
                        "cost": {"low": 40000, "high": 100000},
                    },
                    "objective": "maximize_net_value",
                },
            },
        ),
        TemplateInfo(
            id="investment-risk",
            name="Investment Risk Assessment",
            category="finance",
            description=(
                "Model investment returns with normal distribution and assess downside risk."
            ),
            example_request={
                "mode": "expert",
                "simulation": {
                    "variables": [
                        {
                            "name": "return_rate",
                            "distribution": "normal",
                            "params": {"mean": 0.08, "std": 0.15},
                        },
                        {
                            "name": "investment",
                            "distribution": "fixed",
                            "params": {"value": 100000},
                        },
                    ],
                    "objective_function": "investment * return_rate",
                },
                "runs": 50000,
                "seed": 42,
            },
        ),
        TemplateInfo(
            id="pricing-decision",
            name="Pricing Decision",
            category="business",
            description="Evaluate the expected revenue impact of different pricing scenarios.",
            example_request={
                "mode": "auto",
                "scenario": {
                    "name": "Price increase scenario",
                    "variables": {
                        "unit_price": {"low": 49, "high": 99},
                        "volume": {"low": 500, "high": 2000},
                    },
                    "objective": "maximize_revenue",
                },
            },
        ),
    ]
    if page is None and limit is None:
        return entries
    envelope = paginate_sequence(entries, page=page or 1, limit=limit or 25)
    return TemplateListResponse(
        templates=envelope.items,
        total=envelope.total,
        page=envelope.page,
        limit=envelope.limit,
        pages=envelope.pages,
    )


# ─── API Key Management ────────────────────────────────────────────────────────


@router.get(
    "/v1/api-keys",
    response_model=list[APIKeyInfo] | APIKeyListResponse,
    summary="List active API keys",
)
async def list_api_keys(
    auth: AuthContext = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
    page: int | None = Query(default=None, ge=1),
    limit: int | None = Query(default=None, ge=1, le=200),
) -> list[APIKeyInfo] | APIKeyListResponse:
    now = datetime.now(UTC)
    result = await db.execute(
        select(APIKey)
        .options(selectinload(APIKey.organization))
        .where(APIKey.org_id == auth["org_id"])
        .where(APIKey.status == APIKeyStatus.ACTIVE)
        .order_by(APIKey.created_at.desc())
    )
    keys = [
        api_key
        for api_key in result.scalars().all()
        if not is_api_key_expired(api_key.expires_at, now=now)
    ]
    entries = [
        APIKeyInfo(
            id=k.id,
            label=k.label,
            key_prefix=k.key_prefix,
            device_limit=_api_key_info_device_limit(auth, k),
            status=k.status.value,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
            expires_at=k.expires_at,
        )
        for k in keys
    ]
    if page is None and limit is None:
        return entries
    envelope = paginate_sequence(entries, page=page or 1, limit=limit or 25)
    return APIKeyListResponse(
        api_keys=envelope.items,
        total=envelope.total,
        page=envelope.page,
        limit=envelope.limit,
        pages=envelope.pages,
    )


@router.post(
    "/v1/api-keys",
    response_model=APIKeyCreated,
    status_code=201,
    summary="Create a new API key",
)
async def create_api_key(
    payload: CreateAPIKeyRequest,
    auth: AuthContext = Depends(require_role("member")),
    db: AsyncSession = Depends(get_db),
) -> APIKeyCreated:
    try:
        stored_device_limit = validate_api_key_device_limit(auth["plan"], payload.device_limit)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "invalid_device_limit",
                    "message": str(exc),
                }
            },
        ) from exc

    raw_key, key_prefix, hashed_key = generate_api_key()
    api_key = APIKey(
        org_id=auth["org_id"],
        user_id=auth.get("user_id"),
        label=payload.label,
        key_prefix=key_prefix,
        hashed_key=hashed_key,
        device_limit=stored_device_limit,
        expires_at=payload.expires_at,
    )
    db.add(api_key)
    await db.flush()
    device_limit = effective_device_limit(auth["plan"], api_key.device_limit)
    logger.info(
        "api_key_created",
        org_id=str(auth["org_id"]),
        label=payload.label,
        device_limit=device_limit,
    )

    # Audit write
    from apps.api_server.services.audit_service import write_audit_event

    await write_audit_event(
        db=db,
        org_id=auth["org_id"],
        action="api_key.create",
        actor_email=auth.get("email", "api_key"),
        resource_type="api_key",
        resource_id=str(api_key.id),
        metadata={"label": payload.label, "device_limit": device_limit},
    )

    return APIKeyCreated(
        id=api_key.id,
        label=api_key.label,
        key_prefix=api_key.key_prefix,
        device_limit=device_limit,
        raw_key=raw_key,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
    )


@router.delete("/v1/api-keys/{key_id}", status_code=204, summary="Revoke an API key")
async def revoke_api_key(
    key_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(require_role("member")),
    db: AsyncSession = Depends(get_db),
    redis_client: object = Depends(get_redis),
) -> None:
    result = await db.execute(
        select(APIKey).where(APIKey.id == key_id).where(APIKey.org_id == auth["org_id"])
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "api_key_not_found",
                    "message": "API key not found.",
                }
            },
        )

    # Prevent revoking the last active key
    count_result = await db.execute(
        select(APIKey)
        .where(APIKey.org_id == auth["org_id"])
        .where(APIKey.status == APIKeyStatus.ACTIVE)
    )
    now = datetime.now(UTC)
    active_count = sum(
        1
        for candidate in count_result.scalars().all()
        if not is_api_key_expired(candidate.expires_at, now=now)
    )
    if active_count <= 1:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "cannot_revoke_last_key",
                    "message": ("Cannot revoke the last active API key. Create a new key first."),
                }
            },
        )

    api_key.status = APIKeyStatus.REVOKED
    await db.flush()
    await invalidate_api_key_cache(api_key.hashed_key, redis_client)
    logger.info("api_key_revoked", key_id=str(key_id), org_id=str(auth["org_id"]))

    # Audit write
    from apps.api_server.services.audit_service import get_client_ip, write_audit_event

    await write_audit_event(
        db=db,
        org_id=auth["org_id"],
        action="api_key.revoke",
        actor_email=auth.get("email", "api_key"),
        resource_type="api_key",
        resource_id=str(key_id),
        ip_address=get_client_ip(request),
        metadata={"label": api_key.label},
    )
