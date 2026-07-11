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


async def activate_product_free_tier(
    db: AsyncSession, *, product: str, email: str, name: str | None = None,
    supabase_uid: str | None = None,
) -> tuple[Organization, User]:
    """Self-service onboarding for ANY product: resolve-or-create the caller's org and ensure it carries
    that product's free entitlement (so the issued device license has ``products.<id>``).

    Resolution is **link-first** when ``supabase_uid`` is given: a stable Supabase uid that already has an
    ``identity_org_links`` row reuses that org — because email is NOT a safe key (Apple private-relay
    rotates, GitHub noreply), so keying on it would mint a duplicate org for the same person and strand
    their API key on it. Only when the uid has no link (or none is supplied) does it fall back to the
    email-keyed org.

    The product AND its free tier come from the product registry — never a caller-supplied string.
    Idempotent. NEVER downgrades a paid plan — it only lifts a brand-new/``free`` org onto the product's
    default free tier. Returns ``(org, user)``; minting the API key is the caller's job.
    """
    from apps.api_server.services.entitlement_service import resolve_entitlement
    from apps.api_server.services.product_registry import get_product

    cfg = get_product(product)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"unknown product {product!r}")
    free_plan = OrgPlan(cfg.default_free_tier)  # the enum value must exist (plan_limits + 0049 migration)

    async def _grant_free_tier(org: Organization) -> None:
        # Grant the free tier only if the org has NO entitlement for THIS product AND is on the free plan
        # — never clobber a paid plan (of any brand).
        has_product = cfg.id in getattr(resolve_entitlement(org.plan.value), "products", {})
        if not has_product and org.plan == OrgPlan.FREE:
            org.plan = free_plan
            await db.flush()

    # ── link-first: the stable uid wins over the (possibly-rotating) email ──────────────────────────
    if supabase_uid:
        from apps.api_server.services.byok_org_resolver import _org_for_identity_link

        linked = await _org_for_identity_link(db, supabase_uid)
        if linked is not None:
            await _grant_free_tier(linked)
            owner = (
                await db.execute(
                    select(User)
                    .where(User.org_id == linked.id)
                    .order_by(User.created_at)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if owner is None:  # linked org with no user (edge) — create the owner
                import secrets as _secrets

                owner = User(
                    org_id=linked.id,
                    email=(email or "").strip().lower() or f"{supabase_uid}@users.noreply.thyn.ai",
                    password_hash=hash_password(_secrets.token_urlsafe(32)),
                    name=name or "Owner",
                    role=UserRole.OWNER,
                    status=UserStatus.ACTIVE,
                    email_verified=bool((email or "").strip()),
                )
                db.add(owner)
                await db.flush()
            logger.info("product_free_tier_activated_via_link", product=cfg.id, org_id=str(linked.id))
            return linked, owner

    email = (email or "").strip().lower()
    if not email:
        raise HTTPException(
            status_code=400, detail=f"a verified email is required to activate {cfg.display_name}"
        )

    existing = await get_user_by_email(email, db)
    if existing is not None:
        org = (
            await db.execute(select(Organization).where(Organization.id == existing.org_id))
        ).scalar_one()
        await _grant_free_tier(org)
        return org, existing

    # Brand-new identity → create an org on the product's free tier + an owner user (OAuth: no usable password).
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
        plan=free_plan,
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
    logger.info("product_free_tier_org_created", product=cfg.id, org_id=str(org.id), email=email, slug=slug)
    return org, user


async def activate_telys_developer(
    db: AsyncSession, *, email: str, name: str | None = None
) -> tuple[Organization, User]:
    """Back-compat shim: Telys onboarding is the generic product free-tier activation for ``telys``.

    Kept so existing callers/tests (POST /v1/telys/onboard) are unchanged; behavior is byte-identical
    (telys' registry ``default_free_tier`` is ``telys_developer``)."""
    return await activate_product_free_tier(db, product="telys", email=email, name=name)
