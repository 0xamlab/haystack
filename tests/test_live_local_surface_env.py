from __future__ import annotations

from tests.integration.live_local_surface_env import (
    LOCAL_LIVE_SIMULATION_PERSIST_TRANSPORT,
    configure_local_live_server_env,
    merge_egress_allowlist,
)


def test_merge_egress_allowlist_preserves_existing_entries_and_adds_loopback_once() -> None:
    merged = merge_egress_allowlist(
        "api.weather.gov,127.0.0.1,api.weather.gov",
        extra_hosts=("127.0.0.1", "db.internal"),
    )

    assert merged == "api.weather.gov,127.0.0.1,localhost,::1,db.internal"


def test_configure_local_live_server_env_sets_artifact_cache_and_loopback_allowlist(
    tmp_path,
) -> None:
    env = {"ALGENTA_EGRESS_ALLOWLIST": "api.weather.gov"}

    configured = configure_local_live_server_env(env, root_dir=tmp_path)

    assert configured is env
    assert env["ALGENTA_SOURCE_ARTIFACT_CACHE_DIR"] == str(tmp_path / "artifact_cache")
    assert (tmp_path / "artifact_cache").is_dir()
    assert env["ALGENTA_EGRESS_ALLOWLIST"] == "api.weather.gov,127.0.0.1,localhost,::1"
    assert (
        env["ALGENTA_SIMULATION_PERSIST_TRANSPORT"]
        == LOCAL_LIVE_SIMULATION_PERSIST_TRANSPORT
    )
