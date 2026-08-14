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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.models.github_app_installation import GithubAppInstallation
from apps.api_server.models.organization import Organization
from apps.api_server.services import github_app_auth
from apps.api_server.services.egress_guard import EgressPolicyDeniedError
from apps.api_server.services.github_app_provisioning import (
    lookup_org_for_account,
    provision_org_for_supabase_uid,
)

logger = structlog.get_logger(__name__)

_CACHE_PREFIX = "byok:org_for_gh_user:"
_CACHE_TTL_S = 300
# Bound the per-request fan-out so a pathological number of org installs can't blow up a single BYOK
# save. Logged when hit — never a silent truncation.
_MAX_ORG_INSTALLS_SCANNED = 200


class OrgResolutionError(Exception):
    """No single eligible org for the caller (mapped to ``http_status`` by the router)."""

    def __init__(self, code: str, message: str, *, http_status: int, orgs: list | None = None) -> None:
        self.code = code
        self.http_status = http_status
        # For 'multiple_orgs': the eligible orgs [{id, name}] so the caller can show a picker.
        self.orgs = orgs or []
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
    selected_org_id: uuid.UUID | None = None,
) -> Organization:
    """Return the engine org the caller may manage, or raise ``OrgResolutionError``. When the caller
    administers several eligible orgs, `selected_org_id` picks one (if valid); otherwise a
    ``multiple_orgs`` error carries the options for a picker."""
    # 0) cache (bounds repeated GitHub fan-out for org-install users). Skip when the caller is
    # explicitly picking an org — an earlier pick must not pin them to it.
    if selected_org_id is None:
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
        # The caller picked one and it's a valid choice — honour it.
        if selected_org_id is not None and selected_org_id in eligible:
            org = eligible[selected_org_id]
            await _cache_org_id(redis, github_user_id, org.id)
            return org
        # Otherwise hand the options back so the caller can render a picker. (Ordered by name for
        # a stable, human-friendly list.)
        options = sorted(
            ({"id": str(o.id), "name": o.name} for o in eligible.values()),
            key=lambda o: (o["name"] or "").lower(),
        )
        raise OrgResolutionError(
            "multiple_orgs",
            "You administer multiple organizations; choose which one to manage.",
            http_status=409,
            orgs=options,
        )
    org = next(iter(eligible.values()))
    await _cache_org_id(redis, github_user_id, org.id)
    return org


# ── Provider-agnostic resolution (github / google / apple / microsoft) ──────────────


async def _org_for_identity_link(db: AsyncSession, supabase_uid: str) -> Organization | None:
    """The org pointed at by this Supabase identity's link row, or None."""
    from apps.api_server.models.identity_org_link import IdentityOrgLink

    link = (
        await db.execute(
            select(IdentityOrgLink).where(IdentityOrgLink.supabase_uid == supabase_uid)
        )
    ).scalar_one_or_none()
    if link is None:
        return None
    return await _org_by_id(db, link.org_id)


async def ensure_identity_link(db: AsyncSession, *, supabase_uid: str, org_id: uuid.UUID) -> uuid.UUID:
    """Point this Supabase identity at ``org_id`` (adopt-legacy / first-provision / CLI-onboard).

    Returns the org id the link ACTUALLY points to — which may differ from ``org_id`` when a concurrent
    insert won the ``unique(supabase_uid)`` race. Callers that just auto-provisioned an org MUST honor
    the returned winner, not their own fresh org, or they strand a duplicate (TOCTOU).

    Idempotent + race safe: no-op if a link already exists; a concurrent insert rolls back only the
    SAVEPOINT (never the outer transaction), so the winner's row stands. Best-effort — a link failure
    never blocks resolution.

    PUBLIC so the self-serve onboarding path (``<product> login``) can bind the just-created email-keyed
    org to the caller's Supabase uid — without it a non-GitHub (google/apple/microsoft) user who onboards
    via the CLI then upgrades on the website would resolve to a DIFFERENT org (an auto-provisioned
    duplicate, or a no_org 403)."""
    from apps.api_server.models.identity_org_link import IdentityOrgLink

    existing = (
        await db.execute(
            select(IdentityOrgLink).where(IdentityOrgLink.supabase_uid == supabase_uid)
        )
    ).scalar_one_or_none()
    if existing is not None:
        # Heal a DANGLING link: the row survives but the org it points at is gone (hard-deleted
        # org, a partial purge, a restore that dropped organizations but kept identity_org_links).
        # Returning the stale id strands the identity on a phantom org forever —
        # resolve_org_for_supabase_user reads the link first, _org_by_id returns None, and the
        # caller 403s `no_org`, while every fresh onboard mints its api key and registers its
        # device on a NEW org the portal never reads. That is exactly the "No devices registered
        # yet" state alongside a CLI that reports success. Repoint instead.
        if await _org_by_id(db, existing.org_id) is None:
            existing.org_id = org_id
            await db.flush()
            return org_id
        return existing.org_id
    try:
        async with db.begin_nested():
            db.add(IdentityOrgLink(supabase_uid=supabase_uid, org_id=org_id))
        return org_id
    except IntegrityError:
        # A concurrent request linked the same uid first — re-read and return the WINNER so the caller
        # converges on it instead of stranding a just-provisioned duplicate.
        winner = (
            await db.execute(
                select(IdentityOrgLink).where(IdentityOrgLink.supabase_uid == supabase_uid)
            )
        ).scalar_one_or_none()
        return winner.org_id if winner is not None else org_id


