"""CI helper: block until the integration services (Postgres, Dragonfly, MinIO) are ready.

All three are launched via plain `docker run` (self-hosted macOS runners can't use GitHub Actions'
`services:` container orchestration at all — Linux-only — and Dragonfly/MinIO never had a usable
in-image health-cmd besides), so nothing gates the job on their readiness automatically. This polls
each from the runner — a real Postgres connection, a Redis PING for Dragonfly, and the MinIO
readiness endpoint — so the integration steps run against ready backends instead of racing them."""

from __future__ import annotations

import asyncio
import os
import sys
import time
import urllib.request

# Non-standard host ports throughout — see ci.yml's `test` job env: block for why (a native
# Homebrew Postgres permanently shadows 5432, and 9000 had a stale colima port-forward).
_POSTGRES_URL = os.environ.get(
    "CI_WAIT_POSTGRES_URL", "postgresql://postgres:postgres@localhost:15432/test_db"
)
_REDIS_URL = "redis://localhost:16379/0"
_MINIO_READY = "http://localhost:19000/minio/health/ready"


def _wait(name: str, check, attempts: int = 30, delay: float = 2.0) -> None:
    last: Exception | None = None
    for _ in range(attempts):
        try:
            check()
            print(f"{name} ready", flush=True)
            return
        except Exception as exc:  # noqa: BLE001 — keep polling until the deadline
            last = exc
            time.sleep(delay)
    raise SystemExit(f"{name} not ready after {attempts * delay:.0f}s: {last}")


def _ping_postgres() -> None:
    import asyncpg

    async def _connect() -> None:
        conn = await asyncpg.connect(_POSTGRES_URL, timeout=2)
        try:
            await conn.fetchval("SELECT 1")
        finally:
            await conn.close()

    asyncio.run(_connect())


def _ping_dragonfly() -> None:
    import redis

    client = redis.from_url(_REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
    if not client.ping():
        raise RuntimeError("PING returned falsey")


def _ping_minio() -> None:
    with urllib.request.urlopen(_MINIO_READY, timeout=2) as resp:  # noqa: S310 — fixed loopback URL
        if resp.status >= 400:
            raise RuntimeError(f"MinIO health status {resp.status}")


_CHECKS = {
    "postgres": _ping_postgres,
    "dragonfly": _ping_dragonfly,
    "minio": _ping_minio,
}


def main() -> int:
    names = sys.argv[1:] or list(_CHECKS)
    for name in names:
        _wait(name, _CHECKS[name])
    return 0


if __name__ == "__main__":
    sys.exit(main())
