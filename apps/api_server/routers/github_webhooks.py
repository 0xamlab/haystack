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
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from apps.api_server.config import get_settings
from apps.api_server.db.session import AsyncSessionDep
from apps.api_server.models.api_key import APIKey
from apps.api_server.models.github_app_installation import GithubAppInstallation
from apps.api_server.models.organization import Organization
from apps.api_server.models.user import User, UserRole
from apps.api_server.services import github_app_auth, tenant_key_store, website_identity
from apps.api_server.services.auth_service import generate_api_key
from apps.api_server.services.github_app_auth import app_configured
from apps.api_server.services.github_app_provisioning import (
    provision_or_lookup_org_for_installation,
)
from apps.api_server.services.webhook_service import verify_webhook_signature

# How long a minted engine-key credential is valid for. One codna-webhook job attempt (default
# CODNA_WEBHOOK_JOB_TIMEOUT_S=3600) needs to fit inside this with margin — resolve_engine_key is
# called fresh per attempt, so this does not need to cover all retries cumulatively.
_ENGINE_KEY_TTL = timedelta(hours=2)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["GitHub App"])


def _redis(request: Request) -> Any | None:
    return getattr(request.app.state, "redis", None)


def _installation_id(payload: dict[str, Any]) -> int | None:
    inst = payload.get("installation") or {}
    iid = inst.get("id")
    return int(iid) if iid is not None else None


