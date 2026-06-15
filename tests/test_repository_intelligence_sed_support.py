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
    repository_intelligence_sed_parser_dispatch as repository_intelligence_sed_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    sed_analysis_support as repository_sed_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    sed_primitives as repository_sed_primitives,
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


def test_repository_intelligence_sed_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["sed"] is (
        repository_intelligence_sed_parser_dispatch._parse_sed_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["sed"] is (
        repository_intelligence_sed_parser_dispatch._parse_sed_dependencies_only
    )


def test_repository_intelligence_sed_helpers_are_modularized() -> None:
    assert repository_service.sed_adapter.has_sed_path_hints is (
        repository_sed_primitives.has_sed_path_hints
    )
    assert repository_service.sed_adapter.is_probable_sed_source is (
        repository_sed_analysis_support.is_probable_sed_source
    )
    assert repository_service.sed_adapter.iter_dependency_entries is (
        repository_sed_primitives.iter_dependency_entries
    )
    assert repository_service.sed_adapter.module_aliases_for_path is (
        repository_sed_analysis_support.module_aliases_for_path
    )
    assert repository_service.sed_adapter.parse_file is repository_sed_analysis_support.parse_file


def test_sed_adapter_parse_file_extracts_label_references() -> None:
    symbols, dependencies, references = repository_service.sed_adapter.parse_file(
        "fix.sed",
        ":loop\ns/cat/dog/g\nt loop\n",
        {},
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert not dependencies
    assert any(symbol.symbol_name == "loop" for symbol in symbols)
    assert any(reference.target_names == ("loop",) for reference in references)


def test_sed_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".sed" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("rules/fix.sed"),
            text=":loop\ns/cat/dog/g\nt loop\n",
        )
        == "sed"
    )
    assert (
        repository_service._language_for_path(
            Path("rules/fix.sed"),
            text="plain notes without sed commands\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_sed_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "sed-profile-repo"
    (repo_path / "rules").mkdir(parents=True)
    for index in range(6):
        (repo_path / "rules" / f"rule_{index}.sed").write_text(
            f":loop{index}\ns/foo/bar/g\nt loop{index}\n",
            encoding="utf-8",
        )
    (repo_path / "tools").mkdir(parents=True)
    for index in range(2):
        (repo_path / "tools" / f"helper_{index}.py").write_text("print('helper')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "sed" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "sed"


def test_repository_snapshot_graph_contains_sed_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "sed-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "fix.sed").write_text(
        ":loop\ns/cat/dog/g\nt loop\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.sed"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    loop_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "fix.sed" and str(row["symbol_name"]) == "loop"
    )

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{loop_symbol_id}"
        for row in graph
    )
