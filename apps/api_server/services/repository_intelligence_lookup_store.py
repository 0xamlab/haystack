"""Cross-replica perf-dedup for the DETERMINISTIC repository-intelligence lookups.

The snapshot / triage / simulation / graph_query lookups map a request's parameters to an
already-computed result. B8 made the underlying result *manifests* durable (recoverable on any
replica by identity); this adds the request→result *lookup index* to the same durable object store
so a cold replica serves a sibling's result instead of recomputing the identical answer (a re-clone,
a re-triage, or a fresh Monte-Carlo simulation).

Because these results are DETERMINISTIC, this whole layer is **pure best-effort**:

* A shared miss *and* an object-store availability fault both return ``None`` — the caller simply
  recomputes the identical deterministic result. There is no fail-open divergence risk (unlike the
  non-deterministic ``decision_plan_lookup``, which is fail-CLOSED in
  ``repository_intelligence_decision_plan_workflow``).
* A failed mirror is logged and swallowed — the perf cache must never fail an otherwise-successful
  operation; a sibling just recomputes.

In local mode (``ALGENTA_RI_OBJECT_STORE`` unset / not ``s3``) every function is a cheap no-op, so
the single-replica behavior is byte-identical to before this module existed. The shared read is only
ever reached AFTER a node-local lookup miss, so it never sits on the warm <15ms fast path.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Only the deterministic lookup families belong here. decision_plan_lookup is intentionally absent:
# it is non-deterministic and uses fail-closed helpers in the decision-plan workflow.
_DETERMINISTIC_LOOKUP_KINDS = frozenset(
    {"snapshot_lookup", "triage_lookup", "simulation_lookup", "graph_query_lookup"}
)


def _lookup_artifact_key(org_id: str, repository_id: str, kind: str, lookup_key: str) -> str:
    from apps.api_server.services.repository_intelligence_object_store import artifact_key

    return artifact_key(
        org_id=org_id, repository_id=repository_id, kind=kind, artifact_id=lookup_key
    )


def read_lookup_shared(
    *, org_id: str, repository_id: str, kind: str, lookup_key: str
) -> dict[str, Any] | None:
    """Read a deterministic lookup from the durable object store (s3 mode only; ``None`` locally).

    Best-effort: a genuine miss AND any object-store availability fault both return ``None``. The
    caller then recomputes the identical deterministic result, so there is no fail-open risk."""
    if kind not in _DETERMINISTIC_LOOKUP_KINDS:
        raise ValueError(f"non-deterministic lookup kind not allowed here: {kind!r}")
    from apps.api_server.services.repository_intelligence_object_store import (
        get_object_store,
        object_store_mode,
    )

    if object_store_mode() != "s3":
        return None
    try:
        return get_object_store().get_json(
            _lookup_artifact_key(org_id, repository_id, kind, lookup_key)
        )
    except Exception as exc:  # noqa: BLE001 — deterministic: degrade to a local recompute
        logger.debug("ri_lookup_shared_read_degraded", kind=kind, error=str(exc))
        return None


def mirror_lookup(
    *, org_id: str, repository_id: str, kind: str, lookup_key: str, payload: dict[str, Any]
) -> None:
    """Mirror a freshly-computed deterministic lookup to the durable object store (s3 only; no-op
    locally). Best-effort: a failed mirror is logged and swallowed — a sibling recomputes."""
    if kind not in _DETERMINISTIC_LOOKUP_KINDS:
        raise ValueError(f"non-deterministic lookup kind not allowed here: {kind!r}")
    from apps.api_server.services.repository_intelligence_object_store import (
        get_object_store,
        object_store_mode,
    )

    if object_store_mode() != "s3":
        return
    try:
        get_object_store().put_json(
            _lookup_artifact_key(org_id, repository_id, kind, lookup_key), payload
        )
    except Exception as exc:  # noqa: BLE001 — best-effort perf cache; never fail the operation
        logger.debug("ri_lookup_shared_mirror_degraded", kind=kind, error=str(exc))
