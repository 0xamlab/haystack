"""User and Organization creation service — handles self-serve signup."""
import re
import secrets
from datetime import UTC, datetime, timedelta

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

    # ── Check duplicate email ─────────────────────────────────────────────────
    existing = await db.execute(
        select(User).where(User.email == request.email.lower())
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "email_already_exists",
                    "message": f"An account with email '{request.email}' already exists.",
                    "docs_url": "https://docs.decisionengine.io/errors/email_already_exists",
                }
            },
        )

    # ── Create Organization ───────────────────────────────────────────────────
    base_slug = _slug_from_email(str(request.email))
    # Ensure slug uniqueness
    slug = base_slug
    suffix = 1
    while True:
        result = await db.execute(
            select(Organization).where(Organization.slug == slug)
        )
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
    verification_token = secrets.token_urlsafe(48)
    verification_expires = datetime.now(UTC) + timedelta(hours=24)
    try:
        user.email_verification_token = verification_token  # type: ignore[assignment]
        user.email_verification_expires_at = verification_expires  # type: ignore[assignment]
    except Exception as exc:
        logger.debug(
            "user_verification_columns_unavailable",
            user_id=str(user.id),
            error=str(exc),
        )

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
            raw_key=raw_key,
            created_at=api_key.created_at,
        ),
    )


async def get_user_by_email(email: str, db: AsyncSession) -> User | None:
    result = await db.execute(
        select(User).where(User.email == email.lower())
    )
    return result.scalar_one_or_none()
