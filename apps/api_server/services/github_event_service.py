"""GitHub App event handlers — turn a webhook event into a fix PR (or a comment).

Runs in the worker / in-process fallback, off the webhook request path. For an
actionable event (CI failure, an issue labelled ``codna-fix``) it:

  1. mints a short-lived installation token (``github_app_auth``),
  2. builds an *ephemeral* ``github_repo`` connector carrying that token,
  3. runs the existing snapshot->triage->plan->simulate pipeline, then
  4. ``apply_repository_decision(mode="remote_pr")`` to open the PR, and
  5. posts the PR link back to GitHub (best-effort, egress-guarded).

Nothing here is new pipeline logic — it reuses the exact service functions the
public repository endpoints call. The connector is never persisted: the token is
short-lived and least-privilege, and the artifacts are keyed by (org, repo id) for
the lifetime of the job only.

Idempotent on re-delivery: a terminal job returns its stored result instead of
re-running (and re-billing) the agent — the same guard ``execute_repository_job`` uses.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.models.data_connector import ConnectorType, DataConnector
from apps.api_server.models.github_app_installation import GithubAppInstallation
from apps.api_server.models.job import Job, JobKind, JobStatus, is_terminal
from apps.api_server.services import egress_guard, github_app_auth
from apps.api_server.services.config_crypto import encrypt_config_json
from apps.api_server.services.egress_guard import EgressAuditContext

logger = structlog.get_logger(__name__)

_GITHUB_API = "https://api.github.com"
_FIX_LABEL = "codna-fix"
# A job stuck in RUNNING longer than this is treated as a crashed prior run and reclaimed.
# Must exceed the worst-case pipeline wall-clock so a genuinely in-flight job is never
# double-run (the fix pipeline is multi-minute; 1h is a safe ceiling).
_RUNNING_RECLAIM_AFTER_S = 3600
# A GitHub repo full name is exactly ``owner/repo`` — no scheme, host, '@', or path traversal.
_VALID_FULL_NAME = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")


def _running_is_stale(job: Any) -> bool:
    """True if a RUNNING job has exceeded the reclaim window (a crashed prior run)."""
    started = getattr(job, "started_at", None)
    if started is None:
        return True
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    return (datetime.now(UTC) - started).total_seconds() > _RUNNING_RECLAIM_AFTER_S


def _ephemeral_connector(
    *, org_id: uuid.UUID, clone_url: str, token: str, default_branch: str | None
) -> DataConnector:
    """An in-memory github_repo connector carrying the freshly-minted token.

    Not added to any session — the RI pipeline operates on the connector object +
    object store, never re-fetching it from the DB (see repository_job_service)."""
    cfg: dict[str, Any] = {"repository_url": clone_url, "access_token": token}
    if default_branch:
        cfg["default_branch"] = default_branch
    connector = DataConnector(
        org_id=org_id,
        name="github-app-event",
        connector_type=ConnectorType.GITHUB_REPO,
        config_json=encrypt_config_json(json.dumps(cfg), org_id=org_id),
    )
    # A stable id for the manifest paths used across this job's stages.
    connector.id = uuid.uuid4()
    connector.workspace_id = None
    return connector


def _signals_for(event: str, payload: dict[str, Any]) -> tuple[Any, str]:
    """Return (RepositorySignals, human label) for the actionable event."""
    from apps.api_server.schemas.repositories import RepositorySignals

    if event == "issues":
        issue = payload.get("issue") or {}
        title = str(issue.get("title") or "").strip()
        body = str(issue.get("body") or "").strip()
        text = f"{title}\n\n{body}".strip() or title or "Resolve the reported issue."
        return RepositorySignals(issue_text=text), f"issue #{issue.get('number')}"

    # check_suite failure (only check_suite is enqueued — see _classify)
    node = payload.get("check_suite") or {}
    head_branch = str(node.get("head_branch") or "").strip()
    text = "CI failed on this repository. Diagnose the failing checks and fix them."
    if head_branch:
        text += f" (branch: {head_branch})"
    return RepositorySignals(issue_text=text), "CI failure"


async def _post_github(
    *, method: str, path: str, token: str, org_id: uuid.UUID, body: dict[str, Any]
) -> None:
    """Best-effort egress-guarded POST to the GitHub API (comments / status back)."""
    try:
        await egress_guard.async_http_request(
            method=method,
            url=f"{_GITHUB_API}{path}",
            surface="github_app_comment",
            egress_class="customer_connector",
            explicit_configured=True,
            audit_context=EgressAuditContext(org_id=org_id),
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json=body,
            client_kwargs={"timeout": 30.0},
        )
    except Exception as exc:  # noqa: BLE001 — posting back is best-effort
        logger.warning("github_event_post_failed", path=path, error=str(exc))


async def _notify(
    *,
    event: str,
    payload: dict[str, Any],
    token: str,
    org_id: uuid.UUID,
    full_name: str,
    pull_request_url: str | None,
) -> None:
    if pull_request_url:
        message = f"🧬 codna opened a fix PR: {pull_request_url}"
    else:
        message = (
            "🧬 codna analysed this but didn't find a fix that passed the safety gate. "
            "No PR was opened."
        )
    if event == "issues":
        number = (payload.get("issue") or {}).get("number")
        if number is not None:
            await _post_github(
                method="POST",
                path=f"/repos/{full_name}/issues/{number}/comments",
                token=token,
                org_id=org_id,
                body={"body": message},
            )
        return
    # check_suite — comment on the head commit
    node = payload.get("check_suite") or {}
    sha = node.get("head_sha")
    if sha:
        await _post_github(
            method="POST",
            path=f"/repos/{full_name}/commits/{sha}/comments",
            token=token,
            org_id=org_id,
            body={"body": message},
        )


async def _handle_pr_review(payload: dict[str, Any], token: str, org_id: uuid.UUID) -> dict[str, Any]:
    """PR review is comment-only — nudge toward the label-driven fix flow."""
    pr = payload.get("pull_request") or {}
    number = pr.get("number")
    full_name = (payload.get("repository") or {}).get("full_name")
    if number is not None and full_name:
        await _post_github(
            method="POST",
            path=f"/repos/{full_name}/issues/{number}/comments",
            token=token,
            org_id=org_id,
            body={
                "body": (
                    "🧬 codna saw this review. Want me to take a pass at the changes? "
                    f"Open an issue and add the `{_FIX_LABEL}` label and I'll open a fix PR."
                )
            },
        )
    return {"status": "commented", "pull_request": number}


async def _drive_fix(
    *, event: str, payload: dict[str, Any], token: str, org_id: uuid.UUID, installation_id: int
) -> dict[str, Any]:
    """Snapshot -> triage -> plan -> simulate -> remote PR, then comment back."""
    from apps.api_server.schemas.repositories import (
        RepositoryApplyRequest,
        RepositoryPipelineRequest,
    )
    from apps.api_server.services.repository_intelligence import apply_repository_decision
    from apps.api_server.services.repository_intelligence_pipeline import (
        run_repository_pipeline,
    )

    repo = payload.get("repository") or {}
    full_name = str(repo.get("full_name") or "").strip()
    default_branch = repo.get("default_branch")
    if not _VALID_FULL_NAME.match(full_name) or ".." in full_name:
        raise ValueError(f"github event has invalid repository.full_name: {full_name!r}")
    # Derive the clone URL from the VALIDATED owner/repo, pinned to github.com — never trust the
    # free-form clone_url field. The egress guard only checks the host is a permitted public
    # destination, not that it is GitHub, so a payload clone_url like https://evil.example/x.git
    # would otherwise receive the freshly-minted installation token in the clone request.
    clone_url = f"https://github.com/{full_name}.git"

    signals, label = _signals_for(event, payload)
    connector = _ephemeral_connector(
        org_id=org_id, clone_url=clone_url, token=token, default_branch=default_branch
    )

    pipeline = await run_repository_pipeline(
        connector=connector,
        request=RepositoryPipelineRequest(signals=signals, stop_after="simulate"),
    )
    plan = pipeline.decision_plan
    sim = pipeline.simulation
    if plan is None or sim is None:
        # triage produced no actionable plan
        await _notify(
            event=event, payload=payload, token=token, org_id=org_id,
            full_name=full_name, pull_request_url=None,
        )
        return {"status": "no_plan", "repository": full_name, "label": label}

    simulation_id = str((sim.validated_inputs or {}).get("simulation_id") or "")
    title = f"codna: fix for {label}"
    apply_resp = await apply_repository_decision(
        connector=connector,
        request=RepositoryApplyRequest(
            snapshot_id=pipeline.snapshot_id,
            decision_plan_id=plan.decision_plan_id,
            simulation_id=simulation_id,
            mode="remote_pr",
            write_permission=True,
            base_branch=default_branch,
            pull_request_title=title,
            pull_request_body=(
                f"Automated fix opened by [codna](https://algenta.ai) for {label}.\n\n"
                "Generated from the repository decision plan + simulation; review before merging."
            ),
        ),
    )
    await _notify(
        event=event, payload=payload, token=token, org_id=org_id,
        full_name=full_name, pull_request_url=apply_resp.pull_request_url,
    )
    return {
        "status": "pr_opened" if apply_resp.pull_request_url else "applied",
        "repository": full_name,
        "label": label,
        "pull_request_url": apply_resp.pull_request_url,
        "decision_plan_id": plan.decision_plan_id,
        "simulation_id": simulation_id,
    }


async def execute_github_event_job(*, job_id: uuid.UUID, db: AsyncSession) -> dict[str, Any]:
    """Execute a GITHUB_EVENT_* job end-to-end (idempotent on a terminal job)."""
    job = (
        await db.execute(
            select(Job)
            .where(Job.id == job_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if job is None:
        raise ValueError(f"Job {job_id} not found")
    # Idempotency under the FOR UPDATE lock: a terminal job returns its stored result. A RUNNING
    # job is a concurrent worker / immediate redelivery — return without re-running so the
    # billable LLM plan + fix PR are never duplicated. BUT a job stuck RUNNING past the reclaim
    # window is a crashed prior run (worker OOM/eviction): fall through and re-execute it so the
    # event is not lost.
    if is_terminal(job.status):
        return job.result_payload or {"status": job.status.value, "job_id": str(job.id)}
    if job.status == JobStatus.RUNNING and not _running_is_stale(job):
        return {"status": job.status.value, "job_id": str(job.id)}

    payload_wrapper = job.request_payload or {}
    installation_id = int(payload_wrapper.get("installation_id") or 0)
    event = str(payload_wrapper.get("event") or "")
    gh_payload = payload_wrapper.get("payload") or {}

    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(UTC)
    await db.commit()

    # Resolve the install row (token cache backstop) + the tenant's keys for the run.
    row = (
        await db.execute(
            select(GithubAppInstallation).where(
                GithubAppInstallation.installation_id == installation_id
            )
        )
    ).scalar_one_or_none()

    from apps.api_server.services.tenant_key_store import resolve_org_keys
    from apps.api_server.services.tenant_keys import (
        reset_org_keys_override,
        set_org_keys_override,
    )

    redis = None  # worker context: token caches on the encrypted row instead
    _tenant_keys_token = set_org_keys_override(await resolve_org_keys(job.org_id))
    try:
        token = await github_app_auth.get_installation_token(
            installation_id, org_id=job.org_id, redis=redis, installation_row=row
        )
        if job.job_kind == JobKind.GITHUB_EVENT_PR_REVIEW.value:
            result = await _handle_pr_review(gh_payload, token, job.org_id)
        else:
            result = await _drive_fix(
                event=event,
                payload=gh_payload,
                token=token,
                org_id=job.org_id,
                installation_id=installation_id,
            )
    except Exception as exc:
        await db.refresh(job)
        if job.status != JobStatus.CANCELLED:
            job.status = JobStatus.FAILED
            job.error_message = str(exc)
            job.completed_at = datetime.now(UTC)
            await db.commit()
        raise
    finally:
        reset_org_keys_override(_tenant_keys_token)

    await db.refresh(job)
    job.result_payload = result
    job.status = JobStatus.COMPLETED
    job.completed_at = datetime.now(UTC)
    job.error_message = None
    await db.commit()
    return result
