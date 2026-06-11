from __future__ import annotations

from pathlib import Path

from apps.api_server.services.cline_proof_common import (
    create_artifact_provenance,
    validate_artifact_provenance,
)


class _Context:
    git_commit = "git123"
    runtime_version = "runtime123"
    parity_ledger_hash = "ledger123"
    source_tree_dirty = False
    cline_docs_snapshot_hash = "docs123"
    vendored_cline_commit = "vendored123"
    algenta_commit = "algenta123"


def test_validate_artifact_provenance_rejects_unredacted_secret_fields() -> None:
    payload = {
        **create_artifact_provenance(
            _Context(),  # type: ignore[arg-type]
            run_id="run_001",
            schema_version="example/v1",
        ),
        "headers": {"authorization": "Bearer live-secret"},
    }

    errors = validate_artifact_provenance(
        payload=payload,
        context=_Context(),  # type: ignore[arg-type]
        artifact_path=Path("artifact.json"),
        allow_dirty_tree=False,
    )

    assert any("unredacted secret field" in error for error in errors)


def test_validate_artifact_provenance_allows_approvals_authorization_metadata() -> None:
    payload = {
        **create_artifact_provenance(
            _Context(),  # type: ignore[arg-type]
            run_id="run_001",
            schema_version="example/v1",
        ),
        "authorization": {
            "caller": "alice",
            "workflow_identity": "workflow/repo",
            "repository_allowed": True,
            "branch_allowed": True,
        },
    }

    errors = validate_artifact_provenance(
        payload=payload,
        context=_Context(),  # type: ignore[arg-type]
        artifact_path=Path("approvals.json"),
        allow_dirty_tree=False,
    )

    assert not errors
