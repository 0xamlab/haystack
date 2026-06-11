from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

LOOPBACK_EGRESS_ALLOWLIST = ("127.0.0.1", "localhost", "::1")
LOCAL_LIVE_SIMULATION_PERSIST_TRANSPORT = "in_process"


def merge_egress_allowlist(
    existing: str | None,
    *,
    extra_hosts: Sequence[str] = (),
) -> str:
    merged: list[str] = []
    seen: set[str] = set()
    for raw_host in [*(existing or "").split(","), *LOOPBACK_EGRESS_ALLOWLIST, *extra_hosts]:
        host = str(raw_host).strip()
        if not host or host in seen:
            continue
        merged.append(host)
        seen.add(host)
    return ",".join(merged)


def configure_local_live_server_env(
    env: dict[str, str],
    *,
    root_dir: Path,
    extra_hosts: Sequence[str] = (),
) -> dict[str, str]:
    artifact_cache_dir = Path(
        env.get("ALGENTA_SOURCE_ARTIFACT_CACHE_DIR", root_dir / "artifact_cache")
    )
    artifact_cache_dir.mkdir(parents=True, exist_ok=True)
    env["ALGENTA_SOURCE_ARTIFACT_CACHE_DIR"] = str(artifact_cache_dir)
    env["ALGENTA_EGRESS_ALLOWLIST"] = merge_egress_allowlist(
        env.get("ALGENTA_EGRESS_ALLOWLIST"),
        extra_hosts=extra_hosts,
    )
    env.setdefault(
        "ALGENTA_SIMULATION_PERSIST_TRANSPORT",
        LOCAL_LIVE_SIMULATION_PERSIST_TRANSPORT,
    )
    return env
