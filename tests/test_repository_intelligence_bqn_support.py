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
    repository_intelligence_bqn_parser_dispatch as repository_bqn_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    bqn_analysis_support as repository_bqn_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    bqn_primitives as repository_bqn_primitives,
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


def test_repository_intelligence_bqn_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["bqn"] is (
        repository_bqn_parser_dispatch._parse_bqn_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["bqn"] is (
        repository_bqn_parser_dispatch._parse_bqn_dependencies_only
    )


def test_repository_intelligence_bqn_helpers_are_modularized() -> None:
    assert repository_service.bqn_adapter.has_bqn_path_hints is (
        repository_bqn_primitives.has_bqn_path_hints
    )
    assert repository_service.bqn_adapter.is_probable_bqn_source is (
        repository_bqn_analysis_support.is_probable_bqn_source
    )
    assert repository_service.bqn_adapter.iter_dependency_entries is (
        repository_bqn_primitives.iter_dependency_entries
    )
    assert repository_service.bqn_adapter.resolve_import_module is (
        repository_bqn_analysis_support.resolve_import_module
    )
    assert repository_service.bqn_adapter.parse_file is (
        repository_bqn_analysis_support.parse_file
    )


def test_bqn_adapter_parse_file_extracts_imports_and_symbol_references() -> None:
    text = 'helper ← •Import "lib/helper.bqn"\nrun ← { helper 1 }\n'

    symbols, dependencies, references = repository_service.bqn_adapter.parse_file(
        "main.bqn",
        text,
        {"lib/helper.bqn": "lib/helper.bqn"},
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "lib/helper.bqn" and dependency.target_symbol == "helper"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "run" for symbol in symbols)
    assert any(
        reference.target_file == "lib/helper.bqn" and reference.target_names == ("helper",)
        for reference in references
    )


def test_bqn_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".bqn" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("lib/csv.bqn"),
            text='Split ← { 𝕊⁼𝕩: Join𝕩 ; helper ← •Import "core.bqn" }\n',
        )
        == "bqn"
    )
    assert (
        repository_service._language_for_path(
            Path("docs/notes.bqn"),
            text="plain notes without bqn syntax\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_bqn_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "bqn-profile-repo"
    repo_path.mkdir(parents=True)
    for index in range(6):
        (repo_path / f"lib_{index}.bqn").write_text(
            'helper ← •Import "core.bqn"\nrun ← { helper 1 }\n',
            encoding="utf-8",
        )
    (repo_path / "core.bqn").write_text("core ← {𝕩}\n", encoding="utf-8")
    (repo_path / "scripts").mkdir(parents=True)
    for index in range(2):
        (repo_path / "scripts" / f"helper_{index}.py").write_text(
            "print('helper')\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "bqn" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "bqn"


def test_repository_snapshot_graph_contains_bqn_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "bqn-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "main.bqn").write_text(
        "helper ← {1}\n"
        "run ← { helper 𝕩 }\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.bqn"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    helper_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "main.bqn" and str(row["symbol_name"]) == "helper"
    )

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph
    )
