"""Offline enforcement of a license's ``active_node_limit`` — the runtime node gate.

Companion to ``worker_broker`` (which enforces ``concurrent_worker_limit`` per node). Where the control
plane counts active nodes in its DB (``device_service.node_admission_block_count``), a SELF-HOSTED engine
has no control plane to phone; so a customer could otherwise run M engine instances off an N-node license.
This module closes that offline, fail-CLOSED, without any phone-home — the deliberate inverse of the
fail-OPEN worker broker.

Layered, strongest-to-weakest (see docs/pricing-algenta.md):

* **L1 device-binding (air-gap-safe, primary).** A per-node license carries ``device_pubkey_thumbprint``
  (the node's Ed25519 public-key thumbprint, ``device_keypair.public_key_thumbprint``). At boot the node
  proves it holds the matching private key by recomputing the thumbprint; a mismatch fails closed. For a
  single-device unit (``active_node_limit=1``, e.g. Community) this alone is an offline node cap of 1 with
  zero coordination — a token cannot run on a second machine (whose key is different). As strong as the private
  key store: OS keychain / machine-id-encrypted file today, TPM/Secure-Enclave optional hardening later.

* **L2 peer census (shared-Redis clusters, defense-in-depth, opt-in ``ALGENTA_ENFORCE_PEER_NODE_CAP``).**
  For a shared-token cluster (one unbound token, ``active_node_limit=N``), nodes count each other via an
  atomic sorted-set census keyed by ``license_id`` on the customer's OWN coordination Redis
  (``apps/runtime/coordination.py``); the N+1-th node is refused. Counts only REACHABLE peers — a network
  partition is a per-segment ceiling, never a global one (the documented residual).

Dark by default: no-op unless license enforcement is on (``require_local_license`` OR
``enforce_license_validation``) AND ``active_node_limit > 0``. L2 additionally requires
``ALGENTA_ENFORCE_PEER_NODE_CAP`` + a reachable coordination Redis. Free-tier / single-node / dev untouched.
"""
from __future__ import annotations

import asyncio
import os

import structlog

from apps.runtime import coordination

logger = structlog.get_logger(__name__)

_DEFAULT_WINDOW_SECONDS = 600  # census liveness window; a node missing for > window frees its slot


class NodeAdmissionError(RuntimeError):
    """Raised (fail-closed) when this node may not run under the license's ``active_node_limit`` —
    device-binding mismatch, over the peer-census cap, or an unbound token that cannot be counted."""


