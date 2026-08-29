"""GET /v1/infrastructure — real compute node health and engine status.
POST /v1/nodes/register — self-hosted worker node registration.
"""

import time
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from apps.api_server.config import get_settings
from apps.api_server.middleware.auth import AuthContext, get_current_org
from apps.privacy_policy import PublicDeploymentMode, publicize_deployment_mode

# In-memory node registry (replace with DB table for persistence across restarts)
_registered_nodes: dict[str, dict[str, Any]] = {}

router = APIRouter(tags=["Infrastructure"])

# Probe payload — minimal 10-run simulation for health check
_PROBE_PAYLOAD = {
    "runs": 10,
    "seed": 1,
    "variables": [{"name": "x", "distribution": "normal", "params": {"mean": 0.0, "std": 1.0}}],
    "objective_function": "x",
}


class NodeInfo(BaseModel):
    node_id: str
    status: str  # live | idle | error | updating
    engine_version: str
    cpu_pct: float | None
    memory_gb: float | None
    jobs_per_sec: float | None
    region: str
    last_heartbeat: datetime


class InfrastructureResponse(BaseModel):
    deployment_mode: PublicDeploymentMode
    engine_version: str
    api_version: str
    nodes: list[NodeInfo]
    probe_latency_ms: float | None = None
    uptime_30d_pct: float | None = None
    avg_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    throughput_rpm: float | None = None
    last_health_check: datetime
    engine_mode: str = (
        "binary"  # "binary" (compiled mojo_build/simulate) | "missing" (not built yet)
    )


async def _check_engine_health() -> tuple[str, float, str, str]:
    """
    Ping the Mojo binary with a minimal test simulation.
    Returns (status, latency_ms, engine_version, engine_mode).
    """
    from apps.api_server.compute.mojo_adapter import _BINARY_PATH, invoke_engine

    engine_mode = "binary" if _BINARY_PATH.exists() else "missing"
    try:
        start = time.perf_counter()
        result = await invoke_engine(_PROBE_PAYLOAD)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        version = result.get("engine_version", "unknown")
        return "live", latency_ms, version, engine_mode
    except Exception:
        return "error", 0.0, "unknown", engine_mode


@router.get(
    "/v1/infrastructure",
    response_model=InfrastructureResponse,
    summary="Real compute infrastructure health",
)
async def get_infrastructure(
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> InfrastructureResponse:
    """Return real engine health status and compute node information."""
    settings = get_settings()

    status, latency_ms, engine_version, engine_mode = await _check_engine_health()

    now = datetime.now(tz=UTC)
    # Primary node (this API server + its mojo engine)
    primary = NodeInfo(
        node_id="algenta-primary",
        status=status,
        engine_version=engine_version,
        cpu_pct=None,
        memory_gb=None,
        jobs_per_sec=None,
        region="local" if settings.is_development else "us-east-1",
        last_heartbeat=now,
    )
    # Add any registered self-hosted nodes
    registered = [
        NodeInfo(
            node_id=n["node_id"],
            status=n.get("status", "live"),
            engine_version=n.get("engine_version", "unknown"),
            cpu_pct=n.get("cpu_pct"),
            memory_gb=n.get("memory_gb"),
            jobs_per_sec=n.get("jobs_per_sec"),
            region=n.get("region", "unknown"),
            last_heartbeat=(
                datetime.fromisoformat(n["last_heartbeat"]) if n.get("last_heartbeat") else now
            ),
        )
        for n in _registered_nodes.values()
        if n.get("org_id") == str(auth["org_id"])
    ]
    nodes = [primary] + registered

    return InfrastructureResponse(
        deployment_mode=publicize_deployment_mode(settings.privacy_policy.deployment_mode),
        engine_version=engine_version,
        api_version="1.0.0",
        nodes=nodes,
        probe_latency_ms=latency_ms if status == "live" else None,
        # Historical aggregates require a metrics backend. Never synthesize them from one probe.
        uptime_30d_pct=None,
        avg_latency_ms=None,
        p95_latency_ms=None,
        throughput_rpm=None,
        last_health_check=now,
        engine_mode=engine_mode,
    )


# ── Node registration ─────────────────────────────────────────────────────


class NodeRegisterRequest(BaseModel):
    node_id: str | None = None  # auto-generated if not provided
    region: str = "local"
    engine_version: str | None = None
    cpu_count: int | None = None
    memory_gb: float | None = None
    capabilities: list[str] | None = None  # ["gpu", "large-memory", etc.]


class NodeRegisterResponse(BaseModel):
    node_id: str
    registered_at: str
    message: str


class NodeHeartbeatRequest(BaseModel):
    node_id: str
    cpu_pct: float | None = None
    memory_gb: float | None = None
    jobs_per_sec: float | None = None
    status: str = "live"


@router.post(
    "/v1/nodes/register",
    response_model=NodeRegisterResponse,
    status_code=201,
    summary="Register a self-hosted compute node",
)
async def register_node(
    payload: NodeRegisterRequest,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> NodeRegisterResponse:
    """
    Called by self-hosted Algenta workers on startup to register with the API.
    The node will appear in GET /v1/infrastructure for the org.
    """
    node_id = payload.node_id or f"node-{str(uuid4())[:8]}"
    now = datetime.now(tz=UTC)

    _registered_nodes[node_id] = {
        "node_id": node_id,
        "org_id": str(auth["org_id"]),
        "region": payload.region,
        "engine_version": payload.engine_version or "unknown",
        "cpu_count": payload.cpu_count,
        "memory_gb": payload.memory_gb,
        "capabilities": payload.capabilities or [],
        "status": "live",
        "registered_at": now.isoformat(),
        "last_heartbeat": now.isoformat(),
    }

    return NodeRegisterResponse(
        node_id=node_id,
        registered_at=now.isoformat(),
        message=(
            f"Node '{node_id}' registered successfully. Send heartbeats to POST /v1/nodes/heartbeat"
        ),
    )


@router.post("/v1/nodes/heartbeat", summary="Worker node heartbeat")
async def node_heartbeat(
    payload: NodeHeartbeatRequest,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> dict[str, object]:
    """Update node status and metrics. Call every 30s from worker nodes."""
    if payload.node_id not in _registered_nodes:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "node_not_found",
                    "message": (
                        f"Node '{payload.node_id}' not registered. Call /v1/nodes/register first."
                    ),
                }
            },
        )
    node = _registered_nodes[payload.node_id]
    if node["org_id"] != str(auth["org_id"]):
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "forbidden",
                    "message": "Node belongs to different org.",
                }
            },
        )

    node.update(
        {
            "status": payload.status,
            "cpu_pct": payload.cpu_pct,
            "memory_gb": payload.memory_gb,
            "jobs_per_sec": payload.jobs_per_sec,
            "last_heartbeat": datetime.now(tz=UTC).isoformat(),
        }
    )

    return {"node_id": payload.node_id, "accepted": True}


@router.delete("/v1/nodes/{node_id}", status_code=204, summary="Deregister a node")
async def deregister_node(
    node_id: str,
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> None:
    """Gracefully deregister a self-hosted worker node."""
    node = _registered_nodes.get(node_id)
    if node and node["org_id"] == str(auth["org_id"]):
        del _registered_nodes[node_id]
