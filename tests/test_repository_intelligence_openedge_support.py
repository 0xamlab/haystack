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
    repository_intelligence_openedge_parser_dispatch as repository_intelligence_openedge_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    openedge_analysis_support as repository_openedge_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    openedge_primitives as repository_openedge_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _candidate_ecosystems_for_path,
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


def test_repository_intelligence_openedge_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["openedge"] is (
        repository_intelligence_openedge_parser_dispatch._parse_openedge_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["openedge"] is (
        repository_intelligence_openedge_parser_dispatch._parse_openedge_dependencies_only
    )


def test_repository_intelligence_openedge_helpers_are_modularized() -> None:
    assert repository_service.openedge_adapter.has_openedge_path_hints is (
        repository_openedge_primitives.has_openedge_path_hints
    )
    assert repository_service.openedge_adapter.is_probable_openedge_source is (
        repository_openedge_primitives.is_probable_openedge_source
    )
    assert repository_service.openedge_adapter.module_aliases_for_path is (
        repository_openedge_primitives.module_aliases_for_path
    )
    assert repository_service.openedge_adapter.parse_dependencies_only is (
        repository_openedge_analysis_support.parse_dependencies_only
    )
    assert repository_service.openedge_adapter.parse_file is (
        repository_openedge_analysis_support.parse_file
    )


def test_openedge_adapter_parse_file_extracts_dependencies_and_references() -> None:
    module_index = repository_service._build_module_index(
        [
            "src/OEUnit/Assertion/Assert.cls",
            "src/helpers/shared.i",
            "src/helpers/setup.p",
            "src/OEUnit/Tests/Sample.cls",
        ],
        root_path=Path("/tmp/openedge-index"),
    )
    text = (
        "USING OEUnit.Assertion.Assert.\n"
        "{helpers/shared.i}\n"
        "RUN helpers/setup.p.\n"
        "CLASS OEUnit.Tests.Sample INHERITS Assert:\n"
        "END CLASS.\n"
    )

    symbols, dependencies, references = repository_service.openedge_adapter.parse_file(
        "src/OEUnit/Tests/Sample.cls",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(symbol.symbol_name == "Sample" for symbol in symbols)
    assert any(dependency.target_file == "src/OEUnit/Assertion/Assert.cls" for dependency in dependencies)
    assert any(dependency.target_file == "src/helpers/shared.i" for dependency in dependencies)
    assert any(dependency.target_file == "src/helpers/setup.p" for dependency in dependencies)
    assert any(reference.target_file == "src/OEUnit/Assertion/Assert.cls" for reference in references)


def test_openedge_language_detection_supports_sources_without_overclaiming() -> None:
    assert ".p" in repository_service._TEXT_FILE_SUFFIXES
    assert ".w" in repository_service._TEXT_FILE_SUFFIXES
    assert ".i" in repository_service._TEXT_FILE_SUFFIXES
    assert ".pf" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("src/OEUnit/Runners/OEUnitRunner.cls"),
            text=(
                "USING Progress.Lang.*.\n"
                "CLASS OEUnit.Runners.OEUnitRunner INHERITS BaseRunner:\n"
                "  DEFINE PROTECTED VARIABLE currentTest AS Object NO-UNDO.\n"
                "END CLASS.\n"
            ),
        )
        == "openedge"
    )
    assert (
        repository_service._language_for_path(
            Path("src/OEUnit/Automation/Pct/RunTests.p"),
            text=(
                "ROUTINE-LEVEL ON ERROR UNDO, THROW.\n"
                "DEFINE INPUT PARAMETER testLocation AS CHARACTER NO-UNDO.\n"
                "RUN FindClassFiles(INPUT testLocation).\n"
            ),
        )
        == "openedge"
    )
    assert (
        repository_service._language_for_path(
            Path("config/session.pf"),
            text="-db sports2000\n-param test=true\n",
        )
        == "openedge"
    )
    assert (
        repository_service._language_for_path(
            Path("docs/article.cls"),
            text="\\NeedsTeXFormat{LaTeX2e}\n\\ProvidesClass{article}\n",
        )
        == "tex"
    )


