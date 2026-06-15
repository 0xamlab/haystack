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
    repository_intelligence_pawn_parser_dispatch as repository_intelligence_pawn_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    pawn_analysis_support as repository_pawn_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    pawn_primitives as repository_pawn_primitives,
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


def test_repository_intelligence_pawn_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["pawn"] is (
        repository_intelligence_pawn_parser_dispatch._parse_pawn_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["pawn"] is (
        repository_intelligence_pawn_parser_dispatch._parse_pawn_dependencies_only
    )


def test_repository_intelligence_pawn_helpers_are_modularized() -> None:
    assert repository_service.pawn_adapter.has_pawn_path_hints is (
        repository_pawn_primitives.has_pawn_path_hints
    )
    assert repository_service.pawn_adapter.is_probable_pawn_source is (
        repository_pawn_analysis_support.is_probable_pawn_source
    )
    assert repository_service.pawn_adapter.iter_dependency_entries is (
        repository_pawn_primitives.iter_dependency_entries
    )
    assert repository_service.pawn_adapter.module_aliases_for_path is (
        repository_pawn_analysis_support.module_aliases_for_path
    )
    assert repository_service.pawn_adapter.parse_file is (
        repository_pawn_analysis_support.parse_file
    )


def test_pawn_adapter_parse_file_extracts_include_dependencies_and_references() -> None:
    module_index = {
        "helpers.inc": "helpers.inc",
        "filterscripts/helpers.inc": "filterscripts/helpers.inc",
    }
    text = (
        '#include "helpers.inc"\n'
        "stock Helper() {\n    return 1;\n}\n"
        "public Run() {\n    Helper();\n    return 1;\n}\n"
    )

    symbols, dependencies, references = repository_service.pawn_adapter.parse_file(
        "main.pwn",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "helpers.inc" for dependency in dependencies)
    assert any(symbol.symbol_name == "Helper" for symbol in symbols)
    assert any(reference.target_names == ("Helper",) for reference in references)


def test_pawn_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".pwn" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("gamemodes/main.pwn"),
            text="public OnGameModeInit() {\n    return 1;\n}\n",
        )
        == "pawn"
    )
    assert (
        repository_service._language_for_path(
            Path("filterscripts/helpers.inc"),
            text="#include <a_samp>\nstock Helper() {\n    return 1;\n}\n",
        )
        == "pawn"
    )
    assert (
        repository_service._language_for_path(
            Path("gamemodes/main.pwn"),
            text="plain notes without pawn markers\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_pawn_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "pawn-profile-repo"
    (repo_path / "gamemodes").mkdir(parents=True)
    for index in range(6):
        (repo_path / "gamemodes" / f"mode_{index}.pwn").write_text(
            f"public Run{index}() {{\n    return {index};\n}}\n",
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

    assert "pawn" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "pawn"


def test_repository_snapshot_graph_contains_pawn_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "pawn-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "main.pwn").write_text(
        "stock Helper() {\n    return 1;\n}\n"
        "public Run() {\n    Helper();\n    return 1;\n}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.pwn", "*.inc"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    helper_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "main.pwn" and str(row["symbol_name"]) == "Helper"
    )

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph
    )
