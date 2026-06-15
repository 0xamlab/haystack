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
    repository_intelligence_angelscript_parser_dispatch as repository_angelscript_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    angelscript_analysis_support as repository_angelscript_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    angelscript_primitives as repository_angelscript_primitives,
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


def test_repository_intelligence_angelscript_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["angelscript"] is (
        repository_angelscript_parser_dispatch._parse_angelscript_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["angelscript"] is (
        repository_angelscript_parser_dispatch._parse_angelscript_dependencies_only
    )


def test_repository_intelligence_angelscript_helpers_are_modularized() -> None:
    assert repository_service.angelscript_adapter.strip_comments is (
        repository_angelscript_primitives.strip_comments
    )
    assert repository_service.angelscript_adapter.has_angelscript_path_hints is (
        repository_angelscript_primitives.has_angelscript_path_hints
    )
    assert repository_service.angelscript_adapter.is_probable_angelscript_source is (
        repository_angelscript_analysis_support.is_probable_angelscript_source
    )
    assert repository_service.angelscript_adapter.module_aliases_for_path is (
        repository_angelscript_analysis_support.module_aliases_for_path
    )
    assert repository_service.angelscript_adapter.parse_dependencies_only is (
        repository_angelscript_analysis_support.parse_dependencies_only
    )
    assert repository_service.angelscript_adapter.parse_file is (
        repository_angelscript_analysis_support.parse_file
    )


def test_angelscript_adapter_module_aliases_include_namespace_type_and_function_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "angelscript-alias-repo"
    (repo_path / "Scripts").mkdir(parents=True)
    (repo_path / "Scripts" / "Main.as").write_text(
        "namespace Demo {\n"
        "class Runner {\n"
        "    void boot() {\n"
        "    }\n"
        "}\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.angelscript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Scripts/Main.as",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Scripts/Main.as" in aliases
    assert "Main" in aliases
    assert "Scripts.Main" in aliases
    assert "Runner" in aliases
    assert "Demo::Runner" in aliases
    assert "boot" in aliases


def test_angelscript_adapter_parse_file_extracts_include_dependencies_and_references() -> None:
    module_index = {
        "Scripts/Main.as": "Scripts/Main.as",
        "Scripts.Main": "Scripts/Main.as",
        "Scripts/Util.as": "Scripts/Util.as",
        "Scripts.Util": "Scripts/Util.as",
        "Main": "Scripts/Main.as",
        "Util": "Scripts/Util.as",
        "log": "Scripts/Util.as",
    }
    main_text = (
        '#include "Util.as"\n\n'
        "namespace Demo {\n"
        "void boot() {\n"
        "    Util::log(\"started\");\n"
        "}\n"
        "}\n"
    )

    symbols, dependencies, references = repository_service.angelscript_adapter.parse_file(
        "Scripts/Main.as",
        main_text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(dependency.target_file == "Scripts/Util.as" for dependency in dependencies)
    assert any(dependency.target_symbol == "Util" for dependency in dependencies)
    assert any(symbol.symbol_name == "boot" for symbol in symbols)
    assert any(reference.target_file == "Scripts/Util.as" for reference in references)
    assert any(reference.target_names == ("log",) for reference in references)


def test_angelscript_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".as" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("Scripts/Main.as"),
            text="namespace Demo {\nvoid Start() {}\n}\n",
        )
        == "angelscript"
    )
    assert (
        repository_service._language_for_path(
            Path("src/Main.as"),
            text="package demo {\npublic class Main {\n}\n}\n",
        )
        == "actionscript"
    )
    assert (
        repository_service._language_for_path(
            Path("notes/Main.as"),
            text="plain notes without actionscript or angelscript markers\n",
        )
        == "unknown"
    )


def test_candidate_ecosystems_for_path_detects_angelscript_with_repo_context(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "angelscript-candidate-repo"
    (repo_path / "Scripts").mkdir(parents=True)
    (repo_path / "Scripts" / "Main.as").write_text(
        "namespace Demo {\nvoid Start() {}\n}\n",
        encoding="utf-8",
    )

    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    assert probe_module._candidate_ecosystems_for_path(
        "Scripts/Main.as",
        repo_path=repo_path,
    ) == {"angelscript"}


def test_operational_seed_plan_without_diagnostics_promotes_angelscript_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "angelscript-profile-repo"
    (repo_path / "Scripts").mkdir(parents=True)
    for index in range(6):
        (repo_path / "Scripts" / f"Scene{index}.as").write_text(
            "namespace Demo {\n"
            f"void Scene{index}Start() {{\n"
            "}\n"
            "}\n",
            encoding="utf-8",
        )
    (repo_path / "tools").mkdir(parents=True)
    for index in range(2):
        (repo_path / "tools" / f"helper_{index}.py").write_text(
            "print('helper')\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "angelscript" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "angelscript"
    assert any(path.endswith(".as") for path in seed_plan["entrypoint_files"])


def test_operational_seed_plan_without_diagnostics_respects_explicit_angelscript_focus_paths(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "angelscript-focused-host-repo"
    (repo_path / "bin" / "Data" / "Scripts").mkdir(parents=True)
    (repo_path / "Source").mkdir(parents=True)
    (repo_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.20)\nproject(FocusedHost)\n",
        encoding="utf-8",
    )
    for index in range(20):
        (repo_path / "Source" / f"Host{index}.cpp").write_text(
            "int main() { return 0; }\n",
            encoding="utf-8",
        )
    for name in ("HelloWorld", "Utilities", "Sample"):
        (repo_path / "bin" / "Data" / "Scripts" / f"{name}.as").write_text(
            '#include "Utilities.as"\n'
            "void Start() {\n"
            "}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["bin/Data/Scripts"],
        max_files=128,
    )

    assert "angelscript" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "angelscript"
    assert any(path.startswith("bin/Data/Scripts/") for path in seed_plan["entrypoint_files"])


def test_repository_intelligence_snapshot_graph_contains_angelscript_dependency_edges(
    tmp_path: Path,
) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "angelscript-snapshot-repo"
    (repo_path / "Scripts").mkdir(parents=True)
    (repo_path / "Scripts" / "Util.as").write_text(
        "namespace Util {\nvoid log(const string &in message) {}\n}\n",
        encoding="utf-8",
    )
    (repo_path / "Scripts" / "Main.as").write_text(
        '#include "Util.as"\n'
        "namespace Demo {\n"
        "void boot() {\n"
        "    Util::log(\"started\");\n"
        "}\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    connector = _connector_for_repo(repo_path)
    request = RepositorySnapshotCreateRequest(
        connector_id=str(connector.id),
        repository_url=None,
        branch="HEAD",
        ref=None,
        subdirectory=None,
        force_refresh=True,
        include_globs=[],
        exclude_globs=[],
    )
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=request,
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()

    assert any(
        row["edge_type"] == "include"
        and str(row["source_node"]) == "file:Scripts/Main.as"
        and str(row["target_node"]) == "file:Scripts/Util.as"
        for row in graph
    )
