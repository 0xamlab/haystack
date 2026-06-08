"""Tests for repository_intelligence_service: repository_snapshot_a.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_repository_snapshot_and_triage_are_deterministic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )
    snapshot_repeat = repository_service.create_repository_snapshot(
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
                "failing_tests": ["tests/test_service.py"],
                "changed_files": ["src/service.py"],
            },
        ),
    )

    assert snapshot.snapshot_id == snapshot_repeat.snapshot_id
    assert snapshot_repeat.status == "existing"
    assert triage.suspect_files[0] == "src/service.py"
    assert triage.workspace_evidence_bundle_ref
    assert triage.evidence_bundle_token_count > 0
    assert triage.reduction_ratio >= 1.0
    assert triage.suspect_symbols[0] == "handle_request"
    assert "handle_request" in triage.suspect_symbols
    assert triage.evidence_items[0].symbol_name == "handle_request"


def test_repository_snapshot_existing_lookup_skips_reanalysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )
    manifest_path = repository_service._snapshot_paths(
        str(connector.org_id),
        str(connector.id),
        snapshot.snapshot_id,
    )["manifest"]

    def _unexpected_iter_repository_files(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("snapshot fast path should reuse the persisted lookup index")

    monkeypatch.setattr(repository_service, "_iter_repository_files", _unexpected_iter_repository_files)
    original_read_json = repository_service._read_json

    def _read_json_without_snapshot_manifest(path: Path) -> dict[str, Any]:
        if Path(path) == manifest_path:
            raise AssertionError("snapshot fast path should not reopen the snapshot manifest")
        return original_read_json(path)

    monkeypatch.setattr(repository_service, "_read_json", _read_json_without_snapshot_manifest)

    snapshot_repeat = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    assert snapshot_repeat.snapshot_id == snapshot.snapshot_id
    assert snapshot_repeat.status == "existing"


def test_repository_snapshot_engine_revision_invalidation_rebuilds_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    baseline = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    monkeypatch.setattr(
        repository_service,
        "_REPOSITORY_INTELLIGENCE_ENGINE_REVISION",
        "repository-intelligence-test-revision-r2",
    )

    rebuilt = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    assert rebuilt.status == "created"
    assert rebuilt.snapshot_id != baseline.snapshot_id


def test_repository_snapshot_tracks_dirty_git_worktree_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    baseline = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    target_file = repo_path / "src" / "service.py"
    target_file.write_text(
        "def handle_request(user):\n    return user.email\n",
        encoding="utf-8",
    )

    dirty_snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    assert dirty_snapshot.status == "created"
    assert dirty_snapshot.snapshot_id != baseline.snapshot_id
    assert dirty_snapshot.resolved_revision != baseline.resolved_revision


def test_repository_snapshot_reuses_shared_file_analysis_across_connectors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    first_connector = _connector_for_repo(repo_path)
    second_connector = _connector_for_repo(repo_path)

    first_snapshot = repository_service.create_repository_snapshot(
        connector=first_connector,
        request=RepositorySnapshotCreateRequest(),
    )

    def _unexpected_analyze_file(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("shared file-analysis cache should avoid reparsing unchanged files")

    monkeypatch.setattr(repository_service, "_analyze_file", _unexpected_analyze_file)

    second_snapshot = repository_service.create_repository_snapshot(
        connector=second_connector,
        request=RepositorySnapshotCreateRequest(),
    )

    assert first_snapshot.status == "created"
    assert second_snapshot.status == "created"
    assert second_snapshot.snapshot_id != first_snapshot.snapshot_id
    assert second_snapshot.file_count == first_snapshot.file_count


def test_repository_snapshot_reuses_shared_file_selection_across_archive_connectors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    archive_path = _sample_archive(tmp_path)
    first_connector = _connector_for_archive(archive_path)
    second_connector = _connector_for_archive(archive_path)

    first_snapshot = repository_service.create_repository_snapshot(
        connector=first_connector,
        request=RepositorySnapshotCreateRequest(),
    )

    def _unexpected_iter_repository_files(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("archive file-selection cache should avoid rescanning extracted files")

    monkeypatch.setattr(repository_service, "_iter_repository_files", _unexpected_iter_repository_files)

    second_snapshot = repository_service.create_repository_snapshot(
        connector=second_connector,
        request=RepositorySnapshotCreateRequest(),
    )

    assert first_snapshot.status == "created"
    assert second_snapshot.status == "created"
    assert second_snapshot.snapshot_id != first_snapshot.snapshot_id
    assert second_snapshot.file_count == first_snapshot.file_count


def test_repository_snapshot_uses_git_blob_hashes_for_clean_tracked_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    original_hash_file = repository_service._hash_file

    def _unexpected_hash_file(path: Path) -> str:
        try:
            path.relative_to(repo_path)
        except ValueError:
            return original_hash_file(path)
        raise AssertionError(f"clean tracked git file should use git blob hash: {path}")

    monkeypatch.setattr(repository_service, "_hash_file", _unexpected_hash_file)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    assert snapshot.status == "created"
    assert snapshot.file_count == 2


def test_repository_snapshot_only_reanalyzes_changed_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    target_file = repo_path / "src" / "service.py"
    target_file.write_text(
        "def handle_request(user):\n    return user.email\n",
        encoding="utf-8",
    )

    original_analyze_file = repository_service._analyze_file
    analyzed_paths: list[str] = []

    def _tracking_analyze_file(*args, **kwargs):  # type: ignore[no-untyped-def]
        analyzed_paths.append(str(kwargs["path"].relative_to(kwargs["root_path"])))
        return original_analyze_file(*args, **kwargs)

    monkeypatch.setattr(repository_service, "_analyze_file", _tracking_analyze_file)

    updated_snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    assert updated_snapshot.status == "created"
    assert analyzed_paths == ["src/service.py"]


def test_repository_snapshot_hashes_only_dirty_git_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    target_file = repo_path / "src" / "service.py"
    target_file.write_text(
        "def handle_request(user):\n    return user.email\n",
        encoding="utf-8",
    )

    original_hash_file = repository_service._hash_file
    hashed_paths: list[str] = []

    def _tracking_hash_file(path: Path) -> str:
        try:
            hashed_paths.append(str(path.relative_to(repo_path)))
        except ValueError:
            return original_hash_file(path)
        return original_hash_file(path)

    monkeypatch.setattr(repository_service, "_hash_file", _tracking_hash_file)

    updated_snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    assert updated_snapshot.status == "created"
    assert hashed_paths == ["src/service.py", "src/service.py"]


def test_repository_snapshot_falls_back_from_unwritable_default_runtime_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ALGENTA_RUNTIME_DIR", raising=False)
    monkeypatch.setattr(repository_runtime, "_RUNTIME_FALLBACK_CACHE", None)
    fallback_runtime_dir = tmp_path / "workspace-runtime"
    default_home = tmp_path / "home"
    default_runtime_dir = (default_home / ".algenta" / "runtime").resolve()
    monkeypatch.setattr(repository_runtime.Path, "home", staticmethod(lambda: default_home))
    monkeypatch.setattr(
        repository_runtime,
        "_runtime_fallback_candidates",
        lambda: [fallback_runtime_dir],
    )
    monkeypatch.setattr(
        repository_runtime,
        "_runtime_dir_writable",
        lambda path: path.resolve() != default_runtime_dir,
    )

    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    manifest = repository_service._load_snapshot_manifest(
        org_id=str(connector.org_id),
        repository_id=str(connector.id),
        snapshot_id=snapshot.snapshot_id,
    )
    storage_path = Path(manifest["repository_snapshot_artifact"]["storage_path"])
    assert str(storage_path).startswith(str(fallback_runtime_dir.resolve()))
    assert fallback_runtime_dir.exists()


def test_repository_snapshot_focus_paths_bound_analysis_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "focused-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "src" / "service.py").write_text(
        "def important_handler() -> str:\n    return 'ok'\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "worker.py").write_text(
        "def background_worker() -> str:\n    return 'worker'\n",
        encoding="utf-8",
    )
    (repo_path / "docs" / "runbook.md").write_text(
        "# Runbook\n\nThis file should not be indexed in the focused snapshot.\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    focused_snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src/service.py"],
            max_total_bytes=4_096,
        ),
    )

    assert focused_snapshot.file_count == 1
    assert focused_snapshot.language_counts == {"python": 1}
    manifest = repository_service._load_snapshot_manifest(
        org_id=str(connector.org_id),
        repository_id=str(connector.id),
        snapshot_id=focused_snapshot.snapshot_id,
    )
    assert manifest["focus_paths"] == ["src/service.py"]
    assert manifest["requested_focus_paths"] == ["src/service.py"]
    assert manifest["effective_focus_paths"] == ["src/service.py"]
    assert [entry["file_path"] for entry in manifest["files"]] == ["src/service.py"]


def test_repository_snapshot_compacts_redundant_broad_focus_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "compact-focus-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "service.py").write_text(
        "def important_handler() -> str:\n    return 'ok'\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "worker.py").write_text(
        "def background_worker() -> str:\n    return 'worker'\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "src/service.py", "src/worker.py"],
        ),
    )

    manifest = repository_service._load_snapshot_manifest(
        org_id=str(connector.org_id),
        repository_id=str(connector.id),
        snapshot_id=snapshot.snapshot_id,
    )
    assert snapshot.file_count == 2
    assert manifest["requested_focus_paths"] == ["src", "src/service.py", "src/worker.py"]
    assert manifest["effective_focus_paths"] == ["src/service.py", "src/worker.py"]
    assert manifest["focus_paths"] == ["src/service.py", "src/worker.py"]


def test_repository_snapshot_preserves_broad_focus_when_it_covers_unique_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "preserve-focus-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "service.py").write_text(
        "def important_handler() -> str:\n    return 'ok'\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "worker.py").write_text(
        "def background_worker() -> str:\n    return 'worker'\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "src/service.py"],
        ),
    )

    manifest = repository_service._load_snapshot_manifest(
        org_id=str(connector.org_id),
        repository_id=str(connector.id),
        snapshot_id=snapshot.snapshot_id,
    )
    assert snapshot.file_count == 2
    assert manifest["requested_focus_paths"] == ["src", "src/service.py"]
    assert manifest["effective_focus_paths"] == ["src", "src/service.py"]
    assert manifest["focus_paths"] == ["src", "src/service.py"]


def test_repository_snapshot_prefer_concrete_focus_paths_drops_broad_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "prefer-concrete-focus-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "service.py").write_text(
        "def important_handler() -> str:\n    return 'ok'\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "worker.py").write_text(
        "def background_worker() -> str:\n    return 'worker'\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src", "src/service.py"],
            prefer_concrete_focus_paths=True,
        ),
    )

    manifest = repository_service._load_snapshot_manifest(
        org_id=str(connector.org_id),
        repository_id=str(connector.id),
        snapshot_id=snapshot.snapshot_id,
    )
    assert snapshot.file_count == 1
    assert manifest["requested_focus_paths"] == ["src", "src/service.py"]
    assert manifest["effective_focus_paths"] == ["src/service.py"]
    assert manifest["prefer_concrete_focus_paths"] is True


def test_repository_snapshot_excludes_nested_generated_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "generated-output-repo"
    (repo_path / "services" / "api" / "src").mkdir(parents=True)
    (repo_path / "services" / "api" / "dist_fresh").mkdir(parents=True)
    (repo_path / "services" / "api" / "src" / "main.ts").write_text(
        "export const value = 1;\n",
        encoding="utf-8",
    )
    (repo_path / "services" / "api" / "dist_fresh" / "main.js").write_text(
        "exports.value = 1;\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["services/api"],
            include_patterns=["services/**/*.ts", "services/**/*.js"],
        ),
    )

    manifest = repository_service._load_snapshot_manifest(
        org_id=str(connector.org_id),
        repository_id=str(connector.id),
        snapshot_id=snapshot.snapshot_id,
    )
    assert snapshot.file_count == 1
    assert [entry["file_path"] for entry in manifest["files"]] == ["services/api/src/main.ts"]


def test_repository_snapshot_includes_control_files_and_skips_binary_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "mixed-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "service.py").write_text(
        "def run() -> str:\n    return 'ok'\n",
        encoding="utf-8",
    )
    (repo_path / "Dockerfile").write_text(
        "FROM python:3.12-slim\nCOPY . /app\n",
        encoding="utf-8",
    )
    (repo_path / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    manifest = repository_service._load_snapshot_manifest(
        org_id=str(connector.org_id),
        repository_id=str(connector.id),
        snapshot_id=snapshot.snapshot_id,
    )
    assert sorted(entry["file_path"] for entry in manifest["files"]) == [
        "Dockerfile",
        "src/service.py",
    ]


def test_repository_snapshot_persists_uncompressed_source_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    manifest = repository_service._load_snapshot_manifest(
        org_id=str(connector.org_id),
        repository_id=str(connector.id),
        snapshot_id=snapshot.snapshot_id,
    )
    source_archive_path = Path(manifest["source_archive_path"])

    assert source_archive_path.name == "source.tar"
    with repository_service.materialized_snapshot(manifest) as extracted_root:
        assert (extracted_root / "src" / "service.py").read_text(encoding="utf-8") == (
            repo_path / "src" / "service.py"
        ).read_text(encoding="utf-8")


def test_repository_snapshot_does_not_rehash_parquet_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _sample_repo(tmp_path)
    connector = _connector_for_repo(repo_path)
    original_hash_file = repository_service._hash_file
    hashed_paths: list[str] = []

    def _tracking_hash_file(path: Path) -> str:
        hashed_paths.append(Path(path).name)
        return original_hash_file(path)

    monkeypatch.setattr(repository_service, "_hash_file", _tracking_hash_file)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(),
    )

    assert snapshot.status == "created"
    assert "source.tar" in hashed_paths
    assert not any(path.endswith(".parquet") for path in hashed_paths)


def test_repository_snapshot_graph_contains_symbol_parent_child_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "graph-symbol-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    target_path = repo_path / "services" / "app" / "src" / "main.ts"
    target_path.write_text(
        "export class Planner {\n"
        "  build(): string {\n"
        "    function finalize(value: string): string {\n"
        "      return value.toUpperCase();\n"
        "    }\n"
        "    return finalize('ok');\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["services/app/src/main.ts"],
            include_patterns=["services/**/*.ts"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {str(row["symbol_name"]): str(row["symbol_id"]) for row in symbol_rows}

    assert any(
        str(row["edge_type"]) == "contains_symbol"
        and str(row["source_node"]) == f"symbol:{symbol_ids['Planner']}"
        and str(row["target_node"]) == f"symbol:{symbol_ids['build']}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "contains_symbol"
        and str(row["source_node"]) == f"symbol:{symbol_ids['build']}"
        and str(row["target_node"]) == f"symbol:{symbol_ids['finalize']}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "graph-reference-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    (repo_path / "services" / "app" / "src" / "util.ts").write_text(
        "export function helper(): string {\n"
        "  return 'ok';\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "src" / "main.ts").write_text(
        "import { helper } from './util';\n"
        "\n"
        "export const run = (): string => {\n"
        "  function finalize(value: string): string {\n"
        "    return `${helper()}-${value}`;\n"
        "  }\n"
        "  return finalize('ok');\n"
        "};\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["services/app/src"],
            include_patterns=["services/**/*.ts"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    run_symbol_id = symbol_ids[("services/app/src/main.ts", "run")]
    finalize_symbol_id = symbol_ids[("services/app/src/main.ts", "finalize")]
    helper_symbol_id = symbol_ids[("services/app/src/util.ts", "helper")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{finalize_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{run_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{finalize_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


def test_repository_snapshot_graph_contains_python_symbol_reference_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "python-graph-reference-repo"
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "app" / "util.py").write_text(
        "def helper() -> str:\n"
        "    return 'ok'\n",
        encoding="utf-8",
    )
    (repo_path / "app" / "main.py").write_text(
        "from app.util import helper\n\n"
        "class Planner:\n"
        "    def finish(self, value: str) -> str:\n"
        "        return value.upper()\n\n"
        "    def build(self) -> str:\n"
        "        return self.finish(helper())\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["app"],
            include_patterns=["app/*.py", "app/**/*.py"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    import pyarrow.parquet as pq

    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    build_symbol_id = symbol_ids[("app/main.py", "build")]
    finish_symbol_id = symbol_ids[("app/main.py", "finish")]
    helper_symbol_id = symbol_ids[("app/util.py", "helper")]

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{build_symbol_id}"
        and str(row["target_node"]) == f"symbol:{finish_symbol_id}"
        for row in graph_rows
    )
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{build_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph_rows
    )


