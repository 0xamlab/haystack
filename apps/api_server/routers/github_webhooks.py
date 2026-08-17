"""GitHub App — inbound webhook receiver + install/OAuth callback.

`POST /webhooks/github` is the one public, unauthenticated route: it verifies the GitHub
HMAC signature and handles installation lifecycle (bind/unbind/suspend a codna org to a
GitHub App installation). It does NOT turn events into fix-PR jobs — that pipeline
(``github_event_service.py``) was retired: the actual, live codna-ai App webhook traffic
is handled by codna's own separate, self-hosted-style service (see the `codna` repo's
``cli/codna/webhook.py`` / ``webhook_worker.py``), which never calls into this backend.
This router still owns the install/OAuth callback (2E) and installation-token minting
used elsewhere, and remains the source of truth for ``GithubAppInstallation`` rows.

The whole surface is inert until ``GITHUB_APP_*`` is configured.
"""
from __future__ import annotations

import hmac
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from apps.api_server.config import get_settings
from apps.api_server.db.session import AsyncSessionDep
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.models.api_key import APIKey
from apps.api_server.models.github_app_installation import GithubAppInstallation
from apps.api_server.services import github_app_auth
from apps.api_server.services.auth_service import AuthContext, generate_api_key
from apps.api_server.services.github_app_auth import app_configured
from apps.api_server.services.github_app_provisioning import (
    provision_or_lookup_org_for_installation,
)
from apps.api_server.services.webhook_service import verify_webhook_signature

# How long a minted engine-key credential is valid for. One codna-webhook job attempt (default
# CODNA_WEBHOOK_JOB_TIMEOUT_S=3600) needs to fit inside this with margin — resolve_engine_key is
# called fresh per attempt, so this does not need to cover all retries cumulatively.
_ENGINE_KEY_TTL = timedelta(hours=2)

# Roles allowed to bind an external code-modifying integration to the org.
_INSTALL_ADMIN_ROLES = frozenset({"owner", "admin"})

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["GitHub App"])


def _redis(request: Request) -> Any | None:
    return getattr(request.app.state, "redis", None)


def _installation_id(payload: dict[str, Any]) -> int | None:
    inst = payload.get("installation") or {}
    iid = inst.get("id")
    return int(iid) if iid is not None else None


@router.post("/webhooks/github", summary="GitHub App webhook receiver")
async def github_webhook(
    request: Request,
    db: AsyncSessionDep,
    x_github_event: Annotated[str | None, Header()] = None,
    x_hub_signature_256: Annotated[str | None, Header()] = None,
    x_github_delivery: Annotated[str | None, Header()] = None,
) -> JSONResponse:
    settings = get_settings()
    if not app_configured() or not settings.github_app_webhook_secret:
        raise HTTPException(status_code=404, detail="github app not configured")

    body = await request.body()
    if not verify_webhook_signature(body, x_hub_signature_256 or "", settings.github_app_webhook_secret):
        raise HTTPException(status_code=401, detail="invalid signature")

    import json

    try:
        payload = json.loads(body or b"{}")
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid json") from None
    event = x_github_event or ""

    iid = _installation_id(payload)
    if iid is None:
        return JSONResponse(status_code=202, content={"status": "ignored", "reason": "no installation"})

    row = (
        await db.execute(
            select(GithubAppInstallation).where(GithubAppInstallation.installation_id == iid)
        )
    ).scalar_one_or_none()

    # installation lifecycle. org_id is taken ONLY from the trusted installation row, never the
    # payload. `deleted` removes the binding (a real uninstall) so the installation can later be
    # bound to a different org; `suspend`/`unsuspend` toggle the flag.
    if event == "installation":
        action = payload.get("action")
        if row is not None and action == "deleted":
            await db.delete(row)
            await db.commit()
        elif row is not None and action == "suspend":
            row.suspended = True
            await db.commit()
        elif row is not None and action == "unsuspend":
            row.suspended = False
            await db.commit()
        elif row is None and action in ("created", "new_permissions_accepted", "unsuspend"):
            # INSTALL-FIRST: a fresh install with no codna org behind it (the user came from the
            # GitHub Marketplace, not a codna dashboard). Mint an org on the fly from the trusted
            # App-JWT-resolved account (NOT the attacker-controllable payload) and bind it. Runs
            # BEFORE the "unknown installation" drop so the funnel works with zero prior signup.
            account = await github_app_auth.resolve_installation_account(iid)
            if account is None:
                return JSONResponse(
                    status_code=202,
                    content={"status": "ignored", "reason": "account unresolved"},
                )
            org = await provision_or_lookup_org_for_installation(
                db,
                account_id=account["id"],
                account_login=account["login"],
                account_type=account["type"],
            )
            db.add(
                GithubAppInstallation(
                    org_id=org.id,
                    installation_id=iid,
                    account_login=account["login"],
                    account_type=account["type"],
                )
            )
            try:
                await db.commit()
            except IntegrityError:
                # A concurrent delivery for the same installation already bound it; ack as ok.
                await db.rollback()
            return JSONResponse(
                status_code=202, content={"status": "ok", "action": action, "provisioned": True}
            )
        return JSONResponse(status_code=202, content={"status": "ok", "action": action})

    if row is None or row.suspended:
        return JSONResponse(status_code=202, content={"status": "ignored", "reason": "unknown installation"})

    # Every other event (check_suite, issues, pull_request_review, ...) is acked and ignored —
    # this backend no longer turns events into fix-PR jobs (see the module docstring).
    return JSONResponse(status_code=202, content={"status": "ignored", "event": event})


