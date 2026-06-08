from __future__ import annotations

from tests.integration.live_repository_fixture import (
    live_repository_fixture,
    local_repository_live_support_reason,
)


def test_live_repository_fixture_creates_expected_repository_contract() -> None:
    with live_repository_fixture("fixture-test") as fixture:
        assert fixture.root_path.exists()
        assert (fixture.root_path / ".git").exists()
        assert fixture.connector_request["connector_type"] == "local_repo"
        assert fixture.connector_request["config"]["path"] == str(fixture.root_path)
        assert fixture.snapshot_request["include_patterns"] == [
            "src/**",
            "tests/**",
            "README.md",
        ]
        assert fixture.snapshot_request["max_files"] == 128
        assert fixture.primary_file == "src/service.py"
        assert fixture.failing_test == "tests/test_service.py::test_normalize_status_open"
        triage_request = fixture.triage_request("snapshot_live_123")
        assert triage_request["snapshot_id"] == "snapshot_live_123"
        assert triage_request["signals"]["changed_files"] == ["src/service.py"]
        assert triage_request["signals"]["diagnostics"][0]["line"] == 4
        assert triage_request["signals"]["diagnostics"][0]["severity"] == "error"
        graph_query_request = fixture.graph_query_request(
            "snapshot_live_123",
            "bundle_live_123",
        )
        assert graph_query_request == {
            "snapshot_id": "snapshot_live_123",
            "workspace_evidence_bundle_ref": "bundle_live_123",
            "file_path": "src/service.py",
            "symbol_name": "normalize_status",
            "direction": "both",
            "max_depth": 2,
            "max_nodes": 64,
        }
        apply_local_branch_request = fixture.apply_local_branch_request(
            "snapshot_live_123",
            "decision_plan_live_123",
            "simulation_live_123",
            branch_name="algenta/test-live-fixture",
        )
        assert apply_local_branch_request == {
            "snapshot_id": "snapshot_live_123",
            "decision_plan_id": "decision_plan_live_123",
            "simulation_id": "simulation_live_123",
            "mode": "local_branch",
            "write_permission": True,
            "branch_name": "algenta/test-live-fixture",
        }
        assert (
            fixture.root_path / "src" / "service.py"
        ).read_text(encoding="utf-8").count("return \"closed\"") == 1


def test_local_repository_live_support_reason_requires_local_base_url() -> None:
    assert local_repository_live_support_reason("http://127.0.0.1:8000") is None
    assert local_repository_live_support_reason("http://localhost:8000") is None
    reason = local_repository_live_support_reason("https://api.algenta.ai")
    assert reason is not None
    assert "local API base URL" in reason
