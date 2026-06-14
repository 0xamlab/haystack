"""Per-org storage-cap enforcement (Wave 2 cleanup — the deferred half of PR-3's storage_gb cap).

Enforces the free-tier ``storage_gb`` cap (plan_limits) on the repository-intelligence object store.
Source of truth is a live S3 ``ListObjectsV2`` sum (``storage_service.compute_org_storage_bytes``) —
NOT a running counter: objects have no delete path and expire via the bucket's 90-day lifecycle, so
a counter would drift upward while the live sum always reflects the true footprint. The sum is
cached per-org with a short TTL (the list is amortized; the durable footprint changes slowly).

OFF BY DEFAULT (``ALGENTA_ENFORCE_STORAGE_CAP``). Self-host / node-local backends never enforce
(``compute_org_storage_bytes`` returns 0 off-S3), so existing deployments + CI are unaffected.

CAVEATS (best-effort, like the managed-LLM spend cap): the cap is a PRE-operation check on a cached
sum, not a reservation — a burst can overshoot slightly before the cache refreshes (bounded by the
concurrent-jobs + per-minute caps), and the sum fails OPEN on an S3 error (never blocks a legit user
on a transient blip). It bounds *when new storage-producing operations stop being accepted*.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid

import structlog
from fastapi import HTTPException

from apps.api_server.services import plan_limits, storage_service

logger = structlog.get_logger(__name__)

_GIB = 1024**3
_TRUE = {"1", "true", "yes", "on"}
_CACHE_TTL_S = 120.0
# org_id(str) -> (expires_monotonic, bytes). Process-local (per replica); mirrors tenant_key_store.
_cache: dict[str, tuple[float, int]] = {}


def storage_enforcement_enabled() -> bool:
    """True when the deployment enforces the per-org storage cap (hosted, opt-in). Default off."""
    return os.environ.get("ALGENTA_ENFORCE_STORAGE_CAP", "").strip().lower() in _TRUE


def resolve_storage_cap_bytes(plan: str) -> int:
    """Monthly storage cap in bytes for the plan. 0 = unlimited (e.g. enterprise)."""
    return max(0, plan_limits.get(plan).storage_gb) * _GIB


def invalidate_org_storage(org_id: uuid.UUID | str | None = None) -> None:
    """Drop the cached storage sum for one org (after a large write) or all orgs."""
    if org_id is None:
        _cache.clear()
    else:
        _cache.pop(str(org_id), None)


async def get_org_storage_bytes(org_id: uuid.UUID | str) -> int:
    """Cached live S3 footprint for the org (bytes). 0 off-S3 / on error (fail-open)."""
    key = str(org_id)
    cached = _cache.get(key)
    if cached is not None and cached[0] > time.monotonic():
        return cached[1]
    used = await asyncio.to_thread(storage_service.compute_org_storage_bytes, org_id)
    _cache[key] = (time.monotonic() + _CACHE_TTL_S, used)
    return used


async def over_storage_cap(org_id: uuid.UUID | str, plan: str) -> tuple[bool, int, int]:
    """(is_over, used_bytes, cap_bytes). Unlimited cap (0) → (False, used?, 0) without an S3 call."""
    cap = resolve_storage_cap_bytes(plan)
    if cap <= 0:
        return False, 0, 0
    used = await get_org_storage_bytes(org_id)
    return used >= cap, used, cap


async def gate_storage_cap(org_id: uuid.UUID | str, plan: str) -> None:
    """Fail closed (HTTP 413) before a storage-producing operation when the org is over its cap.

    No-op unless enforcement is enabled AND the plan has a finite cap. Mirrors
    ``check_llm_spend_quota`` (which raises HTTP 402): the enforcement gate raises an HTTP error the
    repository routers surface directly."""
    if not storage_enforcement_enabled():
        return
    is_over, used, cap = await over_storage_cap(org_id, plan)
    if is_over:
        logger.warning(
            "storage_cap_exceeded",
            org_id=str(org_id), plan=plan, used_bytes=used, cap_bytes=cap,
        )
        raise HTTPException(
            status_code=413,
            detail={
                "error": {
                    "code": "storage_cap_exceeded",
                    "message": (
                        f"Storage cap reached ({used / _GIB:.2f} GB of {cap // _GIB} GB). "
                        "Delete artifacts or upgrade your plan to store more."
                    ),
                    "used_gb": round(used / _GIB, 3),
                    "limit_gb": cap // _GIB,
                }
            },
        )
