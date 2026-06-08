from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from apps.api_server.routers import infrastructure


@pytest.mark.anyio
async def test_register_and_heartbeat_node_for_same_org() -> None:
    infrastructure._registered_nodes.clear()
    auth = {"org_id": uuid.uuid4()}

    registered = await infrastructure.register_node(
        infrastructure.NodeRegisterRequest(region="test-region"),
        auth=auth,  # type: ignore[arg-type]
    )

    heartbeat = await infrastructure.node_heartbeat(
        infrastructure.NodeHeartbeatRequest(
            node_id=registered.node_id,
            cpu_pct=12.5,
            memory_gb=3.0,
            jobs_per_sec=42.0,
            status="live",
        ),
        auth=auth,  # type: ignore[arg-type]
    )

    assert heartbeat == {"node_id": registered.node_id, "accepted": True}
    stored = infrastructure._registered_nodes[registered.node_id]
    assert stored["region"] == "test-region"
    assert stored["cpu_pct"] == 12.5
    assert stored["jobs_per_sec"] == 42.0


@pytest.mark.anyio
async def test_node_heartbeat_rejects_cross_org_access() -> None:
    infrastructure._registered_nodes.clear()
    owner_org = uuid.uuid4()
    other_org = uuid.uuid4()
    node_id = "node-test"
    infrastructure._registered_nodes[node_id] = {
        "node_id": node_id,
        "org_id": str(owner_org),
        "region": "test-region",
        "engine_version": "unknown",
        "status": "live",
        "registered_at": "2026-04-18T00:00:00+00:00",
        "last_heartbeat": "2026-04-18T00:00:00+00:00",
    }

    with pytest.raises(HTTPException) as exc_info:
        await infrastructure.node_heartbeat(
            infrastructure.NodeHeartbeatRequest(node_id=node_id),
            auth={"org_id": other_org},  # type: ignore[arg-type]
        )

    exc = exc_info.value
    assert exc.status_code == 403
    assert exc.detail == {
        "error": {
            "code": "forbidden",
            "message": "Node belongs to different org.",
        }
    }
