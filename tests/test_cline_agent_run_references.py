from __future__ import annotations

from pathlib import Path

from apps.api_server.services.cline_agent_run_references import (
    collect_agent_run_references,
)
from apps.api_server.services.cline_proof_common import write_json


def test_collect_agent_run_references_reads_summary_artifact_entries(
    tmp_path: Path,
) -> None:
    summary_path = write_json(
        tmp_path / "build" / "python_sdk_integration_summary.json",
        {
            "agent_run_references": [
                {"run_id": "run_001", "agent_run_id": "agent_001"},
                {"run_id": "run_001", "agent_run_id": "agent_001"},
            ],
            "details": {
                "agent_run_references": [
                    {"session_id": "session_001", "run_dir": "build/proofs/cline/runs/run_001"}
                ]
            },
        },
    )

    references = collect_agent_run_references(
        root=tmp_path,
        summary_artifacts=["build/python_sdk_integration_summary.json"],
    )

    assert references == [
        {
            "source_artifact": str(summary_path),
            "run_id": "run_001",
            "agent_run_id": "agent_001",
        },
        {
            "source_artifact": str(summary_path),
            "session_id": "session_001",
            "run_dir": "build/proofs/cline/runs/run_001",
        },
    ]


def test_collect_agent_run_references_falls_back_to_live_run_proof(
    tmp_path: Path,
) -> None:
    live_run_proof_path = write_json(
        tmp_path / "build" / "proofs" / "cline" / "live_run_proof.json",
        {
            "run_id": "live_run_proof",
            "agent_run_id": "agent_live_001",
            "session_id": "session_live_001",
            "run_dir": "build/proofs/cline/runs/session_live_001",
        },
    )

    references = collect_agent_run_references(
        root=tmp_path,
        summary_artifacts=["build/missing_summary.json"],
    )

    assert references == [
        {
            "source_artifact": str(live_run_proof_path),
            "run_id": "live_run_proof",
            "agent_run_id": "agent_live_001",
            "session_id": "session_live_001",
            "run_dir": "build/proofs/cline/runs/session_live_001",
        }
    ]
