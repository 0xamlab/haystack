from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from apps.api_server.services.cline_proof_bundle import (
    _collect_or_reuse_competitive_report,
    build_cline_proof_bundle,
)
from apps.api_server.services.cline_proof_common import (
    CLINE_DOCS_SNAPSHOT_HASH_PATH,
    CLINE_DOCS_SNAPSHOT_PATH,
    sha256_hex,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_cline_proof_bundle.py"


def _write_docs_snapshot(root: Path) -> None:
    snapshot_text = "\n".join(
        [
            "ClineCore",
            "Sessions",
            "Events",
            "Permission Handling",
            "Writing Plugins",
            "Hooks",
            "MCP",
            "ACP: Editor Integrations",
            "GitHub Actions Integration",
            "GitHub PR Review",
            "Multi-Agent Teams",
            "Scheduled Agents",
        ]
    )
    snapshot_path = root / CLINE_DOCS_SNAPSHOT_PATH
    snapshot_hash_path = root / CLINE_DOCS_SNAPSHOT_HASH_PATH
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(snapshot_text, encoding="utf-8")
    snapshot_hash_path.write_text(sha256_hex(snapshot_text), encoding="utf-8")


def _runtime_contract_payload() -> dict[str, object]:
    return {
        "artifact_path": "build/proofs/cline/runtime_contract_report.json",
        "runtime_manifest": {
            "status_code": 200,
            "payload": {
                "runtime": {
                    "kind": "cline",
                    "is_stub": False,
                }
            },
        },
        "session_contract": {
            "create": {"status_code": 201},
            "list": {"status_code": 200},
            "get": {"status_code": 200},
            "messages": {"status_code": 200},
            "usage": {"status_code": 200},
            "events": {"status_code": 200},
            "events_ndjson": {"status_code": 200},
            "events_sse": {"status_code": 200},
            "start": {
                "status_code": 409,
                "payload": {
                    "error": {
                        "code": "session_start_failed",
                        "message": "no API key in env for provider",
                    }
                },
            },
            "run_compatibility": {"status_code": 200, "final_frame_present": True},
            "delete": {"status_code": 200},
        },
    }


def _stage_status(payload: dict[str, object], stage_name: str) -> dict[str, object]:
    return next(stage for stage in payload["stage_results"] if stage["stage"] == stage_name)


def test_build_cline_proof_bundle_orchestrates_requested_stages(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_docs_snapshot(tmp_path)
    observed_order: list[str] = []

    def _runtime_contract(*, root):
        assert root == tmp_path
        observed_order.append("runtime_contract")
        return _runtime_contract_payload()

    def _live_run_proof(*, root):
        assert root == tmp_path
        observed_order.append("live_run_proof")
        return {
            "artifact_path": "build/proofs/cline/live_run_proof.json",
            "status": "passed",
            "terminal_state": "succeeded",
        }

    def _live_matrix(*, root, env, execute, max_languages):
        assert root == tmp_path
        assert execute is True
        assert max_languages == 3
        observed_order.append("live_matrix")
        return {
            "status": "passed",
            "blockers": [],
        }

    def _parity(*, root, allow_offline_live_docs, allow_dirty_tree):
        assert root == tmp_path
        assert allow_offline_live_docs is True
        assert allow_dirty_tree is False
        observed_order.append("parity")
        return (
            {"status": "passed"},
            {
                "status": "passed",
                "unresolved_required_capabilities": [],
            },
            {"status": "passed"},
        )

    def _competitive(**kwargs):
        assert kwargs["root"] == tmp_path
        assert kwargs["execute_competitive"] is True
        assert kwargs["cursor_repetitions"] == 5
        assert kwargs["warm_repetitions"] == 4
        observed_order.append("competitive")
        return {
            "artifact_path": "build/proofs/cline/competitive_experience_report.json",
            "status": "passed",
            "blockers": [],
            "source_validation_errors": [],
        }

    monkeypatch.setattr(
        "apps.api_server.services.cline_proof_bundle.collect_runtime_contract_report",
        _runtime_contract,
    )
    monkeypatch.setattr(
        "apps.api_server.services.cline_proof_bundle.collect_live_run_proof",
        _live_run_proof,
    )
    monkeypatch.setattr(
        "apps.api_server.services.cline_proof_bundle.build_live_matrix_results_artifact",
        _live_matrix,
    )
    monkeypatch.setattr(
        "apps.api_server.services.cline_proof_bundle.build_cline_parity_artifacts",
        _parity,
    )
    monkeypatch.setattr(
        "apps.api_server.services.cline_proof_bundle._collect_or_reuse_competitive_report",
        _competitive,
    )

    payload = build_cline_proof_bundle(
        root=tmp_path,
        execute_live_matrix=True,
        max_live_matrix_languages=3,
        execute_competitive=True,
        cursor_repetitions=5,
        warm_repetitions=4,
        env={"ANTHROPIC_API_KEY": "test-key"},
    )

    assert observed_order == [
        "runtime_contract",
        "live_run_proof",
        "live_matrix",
        "parity",
        "competitive",
    ]
    assert payload["status"] == "passed"
    assert payload["requested_stage_count"] == 5
    assert payload["passed_requested_stage_count"] == 5
    assert payload["progress_percent"] == 100.0
    assert _stage_status(payload, "competitive")["requested"] is True
    assert payload["artifacts"]["runtime_contract_report"] == "build/proofs/cline/runtime_contract_report.json"
    assert payload["artifacts"]["competitive_experience_report"] == (
        "build/proofs/cline/competitive_experience_report.json"
    )


def test_build_cline_proof_bundle_clears_stale_owned_outputs_before_regeneration(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_docs_snapshot(tmp_path)
    stale_runtime_contract = tmp_path / "build" / "proofs" / "cline" / "runtime_contract_report.json"
    stale_runs_file = tmp_path / "build" / "proofs" / "cline" / "runs" / "stale" / "runtime_manifest.json"
    stale_runtime_contract.parent.mkdir(parents=True, exist_ok=True)
    stale_runtime_contract.write_text("stale", encoding="utf-8")
    stale_runs_file.parent.mkdir(parents=True, exist_ok=True)
    stale_runs_file.write_text("stale", encoding="utf-8")

    def _runtime_contract(*, root):
        assert root == tmp_path
        raise RuntimeError("runtime contract boom")

    def _live_run_proof(*, root):
        assert root == tmp_path
        raise RuntimeError("live run boom")

    def _live_matrix(**_kwargs):
        return {
            "status": "ready_for_execution",
            "blockers": [],
        }

    def _parity(**_kwargs):
        return (
            {"status": "failed"},
            {
                "status": "failed",
                "unresolved_required_capabilities": ["runtime.truth.manifest"],
            },
            {"status": "failed"},
        )

    def _competitive(**_kwargs):
        return {
            "artifact_path": "build/proofs/cline/competitive_experience_report.json",
            "status": "blocked_missing_benchmark_artifacts",
            "blockers": ["missing benchmark artifact file"],
            "source_validation_errors": [],
        }

    monkeypatch.setattr(
        "apps.api_server.services.cline_proof_bundle.collect_runtime_contract_report",
        _runtime_contract,
    )
    monkeypatch.setattr(
        "apps.api_server.services.cline_proof_bundle.collect_live_run_proof",
        _live_run_proof,
    )
    monkeypatch.setattr(
        "apps.api_server.services.cline_proof_bundle.build_live_matrix_results_artifact",
        _live_matrix,
    )
    monkeypatch.setattr(
        "apps.api_server.services.cline_proof_bundle.build_cline_parity_artifacts",
        _parity,
    )
    monkeypatch.setattr(
        "apps.api_server.services.cline_proof_bundle._collect_or_reuse_competitive_report",
        _competitive,
    )

    payload = build_cline_proof_bundle(root=tmp_path)

    assert payload["status"] == "failed"
    assert payload["progress_percent"] == 25.0
    assert not stale_runtime_contract.exists()
    assert not (tmp_path / "build" / "proofs" / "cline" / "runs").exists()
    assert "runtime contract boom" in str(_stage_status(payload, "runtime_contract")["error"])
    assert "live run boom" in str(_stage_status(payload, "live_run_proof")["error"])


def test_generate_cline_proof_bundle_script_exposes_bundle_flags() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--execute-live-matrix" in completed.stdout
    assert "--execute-competitive" in completed.stdout
    assert "--review-live-docs" in completed.stdout


def test_collect_or_reuse_competitive_report_executes_live_collectors_with_local_api_key(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_docs_snapshot(tmp_path)
    g0_artifact = write_json(
        tmp_path / "build/proofs/cline/g0_token_benchmark.json",
        {"schema_version": "cline-g0-benchmark-results/v1"},
    )
    observed: list[tuple[str, object, object, object]] = []

    def _cursor(*, api_key, root, g0_artifact_path, repetitions):
        observed.append(("cursor", api_key, root, repetitions))
        assert Path(g0_artifact_path) == g0_artifact
        write_json(
            tmp_path / "build/proofs/cline/cursor_mcp_comparison.json",
            {"schema_version": "cline-cursor-mcp-comparison/v1"},
        )
        return {"status": "passed"}

    def _warm(*, root, g0_artifact_path, warm_repetitions):
        observed.append(("warm", root, g0_artifact_path, warm_repetitions))
        write_json(
            tmp_path / "build/proofs/cline/warm_cache_comparison.json",
            {"schema_version": "cline-warm-cache-comparison/v1"},
        )
        return {"status": "passed"}

    def _validated(*, root, allow_dirty_tree, g0_artifact_path):
        return (
            {"benchmark_suite": "g0_token_benchmark"},
            [],
            {
                "g0_artifact": Path(g0_artifact_path),
                "cursor_mcp_artifact": tmp_path / "build/proofs/cline/cursor_mcp_comparison.json",
                "warm_cache_artifact": tmp_path / "build/proofs/cline/warm_cache_comparison.json",
            },
        )

    def _report(*, benchmark_input, root):
        assert benchmark_input["benchmark_suite"] == "g0_token_benchmark"
        return {
            "status": "passed",
            "artifact_path": "build/proofs/cline/competitive_experience_report.json",
            "blockers": [],
            "source_validation_errors": [],
        }

    monkeypatch.setattr(
        "apps.api_server.services.cline_proof_bundle.collect_live_cursor_mcp_comparison_artifact",
        _cursor,
    )
    monkeypatch.setattr(
        "apps.api_server.services.cline_proof_bundle.collect_live_warm_cache_comparison_artifact",
        _warm,
    )
    monkeypatch.setattr(
        "apps.api_server.services.cline_proof_bundle._validated_competitive_input",
        _validated,
    )
    monkeypatch.setattr(
        "apps.api_server.services.cline_proof_bundle.build_competitive_experience_report",
        _report,
    )

    payload = _collect_or_reuse_competitive_report(
        root=tmp_path,
        allow_dirty_tree=True,
        execute_competitive=True,
        cursor_repetitions=6,
        warm_repetitions=2,
        g0_artifact_path=g0_artifact,
        env={"ALGENTA_API_KEY": "local-live-key"},
    )

    assert payload["status"] == "passed"
    assert observed == [
        ("cursor", "local-live-key", tmp_path, 6),
        ("warm", tmp_path, g0_artifact, 2),
    ]


def test_collect_or_reuse_competitive_report_blocks_when_local_api_key_missing(
    tmp_path: Path,
) -> None:
    _write_docs_snapshot(tmp_path)
    g0_artifact = write_json(
        tmp_path / "build/proofs/cline/g0_token_benchmark.json",
        {"schema_version": "cline-g0-benchmark-results/v1"},
    )

    payload = _collect_or_reuse_competitive_report(
        root=tmp_path,
        allow_dirty_tree=True,
        execute_competitive=True,
        cursor_repetitions=4,
        warm_repetitions=3,
        g0_artifact_path=g0_artifact,
        env={"ANTHROPIC_API_KEY": "anthropic-key"},
    )

    assert payload["status"] == "blocked_missing_benchmark_artifacts"
    assert any(
        "ALGENTA_API_KEY or DE_API_KEY" in blocker
        for blocker in payload["blockers"]
    )
    written = json.loads(
        (tmp_path / "build/proofs/cline/competitive_experience_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert written["status"] == "blocked_missing_benchmark_artifacts"
