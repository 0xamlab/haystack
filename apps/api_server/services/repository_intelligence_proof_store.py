"""B9: mirror an agent run's proof bundle to the durable object store for cross-replica recovery.

The proof artifacts (runtime_manifest / messages / usage / tool_calls / approvals / gate / events)
are written by the TS sidecar to its node-local disk and exposed read-only at ``GET /proofs/<run_id>``
(already secret-redacted at write time). This fetches that bundle through the egress-guarded sidecar
client and mirrors each artifact through the object-store abstraction under ``kind="proofs"``, so a
run's evidence survives the loss of the node that produced it and is recoverable from any replica.

BEST-EFFORT by design: proof archival must NEVER fail an otherwise-successful agent run, so every
fetch/mirror error is logged and swallowed. s3 mode only (a no-op in local mode — the proofs already
live on the local disk). ``put_json`` re-applies credential-field redaction defense-in-depth.
"""

from __future__ import annotations

import json
import os
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_AGENT_CORE_URL_ENV = "ALGENTA_AGENT_CORE_URL"


def _proof_artifact_key(org_id: str, repository_id: str, agent_run_id: str, name: str) -> str:
    from apps.api_server.services.repository_intelligence_object_store import artifact_key

    # artifact_key segments forbid '/', so group a run's proofs with a ':' separator (allowed, and
    # still prefix-listable as proofs/<run_id>:). agent_run_id + name are both already path-safe.
    return artifact_key(
        org_id=org_id,
        repository_id=repository_id,
        kind="proofs",
        artifact_id=f"{agent_run_id}:{name}",
    )


async def _fetch_proof_bundle(agent_run_id: str) -> dict[str, Any] | None:
    from apps.api_server.services.egress_guard import async_http_request

    base_url = os.environ.get(_AGENT_CORE_URL_ENV)
    if not base_url:
        return None
    url = base_url.rstrip("/") + f"/proofs/{agent_run_id}"
    headers: dict[str, str] = {}
    token = os.environ.get("ALGENTA_AGENT_CORE_TOKEN") or os.environ.get("AGENT_CORE_AUTH_TOKEN")
    if token:
        headers["authorization"] = f"Bearer {token}"
    response = await async_http_request(
        method="GET",
        url=url,
        surface="repository_proof_mirror",
        explicit_configured=True,
        egress_class="operator_service",
        headers=headers,
        timeout=30.0,
    )
    if getattr(response, "status_code", 200) >= 400:
        return None  # 404 = proofs not on this node / not generated; nothing to mirror
    return json.loads(response.text)


async def mirror_proof_artifacts(
    *, org_id: str, repository_id: str, agent_run_id: str | None
) -> int:
    """Mirror a run's proof bundle to the durable object store. Returns the number of artifacts
    mirrored (0 when disabled / no run / unavailable). NEVER raises — proof archival is best-effort."""
    from apps.api_server.services.repository_intelligence_object_store import (
        get_object_store,
        object_store_mode,
    )

    if not agent_run_id or object_store_mode() != "s3":
        return 0
    try:
        bundle = await _fetch_proof_bundle(agent_run_id)
    except Exception as exc:  # noqa: BLE001 — best-effort; never fail the run
        logger.warning("ri_proof_mirror_fetch_degraded", agent_run_id=agent_run_id, error=str(exc))
        return 0
    artifacts = (bundle or {}).get("artifacts") or {}
    if not isinstance(artifacts, dict) or not artifacts:
        return 0
    store = get_object_store()
    mirrored = 0
    for name, content in artifacts.items():
        try:
            key = _proof_artifact_key(org_id, repository_id, agent_run_id, str(name))
            if isinstance(content, dict):
                store.put_json(key, content)  # redacts credential-shaped fields
            else:
                # events.ndjson decodes to a list; persist it as a JSON document
                store.put_bytes(
                    key, json.dumps(content).encode("utf-8"), content_type="application/json"
                )
            mirrored += 1
        except Exception as exc:  # noqa: BLE001 — skip a bad artifact, keep mirroring the rest
            logger.warning(
                "ri_proof_mirror_put_degraded", artifact=str(name), agent_run_id=agent_run_id,
                error=str(exc),
            )
    logger.info("ri_proof_mirror_complete", agent_run_id=agent_run_id, mirrored=mirrored)
    return mirrored
