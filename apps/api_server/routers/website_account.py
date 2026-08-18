"""Website account settings — Supabase-authenticated (companion to /account/team, /account/devices).

``/v1/me`` (apps/api_server/routers/account.py) is the CLI/MCP-tool surface: authenticated by a
codna API key via ``get_current_org``. The website never held one of those — it authenticates
every account-page action with the user's Supabase access_token — so calling ``/v1/me`` with that
token always 401'd (``get_current_org`` doesn't understand Supabase JWTs at all). That 401 was
silent everywhere it mattered: ``getCodnaFixEnabled()`` swallows it behind a permissive default,
and ``setCodnaFixEnabled()`` surfaces a generic "could not update" without ever explaining why
the toggle never persisted. This is a dedicated Supabase-authenticated twin of the ``codna_fix_enabled``
slice of ``/v1/me``, same shape as every other ``website_*`` router. Inert until SUPABASE_URL is set.
"""

from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_redis
from apps.api_server.models.github_app_installation import GithubAppInstallation
from apps.api_server.models.organization import Organization
from apps.api_server.models.user import User, UserRole
from apps.api_server.services import github_app_auth, website_identity

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["account"])


class GithubInstallationInfo(BaseModel):
    installation_id: int
    account_login: str | None
    account_type: str | None
    suspended: bool


class AccountSettingsResponse(BaseModel):
    org_id: str
    org_name: str
    codna_fix_enabled: bool
    # REAL GitHub App install state for this org, verified against GitHub. The account page used
    # to infer "Connected via GitHub" from "the caller resolved at least one org", which is a
    # completely different fact: an org resolves from an identity_org_links row / an email
    # membership / a CLI onboard, none of which involve a GitHub App install at all. So the card
    # read "Connected via GitHub" for every signed-in user forever -- including right after they
    # uninstalled the App, which is exactly what was reported.
    github_installations: list[GithubInstallationInfo]
    github_connected: bool


class UpdateAccountSettingsRequest(BaseModel):
    codna_fix_enabled: bool | None = None
    org_name: str | None = None


async def _require_org_admin(db: AsyncSession, org: Organization, identity: dict[str, Any]) -> None:
    """Same gate as website_team.py's _require_team_manager: a caller with a Users row in this
    org must hold owner/admin; a caller with no row got here via GitHub-install admin
    resolution (the only row-less path), which already proves admin."""
    email = (identity.get("email") or "").strip().lower()
    if not email:
        return
    member = (
        await db.execute(
            select(User).where(User.org_id == org.id, func.lower(User.email) == email)
        )
    ).scalar_one_or_none()
    if member is not None and member.role not in (UserRole.OWNER, UserRole.ADMIN):
        raise HTTPException(
            status_code=403,
            detail=website_identity.error_body(
                "insufficient_role", "Only owners and admins can change this."
            ),
        )


async def _live_github_installations(
    db: AsyncSession, org: Organization, redis: Any | None = None
) -> list[GithubInstallationInfo]:
    """This org's GitHub App installations, each verified to still exist on GitHub.

    A row here is NOT proof of a live install. The codna-ai App's webhooks are delivered to
    codna's own webhook service, not to this backend, so this backend's ``installation.deleted``
    handler never fires for it -- an uninstall leaves the row behind indefinitely (confirmed
    live: GitHub reported 0 installations while two rows were still present). Verify against
    GitHub and PRUNE what's definitively gone, so every reader converges on the truth instead
    of trusting a row nothing maintains.

    Fails OPEN: only a definitive 404 prunes. An unverifiable result (egress denied,
    GitHub unreachable, App unconfigured) keeps the row and reports it as-is, so a transient
    blip never tells a paying customer their integration vanished."""
    rows = (
        (
            await db.execute(
                select(GithubAppInstallation).where(GithubAppInstallation.org_id == org.id)
            )
        )
        .scalars()
        .all()
    )
    if not rows or not github_app_auth.app_configured():
        return [
            GithubInstallationInfo(
                installation_id=r.installation_id,
                account_login=r.account_login,
                account_type=r.account_type,
                suspended=r.suspended,
            )
            for r in rows
        ]
    live: list[GithubInstallationInfo] = []
    pruned = 0
    for row in rows:
        alive = await github_app_auth.installation_is_live(
            row.installation_id, org_id=org.id, redis=redis
        )
        if alive is False:
            await db.delete(row)
            pruned += 1
            continue
        live.append(
            GithubInstallationInfo(
                installation_id=row.installation_id,
                account_login=row.account_login,
                account_type=row.account_type,
                suspended=row.suspended,
            )
        )
    if pruned:
        await db.commit()
        logger.info("website_pruned_dead_github_installations", org_id=str(org.id), pruned=pruned)
    return live


@router.get(
    "/account/settings",
    response_model=AccountSettingsResponse,
    summary="Get org settings (website / Supabase auth)",
)
async def get_account_settings(
    response: Response,
    authorization: Annotated[str | None, Header()] = None,
    x_org_id: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
) -> AccountSettingsResponse:
    response.headers["Cache-Control"] = "no-store"  # reflects live DB state, never cache it
    org, _identity = await website_identity.verify_and_resolve_org(
        authorization, db, redis, selected_org_id=website_identity.parse_org_id(x_org_id)
    )
    installs = await _live_github_installations(db, org, redis)
    return AccountSettingsResponse(
        org_id=str(org.id),
        org_name=org.name,
        codna_fix_enabled=org.codna_fix_enabled,
        github_installations=installs,
        github_connected=any(not i.suspended for i in installs),
    )


@router.patch(
    "/account/settings",
    response_model=AccountSettingsResponse,
    summary="Update org settings (website / Supabase auth)",
)
async def update_account_settings(
    payload: UpdateAccountSettingsRequest,
    response: Response,
    authorization: Annotated[str | None, Header()] = None,
    x_org_id: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
    redis: Any = Depends(get_redis),
) -> AccountSettingsResponse:
    response.headers["Cache-Control"] = "no-store"
    org, identity = await website_identity.verify_and_resolve_org(
        authorization, db, redis, selected_org_id=website_identity.parse_org_id(x_org_id)
    )
    if payload.codna_fix_enabled is not None or payload.org_name is not None:
        await _require_org_admin(db, org, identity)
    if payload.codna_fix_enabled is not None:
        org.codna_fix_enabled = payload.codna_fix_enabled
    if payload.org_name is not None:
        org.name = payload.org_name
    await db.commit()
    logger.info(
        "website_account_settings_updated",
        org_id=str(org.id),
        codna_fix_enabled_updated=payload.codna_fix_enabled is not None,
        org_name_updated=payload.org_name is not None,
    )
    # Report install state straight from the rows here (no GitHub round-trip): a settings WRITE
    # must not be able to fail, or slow down, on an unrelated GitHub API call. The GET is what
    # reconciles.
    rows = (
        (
            await db.execute(
                select(GithubAppInstallation).where(GithubAppInstallation.org_id == org.id)
            )
        )
        .scalars()
        .all()
    )
    installs = [
        GithubInstallationInfo(
            installation_id=r.installation_id,
            account_login=r.account_login,
            account_type=r.account_type,
            suspended=r.suspended,
        )
        for r in rows
    ]
    return AccountSettingsResponse(
        org_id=str(org.id),
        org_name=org.name,
        codna_fix_enabled=org.codna_fix_enabled,
        github_installations=installs,
        github_connected=any(not i.suspended for i in installs),
    )
