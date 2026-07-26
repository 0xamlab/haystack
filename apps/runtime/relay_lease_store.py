"""Relay HA — a shared, persistent lease ledger with cross-process atomic admission.

The in-memory :class:`~apps.runtime.relay_lease.LeaseLedger` is per-process: two Relay replicas
each holding the full pool would double-allocate (the documented single-relay limit). This
SQLite-backed ledger gives the SAME semantics (pool ceiling, idempotent acquire, borrow-with-
expiry, TTL reclaim, never-evict) but over SHARED state: multiple replicas point at the same
database file (on shared storage) and every admission runs inside a ``BEGIN IMMEDIATE`` write
transaction, so SQLite's write lock serializes the check-and-set ACROSS processes — no two
replicas can jointly exceed the pool.

This is the concrete HA foundation for small/medium fleets (single shared DB file). For large
fleets or multi-region, back it with Postgres (SELECT ... FOR UPDATE / advisory lock) or run a
quorum/leader-elected relay set; the API here is the seam. Deterministic ``now`` throughout.

IMPORTANT (locking scope): the ``BEGIN IMMEDIATE`` write lock only serializes replicas that share
the file through WORKING POSIX file locks — i.e. replicas on the SAME host or a shared volume with
reliable ``fcntl`` locking. SQLite locking is unsafe over most network filesystems (NFS/SMB), so
do NOT run cross-HOST HA on a network-mounted SQLite file — use the Postgres-backed store for
cross-host / multi-region. (WAL mode does not change this: WAL requires shared memory and is also
local-only.)
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from apps.runtime.relay_lease import DEFAULT_BORROW_SECONDS, DEFAULT_LEASE_TTL_SECONDS, Lease, LeaseError


class SqliteLeaseLedger:
    """Shared-state lease ledger backed by a SQLite file. Drop-in for ``LeaseLedger`` in
    ``relay_server.create_relay_app`` to make a relay HA-capable (replicas share one file)."""

    def __init__(self, db_path: str | Path, max_units: int, *, node_ceiling: int = 0) -> None:
        if max_units <= 0:
            raise ValueError("max_units must be > 0")
        self.max_units = int(max_units)
        self.node_ceiling = int(node_ceiling)
        self.db_path = str(db_path)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        # isolation_level=None → autocommit; we drive explicit BEGIN IMMEDIATE for the write lock.
        conn = sqlite3.connect(self.db_path, timeout=30.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_schema(self) -> None:
        conn = self._conn()
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS leases ("
                "node_id TEXT PRIMARY KEY, granted_units INTEGER NOT NULL, "
                "expires_at REAL NOT NULL, borrowed_until REAL NOT NULL)"
            )
        finally:
            conn.close()

    @staticmethod
    def _prune(conn: sqlite3.Connection, now: float) -> None:
        conn.execute(
            "DELETE FROM leases WHERE MAX(expires_at, borrowed_until) <= ?", (now,)
        )

    def used_units(self, now: float, *, exclude: str = "") -> int:
        conn = self._conn()
        try:
            self._prune(conn, now)
            row = conn.execute(
                "SELECT COALESCE(SUM(granted_units), 0) FROM leases WHERE node_id != ?", (exclude,)
            ).fetchone()
            return int(row[0] or 0)
        finally:
            conn.close()

    def available_units(self, now: float) -> int:
        return max(0, self.max_units - self.used_units(now))

    def active_leases(self, now: float) -> list[Lease]:
        conn = self._conn()
        try:
            self._prune(conn, now)
            rows = conn.execute(
                "SELECT node_id, granted_units, expires_at, borrowed_until FROM leases"
            ).fetchall()
            return [Lease(node_id=r[0], granted_units=int(r[1]), issued_at=0.0,
                          expires_at=float(r[2]), borrowed_until=float(r[3])) for r in rows]
        finally:
            conn.close()

    def acquire(self, node_id: str, units: int, now: float, *,
                ttl: float = DEFAULT_LEASE_TTL_SECONDS, borrow: float = DEFAULT_BORROW_SECONDS) -> Lease:
        """Atomic across processes: BEGIN IMMEDIATE takes SQLite's write lock, so concurrent
        acquires from OTHER replicas sharing this file are serialized — the pool ceiling holds
        cluster-wide. Same semantics as the in-memory ledger otherwise."""
        if not node_id:
            raise LeaseError("node_id required")
        if units <= 0:
            raise LeaseError("units must be > 0")
        conn = self._conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            self._prune(conn, now)
            used_others = int(conn.execute(
                "SELECT COALESCE(SUM(granted_units), 0) FROM leases WHERE node_id != ?", (node_id,)
            ).fetchone()[0] or 0)
            if used_others + units > self.max_units:
                conn.execute("ROLLBACK")
                raise LeaseError(
                    f"pool exhausted: {used_others} units in use by peers + {units} requested "
                    f"exceeds pool of {self.max_units}"
                )
            if self.node_ceiling:
                existing_row = conn.execute(
                    "SELECT 1 FROM leases WHERE node_id = ?", (node_id,)
                ).fetchone()
                count = int(conn.execute("SELECT COUNT(*) FROM leases").fetchone()[0] or 0)
                if existing_row is None and count >= self.node_ceiling:
                    conn.execute("ROLLBACK")
                    raise LeaseError(f"node ceiling reached ({self.node_ceiling} nodes)")
            expires_at = now + float(ttl)
            borrowed_until = now + float(max(ttl, borrow))
            conn.execute(
                "INSERT INTO leases (node_id, granted_units, expires_at, borrowed_until) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(node_id) DO UPDATE SET "
                "granted_units=excluded.granted_units, expires_at=excluded.expires_at, "
                "borrowed_until=excluded.borrowed_until",
                (node_id, int(units), expires_at, borrowed_until),
            )
            conn.execute("COMMIT")
            return Lease(node_id=node_id, granted_units=int(units), issued_at=now,
                         expires_at=expires_at, borrowed_until=borrowed_until)
        except LeaseError:
            raise
        except Exception:  # noqa: BLE001 — ensure the write lock is always released
            try:
                conn.execute("ROLLBACK")
            except Exception:  # noqa: BLE001
                pass
            raise
        finally:
            conn.close()

    def renew(self, node_id: str, now: float, *,
              ttl: float = DEFAULT_LEASE_TTL_SECONDS, borrow: float = DEFAULT_BORROW_SECONDS) -> Lease:
        conn = self._conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            self._prune(conn, now)
            row = conn.execute(
                "SELECT granted_units FROM leases WHERE node_id = ?", (node_id,)
            ).fetchone()
            if row is None:
                conn.execute("ROLLBACK")
                raise LeaseError(f"no active lease for node {node_id!r} — re-acquire")
            units = int(row[0])
            expires_at = now + float(ttl)
            borrowed_until = now + float(max(ttl, borrow))
            conn.execute(
                "UPDATE leases SET expires_at=?, borrowed_until=? WHERE node_id=?",
                (expires_at, borrowed_until, node_id),
            )
            conn.execute("COMMIT")
            return Lease(node_id=node_id, granted_units=units, issued_at=now,
                         expires_at=expires_at, borrowed_until=borrowed_until)
        except LeaseError:
            raise
        except Exception:  # noqa: BLE001
            try:
                conn.execute("ROLLBACK")
            except Exception:  # noqa: BLE001
                pass
            raise
        finally:
            conn.close()

    def release(self, node_id: str, now: float) -> None:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM leases WHERE node_id = ?", (node_id,))
        finally:
            conn.close()