@router.get("/internal/codna-webhook/engine-key", include_in_schema=False)
async def codna_webhook_engine_key(
    db: AsyncSessionDep,
    installation_id: int,
    authorization: Annotated[str | None, Header()] = None,
) -> JSONResponse:
    """Service-to-service only: codna-webhook calls this, live, every time it needs to run a
    fix on behalf of a linked installation. There is deliberately no static installation_id ->
    credential store anywhere (no Fly volume, no synced file) — decision-engine is the one
    place that actually knows an installation's org/entitlement, so it answers live instead of
    something else trying to keep a copy in sync. Never exposed to a customer-facing auth
    context: gated on a shared secret, not an org API key or session.

    Mints a FRESH short-lived service credential per call rather than returning a stored raw
    key — APIKey only ever persists a hash (see models/api_key.py), so a previously-minted raw
    value (e.g. the "GitHub App" key created at provisioning time) can never be recovered
    later anyway. A fresh short-lived key per call is also strictly safer to hand across a
    network boundary than a long-lived one.
    """
    settings = get_settings()
    secret = settings.codna_webhook_internal_secret
    if not secret:
        raise HTTPException(status_code=404, detail="not configured")
    if not authorization or not hmac.compare_digest(authorization, f"Bearer {secret}"):
        raise HTTPException(status_code=401, detail="unauthorized")

    row = (
        await db.execute(
            select(GithubAppInstallation).where(
                GithubAppInstallation.installation_id == installation_id
            )
        )
    ).scalar_one_or_none()
    if row is None or row.suspended:
        raise HTTPException(status_code=404, detail="installation not linked")

    raw_key, key_prefix, hashed_key = generate_api_key()
    expires_at = datetime.now(UTC) + _ENGINE_KEY_TTL
    db.add(
        APIKey(
            org_id=row.org_id,
            user_id=None,
            label="codna-webhook (short-lived)",
            key_prefix=key_prefix,
            hashed_key=hashed_key,
            is_service=True,
            expires_at=expires_at,
        )
    )
    await db.commit()
    return JSONResponse(
        status_code=200,
        content={
            "engine_key": raw_key,
            "org_id": str(row.org_id),
            "expires_at": expires_at.isoformat(),
        },
    )


