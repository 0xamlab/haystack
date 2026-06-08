"""
Bootstrap a self-hosted Algenta installation with a local owner and API key.

This script is intended for customer-run service deployments, not local dev seeding.
It creates a bootstrap organization/user if missing, then always creates a fresh
bootstrap API key and prints machine-readable output for installer consumption.
"""
# ruff: noqa: E402

from __future__ import annotations

import asyncio
import os
import secrets
import string
import sys
from dataclasses import dataclass
from pathlib import Path

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.api_server.config import get_settings
from apps.api_server.models.api_key import APIKey
from apps.api_server.models.organization import Organization, OrgPlan, OrgStatus
from apps.api_server.models.user import User, UserRole, UserStatus
from apps.api_server.services.auth_service import generate_api_key

settings = get_settings()

DEFAULT_ORG_NAME = "Self-Hosted Organization"
DEFAULT_ORG_SLUG = "self-hosted-org"
DEFAULT_USER_EMAIL = "owner@selfhost.algenta.ai"
DEFAULT_USER_NAME = "Self-Hosted Owner"
PASSWORD_LENGTH = 32


@dataclass(frozen=True)
class BootstrapConfig:
    org_name: str
    org_slug: str
    user_email: str
    user_name: str
    user_password: str | None
    test_key: bool


@dataclass(frozen=True)
class BootstrapResult:
    org_slug: str
    user_email: str
    user_password: str | None
    user_created: bool
    api_key_id: str
    api_key_prefix: str
    api_key: str


def _generate_password(length: int = PASSWORD_LENGTH) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _get_config() -> BootstrapConfig:
    password = os.getenv("ALGENTA_BOOTSTRAP_PASSWORD")
    test_key_raw = os.getenv("ALGENTA_BOOTSTRAP_TEST_KEY", "true").strip().lower()
    return BootstrapConfig(
        org_name=os.getenv("ALGENTA_BOOTSTRAP_ORG_NAME", DEFAULT_ORG_NAME).strip()
        or DEFAULT_ORG_NAME,
        org_slug=os.getenv("ALGENTA_BOOTSTRAP_ORG_SLUG", DEFAULT_ORG_SLUG).strip()
        or DEFAULT_ORG_SLUG,
        user_email=os.getenv("ALGENTA_BOOTSTRAP_EMAIL", DEFAULT_USER_EMAIL).strip()
        or DEFAULT_USER_EMAIL,
        user_name=os.getenv("ALGENTA_BOOTSTRAP_NAME", DEFAULT_USER_NAME).strip()
        or DEFAULT_USER_NAME,
        user_password=password.strip() if password and password.strip() else None,
        test_key=test_key_raw not in {"0", "false", "no"},
    )


async def _ensure_bootstrap(
    session: AsyncSession,
    *,
    config: BootstrapConfig,
) -> BootstrapResult:
    org_result = await session.execute(
        select(Organization).where(Organization.slug == config.org_slug)
    )
    org = org_result.scalar_one_or_none()
    if org is None:
        org = Organization(
            name=config.org_name,
            slug=config.org_slug,
            plan=OrgPlan.FREE,
            status=OrgStatus.ACTIVE,
        )
        session.add(org)
        await session.flush()

    user_result = await session.execute(select(User).where(User.email == config.user_email))
    user = user_result.scalar_one_or_none()
    user_created = False
    user_password: str | None = None
    if user is None:
        user_password = config.user_password or _generate_password()
        user = User(
            org_id=org.id,
            email=config.user_email,
            password_hash=bcrypt.hashpw(
                user_password.encode("utf-8"),
                bcrypt.gensalt(),
            ).decode("utf-8"),
            name=config.user_name,
            role=UserRole.OWNER,
            status=UserStatus.ACTIVE,
            email_verified=True,
        )
        session.add(user)
        await session.flush()
        user_created = True
    elif user.org_id != org.id:
        raise RuntimeError(
            "Bootstrap email already belongs to a different organization. "
            "Set ALGENTA_BOOTSTRAP_EMAIL or ALGENTA_BOOTSTRAP_ORG_SLUG explicitly."
        )

    raw_key, key_prefix, hashed_key = generate_api_key(test=config.test_key)
    api_key = APIKey(
        org_id=org.id,
        user_id=user.id,
        label="Bootstrap Key",
        key_prefix=key_prefix,
        hashed_key=hashed_key,
    )
    session.add(api_key)
    await session.flush()
    await session.commit()

    return BootstrapResult(
        org_slug=org.slug,
        user_email=user.email,
        user_password=user_password,
        user_created=user_created,
        api_key_id=str(api_key.id),
        api_key_prefix=api_key.key_prefix,
        api_key=raw_key,
    )


def _render_result(result: BootstrapResult) -> str:
    lines = [
        "ALGENTA_BOOTSTRAP_READY=1",
        f"BOOTSTRAP_ORG_SLUG={result.org_slug}",
        f"BOOTSTRAP_USER_EMAIL={result.user_email}",
        f"BOOTSTRAP_USER_CREATED={'1' if result.user_created else '0'}",
        f"BOOTSTRAP_API_KEY_ID={result.api_key_id}",
        f"BOOTSTRAP_API_KEY_PREFIX={result.api_key_prefix}",
        f"BOOTSTRAP_API_KEY={result.api_key}",
    ]
    if result.user_password is not None:
        lines.append(f"BOOTSTRAP_USER_PASSWORD={result.user_password}")
    return "\n".join(lines)


async def _main() -> int:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with session_factory() as session:
            result = await _ensure_bootstrap(session, config=_get_config())
        print(_render_result(result))
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
