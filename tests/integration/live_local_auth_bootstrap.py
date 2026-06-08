"""Helpers for standalone live integration scripts that target a local server."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

from tests.integration.live_local_defaults import DEFAULT_LOCAL_LIVE_API_KEY

ROOT = Path(__file__).resolve().parents[2]
_LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _settings():
    from apps.api_server.config import get_settings

    return get_settings()


def is_local_live_base_url(url: str | None) -> bool:
    """Return whether the target URL resolves to a loopback local live harness."""
    if not url:
        return False
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    return (parsed.hostname or "").lower() in _LOCAL_HOSTS


def _build_bootstrap_env() -> dict[str, str]:
    settings = _settings()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env.setdefault("API_ENV", settings.api_env)
    env.setdefault("DATABASE_URL", settings.database_url)
    env.setdefault("DATABASE_URL_SYNC", settings.database_url_sync)
    env.setdefault("REDIS_URL", settings.redis_url)
    env.setdefault("JWT_SECRET", settings.jwt_secret)
    return env


def run_local_live_migrations() -> None:
    """Apply local migrations before seeding the placeholder live API key."""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(ROOT / "apps" / "api_server" / "alembic.ini"),
            "upgrade",
            "head",
        ],
        cwd=str(ROOT),
        env=_build_bootstrap_env(),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "Alembic upgrade failed while bootstrapping the local live API key:\n"
            f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )


async def _seed_placeholder_live_api_key_async(database_url: str) -> str:
    from sqlalchemy import delete, select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from apps.api_server.models import (
        APIKey,
        APIKeyStatus,
        Deployment,
        Organization,
        OrgPlan,
        OrgStatus,
        User,
        UserRole,
        UserStatus,
    )
    from apps.api_server.services.auth_service import hash_api_key

    engine = create_async_engine(database_url, echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    hashed_key = hash_api_key(DEFAULT_LOCAL_LIVE_API_KEY)

    org_suffix = uuid.uuid4().hex[:12]
    async with session_factory() as session:
        org = Organization(
            name="Standalone Live Localhost",
            slug=f"standalone-live-localhost-{org_suffix}",
            plan=OrgPlan.PRO,
            status=OrgStatus.ACTIVE,
        )
        session.add(org)
        await session.flush()

        user = User(
            org_id=org.id,
            email=f"standalone-live+{org_suffix}@example.com",
            password_hash="standalone-live-localhost",
            name="Standalone Live",
            role=UserRole.OWNER,
            status=UserStatus.ACTIVE,
            email_verified=True,
        )
        session.add(user)
        await session.flush()

        await session.execute(delete(Deployment).where(Deployment.org_id == org.id))

        key_result = await session.execute(select(APIKey).where(APIKey.hashed_key == hashed_key))
        api_key = key_result.scalar_one_or_none()
        if api_key is None:
            api_key = APIKey(
                org_id=org.id,
                user_id=user.id,
                label="Standalone Live Localhost",
                key_prefix=DEFAULT_LOCAL_LIVE_API_KEY[:12],
                hashed_key=hashed_key,
                status=APIKeyStatus.ACTIVE,
            )
            session.add(api_key)
        else:
            api_key.org_id = org.id
            api_key.user_id = user.id
            api_key.label = "Standalone Live Localhost"
            api_key.key_prefix = DEFAULT_LOCAL_LIVE_API_KEY[:12]
            api_key.status = APIKeyStatus.ACTIVE

        await session.commit()

    await engine.dispose()
    return DEFAULT_LOCAL_LIVE_API_KEY


def ensure_bootstrapped_local_live_api_key(
    *,
    api_key: str,
    api_key_configured: bool,
    active_base_url: str,
) -> tuple[str, bool, str | None]:
    """Return a usable local live API key, bootstrapping the placeholder when safe."""
    if api_key_configured and api_key != DEFAULT_LOCAL_LIVE_API_KEY:
        return api_key, True, None
    if not is_local_live_base_url(active_base_url):
        return (
            api_key,
            False,
            "DE_API_KEY is not set and the active live base URL is not local.",
        )

    settings = _settings()
    try:
        run_local_live_migrations()
        seeded_key = asyncio.run(_seed_placeholder_live_api_key_async(settings.database_url))
    except Exception as exc:  # pragma: no cover - exercised via caller integration failures
        return api_key, False, f"Failed to bootstrap the local live API key: {exc}"

    os.environ["DE_API_KEY"] = seeded_key
    os.environ["ALGENTA_API_KEY"] = seeded_key
    return seeded_key, True, None