@router.post("/webhooks/github", summary="GitHub App webhook receiver", include_in_schema=False)
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

    SELF-PROVISIONS on first call for an unknown installation. The webhook's own install-first
    path (``installation: created``, above) can never reach this org's binding for any real
    installer: a GitHub App has exactly one configured webhook URL, and codna-ai's points at
    codna-webhook, not here — so that path has never fired for anyone, including thyn-ai's own
    install. Rather than leave every fresh external install permanently unlinked (the same
    "please link your account" wall forever, for zero-config installs that were never supposed
    to need one), mirror that install-first logic here: resolve the installing account via the
    App JWT (not the caller-supplied installation_id's trust — GitHub's own API is the source of
    truth for which account a given installation_id belongs to) and provision/lookup its org.
    Explicit suspension (``row.suspended``) still 404s — that is a real "not allowed" state,
    not "not yet known".
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
    if row is not None and row.suspended:
        raise HTTPException(status_code=404, detail="installation not linked")

    if row is None:
        account = await github_app_auth.resolve_installation_account(installation_id)
        if account is None:
            raise HTTPException(status_code=404, detail="installation not linked")
        org = await provision_or_lookup_org_for_installation(
            db,
            account_id=account["id"],
            account_login=account["login"],
            account_type=account["type"],
        )
        row = GithubAppInstallation(
            org_id=org.id,
            installation_id=installation_id,
            account_login=account["login"],
            account_type=account["type"],
        )
        db.add(row)
        try:
            await db.commit()
        except IntegrityError:
            # A concurrent call (or a webhook delivery landing at the same moment) already
            # bound this installation; resolve to whichever row won.
            await db.rollback()
            row = (
                await db.execute(
                    select(GithubAppInstallation).where(
                        GithubAppInstallation.installation_id == installation_id
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                raise HTTPException(status_code=404, detail="installation not linked") from None
        logger.info(
            "codna_webhook_engine_key_self_provisioned",
            installation_id=installation_id,
            org_id=str(row.org_id),
        )

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

    provider, provider_key = None, None
    try:
        org_keys = await tenant_key_store.resolve_org_keys(row.org_id)
        provider, provider_key = _first_configured_provider(org_keys.provider_keys)
    except Exception:  # noqa: BLE001 — a BYOK-lookup hiccup must never break the engine-key mint
        # above (the fix can still run house-metered); the caller falls back to its own defaults.
        logger.warning("codna_webhook_engine_key_byok_lookup_failed", org_id=str(row.org_id))

    # Fail-open on lookup issues — this is a convenience kill switch, not a security boundary.
    fix_enabled = True
    try:
        org_row = (
            await db.execute(select(Organization).where(Organization.id == row.org_id))
        ).scalar_one_or_none()
        if org_row is not None:
            fix_enabled = bool(org_row.codna_fix_enabled)
    except Exception:  # noqa: BLE001 — same fail-open contract as the BYOK lookup above
        logger.warning("codna_webhook_engine_key_fix_enabled_lookup_failed", org_id=str(row.org_id))

    return JSONResponse(
        status_code=200,
        content={
            "engine_key": raw_key,
            "org_id": str(row.org_id),
            "expires_at": expires_at.isoformat(),
            "provider": provider,
            "provider_key": provider_key,
            "fix_enabled": fix_enabled,
        },
    )


# Priority order when an org has configured more than one BYOK backend — first match wins.
# Maps decision-engine's internal backend id (apps/api_server/services/llm_provider_service)
# to codna's own provider name (cli/codna/keystore.py's PROVIDER_TO_ENV) — the two repos name
# Google's backend differently ("google_genai" vs "google").
_BACKEND_TO_CODNA_PROVIDER = {
    "anthropic": "anthropic",
    "openai": "openai",
    "google_genai": "google",
}


def _first_configured_provider(provider_keys: dict[str, str]) -> tuple[str | None, str | None]:
    """Return (codna_provider_name, raw_key) for the first BYOK backend an org has configured,
    in a fixed, deterministic priority order — or (None, None) if none are set."""
    for backend, codna_provider in _BACKEND_TO_CODNA_PROVIDER.items():
        key = provider_keys.get(backend)
        if key:
            return codna_provider, key
    return None, None


# ── Install / OAuth ──────────────────────────────────────────────────────────
@router.get(
    "/github/app/install/start",
    summary="Begin a GitHub App install for this org",
    include_in_schema=False,
)
async def github_install_start(
    request: Request,
    db: AsyncSessionDep,
    authorization: Annotated[str | None, Header()] = None,
    x_org_id: Annotated[str | None, Header()] = None,
) -> RedirectResponse:
    """Dashboard-first install kickoff — Supabase-authenticated (companion to /account/team,
    /account/devices), NOT an API key. The site calls this with the caller's Supabase
    access_token (a browser session, never a codna API key), so it must resolve org the same
    way every other website surface does (``website_identity``) rather than via
    ``get_current_org`` — that call always 401'd here before this fix, silently dropping every
    "Connect GitHub" click to the stateless install-first fallback (state never set), which then
    binds the installation to an org keyed off the GitHub org account itself instead of the
    clicking user's own org. That is how an installation could end up bound to a DIFFERENT org
    than the one the user's BYOK key lives in, with no error surfaced anywhere."""
    settings = get_settings()
    if not app_configured() or not settings.github_app_slug:
        raise HTTPException(status_code=404, detail="github app not configured")
    redis = _redis(request)
    org, identity = await website_identity.verify_and_resolve_org(
        authorization, db, redis, selected_org_id=website_identity.parse_org_id(x_org_id)
    )
    # Binding an external code-modifying integration is an admin action — org membership
    # (any valid key) is not enough. A caller with no Users row in this org got here via a
    # GitHub-install admin resolution (the only row-less path), which already proves admin.
    email = (identity.get("email") or "").strip().lower()
    if email:
        member = (
            await db.execute(
                select(User).where(User.org_id == org.id, func.lower(User.email) == email)
            )
        ).scalar_one_or_none()
        if member is not None and member.role not in (UserRole.OWNER, UserRole.ADMIN):
            raise HTTPException(
                status_code=403, detail="only an org owner or admin can connect GitHub"
            )

    import secrets

    state = secrets.token_urlsafe(24)
    if redis:
        await redis.set(f"github_app:install_state:{state}", str(org.id), ex=900)
    return RedirectResponse(
        url=f"https://github.com/apps/{settings.github_app_slug}/installations/new?state={state}"
    )


@router.get(
    "/github/app/install/callback",
    summary="GitHub App post-install callback",
    include_in_schema=False,
)
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
    # Never silently re-home an installation a human has actually claimed. (To move THAT one,
    # uninstall the app from the first org — `installation.deleted` clears the binding.)
    #
    # EXCEPTION: the install-first self-provisioning path (above, and the engine-key bridge's own
    # copy of it) mints an org with zero Users the instant codna-webhook first sees an unknown
    # installation — often before anyone has ever visited the dashboard. That org is provably
    # unclaimed (nothing but an api_key row points at it), so a verified admin completing THIS
    # OAuth flow may claim it outright instead of being told to uninstall/reinstall the App just
    # to correct a binding nobody chose.
    if row is not None and row.org_id != org_uuid:
        user_count = (
            await db.execute(select(func.count()).select_from(User).where(User.org_id == row.org_id))
        ).scalar_one_or_none()
        if user_count:
            raise HTTPException(
                status_code=409,
                detail=(
                    "this GitHub installation is already linked to another codna org; "
                    "uninstall the app there first"
                ),
            )
        logger.info(
            "codna_github_install_reclaimed_unclaimed_org",
            installation_id=installation_id,
            previous_org_id=str(row.org_id),
            claimed_org_id=str(org_uuid),
        )
        row.org_id = org_uuid
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


@router.get(
    "/github/app/setup",
    summary="GitHub App post-install success page",
    include_in_schema=False,
)
async def github_app_setup(installation_id: int) -> HTMLResponse:
    """Dependency-free post-install landing page.

    ``installation_id`` is int-cast by FastAPI's path/query coercion AND re-int-cast into the markup
    below, so nothing user-supplied is interpolated as raw HTML (no XSS surface). Deliberately NO
    BYOK key form: a freshly install-first-provisioned org has no human admin credential yet, so
    the key is collected on the account page (linked below) rather than here.

    The copy is deliberately specific, because a vaguer earlier version was wrong three ways:
    it promised codna fixes "failing CI checks" (it deliberately does NOT react to a failing
    check_suite on its own -- see codna's webhook.py), it named Anthropic as though it were the only
    provider (three are supported), and it dead-ended the user with no link back to the portal that
    owns every remaining setting."""
    iid = int(installation_id)
    accounts = get_settings().accounts_base_url.rstrip("/")
    # Brand-scoped so the portal opens on the codna lens (?app=) rather than the default brand.
    account_url = f"{accounts}/account?app=codna"
    html = (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>codna installed</title></head>"
        "<body style=\"font-family:system-ui,sans-serif;max-width:34rem;margin:4rem auto;"
        "padding:0 1rem;line-height:1.5\">"
        "<h1>codna is installed</h1>"
        "<p>Your GitHub App installation "
        f"(<code>#{iid}</code>) is connected and a <strong>free trial is active</strong>.</p>"
        "<p>codna gets to work on its own from here. It reviews new pull requests, fixes issues you "
        "label <code>codna-fix</code>, and responds when you comment "
        "<code>@codna fix</code> or <code>@codna review</code>.</p>"
        "<p>When your free trial is used up, add your own model key to keep codna running &mdash; "
        "your choice of <strong>Anthropic (Claude)</strong>, <strong>OpenAI</strong> or "
        "<strong>Google Gemini</strong>.</p>"
        f"<p style=\"margin-top:2rem\"><a href=\"{account_url}\" "
        "style=\"display:inline-block;background:#111;color:#fff;text-decoration:none;"
        "padding:10px 18px;border-radius:8px;font-weight:600\">Back to your account</a></p>"
        "<p style=\"color:#555;font-size:14px\">Manage your model key, choose which repositories "
        "codna can see, and turn automatic fixes on or off there at any time.</p>"
        "</body></html>"
    )
    return HTMLResponse(content=html)
