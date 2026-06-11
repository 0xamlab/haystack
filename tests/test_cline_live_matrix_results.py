from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from apps.api_server.services.cline_live_matrix_results import (
    build_live_matrix_results_artifact,
)
from apps.api_server.services.cline_live_matrix_selection import (
    ClineLiveMatrixArtifacts,
)
from apps.api_server.services.cline_proof_common import (
    CLINE_DOCS_SNAPSHOT_HASH_PATH,
    CLINE_DOCS_SNAPSHOT_PATH,
    read_json,
    sha256_hex,
)


ROOT = Path(__file__).resolve().parents[1]


def _write_docs_snapshot(root: Path) -> None:
    snapshot_text = "\n".join(
        [
            "ClineCore",
            "Sessions",
            "Events",
            "Permission Handling",
            "Writing Plugins",
            "MCP",
            "ACP",
            "GitHub",
        ]
    )
    snapshot_path = root / CLINE_DOCS_SNAPSHOT_PATH
    snapshot_hash_path = root / CLINE_DOCS_SNAPSHOT_HASH_PATH
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(snapshot_text, encoding="utf-8")
    snapshot_hash_path.write_text(sha256_hex(snapshot_text), encoding="utf-8")


def test_build_live_matrix_results_artifact_reports_ready_without_external_runtime_env(
    tmp_path: Path,
) -> None:
    _write_docs_snapshot(tmp_path)

    payload = build_live_matrix_results_artifact(root=tmp_path, env={})

    assert payload["status"] == "ready_for_execution"
    assert payload["blockers"] == []
    assert payload["required_environment"] == []
    assert payload["environment_status"]["anthropic_api_key"] is False
    assert payload["selected_language_count"] > 0
    assert payload["live_progress_percent"] == 0.0
    assert payload["results"] == []


def test_build_live_matrix_results_artifact_reports_ready_when_environment_present(
    tmp_path: Path,
) -> None:
    _write_docs_snapshot(tmp_path)

    payload = build_live_matrix_results_artifact(
        root=tmp_path,
        env={
            "ANTHROPIC_API_KEY": "test-key",
        },
    )

    assert payload["status"] == "ready_for_execution"
    assert payload["blockers"] == []
    assert payload["selected_language_count"] > 0
    assert payload["live_progress_percent"] == 0.0


def test_generate_cline_live_matrix_results_script_writes_artifact(tmp_path: Path) -> None:
    _write_docs_snapshot(tmp_path)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/generate_cline_live_matrix_results.py",
            "--root",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = read_json(tmp_path / "build/proofs/cline/live_matrix_results.json")
    assert payload["status"] == "ready_for_execution"


def test_build_live_matrix_results_artifact_executes_selected_languages(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_docs_snapshot(tmp_path)
    adapter_registry_path = tmp_path / "build" / "proofs" / "cline" / "adapter_registry.json"
    live_matrix_selection_path = tmp_path / "build" / "proofs" / "cline" / "live_matrix_selection.json"
    adapter_registry_path.parent.mkdir(parents=True, exist_ok=True)
    selection_payload = {
        "selected_live_languages": [
            {
                "language": "python",
                "rank": 1,
                "adapter_family": "python_language",
                "selection_reason": "top_24",
            },
            {
                "language": "typescript",
                "rank": 2,
                "adapter_family": "js_like",
                "selection_reason": "top_24",
            },
        ]
    }
    monkeypatch.setattr(
        "apps.api_server.services.cline_live_matrix_results.build_cline_live_matrix_artifacts",
        lambda **_: ClineLiveMatrixArtifacts(
            adapter_registry_path=adapter_registry_path,
            adapter_registry_payload={},
            live_matrix_selection_path=live_matrix_selection_path,
            live_matrix_selection_payload=selection_payload,
        ),
    )

    observed_targets: list[str] = []

    def _fake_collect(**kwargs):
        observed_targets.append(kwargs["target_file"])
        return {
            "status": "passed",
            "session_id": f"session_{kwargs['language']}",
            "agent_run_id": f"agent_{kwargs['language']}",
            "terminal_state": "succeeded",
            "artifact_path": str(
                Path("build")
                / "proofs"
                / "cline"
                / "live_matrix_runs"
                / f"{kwargs['language']}.json"
            ),
            "runtime_manifest": {
                "backend": {
                    "provider": "algenta-proof",
                    "model": "algenta/gpt-proof-model",
                }
            },
            "usage": {
                "usage": {
                    "inputTokens": 10,
                    "outputTokens": 2,
                    "cacheReadTokens": 1,
                    "cacheWriteTokens": 3,
                }
            },
            "tool_calls": {
                "govern_hook": {"status": "observed"},
                "tool_calls_by_name": {
                    "localize": {"count": 1},
                    "graph_query": {"count": 1},
                    "simulate_patch": {"count": 1},
                },
            },
            "engine_requests": {
                "triage_calls": 1,
                "graph_query_calls": 1,
                "simulate_patch_calls": 2,
            },
            "gate": {
                "terminal_state": "succeeded",
                "apply_allowed": True,
            },
        }

    payload = build_live_matrix_results_artifact(
        root=tmp_path,
        execute=True,
        live_run_collector=_fake_collect,
    )

    assert payload["status"] == "passed"
    assert payload["execution_mode"] == "local_proof"
    assert payload["executed_run_count"] == 2
    assert payload["failed_run_count"] == 0
    assert payload["live_progress_percent"] == 100.0
    assert len(payload["results"]) == 2
    assert payload["results"][0]["usage"]["input_tokens"] == 10
    assert payload["results"][0]["engine_calls_by_name"]["simulate_patch"] == 2
    assert payload["results"][0]["govern_hook_status"] == "observed"
    assert observed_targets == [
        "matrix/001_python/main.py",
        "matrix/002_typescript/main.ts",
    ]
