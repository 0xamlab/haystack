from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from apps.api_server.services.cline_live_run_proof import collect_live_run_proof


ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None or shutil.which("bun") is None,
    reason="node and bun are required for the live Cline proof run",
)


def test_collect_live_run_proof_emits_real_engine_and_plugin_evidence(tmp_path: Path) -> None:
    payload = collect_live_run_proof(
        root=ROOT,
        output_path=tmp_path / "live_run_proof.json",
    )

    assert payload["status"] == "passed"
    assert payload["terminal_state"] == "succeeded"
    assert payload["runtime_manifest"]["runtime"]["kind"] == "cline"
    assert payload["runtime_manifest"]["engine"]["enabled"] is True
    assert payload["runtime_manifest"]["plugins"]["simulate_patch"] == "loaded"
    assert payload["tool_calls"]["tool_calls_by_name"]["localize"]["count"] == 1
    assert payload["tool_calls"]["tool_calls_by_name"]["graph_query"]["count"] == 1
    assert payload["tool_calls"]["tool_calls_by_name"]["simulate_patch"]["count"] == 1
    assert payload["tool_calls"]["govern_hook"]["status"] == "observed"
    assert payload["engine_requests"]["triage_calls"] == 1
    assert payload["engine_requests"]["graph_query_calls"] == 1
    assert payload["engine_requests"]["simulate_patch_calls"] >= 2
    assert payload["engine_requests"]["all_authorized"] is True
    assert payload["gate"]["terminal_state"] == "succeeded"
    assert payload["approvals"]["approval_events"]
    assert "beta" in payload["proof_repository_file"]["content"]
