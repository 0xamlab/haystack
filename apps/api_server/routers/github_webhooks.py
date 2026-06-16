"""GitHub App — inbound webhook receiver + install/OAuth callback.

`POST /webhooks/github` is the one public, unauthenticated route: it verifies the
GitHub HMAC signature, maps the installation to a codna org, dedupes by delivery id,
then *enqueues* a job and returns 202 immediately (GitHub times out at ~10s). The
multi-minute fix→PR pipeline runs in the worker (see the GITHUB_EVENT_* handlers).

The whole surface is inert until ``GITHUB_APP_*`` is configured.
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from apps.api_server.config import get_settings
from apps.api_server.db.session import AsyncSessionDep, AsyncSessionLocal
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.models.github_app_installation import (
    GithubAppInstallation,
    GithubWebhookDelivery,
)
from apps.api_server.models.job import JobKind
from apps.api_server.services import github_app_auth
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.github_app_auth import app_configured
from apps.api_server.services.github_app_provisioning import (
    provision_or_lookup_org_for_installation,
)
from apps.api_server.services.job_service import create_job
from apps.api_server.services.webhook_service import verify_webhook_signature

# Roles allowed to bind an external code-modifying integration to the org.
_INSTALL_ADMIN_ROLES = frozenset({"owner", "admin"})

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["GitHub App"])

# Label that opts an issue into an automated fix.
_FIX_LABEL = "codna-fix"
# check_suite conclusions that represent an actionable CI failure (not success/neutral/
# cancelled/skipped/stale, which we do not act on).
_FAILING_CONCLUSIONS = frozenset({"failure", "timed_out", "startup_failure", "action_required"})


def _redis(request: Request) -> Any | None:
    return getattr(request.app.state, "redis", None)


async def _claim_delivery(
    db: Any, delivery_id: str, installation_id: int | None
) -> tuple[bool, uuid.UUID | None]:
    """Durably claim a webhook delivery (first writer wins).

    Returns ``(claimed, existing_job_id)``: ``(True, None)`` on a fresh claim, or
    ``(False, job_id|None)`` if the delivery was already claimed (job_id of the job it
    produced, for re-delivery recovery). Postgres INSERT ... ON CONFLICT DO NOTHING on the
    unique delivery_id survives a Redis outage + the multi-replica race, so one delivery can
    never spawn two billed fix-PR jobs. Flushed (not committed) so it shares the route's
    transaction — a failed job creation rolls the claim back and GitHub re-delivery re-claims."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    stmt = (
        pg_insert(GithubWebhookDelivery)
        .values(id=uuid.uuid4(), delivery_id=delivery_id, installation_id=installation_id)
        .on_conflict_do_nothing(index_elements=["delivery_id"])
    )
    result = await db.execute(stmt)
    await db.flush()
    if (result.rowcount or 0) == 1:
        return True, None
    existing = (
        await db.execute(
            select(GithubWebhookDelivery).where(
                GithubWebhookDelivery.delivery_id == delivery_id
            )
        )
    ).scalar_one_or_none()
    return False, (existing.job_id if existing is not None else None)


def _classify(event: str, payload: dict[str, Any]) -> JobKind | None:
    """Map a GitHub event to an actionable job kind (or None to ack + ignore).

    Acts on ``check_suite`` (one per CI app per commit) and deliberately IGNORES per-check
    ``check_run`` failures: a single failing CI run emits one check_suite plus N check_run
    events, each with its own delivery id, so acting on check_run would fan one logical
    failure out into N duplicate fix PRs + N billed plans. (Multiple CI apps on one commit
    still produce one check_suite each — acceptable over-firing, not the N-per-suite fan-out.)"""
    action = payload.get("action")
    if event == "check_suite":
        node = payload.get("check_suite") or {}
        if action == "completed" and node.get("conclusion") in _FAILING_CONCLUSIONS:
            return JobKind.GITHUB_EVENT_CHECK
    elif event == "issues" and action == "labeled":
        if (payload.get("label") or {}).get("name") == _FIX_LABEL:
            return JobKind.GITHUB_EVENT_ISSUE
    elif event == "pull_request_review" and action == "submitted":
        return JobKind.GITHUB_EVENT_PR_REVIEW
    return None


