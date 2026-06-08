from __future__ import annotations

import asyncio

from apps.api_server.schemas.agent_runs import AgentRunCreateRequest
from apps.api_server.services import agent_run_service, execution_policy_service


def _auth(org_id: str = "org_policy") -> dict[str, str]:
    return {
        "org_id": org_id,
        "key_id": "key_policy",
        "plan": "enterprise",
        "role": "owner",
        "email": "owner@algenta.test",
    }


def test_execution_policy_service_persists_default_and_updated_snapshots(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))

    current = execution_policy_service.get_policy("org_policy")
    updated = execution_policy_service.set_policy(
        "org_policy",
        min_confidence=0.82,
        allow_reexecution=True,
    )
    noop = execution_policy_service.set_policy(
        "org_policy",
        min_confidence=0.82,
        allow_reexecution=True,
    )
    snapshots = execution_policy_service.list_policy_snapshots("org_policy")

    assert current.revision == 1
    assert current.snapshot_id.startswith("execution-policy-v1-r1:")
    assert updated.revision == 2
    assert updated.previous_snapshot_id == current.snapshot_id
    assert updated.snapshot_id != current.snapshot_id
    assert noop.snapshot_id == updated.snapshot_id
    assert len(snapshots) == 2
    assert snapshots[-1].snapshot_id == updated.snapshot_id

    snapshot_dir = tmp_path / "runtime" / "execution_policies" / "org_policy" / "snapshots"
    assert (snapshot_dir / f"{current.snapshot_id}.json").exists()
    assert (snapshot_dir / f"{current.snapshot_id}.parquet").exists()
    assert (snapshot_dir / f"{updated.snapshot_id}.json").exists()
    assert (snapshot_dir / f"{updated.snapshot_id}.parquet").exists()


def test_agent_runs_reference_live_policy_snapshots(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))

    policy = execution_policy_service.set_policy(
        "org_agent_policy",
        min_confidence=0.91,
        require_calibration=False,
    )
    run = asyncio.run(
        agent_run_service.create_agent_run(
            AgentRunCreateRequest(task="Search the latest policy bundle"),
            auth=_auth("org_agent_policy"),
        )
    )

    assert run.policy_snapshot_id == policy.snapshot_id
    checkpoints = agent_run_service.get_agent_run_checkpoints(
        run_id=run.run_id,
        auth=_auth("org_agent_policy"),
    )
    assert checkpoints.data[0].policy_snapshot_id == policy.snapshot_id
