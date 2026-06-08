"""Tests for repository_intelligence_service: repository_graph.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_repository_graph_query_returns_dependency_and_dependent_view(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _graph_neighbor_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    response = repository_service.query_repository_graph(
        connector=connector,
        request=repository_service.RepositoryGraphQueryRequest(
            snapshot_id=snapshot.snapshot_id,
            file_path="src/worker.py",
            direction="both",
            max_depth=2,
        ),
    )

    assert response.seed_file_paths == ["src/worker.py"]
    assert response.direct_dependents == ["src/main.py"]
    assert response.impacted_files[:2] == ["src/worker.py", "src/main.py"]
    assert response.top_change_risk_files[0].file_path == "src/worker.py"


def test_repository_graph_query_resolves_symbol_seed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _typescript_barrel_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    response = repository_service.query_repository_graph(
        connector=connector,
        request=repository_service.RepositoryGraphQueryRequest(
            snapshot_id=snapshot.snapshot_id,
            symbol_name="usefulHelper",
            direction="inbound",
            max_depth=2,
        ),
    )

    assert "src/common/shared.ts" in response.seed_file_paths
    assert "src/app/main.ts" in response.direct_dependents
    assert any(item.top_symbol == "usefulHelper" for item in response.top_change_risk_files)


def test_repository_graph_query_promotes_wrapper_seed_to_actionable_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _typescript_barrel_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    response = repository_service.query_repository_graph(
        connector=connector,
        request=repository_service.RepositoryGraphQueryRequest(
            snapshot_id=snapshot.snapshot_id,
            file_path="src/common/index.ts",
            direction="both",
            max_depth=2,
        ),
    )

    assert response.seed_file_paths == ["src/common/shared.ts"]
    assert "src/app/main.ts" in response.direct_dependents
    assert response.top_change_risk_files[0].file_path == "src/common/shared.ts"


def test_repository_graph_query_promotes_config_seed_to_nearby_actionable_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _typescript_rootdir_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=[
                "services/app",
                "packages/common",
                "services/app/tsconfig.test.json",
                "services/app/tsconfig.json",
            ],
            include_patterns=[
                "services/**/*.ts",
                "services/**/*.json",
                "packages/**/*.ts",
                "packages/**/*.json",
            ],
        ),
    )

    response = repository_service.query_repository_graph(
        connector=connector,
        request=repository_service.RepositoryGraphQueryRequest(
            snapshot_id=snapshot.snapshot_id,
            file_path="services/app/tsconfig.test.json",
            direction="both",
            max_depth=2,
        ),
    )

    assert response.seed_file_paths == ["services/app/src/index.ts"]
    assert response.direct_dependencies == ["packages/common/src/shared.ts"]
    assert response.top_change_risk_files[0].file_path == "services/app/src/index.ts"


def test_repository_graph_query_existing_lookup_skips_recomputation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _graph_neighbor_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    first = repository_service.query_repository_graph(
        connector=connector,
        request=repository_service.RepositoryGraphQueryRequest(
            snapshot_id=snapshot.snapshot_id,
            file_path="src/worker.py",
            direction="both",
            max_depth=2,
        ),
    )

    def _fail_load_snapshot_manifest(**_kwargs: object) -> dict[str, object]:
        raise AssertionError("cached graph query should not reload the snapshot manifest")

    monkeypatch.setattr(
        repository_service,
        "_load_snapshot_manifest",
        _fail_load_snapshot_manifest,
    )

    second = repository_service.query_repository_graph(
        connector=connector,
        request=repository_service.RepositoryGraphQueryRequest(
            snapshot_id=snapshot.snapshot_id,
            file_path="src/worker.py",
            direction="both",
            max_depth=2,
        ),
    )

    assert second.model_dump(mode="json") == first.model_dump(mode="json")


def test_repository_graph_query_uses_workspace_evidence_bundle_seed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
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
        ),
    )

    response = repository_service.query_repository_graph(
        connector=connector,
        request=repository_service.RepositoryGraphQueryRequest(
            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
            direction="both",
            max_depth=2,
        ),
    )

    assert response.seed_file_paths == ["src/service.py"]
    assert response.direct_dependents == ["tests/test_service.py"]
    assert response.top_change_risk_files[0].file_path == "src/service.py"


def test_repository_graph_query_workspace_evidence_bundle_snapshot_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    first_snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )
    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=first_snapshot.snapshot_id,
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
        ),
    )
    second_snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(ref="HEAD"),
    )

    with pytest.raises(repository_service.RepositoryIntelligenceError) as excinfo:
        repository_service.query_repository_graph(
            connector=connector,
            request=repository_service.RepositoryGraphQueryRequest(
                snapshot_id=second_snapshot.snapshot_id,
                workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
                direction="both",
                max_depth=2,
            ),
        )

    assert excinfo.value.code == "repository_graph_query_snapshot_mismatch"


