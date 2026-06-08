"""Tests for repository_intelligence_service: repository_triage.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_repository_triage_existing_lookup_skips_retriage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )
    request = RepositoryTriageRequest(
        snapshot_id=snapshot.snapshot_id,
        signals={
            "issue_text": "handle_request crashes when user is null",
            "diagnostics": [
                {
                    "path": "src/service.py",
                    "line": 2,
                    "severity": "error",
                    "message": "AttributeError: 'NoneType' object has no attribute 'name'",
                }
            ],
        },
    )

    first = repository_service.triage_repository(connector=connector, request=request)
    triage_path = repository_service._triage_dir(
        str(connector.org_id),
        str(connector.id),
    ) / f"{first.workspace_evidence_bundle_ref}.json"

    def _unexpected_materialized_snapshot(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("triage fast path should reuse the persisted evidence bundle")

    monkeypatch.setattr(
        repository_service,
        "materialized_snapshot",
        _unexpected_materialized_snapshot,
    )
    original_read_json = repository_service._read_json

    def _read_json_without_triage_manifest(path: Path) -> dict[str, Any]:
        if Path(path) == triage_path:
            raise AssertionError("triage fast path should not reopen the triage manifest")
        return original_read_json(path)

    monkeypatch.setattr(repository_service, "_read_json", _read_json_without_triage_manifest)
    second = repository_service.triage_repository(connector=connector, request=request)

    assert second.workspace_evidence_bundle_ref == first.workspace_evidence_bundle_ref
    assert second.evidence_items == first.evidence_items


def test_repository_triage_propagates_graph_neighbor_risk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _graph_neighbor_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=snapshot.snapshot_id,
            signals={
                "issue_text": "fragile_helper fails on malformed whitespace input",
                "diagnostics": [
                    {
                        "path": "src/worker.py",
                        "line": 2,
                        "severity": "error",
                        "message": "ValueError raised inside fragile_helper",
                    }
                ],
            },
            max_evidence_items=4,
        ),
    )

    assert triage.suspect_files[0] == "src/worker.py"
    assert "src/main.py" in triage.suspect_files


def test_repository_triage_lifts_related_diagnostic_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _typescript_rootdir_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    related_path = repo_path / "packages" / "common" / "src" / "shared.ts"
    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=snapshot.snapshot_id,
            signals={
                "issue_text": "TypeScript rootDir drift",
                "diagnostics": [
                    {
                        "path": "services/app/src/index.ts",
                        "line": 1,
                        "severity": "error",
                        "code": "TS6059",
                        "message": (
                            f"File '{related_path}' is not under 'rootDir' "
                            f"'{repo_path / 'services' / 'app'}'. 'rootDir' is expected "
                            "to contain all source files."
                        ),
                    }
                ],
            },
            max_evidence_items=4,
        ),
    )

    assert triage.suspect_files[0] == "packages/common/src/shared.ts"
    assert triage.evidence_items[0].file_path == "packages/common/src/shared.ts"
    assert triage.evidence_items[0].symbol_name == "shared"


def test_repository_triage_penalizes_typescript_barrel_wrappers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _typescript_barrel_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    related_path = repo_path / "src" / "common" / "shared.ts"
    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=snapshot.snapshot_id,
            signals={
                "issue_text": "Helper import crosses a wrapper barrel",
                "diagnostics": [
                    {
                        "path": "src/common/index.ts",
                        "line": 1,
                        "severity": "error",
                        "code": "TS6059",
                        "message": (
                            f"File '{related_path}' is not under 'rootDir' "
                            f"'{repo_path / 'src' / 'app'}'. 'rootDir' is expected "
                            "to contain all source files."
                        ),
                    }
                ],
            },
            max_evidence_items=4,
        ),
    )

    assert triage.suspect_files[0] == "src/common/shared.ts"
    assert "src/common/index.ts" in triage.suspect_files
    assert triage.evidence_items[0].symbol_name == "usefulHelper"


