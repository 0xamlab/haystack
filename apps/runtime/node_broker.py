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


def _is_community_floor(lic: object) -> bool:
    """The always-free Community fallback (a lapsed paid license that settled to the floor). It is
    NEVER capacity-gated — the never-hard-cut invariant wins over any node cap. Without this an
    unbound, license_id-less Community token would fail the peer census closed and hard-block the
    free floor (violating never-hard-cut)."""
    return str(getattr(lic, "source", "") or "") == "community-fallback"


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
    if _is_community_floor(lic):
        return  # never-hard-cut: the free Community floor is never blocked by binding
    # A BOUND token (carries device_pubkey_thumbprint) may run ONLY on its bound node — enforced
    # regardless of node_limit. Deployment/server licenses have active_node_limit=0 (units, not
    # nodes, are the metric); gating this check on node_limit>0 (the old behavior) made binding
    # dead code for exactly those licenses, letting an offline deployment license be copied across
    # nodes. Binding is now independent of node_limit; unbound tokens fall through to the L2 census.
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
            "this machine is not the licensed node — the license is bound to a different node "
            "(a bound device/deployment license runs only on the node it was issued for)"
        )


# ── Deployment scope: Compute-Unit capacity (server/enterprise) ───────────────────────────────────


def node_compute_units(lic: object) -> float:
    """This node's fractional Compute-Unit contribution under the license's measurement policy.

    Uses the cgroup-aware effective-vCPU measurement (apps/runtime/capacity.py) divided by the
    license's ``vcpu_per_unit``. Deterministic; safe to call at boot and on heartbeat."""
    from apps.runtime.capacity import measure_effective_vcpu, node_contribution

    unit_size = int(getattr(lic, "unit_size", lambda: 0)() or 0)
    measurement = measure_effective_vcpu()
    return node_contribution(measurement.effective_vcpu, unit_size or 4)


def assert_deployment_capacity(lic: object, *, enforcing: bool) -> None:
    """Fail closed if THIS node alone exceeds the deployment's Compute-Unit pool ceiling.

    This is the local (air-gap-safe, no-coordination) ceiling for a PINNED single-node server
    deployment: a node measured at more Compute Units than the whole purchased pool can never be
    admitted. The DISTRIBUTED pool sum across many nodes (floating pool) is the L3/Relay lease
    authority — this covers the single-node case that needs no backend. No-op for device scope,
    when dark, or when no unit ceiling is set."""
    if not enforcing:
        return
    if not bool(getattr(lic, "is_deployment_scope", lambda: False)()):
        return
    max_units = int(getattr(lic, "max_concurrent_units", 0) or 0)
    if max_units <= 0:
        return
    this_node = node_compute_units(lic)
    # Fractional node contribution rounded up to whole units for the ceiling comparison — a node
    # consuming 4.2 units needs a pool of at least 5.
    import math

    needed = int(math.ceil(this_node)) if this_node > 0 else 0
    if needed > max_units:
        raise NodeAdmissionError(
            f"this node measures {this_node:.2f} Compute Units (needs {needed}) but the deployment "
            f"pool ceiling is {max_units} — provision more Compute Units or split the workload"
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
    if _is_community_floor(lic):
        return None  # never-hard-cut: the free Community floor is never blocked by the census
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
