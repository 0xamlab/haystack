"""CI helper: block until the optional integration services (Dragonfly, MinIO) are ready.

GitHub-Actions service containers without a usable in-image health-cmd (Dragonfly has no redis-cli;
the MinIO server is launched via `docker run`) are started but not waited on. This polls both from
the runner — a Redis PING for Dragonfly and the MinIO readiness endpoint — so the coordination /
object-store integration steps run against ready backends instead of racing them."""

from __future__ import annotations

import sys
import time
import urllib.request

_REDIS_URL = "redis://localhost:6379/0"
_MINIO_READY = "http://localhost:9000/minio/health/ready"


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


def _ping_dragonfly() -> None:
    import redis

    client = redis.from_url(_REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
    if not client.ping():
        raise RuntimeError("PING returned falsey")


def _ping_minio() -> None:
    with urllib.request.urlopen(_MINIO_READY, timeout=2) as resp:  # noqa: S310 — fixed loopback URL
        if resp.status >= 400:
            raise RuntimeError(f"MinIO health status {resp.status}")


def main() -> int:
    _wait("dragonfly", _ping_dragonfly)
    _wait("minio", _ping_minio)
    return 0


if __name__ == "__main__":
    sys.exit(main())