def _installation_id(payload: dict[str, Any]) -> int | None:
    inst = payload.get("installation") or {}
    iid = inst.get("id")
    return int(iid) if iid is not None else None


async def _enqueue(job_id: uuid.UUID) -> None:
    enqueued = False
    try:
        from apps.worker.tasks.repository_task import enqueue_repository_job

        enqueued = enqueue_repository_job(str(job_id))
    except Exception as exc:  # noqa: BLE001 — degrade to in-process on broker issues
        logger.warning("github_job_enqueue_failed", job_id=str(job_id), error=str(exc))
    if not enqueued:
        import asyncio

        async def _run() -> None:
            from apps.api_server.services.repository_job_service import execute_job_by_kind

            async with AsyncSessionLocal() as db:
                try:
                    await execute_job_by_kind(job_id=job_id, db=db)
                except Exception as exc:  # noqa: BLE001 — status persisted on the job
                    logger.error("github_job_in_process_failed", job_id=str(job_id), error=str(exc))

        asyncio.create_task(_run())


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

    # idempotency, layer 1: Redis read-through fast-path. A hit is a delivery we already
    # *durably processed* (the key is SET only after commit+enqueue below), so it can short-
    # circuit cheaply. A miss falls through to the authoritative DB claim — Redis never gates
    # a delivery it hasn't confirmed, so it can't poison recovery on a rolled-back transaction.
    redis = _redis(request)
    if redis and x_github_delivery:
        try:
            if await redis.get(f"gh_delivery:{x_github_delivery}"):
                return JSONResponse(status_code=202, content={"status": "duplicate"})
        except Exception:  # noqa: BLE001 — Redis is a cache; the DB claim below is authoritative
            pass

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

    kind = _classify(event, payload)
    if kind is None:
        return JSONResponse(status_code=202, content={"status": "ignored", "event": event})

    # idempotency, layer 2: durable first-writer-wins claim (authoritative). Survives a Redis
    # outage + the multi-replica race; claimed in the SAME transaction as the job.
    org_id = row.org_id
    if x_github_delivery:
        claimed, existing_job_id = await _claim_delivery(db, x_github_delivery, iid)
        if not claimed:
            # A prior delivery already created the job. Re-enqueue it (idempotent — the worker's
            # re-entry guard makes a still-running/terminal job a no-op) so a job that was
            # committed but never enqueued (a crash in the commit->enqueue gap) still recovers.
            if existing_job_id is not None:
                await _enqueue(existing_job_id)
                return JSONResponse(
                    status_code=202,
                    content={"status": "requeued", "job_id": str(existing_job_id)},
                )
            return JSONResponse(status_code=202, content={"status": "duplicate"})

    job = await create_job(
        None,
        org_id,
        db,
        queue_name="repository",
        job_kind=kind,
        request_payload={
            "installation_id": iid,
            "org_id": str(org_id),
            "event": event,
            "delivery_id": x_github_delivery,
            "payload": payload,
        },
    )
    # Link the delivery to its job so a re-delivery can recover an un-enqueued job (above).
    if x_github_delivery:
        await db.execute(
            update(GithubWebhookDelivery)
            .where(GithubWebhookDelivery.delivery_id == x_github_delivery)
            .values(job_id=job.id)
        )
    await db.commit()
    await _enqueue(job.id)
    # Populate the Redis fast-path ONLY after the job is durably committed AND enqueued, so the
    # key marks a fully-processed delivery and never blocks recovery of a half-done one.
    if redis and x_github_delivery:
        try:
            await redis.set(f"gh_delivery:{x_github_delivery}", "1", ex=86400)
        except Exception:  # noqa: BLE001 — best-effort cache priming
            pass
    return JSONResponse(
        status_code=202,
        content={"status": "queued", "job_id": str(job.id), "job_kind": kind.value},
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
    return RedirectResponse(
        url=f"/github/app/setup?installation_id={installation_id}"
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
