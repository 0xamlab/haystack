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
    repository_intelligence_reasonml_parser_dispatch as repository_reasonml_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    reasonml_analysis_support as repository_reasonml_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    reasonml_primitives as repository_reasonml_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _build_connected_dependency_map,
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


def test_repository_intelligence_reasonml_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["reasonml"] is (
        repository_reasonml_parser_dispatch._parse_reasonml_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["reasonml"] is (
        repository_reasonml_parser_dispatch._parse_reasonml_dependencies_only
    )


def test_repository_intelligence_reasonml_helpers_are_modularized() -> None:
    assert repository_service.reasonml_adapter.strip_comments is (
        repository_reasonml_primitives.strip_comments
    )
    assert repository_service.reasonml_adapter.has_reasonml_path_hints is (
        repository_reasonml_primitives.has_reasonml_path_hints
    )
    assert repository_service.reasonml_adapter.is_probable_reasonml_source is (
        repository_reasonml_primitives.is_probable_reasonml_source
    )
    assert repository_service.reasonml_adapter.module_aliases_for_path is (
        repository_reasonml_analysis_support.module_aliases_for_path
    )
    assert repository_service.reasonml_adapter.resolve_import is (
        repository_reasonml_analysis_support.resolve_import
    )
    assert repository_service.reasonml_adapter.parse_dependencies_only is (
        repository_reasonml_analysis_support.parse_dependencies_only
    )
    assert repository_service.reasonml_adapter.parse_file is (
        repository_reasonml_analysis_support.parse_file
    )


def test_reasonml_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "reasonml-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "JsonDecode.re").write_text(
        "module Error = {\n"
        "  let expected = kind => kind;\n"
        "};\n"
        "\n"
        "let string = json => json;\n",
        encoding="utf-8",
    )

    aliases = repository_service.reasonml_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/JsonDecode.re",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/JsonDecode.re" in aliases
    assert "src/JsonDecode" in aliases
    assert "src.JsonDecode" in aliases
    assert "JsonDecode" in aliases
    assert "Error" in aliases
    assert "string" in aliases
    assert "JsonDecode.string" in aliases


def test_reasonml_adapter_parse_dependencies_resolves_open_and_module_alias(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "reasonml-deps-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "Helper.re").write_text(
        "let helperValue = 1;\n",
        encoding="utf-8",
    )
    main_path = repo_path / "src" / "Main.re"
    main_path.write_text(
        "open Helper;\n"
        "module Alias = Helper;\n"
        "let main = Alias.helperValue;\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["src/Helper.re", "src/Main.re"],
        root_path=repo_path,
    )

    dependencies = repository_service.reasonml_adapter.parse_dependencies_only(
        "src/Main.re",
        main_path.read_text(encoding="utf-8"),
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert {dependency.target_file for dependency in dependencies} == {"src/Helper.re"}


def test_reasonml_language_detection_supports_suffixes() -> None:
    assert ".re" in repository_service._TEXT_FILE_SUFFIXES
    assert ".rei" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("src/Main.re"),
            text="open Helper;\nlet main = helperValue;\n",
        )
        == "reasonml"
    )
    assert (
        repository_service._language_for_path(
            Path("src/Json.rei"),
            text="module Decode = JsonDecode;\nlet decode: json => string;\n",
        )
        == "reasonml"
    )


def test_operational_seed_plan_without_diagnostics_promotes_reasonml_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "reasonml-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "Helper.re").write_text(
        "let helperValue = 1;\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.re").write_text(
        "open Helper;\nlet main = helperValue;\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["src"],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["reasonml"]
    assert seed_plan["operational_ecosystems"] == ["reasonml"]


def test_connected_dependency_map_follows_reasonml_open_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "reasonml-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "Helper.re").write_text("let helperValue = 1;\n", encoding="utf-8")
    (repo_path / "src" / "Main.re").write_text(
        "open Helper;\nlet main = helperValue;\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/Main.re"],
        bridge_paths=["src"],
        include_patterns=["src/**/*.re", "src/*.re", "*.re", "*.rei"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "src/Main.re",
        "src/Helper.re",
    }


def test_repository_snapshot_graph_contains_reasonml_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "reasonml-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "Helper.re").write_text("let helperValue = 1;\n", encoding="utf-8")
    (repo_path / "src" / "Main.re").write_text(
        "open Helper;\nlet main = helperValue;\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.re", "src/*.re", "*.re", "*.rei"],
        ),
    )

    initialize_pyarrow_parquet_runtime()
    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    symbol_ids = {
        (str(row["file_path"]), str(row["symbol_name"])): str(row["symbol_id"])
        for row in symbol_rows
    }

    assert any(
        str(row["edge_type"]) == "imports"
        and str(row["source_node"]) == "file:src/Main.re"
        and str(row["target_node"]) == "file:src/Helper.re"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("src/Main.re", "main")]
    helper_value_symbol_id = symbol_ids[("src/Helper.re", "helperValue")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_value_symbol_id}"
        for row in graph_rows
    )