# ── Install / OAuth ──────────────────────────────────────────────────────────
@router.get("/github/app/install/start", summary="Begin a GitHub App install for this org")
async def github_install_start(
    request: Request,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> RedirectResponse:
    settings = get_settings()
    if not app_configured() or not settings.github_app_slug:
        raise HTTPException(status_code=404, detail="github app not configured")
    # Binding an external code-modifying integration is an admin action — org membership
    # (any valid key) is not enough.
    if auth.get("role") not in _INSTALL_ADMIN_ROLES:
        raise HTTPException(
            status_code=403, detail="only an org owner or admin can connect GitHub"
        )
    import secrets

    state = secrets.token_urlsafe(24)
    redis = _redis(request)
    if redis:
        await redis.set(f"github_app:install_state:{state}", str(auth["org_id"]), ex=900)
    return RedirectResponse(
        url=f"https://github.com/apps/{settings.github_app_slug}/installations/new?state={state}"
    )


@router.get("/github/app/install/callback", summary="GitHub App post-install callback")
async def github_install_callback(
    request: Request,
    db: AsyncSessionDep,
    installation_id: int,
    code: str | None = None,
    state: str | None = None,
    setup_action: str | None = None,
) -> RedirectResponse:
    if not app_configured():
        raise HTTPException(status_code=404, detail="github app not configured")
    # 1) The codna side: when present, the `state` nonce identifies which org started this install
    #    (the dashboard-first flow). Consumed single-use so it can't be replayed. ABSENT state =
    #    INSTALL-FIRST (the user installed straight from the GitHub Marketplace): we mint/look up
    #    the org from the App-JWT-verified account instead. Either way the GitHub-side ownership
    #    check below still gates the bind.
    redis = _redis(request)
    org_id: str | None = None
    if state and redis:
        key = f"github_app:install_state:{state}"
        raw = await redis.get(key)
        org_id = raw.decode() if isinstance(raw, bytes) else raw
        try:
            await redis.delete(key)
        except Exception:  # noqa: BLE001 — single-use is best-effort; ownership check still gates
            pass
    if state and not org_id:
        # A state nonce was supplied but is unknown/expired — do not silently fall through to the
        # install-first path (that would let a stale-state retry bind to a different org).
        raise HTTPException(
            status_code=400,
            detail="missing or expired install state — start the install from your codna dashboard",
        )

    # 2) The GitHub side: `installation_id` is an attacker-controllable query param. Verify the
    #    user who completed the OAuth install actually administers THIS installation before binding,
    #    else an attacker could bind a victim's (enumerable) installation id to their own org. On
    #    success this returns the trusted App-JWT-resolved account (used to provision install-first
    #    when there's no codna state nonce).
    account = await github_app_auth.verify_user_administers_installation(
        installation_id, code or "", org_id=org_id if org_id else None
    )
    if not account:
        raise HTTPException(
            status_code=403,
            detail="could not verify you administer this GitHub installation",
        )

    if org_id:
        # Dashboard-first: the org is the one that started the install.
        try:
            org_uuid = uuid.UUID(org_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid install state") from exc
    else:
        # Install-first: mint/look up the org from the verified account (commit deferred to below).
        org = await provision_or_lookup_org_for_installation(
            db,
            account_id=account["id"],
            account_login=account["login"],
            account_type=account["type"],
        )
        org_uuid = org.id

    async def _existing() -> GithubAppInstallation | None:
        return (
            await db.execute(
                select(GithubAppInstallation).where(
                    GithubAppInstallation.installation_id == installation_id
                )
            )
        ).scalar_one_or_none()

    row = await _existing()
    # Never silently re-home an installation already linked to a different org. (To move it,
    # uninstall the app from the first org — `installation.deleted` clears the binding.)
    if row is not None and row.org_id != org_uuid:
        raise HTTPException(
            status_code=409,
            detail=(
                "this GitHub installation is already linked to another codna org; "
                "uninstall the app there first"
            ),
        )
    if row is None:
        db.add(
            GithubAppInstallation(
                org_id=org_uuid,
                installation_id=installation_id,
                account_login=account["login"],
                account_type=account["type"],
            )
        )
        try:
            await db.commit()
        except IntegrityError:
            # A concurrent verified callback won the first-bind race; resolve to its outcome.
            await db.rollback()
            row = await _existing()
            if row is None or row.org_id != org_uuid:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "this GitHub installation is already linked to another codna org; "
                        "uninstall the app there first"
                    ),
                ) from None
    else:
        row.suspended = False
        await db.commit()
    # installation_id is a FastAPI-coerced int (see the handler signature). Re-cast it so the
    # redirect target is provably a constant, local relative path with an integer query value —
    # there is no attacker-controllable host/scheme/path here (closes the CodeQL py/url-redirection
    # finding, which doesn't model the int coercion as a sanitizer).
    return RedirectResponse(
        url=f"/github/app/setup?installation_id={int(installation_id)}"
    )


@router.get("/github/app/setup", summary="GitHub App post-install success page")
async def github_app_setup(installation_id: int) -> HTMLResponse:
    """Dependency-free post-install landing page.

    Confirms codna is installed and a free trial is active. ``installation_id`` is int-cast by
    FastAPI's path/query coercion AND re-int-cast into the markup below, so nothing user-supplied
    is interpolated as raw HTML (no XSS surface). Deliberately NO BYOK key form: a freshly
    install-first-provisioned org has no human admin credential yet, so collecting a provider key
    here is a separate follow-up — for now we just say they'll be asked when the trial runs out."""
    iid = int(installation_id)
    html = (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>codna installed</title></head>"
        "<body style=\"font-family:system-ui,sans-serif;max-width:34rem;margin:4rem auto;"
        "padding:0 1rem;line-height:1.5\">"
        "<h1>codna is installed</h1>"
        "<p>Your GitHub App installation "
        f"(<code>#{iid}</code>) is connected and a <strong>free trial is active</strong>.</p>"
        "<p>codna will start fixing failing CI checks and labeled issues automatically — "
        "there is nothing else to set up right now.</p>"
        "<p>When your free trial is used up, we&rsquo;ll ask you to add your own Anthropic API "
        "key so codna can keep running on your account.</p>"
        "</body></html>"
    )
    return HTMLResponse(content=html)