def _env_truthy(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _enforce_peer_node_cap() -> bool:
    """L2 census flag — parallel to the control plane's ``ALGENTA_ENFORCE_ACTIVE_NODE_CAP``. Default OFF."""
    return _env_truthy("ALGENTA_ENFORCE_PEER_NODE_CAP")


def license_enforcing() -> bool:
    """The license-enforcement predicate that gates L1 (mirrors the daemon startup gate)."""
    try:
        from apps.privacy_policy import policy_from_environment

        pol = policy_from_environment()
        return bool(pol.require_local_license or pol.enforce_license_validation)
    except Exception:  # noqa: BLE001 — if the policy can't load, stay dark (don't hard-fail boot)
        return False


def _window_seconds() -> int:
    try:
        val = int(os.environ.get("ALGENTA_NODE_CAP_WINDOW_SECONDS", str(_DEFAULT_WINDOW_SECONDS)))
    except (TypeError, ValueError):
        val = _DEFAULT_WINDOW_SECONDS
    return max(120, val)  # floor so a single missed heartbeat never evicts a live node


def _heartbeat_interval(window: int) -> int:
    return max(30, window // 3)


def resolve_node_identity() -> str:
    """This node's stable public-key thumbprint (== the license's ``device_pubkey_thumbprint`` claim).
    Raises if the keypair is unavailable — callers translate that to a fail-closed admission error."""
    from apps.runtime.device_keypair import public_key_thumbprint

    return public_key_thumbprint()


# ── L1: device binding (sync, air-gap-safe, primary) ──────────────────────────────────────────────


def assert_node_binding(lic: object, *, enforcing: bool) -> None:
    """Fail closed unless THIS machine is the license's bound node. No-op for unbound tokens (L2 counts
    those) and when dark. Called at daemon startup (sync, before anything binds)."""
    if not enforcing:
        return
    limit = int(getattr(lic, "node_limit", lambda: 0)())
    if limit <= 0:
        return
    claimed = (getattr(lic, "device_pubkey_thumbprint", "") or "").strip()
    if not claimed:
        return  # unbound token → the peer census (L2) is the enforcement path, not binding
    try:
        local = resolve_node_identity()
    except Exception as exc:  # noqa: BLE001 — no identity ⇒ can't prove binding ⇒ fail closed
        raise NodeAdmissionError(
            "device identity unavailable; cannot verify this node's license binding"
        ) from exc
    if local != claimed:
        raise NodeAdmissionError(
            "this machine is not the licensed node — the license is device-bound to a different node "
            "(active_node_limit is per-device for self-hosted deployments)"
        )


# ── L2: peer census (async, shared-Redis clusters, opt-in) ────────────────────────────────────────


async def assert_node_census(lic: object, *, enforcing: bool, now: float | None = None) -> str | None:
    """Fail closed if admitting this node would exceed ``active_node_limit`` among peers sharing the
    license's census. Returns the census member id when the node is admitted (so the heartbeat can refresh
    it), or ``None`` when the gate is a no-op. Raises :class:`NodeAdmissionError` on over-cap / unverifiable.

    Fallbacks: no coordination backend or a census error ⇒ a BOUND token still boots (L1 authorized it),
    an UNBOUND token with a finite pool fails closed (it cannot be counted offline)."""
    if not enforcing or not _enforce_peer_node_cap():
        return None
    limit = int(getattr(lic, "node_limit", lambda: 0)())
    if limit <= 0:
        return None
    bound = bool((getattr(lic, "device_pubkey_thumbprint", "") or "").strip())
    license_id = (getattr(lic, "license_id", "") or "").strip()

    redis = coordination.get_runtime_coordination_redis()
    if redis is None:
        if bound:
            return None  # air-gap-safe: L1 device-binding already authorizes this exact node
        raise NodeAdmissionError(
            "unbound self-host license with a finite node pool requires a coordination backend "
            "(ALGENTA_COORDINATION=redis) to enforce the node count offline"
        )
    if not license_id:
        if bound:
            return None
        raise NodeAdmissionError("license has no license_id; cannot group a node census")

    try:
        member = resolve_node_identity()
    except Exception as exc:  # noqa: BLE001
        if bound:
            return None
        raise NodeAdmissionError("device identity unavailable; cannot join the node census") from exc

    from apps.runtime.trusted_time import trusted_now_epoch

    ts = float(now) if now is not None else float(trusted_now_epoch())
    window = _window_seconds()
    admitted = await coordination.census_admit(
        redis, license_id, member, now=ts, window=window, limit=limit
    )
    if admitted is None:  # census unavailable (Redis error)
        if bound:
            return None
        raise NodeAdmissionError("node census unavailable and the license is unbound; failing closed")
    if not admitted:
        raise NodeAdmissionError(
            f"active node limit reached ({limit}) — this deployment already runs {limit} licensed "
            "node(s); provision more nodes or an enterprise site license"
        )
    return member


# ── process-wide heartbeat state (keeps this node's census slot alive) ─────────────────────────────

_hb_task: asyncio.Task | None = None
_hb_member: str = ""
_hb_license_id: str = ""


def _load_current_license() -> object | None:
    try:
        from apps.runtime.license import load_license

        api_key = os.environ.get("ALGENTA_API_KEY", "") or os.environ.get("DE_API_KEY", "")
        lic = load_license(api_key)
        return lic if getattr(lic, "valid", False) else None
    except Exception:  # noqa: BLE001
        logger.debug("node_broker_license_unresolved", exc_info=True)
        return None


async def admit_node_and_start_heartbeat() -> None:
    """Server-start entrypoint (async): load the license, run the L2 census admission (raises on
    over-cap), and if admitted keep the census slot alive with a background heartbeat. No-op when dark.
    Mirrors ``worker_broker.configure_from_license`` but fails closed."""
    global _hb_member, _hb_license_id
    lic = _load_current_license()
    if lic is None:
        return
    member = await assert_node_census(lic, enforcing=license_enforcing())
    if not member:
        return
    _hb_member = member
    _hb_license_id = (getattr(lic, "license_id", "") or "").strip()
    _start_heartbeat(int(getattr(lic, "node_limit", lambda: 0)()))


def _start_heartbeat(limit: int) -> None:
    global _hb_task
    if _hb_task is not None and not _hb_task.done():
        return
    _hb_task = asyncio.create_task(_heartbeat_loop(limit))


async def _heartbeat_loop(limit: int) -> None:
    from apps.runtime.trusted_time import trusted_now_epoch

    window = _window_seconds()
    interval = _heartbeat_interval(window)
    while True:
        try:
            await asyncio.sleep(interval)
            redis = coordination.get_runtime_coordination_redis()
            if redis is None or not _hb_license_id or not _hb_member:
                continue
            # Re-admit refreshes an existing member's score (never evicts) and keeps the slot alive.
            await coordination.census_admit(
                redis, _hb_license_id, _hb_member,
                now=float(trusted_now_epoch()), window=window, limit=limit,
            )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — a heartbeat hiccup must never crash the node
            logger.debug("node_census_heartbeat_error", exc_info=True)


async def stop_node_census_heartbeat() -> None:
    """Cancel the heartbeat and release this node's census slot (frees it immediately on graceful stop)."""
    global _hb_task
    if _hb_task is not None:
        _hb_task.cancel()
        try:
            await _hb_task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        _hb_task = None
    if _hb_license_id and _hb_member:
        redis = coordination.get_runtime_coordination_redis()
        if redis is not None:
            await coordination.census_release(redis, _hb_license_id, _hb_member)


def reset_node_broker() -> None:
    """Drop heartbeat state (tests / daemon restart)."""
    global _hb_task, _hb_member, _hb_license_id
    if _hb_task is not None:
        _hb_task.cancel()
    _hb_task = None
    _hb_member = ""
    _hb_license_id = ""
