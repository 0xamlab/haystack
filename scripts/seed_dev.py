"""
Development seed script — creates a dev org, user, and API key.
Run with: make seed (inside the API container) or: python scripts/seed_dev.py

Prints the raw API key (and, on first run, the dev user's password) to stdout — save them,
they won't be shown again. Set SEED_DEV_PASSWORD to choose the dev user's password.
"""

import asyncio
import os
import secrets
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.local_operator_contract import DEFAULT_LOCAL_OPERATOR_BASE_URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api_server.config import get_settings
from apps.api_server.models.api_key import APIKey
from apps.api_server.models.organization import Organization, OrgPlan, OrgStatus
from apps.api_server.models.user import User, UserRole, UserStatus
from apps.api_server.services.auth_service import generate_api_key

settings = get_settings()


async def seed() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    session_local = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_local() as session:
        # Check if dev org already exists
        from sqlalchemy import select

        result = await session.execute(select(Organization).where(Organization.slug == "dev-org"))
        existing_org = result.scalar_one_or_none()

        if existing_org:
            print("Dev org already exists. Creating new API key...")
            org = existing_org
        else:
            # Create dev organization
            org = Organization(
                name="Dev Organization",
                slug="dev-org",
                plan=OrgPlan.DEVELOPER,
                status=OrgStatus.ACTIVE,
            )
            session.add(org)
            await session.flush()

            # Create dev user
            import bcrypt

            password = os.environ.get("SEED_DEV_PASSWORD") or secrets.token_urlsafe(16)
            password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            user = User(
                org_id=org.id,
                email="dev@example.com",
                password_hash=password_hash,
                name="Dev User",
                role=UserRole.OWNER,
                status=UserStatus.ACTIVE,
                email_verified=True,
            )
            session.add(user)
            await session.flush()
            print(f"✅ Created dev user: dev@example.com / {password}  (shown once only)")

        # Generate new API key
        raw_key, key_prefix, hashed_key = generate_api_key()

        api_key = APIKey(
            org_id=org.id,
            label="Dev Key",
            key_prefix=key_prefix,
            hashed_key=hashed_key,
        )
        session.add(api_key)
        await session.commit()

        print()
        print("=" * 60)
        print("🔑 YOUR DEV API KEY (shown once only):")
        print()
        print(f"   {raw_key}")
        print()
        print("Usage:")
        print(f'   curl -H "X-API-Key: {raw_key}" {DEFAULT_LOCAL_OPERATOR_BASE_URL}/v1/health')
        print()
        print("Or set environment variables:")
        print(f'   export ALGENTA_API_KEY="{raw_key}"')
        print(f'   export DE_API_KEY="{raw_key}"')
        print("=" * 60)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
