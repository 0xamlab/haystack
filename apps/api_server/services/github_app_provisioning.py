"""Install-first org provisioning for the codna GitHub App.

When a GitHub App install arrives (webhook ``installation.created`` or the post-install
callback WITHOUT a codna ``state`` nonce — i.e. the user found us on the GitHub Marketplace
first, not from a codna dashboard), there is no pre-existing codna org to bind to. This
module mints one on the fly, idempotently, so the install-first funnel works with zero
prior signup.

The org gets the FREE plan (whose $5 managed-LLM cap is the trial bound — we deliberately do
NOT set a per-org quota) plus a single ``is_service`` API key the agent uses for engine
callbacks. Everything keys off a deterministic slug derived from the GitHub account id, so a
re-delivered webhook / retried callback resolves to the SAME org instead of forking a new one.

Inert until the GitHub App is configured; only reached from the (signature-verified) webhook
and the (App-JWT-verified) install callback.
"""
from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.config import get_settings
from apps.api_server.models.api_key import APIKey
from apps.api_server.models.organization import Organization, OrgPlan, OrgStatus
from apps.api_server.services.auth_service import generate_api_key

logger = structlog.get_logger(__name__)


def _slug_for_account(account_id: int, account_type: str) -> str:
    """Deterministic, collision-stable slug for a GitHub account.

    Keyed on the immutable numeric account id (NOT the renamable login) so a login change on
    the GitHub side can never fork a second org. ``Organization.slug`` is UNIQUE, which is what
    makes provisioning idempotent under the multi-replica webhook race."""
    kind = "org" if str(account_type).strip().lower() == "organization" else "user"
    return f"gh-{kind}-{int(account_id)}"


async def lookup_org_for_account(
    db: AsyncSession, *, account_id: int, account_type: str
) -> Organization | None:
    """Lookup-only resolution by the deterministic ``gh-{org|user}-{account_id}`` slug.

    Unlike :func:`provision_or_lookup_org_for_installation`, this NEVER creates an org — it returns
    the existing org for a GitHub account or ``None`` if that account has never installed the App.
    Used by the website BYOK bridge to map a logged-in GitHub user (personal install) to their org
    without minting anything."""
    slug = _slug_for_account(account_id, account_type)
    return (
        await db.execute(select(Organization).where(Organization.slug == slug))
    ).scalar_one_or_none()


async def provision_or_lookup_org_for_installation(
    db: AsyncSession,
    *,
    account_id: int,
    account_login: str,
    account_type: str,
) -> Organization:
    """Return the codna org for a GitHub account, creating it on first install (idempotent).

    Resolution is by the deterministic ``gh-{org|user}-{account_id}`` slug:
      1. SELECT by slug — return the existing org if found (re-delivery / retry).
      2. Else create FREE/ACTIVE org + flush; on IntegrityError (a concurrent replica won the
         unique-slug race) rollback + re-SELECT and use the winner.
    A fresh org also gets one ``is_service`` API key ("GitHub App") for agent engine callbacks.
    The caller commits (this only flushes), so the org + key + installation binding all land in
    a single transaction."""
    slug = _slug_for_account(account_id, account_type)

    existing = (
        await db.execute(select(Organization).where(Organization.slug == slug))
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    org = Organization(
        name=f"{account_login} (GitHub)",
        slug=slug,
        plan=OrgPlan.FREE,
        status=OrgStatus.ACTIVE,
        # FREE plan's managed-LLM $5 cap is the trial bound — no per-org quota override.
        managed_llm_enabled=bool(get_settings().algenta_managed_llm),
    )
    db.add(org)
    try:
        await db.flush()
    except IntegrityError:
        # A concurrent install on another replica created the same slug first; resolve to it.
        await db.rollback()
        winner = (
            await db.execute(select(Organization).where(Organization.slug == slug))
        ).scalar_one_or_none()
        if winner is not None:
            return winner
        raise  # genuinely unexpected — surface it rather than loop

    # Service key for the agent's engine callbacks (no human owner -> user_id=None, is_service).
    _raw_key, key_prefix, hashed_key = generate_api_key()
    db.add(
        APIKey(
            org_id=org.id,
            user_id=None,
            label="GitHub App",
            key_prefix=key_prefix,
            hashed_key=hashed_key,
            is_service=True,
        )
    )
    await db.flush()
    logger.info(
        "github_app_org_provisioned",
        org_id=str(org.id),
        slug=slug,
        account_type=str(account_type),
    )
    return org
