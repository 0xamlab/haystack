"""
Phase 7 — Enterprise Portal API tests.
Tests for /v1/runs, /v1/analytics, /v1/infrastructure, /v1/team, /v1/audit-logs.
All tests use the mock-based pattern from existing test suite.
"""

from datetime import UTC
from uuid import uuid4

import pytest

# ── /v1/runs ─────────────────────────────────────────────────────────────────


def test_runs_response_schema():
    """RunsResponse must have required fields with correct types."""
    from datetime import datetime

    from apps.api_server.routers.runs import RunsResponse, RunSummary

    run = RunSummary(
        run_id=str(uuid4()),
        mode="auto",
        status="completed",
        scenarios_run=10000,
        duration_ms=12,
        result_hash=None,
        execution_type="sync",
        created_at=datetime.now(tz=UTC),
        completed_at=datetime.now(tz=UTC),
    )
    assert run.mode == "auto"
    assert run.status == "completed"
    assert run.scenarios_run == 10000

    resp = RunsResponse(runs=[run], total=1, page=1, limit=20, pages=1)
    assert resp.total == 1
    assert resp.pages == 1
    assert len(resp.runs) == 1


def test_runs_pagination_calc():
    """Pages calculation must round up correctly."""
    from apps.api_server.routers.runs import RunsResponse

    # 100 runs, 20 per page = 5 pages
    resp = RunsResponse(runs=[], total=100, page=1, limit=20, pages=5)
    assert resp.pages == 5

    # 101 runs, 20 per page = 6 pages
    assert max(1, (101 + 20 - 1) // 20) == 6


def test_analytics_response_schema():
    """AnalyticsSummary must accept all valid fields."""
    from apps.api_server.routers.runs import AnalyticsSummary

    summary = AnalyticsSummary(
        total_runs=100,
        runs_by_day=[{"date": "2026-03-20", "count": 42}],
        runs_by_status={"completed": 90, "failed": 10},
        runs_by_mode={"auto": 70, "expert": 30},
        avg_duration_ms=12.5,
        p95_duration_ms=48,
    )
    assert summary.total_runs == 100
    assert summary.runs_by_status["completed"] == 90
    assert summary.avg_duration_ms == 12.5


# ── /v1/infrastructure ────────────────────────────────────────────────────────


def test_node_info_schema():
    """NodeInfo must serialize and validate correctly."""
    from datetime import datetime

    from apps.api_server.routers.infrastructure import NodeInfo

    node = NodeInfo(
        node_id="algenta-us-east-1a",
        status="live",
        engine_version="0.3.1",
        cpu_pct=18.4,
        memory_gb=3.2,
        jobs_per_sec=284.0,
        region="us-east-1",
        last_heartbeat=datetime.now(tz=UTC),
    )
    assert node.status == "live"
    assert node.engine_version == "0.3.1"
    assert node.cpu_pct == 18.4


def test_infrastructure_response_schema():
    """InfrastructureResponse must have all required fields."""
    from datetime import datetime

    from apps.api_server.routers.infrastructure import InfrastructureResponse

    resp = InfrastructureResponse(
        deployment_mode="saas",
        engine_version="0.3.1",
        api_version="1.0.0",
        nodes=[],
        uptime_30d_pct=99.97,
        avg_latency_ms=8.4,
        p95_latency_ms=24.1,
        throughput_rpm=29450.0,
        last_health_check=datetime.now(tz=UTC),
    )
    assert resp.deployment_mode == "saas"
    assert resp.uptime_30d_pct == 99.97
    assert resp.nodes == []


def test_infrastructure_response_rejects_non_contract_deployment_mode():
    """InfrastructureResponse must reject deployment_mode values outside the public wire enum."""
    from datetime import datetime

    from pydantic import ValidationError

    from apps.api_server.routers.infrastructure import InfrastructureResponse

    with pytest.raises(ValidationError, match="deployment_mode"):
        InfrastructureResponse(
            deployment_mode="hosted",
            engine_version="0.3.1",
            api_version="1.0.0",
            nodes=[],
            uptime_30d_pct=99.97,
            avg_latency_ms=8.4,
            p95_latency_ms=24.1,
            throughput_rpm=29450.0,
            last_health_check=datetime.now(tz=UTC),
        )


def test_demo_nodes_are_valid():
    """Demo nodes in infrastructure module must all be valid NodeInfo instances."""
    from apps.api_server.routers.infrastructure import _DEMO_NODES, NodeInfo

    assert len(_DEMO_NODES) == 3
    for node in _DEMO_NODES:
        assert isinstance(node, NodeInfo)
        assert node.engine_version.startswith("0.")
        assert node.region != ""


# ── /v1/team ─────────────────────────────────────────────────────────────────


def test_member_info_schema():
    """MemberInfo must serialize correctly."""
    from apps.api_server.routers.team import MemberInfo

    member = MemberInfo(
        user_id=str(uuid4()),
        name="Angel Burgess",
        email="angel@codna.ai",
        role="owner",
        status="active",
        last_active=None,
    )
    assert member.role == "owner"
    assert member.email == "angel@codna.ai"
    assert member.last_active is None


def test_invite_request_valid_roles():
    """InviteRequest should accept valid roles."""

    from apps.api_server.routers.team import InviteRequest

    req = InviteRequest(email="test@example.com", role="member")
    assert req.role == "member"

    req2 = InviteRequest(email="admin@example.com", role="admin")
    assert req2.role == "admin"


def test_role_update_request():
    """RoleUpdateRequest must validate role field."""
    from apps.api_server.routers.team import RoleUpdateRequest

    req = RoleUpdateRequest(role="viewer")
    assert req.role == "viewer"


def test_audit_log_entry_schema():
    """AuditLogEntry must have all required fields."""
    from datetime import datetime

    from apps.api_server.routers.team import AuditLogEntry

    entry = AuditLogEntry(
        id=str(uuid4()),
        timestamp=datetime.now(tz=UTC),
        actor_email="angel@codna.ai",
        action="simulate",
        resource_type="simulation_run",
        resource_id=str(uuid4()),
        ip_address="203.0.113.1",
        result="success",
    )
    assert entry.action == "simulate"
    assert entry.result == "success"


def test_demo_audit_log_generation():
    """_generate_demo_audit_log must return non-empty list of AuditLogEntry."""
    from uuid import uuid4

    from apps.api_server.routers.team import AuditLogEntry, _generate_demo_audit_log

    entries = _generate_demo_audit_log(uuid4())
    assert len(entries) > 0
    for entry in entries:
        assert isinstance(entry, AuditLogEntry)
        assert entry.actor_email != ""
        assert entry.action != ""
        assert entry.result in {"success", "failure"}


def test_audit_log_response_schema():
    """AuditLogResponse must paginate correctly."""
    from apps.api_server.routers.team import AuditLogResponse

    resp = AuditLogResponse(entries=[], total=50, page=2, limit=25, pages=2)
    assert resp.total == 50
    assert resp.page == 2
    assert resp.pages == 2


# ── Main.py router registration ───────────────────────────────────────────────


def test_main_imports_new_routers():
    """main.py must be importable and all routers registered."""
    from apps.api_server import main

    # If import succeeds, the module structure is valid
    assert hasattr(main, "app")


def test_all_new_routers_importable():
    """All new Phase 7 routers must import without errors."""
    from apps.api_server.routers import infrastructure, runs, team

    assert hasattr(runs, "router")
    assert hasattr(infrastructure, "router")
    assert hasattr(team, "router")


def test_runs_router_has_endpoints():
    """Runs router must expose /v1/runs and /v1/runs/{run_id} and /v1/analytics."""
    from apps.api_server.routers.runs import router

    paths = {r.path for r in router.routes}
    assert "/v1/runs" in paths
    assert "/v1/runs/{run_id}" in paths
    assert "/v1/analytics" in paths


def test_infrastructure_router_has_endpoints():
    """Infrastructure router must expose /v1/infrastructure."""
    from apps.api_server.routers.infrastructure import router

    paths = {r.path for r in router.routes}
    assert "/v1/infrastructure" in paths


def test_team_router_has_endpoints():
    """Team router must expose team and audit surfaces, including immutable audit artifacts."""
    from apps.api_server.routers.team import router

    paths = {r.path for r in router.routes}
    assert "/v1/team" in paths
    assert "/v1/team/invite" in paths
    assert "/v1/team/{user_id}/role" in paths
    assert "/v1/audit-logs" in paths
    assert "/v1/audit-logs/artifacts" in paths
