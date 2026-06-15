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
    repository_intelligence_mercury_parser_dispatch as repository_intelligence_mercury_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    mercury_analysis_support as repository_mercury_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    mercury_primitives as repository_mercury_primitives,
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


def test_repository_intelligence_mercury_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["mercury"] is (
        repository_intelligence_mercury_parser_dispatch._parse_mercury_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["mercury"] is (
        repository_intelligence_mercury_parser_dispatch._parse_mercury_dependencies_only
    )


def test_repository_intelligence_mercury_helpers_are_modularized() -> None:
    assert repository_service.mercury_adapter.has_mercury_path_hints is (
        repository_mercury_primitives.has_mercury_path_hints
    )
    assert repository_service.mercury_adapter.is_probable_mercury_source is (
        repository_mercury_analysis_support.is_probable_mercury_source
    )
    assert repository_service.mercury_adapter.iter_dependency_entries is (
        repository_mercury_primitives.iter_dependency_entries
    )
    assert repository_service.mercury_adapter.resolve_import_module is (
        repository_mercury_analysis_support.resolve_import_module
    )
    assert repository_service.mercury_adapter.parse_file is (
        repository_mercury_analysis_support.parse_file
    )


def test_mercury_adapter_parse_file_extracts_imports_and_local_symbol_references() -> None:
    text = (
        ":- module example.\n"
        ":- interface.\n"
        ":- import_module list.\n"
        ":- pred helper(int::in, int::out) is det.\n"
        ":- pred run(int::in, int::out) is det.\n"
        "\n"
        ":- implementation.\n"
        "\n"
        "run(X, Y) :-\n"
        "    helper(X, Y).\n"
        "\n"
        "helper(X, Y) :-\n"
        "    Y = X.\n"
    )

    symbols, dependencies, references = repository_service.mercury_adapter.parse_file(
        "library/example.m",
        text,
        {"list": "library/list.m"},
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(symbol.symbol_name == "helper" for symbol in symbols)
    assert any(symbol.symbol_name == "run" for symbol in symbols)
    assert any(
        dependency.target_file == "library/list.m" and dependency.target_symbol == "list"
        for dependency in dependencies
    )
    assert any(reference.target_names == ("helper",) for reference in references)


def test_mercury_language_detection_disambiguates_m_sources() -> None:
    assert ".m" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("library/example.m"),
            text=":- module example.\n:- interface.\n:- pred run(int::in, int::out) is det.\n",
        )
        == "mercury"
    )
    assert (
        repository_service._language_for_path(
            Path("ios/AppDelegate.m"),
            text="#import <Foundation/Foundation.h>\n@interface AppDelegate : NSObject\n@end\n",
        )
        == "objectivec"
    )
    assert (
        repository_service._language_for_path(
            Path("src/main.m"),
            text="plain notes without mercury directives\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_mercury_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "mercury-profile-repo"
    (repo_path / "library").mkdir(parents=True)
    for index in range(6):
        (repo_path / "library" / f"module_{index}.m").write_text(
            ":- module module_{0}.\n"
            ":- interface.\n"
            ":- pred run(int::in, int::out) is det.\n"
            ":- implementation.\n"
            "run(X, Y) :-\n"
            "    Y = X.\n".format(index),
            encoding="utf-8",
        )
    (repo_path / "ios").mkdir(parents=True)
    (repo_path / "ios" / "AppDelegate.m").write_text(
        "#import <Foundation/Foundation.h>\n@interface AppDelegate : NSObject\n@end\n",
        encoding="utf-8",
    )
    (repo_path / "+acme").mkdir(parents=True)
    (repo_path / "+acme" / "helper.m").write_text(
        "function y = helper(x)\ny = x;\nend\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "mercury" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "mercury"


def test_repository_snapshot_graph_contains_mercury_symbol_reference_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "mercury-graph-repo"
    repo_path.mkdir(parents=True)
    (repo_path / "main.m").write_text(
        ":- module main.\n"
        ":- interface.\n"
        ":- pred helper(int::in, int::out) is det.\n"
        ":- pred run(int::in, int::out) is det.\n"
        ":- implementation.\n"
        "run(X, Y) :-\n"
        "    helper(X, Y).\n"
        "helper(X, Y) :-\n"
        "    Y = X.\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.m"],
            max_files=16,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    helper_symbol_id = next(
        str(row["symbol_id"])
        for row in symbol_rows
        if str(row["file_path"]) == "main.m" and str(row["symbol_name"]) == "helper"
    )

    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["target_node"]) == f"symbol:{helper_symbol_id}"
        for row in graph
    )
