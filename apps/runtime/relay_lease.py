"""Algenta Relay — Compute-Unit lease ledger (the floating-pool enforcement heart).

For air-gapped / multi-node fleets the customer runs a Relay inside their network: it holds a
vendor-minted pool entitlement (N Compute Units) and leases units to engine nodes via short-TTL
heartbeats. This module is the pure, deterministic LEDGER — the pool accounting that makes the
distributed unit ceiling real:

  * pool ceiling: Σ granted units across active leases ≤ ``max_units`` (fail CLOSED past it)
  * idempotent acquire: a node re-acquiring refreshes its lease, never double-counts (autoscale
    race-safe)
  * borrow-with-expiry: a node's units stay reserved until ``borrowed_until`` even if it goes
    silent, so a disconnected node doesn't instantly free capacity to a racing peer
  * TTL expiry: a lease past both its TTL and borrow window frees its units (dead node reclaim)
  * never-evict: acquiring/renewing never removes another node's active lease; over-cap requests
    are refused, running work is untouched

All methods take an explicit ``now`` (deterministic + testable; no wall-clock in the core). The
cryptographic delegation chain (root→pool-root→node-lease signing) and the HTTP heartbeat API
wrap this ledger; the pool math is here so it can be exhaustively unit-tested.
"""
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_LEASE_TTL_SECONDS = 300  # short — reclaim a dead node's units quickly
DEFAULT_BORROW_SECONDS = 300  # units reserved for a silent node this long past its lease


class LeaseError(RuntimeError):
    """A lease request is refused (pool exhausted, node ceiling, or invalid units)."""


@dataclass
class Lease:
    node_id: str
    granted_units: int
    issued_at: float
    expires_at: float  # TTL boundary (heartbeat refreshes it)
    borrowed_until: float  # units stay reserved until here even without a heartbeat

    def reserved_until(self) -> float:
        return max(self.expires_at, self.borrowed_until)

    def is_active(self, now: float) -> bool:
        return now < self.reserved_until()


class LeaseLedger:
    """Tracks active node leases against a fixed Compute-Unit pool.

    ``max_units`` is the pool ceiling (from the vendor-minted pool root). ``node_ceiling`` is an
    optional safety cap on the NUMBER of concurrent nodes (0 = unlimited)."""

    def __init__(self, max_units: int, *, node_ceiling: int = 0) -> None:
        if max_units <= 0:
            raise ValueError("max_units must be > 0")
        self.max_units = int(max_units)
        self.node_ceiling = int(node_ceiling)
        self._leases: dict[str, Lease] = {}

    # ── queries ──
    def _prune(self, now: float) -> None:
        self._leases = {nid: le for nid, le in self._leases.items() if le.is_active(now)}

    def active_leases(self, now: float) -> list[Lease]:
        self._prune(now)
        return list(self._leases.values())

    def used_units(self, now: float, *, exclude: str = "") -> int:
        self._prune(now)
        return sum(le.granted_units for nid, le in self._leases.items() if nid != exclude)

    def available_units(self, now: float) -> int:
        return max(0, self.max_units - self.used_units(now))

    # ── mutations ──
    def acquire(
        self,
        node_id: str,
        units: int,
        now: float,
        *,
        ttl: float = DEFAULT_LEASE_TTL_SECONDS,
        borrow: float = DEFAULT_BORROW_SECONDS,
    ) -> Lease:
        """Grant (or idempotently refresh) a lease of ``units`` for ``node_id``.

        Idempotent: if the node already holds a lease, its old grant is REPLACED (not added), so
        re-acquiring / retrying never double-counts. Fails closed (:class:`LeaseError`) if the
        grant would exceed the pool ceiling or the node ceiling — never evicting a peer."""
        if not node_id:
            raise LeaseError("node_id required")
        if units <= 0:
            raise LeaseError("units must be > 0")
        self._prune(now)

        used_by_others = self.used_units(now, exclude=node_id)
        if used_by_others + units > self.max_units:
            raise LeaseError(
                f"pool exhausted: {used_by_others} units in use by peers + {units} requested "
                f"exceeds pool of {self.max_units}"
            )
        if self.node_ceiling and node_id not in self._leases and len(self._leases) >= self.node_ceiling:
            raise LeaseError(f"node ceiling reached ({self.node_ceiling} nodes)")

        lease = Lease(
            node_id=node_id,
            granted_units=int(units),
            issued_at=now,
            expires_at=now + float(ttl),
            borrowed_until=now + float(max(ttl, borrow)),
        )
        self._leases[node_id] = lease
        return lease

    def renew(self, node_id: str, now: float, *, ttl: float = DEFAULT_LEASE_TTL_SECONDS,
              borrow: float = DEFAULT_BORROW_SECONDS) -> Lease:
        """Heartbeat: extend an existing lease's TTL without changing its unit grant. Raises if
        the node has no active lease (it must re-acquire)."""
        self._prune(now)
        existing = self._leases.get(node_id)
        if existing is None:
            raise LeaseError(f"no active lease for node {node_id!r} — re-acquire")
        existing.expires_at = now + float(ttl)
        existing.borrowed_until = now + float(max(ttl, borrow))
        return existing

    def release(self, node_id: str, now: float) -> None:
        """Explicit give-back — frees the node's units immediately (graceful shutdown). Unlike
        expiry, release does NOT honor the borrow window (the node said it's done)."""
        self._leases.pop(node_id, None)
