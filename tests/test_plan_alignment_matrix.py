from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from apps.plan_alignment import collect_plan_alignment_snapshot

ROOT = Path(__file__).resolve().parents[1]


def test_plan_alignment_snapshot_tracks_planned_public_llm_routes_truthfully() -> None:
    snapshot = collect_plan_alignment_snapshot()
    routes = {(item.method, item.path): item for item in snapshot.public_llm_routes}

    assert len(routes) == 18
    assert routes[("GET", "/v1/models")].status == "implemented"
    assert routes[("POST", "/v1/tokenize")].status == "implemented"
    assert routes[("POST", "/v1/count_tokens")].status == "implemented"
    assert routes[("POST", "/v1/decisions/plan")].status == "implemented"

    assert routes[("POST", "/v1/chat/completions")].status == "implemented"
    assert routes[("POST", "/v1/responses")].status == "implemented"
    assert routes[("POST", "/v1/embeddings")].status == "implemented"
    assert routes[("POST", "/v1/rerank")].status == "implemented"
    assert routes[("GET", "/v1/agent/runs")].status == "implemented"
    assert routes[("POST", "/v1/agent/runs")].status == "implemented"
    assert routes[("GET", "/v1/agent/runs/checkpoints")].status == "implemented"
    assert routes[("GET", "/v1/agent/runs/mission-events")].status == "implemented"
    assert routes[("GET", "/v1/agent/runs/telemetry")].status == "implemented"
    assert routes[("GET", "/v1/agent/runs/{run_id}")].status == "implemented"
    assert routes[("GET", "/v1/agent/runs/{run_id}/events")].status == "implemented"
    assert routes[("POST", "/v1/agent/runs/{run_id}/resume")].status == "implemented"
    assert routes[("POST", "/v1/agent/runs/{run_id}/cancel")].status == "implemented"
    assert routes[("POST", "/v1/agent/runs/{run_id}/approve")].status == "implemented"


def test_plan_alignment_snapshot_tracks_immediate_pr_sequence_truthfully() -> None:
    snapshot = collect_plan_alignment_snapshot()
    tranches = {item.pr: item for item in snapshot.immediate_pr_sequence}

    assert len(tranches) == 13
    assert tranches["PR 0"].status == "implemented"
    assert tranches["PR 1"].status == "implemented"
    assert tranches["PR 2"].status == "implemented"
    assert tranches["PR 3"].status == "implemented"
    assert tranches["PR 4"].status == "implemented"
    assert tranches["PR 5"].status == "partial"
    assert tranches["PR 6"].status == "implemented"
    assert tranches["PR 7"].status == "missing"
    assert tranches["PR 8"].status == "implemented"
    assert tranches["PR 9"].status == "implemented"
    assert tranches["PR 10"].status == "implemented"
    assert tranches["PR 11"].status == "implemented"
    assert tranches["PR 12"].status == "implemented"
    assert "apps/api_server/services/llm_provider_service.py" in tranches["PR 5"].evidence
    assert "apps/api_server/routers/llm.py" in tranches["PR 5"].evidence
    assert "packages/ts-sdk/src/client.ts" in tranches["PR 8"].evidence
    assert "packages/ts-sdk/src/runtime.ts" in tranches["PR 8"].evidence
    assert "apps/runtime_manifest.py" in tranches["PR 9"].evidence
    assert "packages/ts-sdk/src/client.ts" in tranches["PR 9"].evidence
    assert "tests/integration/test_openapi.py" in tranches["PR 9"].evidence
    assert "apps/cli/main.py" in tranches["PR 10"].evidence
    assert "apps/mcp_server/tools/control_plane.py" in tranches["PR 10"].evidence
    assert "apps/mcp_server/tools/deployments.py" in tranches["PR 10"].evidence
    assert "packages/ts-sdk/src/runtime.ts" in tranches["PR 10"].evidence
    assert "tests/integration/test_mcp_server.py" in tranches["PR 10"].evidence
    assert "packages/ts-sdk/src/runtime.ts" in tranches["PR 11"].evidence
    assert "tests/integration/test_openapi.py" in tranches["PR 11"].evidence
    assert "packages/ts-sdk/src/runtime.ts" in tranches["PR 12"].evidence
    assert "apps/mcp_server/tools/deployments.py" in tranches["PR 12"].evidence


def test_emit_plan_alignment_matrix_writes_expected_artifact(tmp_path: Path) -> None:
    del tmp_path
    artifact = ROOT / "build" / "plan_alignment_matrix.json"
    if artifact.exists():
        artifact.unlink()

    subprocess.run(
        [sys.executable, "scripts/emit_plan_alignment_matrix.py"],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    route_status = {(item["method"], item["path"]): item["status"] for item in payload["public_llm_routes"]}
    tranche_status = {item["pr"]: item["status"] for item in payload["immediate_pr_sequence"]}

    assert route_status[("GET", "/v1/models")] == "implemented"
    assert route_status[("POST", "/v1/chat/completions")] == "implemented"
    assert route_status[("POST", "/v1/responses")] == "implemented"
    assert route_status[("POST", "/v1/embeddings")] == "implemented"
    assert route_status[("POST", "/v1/rerank")] == "implemented"
    assert route_status[("POST", "/v1/decisions/plan")] == "implemented"
    assert tranche_status["PR 0"] == "implemented"
    assert tranche_status["PR 3"] == "implemented"
    assert tranche_status["PR 5"] == "partial"
    assert tranche_status["PR 6"] == "implemented"
    assert tranche_status["PR 8"] == "implemented"
    assert tranche_status["PR 9"] == "implemented"
    assert tranche_status["PR 10"] == "implemented"
    assert tranche_status["PR 11"] == "implemented"
    assert tranche_status["PR 12"] == "implemented"
    assert tranche_status["PR 7"] == "missing"
