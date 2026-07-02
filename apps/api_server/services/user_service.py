"""User and Organization creation service — handles self-serve signup."""

import re

import bcrypt
import structlog
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.models.api_key import APIKey
from apps.api_server.models.organization import Organization, OrgPlan, OrgStatus
from apps.api_server.models.user import User, UserRole, UserStatus
from apps.api_server.schemas.auth import (
    APIKeyCreated,
    OrgInfo,
    SignUpRequest,
    SignUpResponse,
    UserInfo,
)
from apps.api_server.services.auth_service import generate_api_key
from apps.api_server.services.auth_tokens import issue_email_verification_token
from apps.api_server.services.plan_limits import effective_device_limit

logger = structlog.get_logger(__name__)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def _slug_from_email(email: str) -> str:
    """Derive a URL-safe org slug from an email address."""
    local = email.split("@")[0]
    slug = re.sub(r"[^a-z0-9]", "-", local.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:50] or "org"


async def create_user_and_org(
    request: SignUpRequest,
    db: AsyncSession,
) -> SignUpResponse:
    """Create org + user + first API key in a single transaction."""

    # Email is unique PER ORG now (not globally): a person (single Supabase identity) may
    # own and/or be a member of multiple orgs and hold subscriptions across them, so we do
    # NOT block sign-up when the email exists in another org. Per-org uniqueness is enforced
    # by the uq_users_org_email DB constraint + the invite/accept flow.

    # ── Create Organization ───────────────────────────────────────────────────
    base_slug = _slug_from_email(str(request.email))
    # Ensure slug uniqueness
    slug = base_slug
    suffix = 1
    while True:
        result = await db.execute(select(Organization).where(Organization.slug == slug))
        if result.scalar_one_or_none() is None:
            break
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    org = Organization(
        name=f"{request.name}'s Organization",
        slug=slug,
        plan=OrgPlan.FREE,
        status=OrgStatus.ACTIVE,
    )
    db.add(org)
    await db.flush()

    # ── Create User ───────────────────────────────────────────────────────────
    user = User(
        org_id=org.id,
        email=str(request.email).lower(),
        password_hash=hash_password(request.password),
        name=request.name,
        role=UserRole.OWNER,
        status=UserStatus.ACTIVE,
        email_verified=False,
    )
    db.add(user)
    await db.flush()

    # ── Create first API key ──────────────────────────────────────────────────
    raw_key, key_prefix, hashed_key = generate_api_key()
    api_key = APIKey(
        org_id=org.id,
        user_id=user.id,
        label="Default Key",
        key_prefix=key_prefix,
        hashed_key=hashed_key,
    )
    db.add(api_key)
    await db.flush()

    # ── Generate email verification token ─────────────────────────────────────
    verification_token = issue_email_verification_token(str(user.id), user.email)

    logger.info(
        "user_signed_up",
        org_id=str(org.id),
        user_id=str(user.id),
        email=request.email,
        slug=slug,
    )

    # ── Send welcome + verification email (non-blocking) ─────────────────────
    try:
        from apps.api_server.services.email_service import (
            send_verification_email,
            send_welcome_email,
        )

        await send_verification_email(str(request.email), verification_token)
        send_welcome_email(str(request.email), request.name, key_prefix)
    except Exception as exc:
        logger.warning("signup_email_failed", email=str(request.email), error=str(exc))

    return SignUpResponse(
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
        api_key=APIKeyCreated(
            id=api_key.id,
            label=api_key.label,
            key_prefix=api_key.key_prefix,
            device_limit=effective_device_limit(org.plan.value, api_key.device_limit),
            raw_key=raw_key,
            created_at=api_key.created_at,
        ),
    )


async def get_user_by_email(email: str, db: AsyncSession) -> User | None:
    # Email is per-org now, so an email can match multiple rows across orgs. Return the
    # earliest match (legacy email/password login is single-org; the shared identity lives
    # in Supabase). Org-scoped callers should query by (org_id, email) directly.
    result = await db.execute(
        select(User).where(User.email == email.lower()).order_by(User.created_at)
    )
    return result.scalars().first()


async def activate_telys_developer(
    db: AsyncSession, *, email: str, name: str | None = None
) -> tuple[Organization, User]:
    """Self-service Telys onboarding: resolve-or-create the caller's org (by Supabase email) and ensure it
    carries the free ``telys_developer`` entitlement (so the issued device license has ``products.telys``).

    Idempotent by email. NEVER downgrades a paid plan — it only lifts a brand-new/``free`` org onto the free
    Telys tier; a caller who already holds a paid plan without Telys keeps it (that cross-product upgrade is a
    separate billing concern). Returns ``(org, user)``. The mint of the API key is the caller's job.
    """
    from apps.api_server.services.entitlement_service import resolve_entitlement

    email = (email or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="a verified email is required to activate Telys")

    existing = await get_user_by_email(email, db)
    if existing is not None:
        org = (
            await db.execute(select(Organization).where(Organization.id == existing.org_id))
        ).scalar_one()
        # Grant the free Telys tier only if the org has NO Telys entitlement AND is on the free plan — never
        # clobber a paid plan.
        has_telys = "telys" in getattr(resolve_entitlement(org.plan.value), "products", {})
        if not has_telys and org.plan == OrgPlan.FREE:
            org.plan = OrgPlan.TELYS_DEVELOPER
            await db.flush()
            logger.info("telys_developer_activated_existing_org", org_id=str(org.id), email=email)
        return org, existing

    # Brand-new identity → create an org on the free Telys tier + an owner user (OAuth: no usable password).
    base_slug = _slug_from_email(email)
    slug = base_slug
    suffix = 1
    while (
        await db.execute(select(Organization).where(Organization.slug == slug))
    ).scalar_one_or_none() is not None:
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    display = name or email.split("@")[0]
    org = Organization(
        name=f"{display}'s Organization",
        slug=slug,
        plan=OrgPlan.TELYS_DEVELOPER,
        status=OrgStatus.ACTIVE,
    )
    db.add(org)
    await db.flush()

    import secrets as _secrets

    user = User(
        org_id=org.id,
        email=email,
        password_hash=hash_password(_secrets.token_urlsafe(32)),  # unusable — OAuth identity, no password login
        name=display,
        role=UserRole.OWNER,
        status=UserStatus.ACTIVE,
        email_verified=True,  # the OAuth provider already verified the email
    )
    db.add(user)
    await db.flush()
    logger.info("telys_developer_org_created", org_id=str(org.id), email=email, slug=slug)
    return org, user
