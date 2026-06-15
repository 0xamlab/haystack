from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

import pyarrow.parquet as pq

from apps.api_server.schemas.repositories import RepositorySnapshotCreateRequest
from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_hoon_parser_dispatch as repository_intelligence_hoon_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    hoon_analysis_support as repository_hoon_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    hoon_primitives as repository_hoon_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def _connector_for_repo(repo_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        owner_key_id=None,
        connector_type=SimpleNamespace(value="local_repo"),
        config_json=json.dumps({"path": str(repo_path)}),
    )


def _init_git_repo(repo_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(repo_path)], check=True)
    subprocess.run(["git", "-C", str(repo_path), "config", "user.name", "Repo Test"], check=True)
    subprocess.run(
        ["git", "-C", str(repo_path), "config", "user.email", "repo-test@example.com"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo_path), "commit", "-qm", "Initial commit"], check=True)


def test_repository_intelligence_hoon_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["hoon"] is (
        repository_intelligence_hoon_parser_dispatch._parse_hoon_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["hoon"] is (
        repository_intelligence_hoon_parser_dispatch._parse_hoon_dependencies_only
    )


def test_repository_intelligence_hoon_helpers_are_modularized() -> None:
    assert repository_service.hoon_adapter.has_hoon_path_hints is (
        repository_hoon_primitives.has_hoon_path_hints
    )
    assert repository_service.hoon_adapter.is_probable_hoon_source is (
        repository_hoon_analysis_support.is_probable_hoon_source
    )
    assert repository_service.hoon_adapter.iter_dependency_entries is (
        repository_hoon_primitives.iter_dependency_entries
    )
    assert repository_service.hoon_adapter.resolve_import_module is (
        repository_hoon_analysis_support.resolve_import_module
    )
    assert repository_service.hoon_adapter.parse_file is (
        repository_hoon_analysis_support.parse_file
    )


def test_hoon_adapter_parse_file_extracts_imports_and_symbol_references() -> None:
    text = "/+  helper\n|%\n++  run\n  (helper 42)\n--\n"

    symbols, dependencies, references = repository_service.hoon_adapter.parse_file(
        "tests/run/main.hoon",
        text,
        {"tests/run/helper.hoon": "tests/run/helper.hoon"},
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(symbol.symbol_name == "run" for symbol in symbols)
    assert any(
        dependency.target_file == "tests/run/helper.hoon" and dependency.target_symbol == "helper"
        for dependency in dependencies
    )
    assert any(
        reference.target_file == "tests/run/helper.hoon"
        and reference.target_names == ("helper",)
        for reference in references
    )


def test_hoon_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".hoon" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("tests/lib/keygen.hoon"),
            text="/+  *test, keygen\n=,  keygen\n|%\n++  test-child-seed-from-seed-0\n  %+  expect-eq\n--\n",
        )
        == "hoon"
    )
    assert (
        repository_service._language_for_path(
            Path("tests/lib/notes.hoon"),
            text="plain notes without hoon syntax\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_hoon_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "hoon-profile-repo"
    (repo_path / "pkg" / "arvo" / "app").mkdir(parents=True)
    for index in range(6):
        (repo_path / "pkg" / "arvo" / "app" / f"app_{index}.hoon").write_text(
            "/+  helper\n|%\n++  run\n  (helper 42)\n--\n",
            encoding="utf-8",
        )
    (repo_path / "pkg" / "interface" / "src").mkdir(parents=True)
    for index in range(2):
        (repo_path / "pkg" / "interface" / "src" / f"helper_{index}.ts").write_text(
            "export const helper = 1;\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "hoon" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "hoon"


def test_repository_snapshot_graph_contains_hoon_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "hoon-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "main.hoon").write_text(
        "|%\n"
        "++  helper\n"
        "  42\n"
        "++  run\n"
        "  (helper)\n"
        "--\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.hoon"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    helper_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "main.hoon" and str(row["symbol_name"]) == "helper"
    )

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph
    )