async def repoint_identity_link(db: AsyncSession, *, supabase_uid: str, org_id: uuid.UUID) -> None:
    """Move this identity's link to ``org_id`` (or create it). Used only when the caller EXPLICITLY
    picks an org (``selected_org_id`` / X-Org-Id) — a multi-org GitHub admin switching orgs — so the
    pick persists as the new default. Idempotent."""
    from apps.api_server.models.identity_org_link import IdentityOrgLink

    existing = (
        await db.execute(
            select(IdentityOrgLink).where(IdentityOrgLink.supabase_uid == supabase_uid)
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.org_id != org_id:
            existing.org_id = org_id
        return
    await ensure_identity_link(db, supabase_uid=supabase_uid, org_id=org_id)


async def resolve_org_for_supabase_user(
    db: AsyncSession,
    *,
    supabase_uid: str,
    email: str | None = None,
    github_user_id: int | None = None,
    github_login: str | None = None,
    redis: Any | None = None,
    selected_org_id: uuid.UUID | None = None,
    auto_provision: bool = False,
) -> Organization:
    """Resolve the engine org for a verified Supabase identity, PROVIDER-AGNOSTICALLY.

    - **GitHub identities** keep the full existing resolution (personal ``gh-user-{id}`` install +
      admin-membership org installs + the multiple-orgs 409), then the resolved org is ADOPTED under
      the Supabase uid (an ``identity_org_links`` row) so a later Google/Apple/Microsoft login on the
      SAME Supabase account resolves to the SAME org.
    - **Non-GitHub identities** resolve via the identity link (their adopted or provisioned personal
      org). With ``auto_provision`` on, a brand-new identity gets an ``sb-user-{uid}`` FREE org on
      first resolve; with it off (default/dark) they get a ``no_org`` 403 until the flip.

    The identity key is the Supabase ``sub`` — never email (Apple privaterelay / GitHub noreply)."""
    # The identity link is AUTHORITATIVE and consulted FIRST for EVERY provider: whatever org this
    # Supabase uid was first bound to (CLI `<product> login`, a prior web resolve, or a GitHub install
    # adoption) is the single org all providers converge on. Checking it before the GitHub branch is
    # what stops a github-linked user who onboarded via the CLI from being hijacked onto a different
    # gh-user-{id} org — or locked out with no_org when they have no install at all. An explicit
    # `selected_org_id` (the org picker / X-Org-Id) bypasses the link so a multi-org GitHub admin can
    # still switch orgs; the switch then re-points the link below.
    if selected_org_id is None:
        linked = await _org_for_identity_link(db, supabase_uid)
        if linked is not None:
            return linked

    # No link yet (or an explicit pick). A GitHub identity resolves via its App install
    # (personal / admin-of-org), then the resolved org is adopted/re-pointed under the uid so later
    # logins on any provider converge on it.
    if github_user_id is not None:
        try:
            org = await resolve_org_for_github_user(
                db,
                github_user_id=github_user_id,
                github_login=github_login or "",
                redis=redis,
                selected_org_id=selected_org_id,
            )
        except OrgResolutionError as exc:
            # A GitHub sign-in with NO App installation is still a customer — without this,
            # "Continue with GitHub" users could never check out (403 at /account/billing/*).
            # Fall through to the same lazy personal org every other provider gets; if they
            # later install the App, the identity link keeps them on this org (no hijack).
            if not (auto_provision and exc.code == "no_org" and selected_org_id is None):
                raise
        else:
            if selected_org_id is not None:
                await repoint_identity_link(db, supabase_uid=supabase_uid, org_id=org.id)
            else:
                await ensure_identity_link(db, supabase_uid=supabase_uid, org_id=org.id)
            return org

    if auto_provision:
        org = await provision_org_for_supabase_uid(db, supabase_uid=supabase_uid, email=email)
        winner_id = await ensure_identity_link(db, supabase_uid=supabase_uid, org_id=org.id)
        if winner_id != org.id:
            # A concurrent path linked a DIFFERENT org first — honor the winner so this request's
            # subscription/devices don't strand on the just-provisioned duplicate (TOCTOU).
            won = await _org_by_id(db, winner_id)
            if won is not None:
                return won
        return org

    raise OrgResolutionError(
        "no_org",
        "No organization is linked to this account yet.",
        http_status=403,
    )
