"""Resolve a website-authenticated GitHub user to the engine org they may manage BYOK for.

The codna site authenticates with Supabase (GitHub OAuth); ``/byok`` verifies the JWT and hands us
the caller's numeric GitHub id + login. The engine org, though, is keyed by the *install account*
(``gh-user-{id}`` for a personal install, ``gh-org-{id}`` for an org install). So:

  1. **Personal install** — the caller's own GitHub id IS the install account; an O(1) slug lookup,
     zero GitHub calls. Covers solo devs (the common case at launch).
  2. **Org install** — the caller's id != the org's id, and there is no user↔org table. We enumerate
     the App's organization installations and, for each, use the App INSTALLATION token to ask
     GitHub whether the caller is an ACTIVE ADMIN of that org. Only admins may manage the org key.

A resolved ``(github_user_id -> org_id)`` mapping is cached in Redis (short TTL) to bound the
per-request GitHub fan-out. Failure posture is **fail-closed**: a per-org GitHub hiccup denies that
org (the user can retry), while a caller-level config failure (App unconfigured / egress denied)
surfaces as a clear 5xx rather than a silent "no org". Admin of >1 installed org raises 409 so the
caller can disambiguate (the site sends no org selector yet)."""
from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.models.github_app_installation import GithubAppInstallation
from apps.api_server.models.organization import Organization
from apps.api_server.services import github_app_auth
from apps.api_server.services.egress_guard import EgressPolicyDeniedError
from apps.api_server.services.github_app_provisioning import lookup_org_for_account

logger = structlog.get_logger(__name__)

_CACHE_PREFIX = "byok:org_for_gh_user:"
_CACHE_TTL_S = 300
# Bound the per-request fan-out so a pathological number of org installs can't blow up a single BYOK
# save. Logged when hit — never a silent truncation.
_MAX_ORG_INSTALLS_SCANNED = 200


class OrgResolutionError(Exception):
    """No single eligible org for the caller (mapped to ``http_status`` by the router)."""

    def __init__(self, code: str, message: str, *, http_status: int) -> None:
        self.code = code
        self.http_status = http_status
        super().__init__(message)


async def _cached_org_id(redis: Any | None, github_user_id: int) -> uuid.UUID | None:
    if redis is None:
        return None
    try:
        raw = await redis.get(f"{_CACHE_PREFIX}{github_user_id}")
    except Exception:  # noqa: BLE001 — cache is best-effort
        return None
    if not raw:
        return None
    raw = raw.decode() if isinstance(raw, bytes) else raw
    try:
        return uuid.UUID(str(raw))
    except ValueError:
        return None


async def _cache_org_id(redis: Any | None, github_user_id: int, org_id: uuid.UUID) -> None:
    if redis is None:
        return
    try:
        await redis.set(f"{_CACHE_PREFIX}{github_user_id}", str(org_id), ex=_CACHE_TTL_S)
    except Exception as exc:  # noqa: BLE001 — cache is best-effort
        logger.debug("byok_org_cache_write_failed", error=str(exc))


async def _org_by_id(db: AsyncSession, org_id: uuid.UUID) -> Organization | None:
    return (
        await db.execute(select(Organization).where(Organization.id == org_id))
    ).scalar_one_or_none()


async def resolve_org_for_github_user(
    db: AsyncSession,
    *,
    github_user_id: int,
    github_login: str,
    redis: Any | None = None,
) -> Organization:
    """Return the one engine org the caller may manage BYOK for, or raise ``OrgResolutionError``."""
    # 0) cache (bounds repeated GitHub fan-out for org-install users)
    cached = await _cached_org_id(redis, github_user_id)
    if cached is not None:
        org = await _org_by_id(db, cached)
        if org is not None:
            return org

    # 1) personal install — the caller's own id is the install account (no GitHub call)
    personal = await lookup_org_for_account(
        db, account_id=github_user_id, account_type="user"
    )
    if personal is not None:
        await _cache_org_id(redis, github_user_id, personal.id)
        return personal

    # 2) org installs — membership-check each via the App's installation token
    rows = list(
        (
            await db.execute(
                select(GithubAppInstallation)
                .where(
                    GithubAppInstallation.account_type == "organization",
                    GithubAppInstallation.suspended.is_(False),
                )
                .order_by(GithubAppInstallation.updated_at.desc())
            )
        )
        .scalars()
        .all()
    )
    if len(rows) > _MAX_ORG_INSTALLS_SCANNED:
        logger.warning(
            "byok_org_scan_truncated",
            scanned=_MAX_ORG_INSTALLS_SCANNED,
            total=len(rows),
            github_user_id=github_user_id,
        )
        rows = rows[:_MAX_ORG_INSTALLS_SCANNED]

    eligible: dict[uuid.UUID, Organization] = {}
    for row in rows:
        if not row.account_login:
            continue
        try:
            membership = await github_app_auth.installation_membership_role(
                row.installation_id,
                row.account_login,
                github_login,
                org_id=row.org_id,
                redis=redis,
                installation_row=row,
            )
        except github_app_auth.GithubAppNotConfiguredError as exc:
            # Caller-level config failure (affects every org) — surface, don't silently deny.
            raise OrgResolutionError(
                "github_app_unconfigured",
                "The GitHub App is not configured on this engine.",
                http_status=503,
            ) from exc
        except EgressPolicyDeniedError as exc:
            raise OrgResolutionError(
                "github_unreachable",
                "Could not reach GitHub to verify organization membership (egress denied).",
                http_status=502,
            ) from exc
        except Exception as exc:  # noqa: BLE001 — a transient failure for THIS org -> skip (fail-closed)
            logger.warning(
                "byok_membership_check_failed",
                org_id=str(row.org_id),
                account_login=row.account_login,
                error=str(exc),
            )
            continue
        if (
            membership
            and str(membership.get("state")) == "active"
            and str(membership.get("role")) == "admin"
        ):
            org = await _org_by_id(db, row.org_id)
            if org is not None:
                eligible[org.id] = org

    # Persist any installation-token cold-cache writes get_installation_token made on the rows.
    try:
        await db.commit()
    except Exception:  # noqa: BLE001 — token caching is best-effort; never fail the request on it
        await db.rollback()

    if not eligible:
        raise OrgResolutionError(
            "no_org",
            "No organization you administer has Algenta installed.",
            http_status=403,
        )
    if len(eligible) > 1:
        raise OrgResolutionError(
            "multiple_orgs",
            "You administer multiple organizations with Algenta installed; "
            "selecting which one isn't supported yet.",
            http_status=409,
        )
    org = next(iter(eligible.values()))
    await _cache_org_id(redis, github_user_id, org.id)
    return org