def test_real_repo_probe_candidate_ecosystems_detect_openedge_sources(tmp_path: Path) -> None:
    repo_path = tmp_path / "openedge-candidate-ecosystem-repo"
    (repo_path / "src" / "OEUnit" / "Automation" / "Pct").mkdir(parents=True)
    (repo_path / "src" / "OEUnit" / "Runners").mkdir(parents=True)
    (repo_path / "src" / "OEUnit" / "Automation" / "Pct" / "RunTests.p").write_text(
        "ROUTINE-LEVEL ON ERROR UNDO, THROW.\n"
        "DEFINE INPUT PARAMETER testLocation AS CHARACTER NO-UNDO.\n"
        "RUN FindClassFiles(INPUT testLocation).\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "OEUnit" / "Runners" / "OEUnitRunner.cls").write_text(
        "USING Progress.Lang.*.\n"
        "CLASS OEUnit.Runners.OEUnitRunner INHERITS BaseRunner:\n"
        "  DEFINE PROTECTED VARIABLE currentTest AS Object NO-UNDO.\n"
        "END CLASS.\n",
        encoding="utf-8",
    )

    assert "openedge" in _candidate_ecosystems_for_path(
        "src/OEUnit/Automation/Pct/RunTests.p",
        repo_path=repo_path,
    )
    assert "openedge" in _candidate_ecosystems_for_path(
        "src/OEUnit/Runners/OEUnitRunner.cls",
        repo_path=repo_path,
    )


def test_operational_seed_plan_without_diagnostics_promotes_openedge_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "openedge-profile-repo"
    (repo_path / "src" / "OEUnit" / "Runners").mkdir(parents=True)
    (repo_path / "src" / "OEUnit" / "Automation" / "Pct").mkdir(parents=True)
    for index in range(5):
        (repo_path / "src" / "OEUnit" / "Runners" / f"Runner{index}.cls").write_text(
            "USING Progress.Lang.*.\n"
            f"CLASS OEUnit.Runners.Runner{index} INHERITS BaseRunner:\n"
            "  DEFINE PROTECTED VARIABLE currentTest AS Object NO-UNDO.\n"
            "END CLASS.\n",
            encoding="utf-8",
        )
    for index in range(2):
        (repo_path / "src" / "OEUnit" / "Automation" / "Pct" / f"RunTests{index}.p").write_text(
            "ROUTINE-LEVEL ON ERROR UNDO, THROW.\n"
            "DEFINE INPUT PARAMETER testLocation AS CHARACTER NO-UNDO.\n"
            "RUN FindClassFiles(INPUT testLocation).\n",
            encoding="utf-8",
        )
    (repo_path / "tools").mkdir(parents=True)
    for index in range(2):
        (repo_path / "tools" / f"helper_{index}.py").write_text("print('helper')\n", encoding="utf-8")

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["src"],
        max_files=128,
    )

    assert "openedge" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "openedge"


def test_repository_snapshot_graph_contains_openedge_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "openedge-graph-repo"
    (repo_path / "src" / "OEUnit" / "Assertion").mkdir(parents=True)
    (repo_path / "src" / "OEUnit" / "Tests").mkdir(parents=True)
    (repo_path / "src" / "OEUnit" / "Assertion" / "Assert.cls").write_text(
        "CLASS OEUnit.Assertion.Assert:\nEND CLASS.\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "OEUnit" / "Tests" / "Sample.cls").write_text(
        "USING OEUnit.Assertion.Assert.\n"
        "CLASS OEUnit.Tests.Sample INHERITS Assert:\n"
        "END CLASS.\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["*.cls", "*.p", "*.i", "*.w", "*.pf"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    assert_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "src/OEUnit/Assertion/Assert.cls"
        and str(row["symbol_name"]) == "Assert"
        and str(row["symbol_kind"]) == "class"
    )

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{assert_symbol_id}"
        for row in graph
    )
