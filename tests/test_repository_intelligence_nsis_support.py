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
    repository_intelligence_nsis_parser_dispatch as repository_intelligence_nsis_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    nsis_analysis_support as repository_nsis_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    nsis_primitives as repository_nsis_primitives,
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


def test_repository_intelligence_nsis_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["nsis"] is (
        repository_intelligence_nsis_parser_dispatch._parse_nsis_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["nsis"] is (
        repository_intelligence_nsis_parser_dispatch._parse_nsis_dependencies_only
    )


def test_repository_intelligence_nsis_helpers_are_modularized() -> None:
    assert repository_service.nsis_adapter.has_nsis_path_hints is (
        repository_nsis_primitives.has_nsis_path_hints
    )
    assert repository_service.nsis_adapter.is_probable_nsis_source is (
        repository_nsis_analysis_support.is_probable_nsis_source
    )
    assert repository_service.nsis_adapter.module_aliases_for_path is (
        repository_nsis_analysis_support.module_aliases_for_path
    )
    assert repository_service.nsis_adapter.parse_dependencies_only is (
        repository_nsis_analysis_support.parse_dependencies_only
    )
    assert repository_service.nsis_adapter.parse_file is repository_nsis_analysis_support.parse_file


def test_nsis_adapter_parse_file_extracts_include_dependencies_and_references() -> None:
    module_index = {
        "include/shared.nsh": "include/shared.nsh",
        "SharedMacro": "include/shared.nsh",
    }
    script_text = (
        '!include "include/shared.nsh"\n'
        "!insertmacro SharedMacro\n"
        "Function Helper\n"
        "FunctionEnd\n"
        "Function Install\n"
        "  Call Helper\n"
        "FunctionEnd\n"
    )

    symbols, dependencies, references = repository_service.nsis_adapter.parse_file(
        "installer/setup.nsi",
        script_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "include/shared.nsh" and dependency.dependency_type == "include"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "Helper" for symbol in symbols)
    assert any(reference.target_names == ("SharedMacro",) for reference in references)
    assert any(reference.target_names == ("Helper",) for reference in references)


def test_nsis_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".nsi" in repository_service._TEXT_FILE_SUFFIXES
    assert ".nsh" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("installer/setup.nsi"),
            text='Name "Demo"\nOutFile "Demo.exe"\nSection "Install"\nSectionEnd\n',
        )
        == "nsis"
    )
    assert (
        repository_service._language_for_path(
            Path("include/shared.nsh"),
            text="!macro SharedMacro\n!macroend\n",
        )
        == "nsis"
    )
    assert (
        repository_service._language_for_path(
            Path("notes/setup.nsi"),
            text="plain notes only\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_nsis_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nsis-profile-repo"
    (repo_path / "installer").mkdir(parents=True)
    (repo_path / "include").mkdir(parents=True)
    for index in range(5):
        (repo_path / "installer" / f"setup_{index}.nsi").write_text(
            'Name "Demo"\n'
            f'OutFile "demo_{index}.exe"\n'
            f'Section "Install{index}" SEC_{index}\n'
            "SectionEnd\n",
            encoding="utf-8",
        )
    (repo_path / "include" / "shared.nsh").write_text(
        "!macro SharedMacro\n!macroend\n",
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

    assert "nsis" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "nsis"


def test_repository_snapshot_graph_contains_nsis_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "nsis-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "setup.nsi").write_text(
        "Function Helper\n"
        "FunctionEnd\n"
        "Function Install\n"
        "  Call Helper\n"
        "FunctionEnd\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.nsi"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    helper_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "setup.nsi" and str(row["symbol_name"]) == "Helper"
    )

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph
    )
