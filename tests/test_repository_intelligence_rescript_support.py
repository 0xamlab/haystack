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
    repository_intelligence_rescript_parser_dispatch as repository_rescript_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    rescript_analysis_support as repository_rescript_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    rescript_primitives as repository_rescript_primitives,
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


def test_repository_intelligence_rescript_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["rescript"] is (
        repository_rescript_parser_dispatch._parse_rescript_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["rescript"] is (
        repository_rescript_parser_dispatch._parse_rescript_dependencies_only
    )


def test_repository_intelligence_rescript_helpers_are_modularized() -> None:
    assert repository_service.rescript_adapter.strip_comments is (
        repository_rescript_primitives.strip_comments
    )
    assert repository_service.rescript_adapter.has_rescript_path_hints is (
        repository_rescript_primitives.has_rescript_path_hints
    )
    assert repository_service.rescript_adapter.is_probable_rescript_source is (
        repository_rescript_primitives.is_probable_rescript_source
    )
    assert repository_service.rescript_adapter.is_probable_rescript_config is (
        repository_rescript_primitives.is_probable_rescript_config
    )
    assert repository_service.rescript_adapter.module_aliases_for_path is (
        repository_rescript_analysis_support.module_aliases_for_path
    )
    assert repository_service.rescript_adapter.resolve_import is (
        repository_rescript_analysis_support.resolve_import
    )
    assert repository_service.rescript_adapter.parse_dependencies_only is (
        repository_rescript_analysis_support.parse_dependencies_only
    )
    assert repository_service.rescript_adapter.parse_file is (
        repository_rescript_analysis_support.parse_file
    )


def test_rescript_adapter_module_aliases_include_module_and_symbol_names(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "rescript-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "Json_Decode.res").write_text(
        "module Error = {\n"
        "  let expected = kind => kind\n"
        "}\n"
        "\n"
        "let string = json => json\n",
        encoding="utf-8",
    )

    aliases = repository_service.rescript_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/Json_Decode.res",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/Json_Decode.res" in aliases
    assert "src/Json_Decode" in aliases
    assert "src.Json_Decode" in aliases
    assert "Json_Decode" in aliases
    assert "Error" in aliases
    assert "string" in aliases
    assert "Json_Decode.string" in aliases


def test_rescript_adapter_parse_dependencies_resolves_open_and_module_alias(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "rescript-deps-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "Json_Decode.res").write_text(
        "let string = json => json\n",
        encoding="utf-8",
    )
    main_path = repo_path / "src" / "Json.res"
    main_path.write_text(
        "open Json_Decode\n"
        "module Decode = Json_Decode\n"
        "let parse = json => Decode.string(json)\n",
        encoding="utf-8",
    )
    module_index = repository_service._build_module_index(
        ["src/Json_Decode.res", "src/Json.res"],
        root_path=repo_path,
    )

    dependencies = repository_service.rescript_adapter.parse_dependencies_only(
        "src/Json.res",
        main_path.read_text(encoding="utf-8"),
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert {dependency.target_file for dependency in dependencies} == {"src/Json_Decode.res"}


def test_rescript_language_detection_supports_suffixes_and_manifest() -> None:
    assert ".res" in repository_service._TEXT_FILE_SUFFIXES
    assert ".resi" in repository_service._TEXT_FILE_SUFFIXES
    assert "rescript.json" in repository_service._TEXT_FILE_BASENAMES
    assert "bsconfig.json" in repository_service._TEXT_FILE_BASENAMES
    assert (
        repository_service._language_for_path(
            Path("src/Main.res"),
            text="open Helper\nlet main = helperValue\n",
        )
        == "rescript"
    )
    assert (
        repository_service._language_for_path(
            Path("src/Json.resi"),
            text="module Decode = Json_Decode\nlet decode: JSON.t => result<string, string>\n",
        )
        == "rescript"
    )
    assert (
        repository_service._language_for_path(
            Path("rescript.json"),
            text='{"name":"demo","sources":[{"dir":"src"}],"suffix":".mjs"}\n',
        )
        == "rescript"
    )


def test_operational_seed_plan_without_diagnostics_promotes_rescript_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "rescript-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "rescript.json").write_text(
        '{"name":"demo","sources":[{"dir":"src"}],"suffix":".mjs"}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Helper.res").write_text(
        "let helperValue = 1\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.res").write_text(
        "open Helper\nlet main = helperValue\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "rescript" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "rescript"
    assert "rescript.json" in seed_plan["config_paths"]
    assert "src/Main.res" in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_does_not_force_rescript_first_in_node_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "rescript-mixed-node-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "rescript.json").write_text(
        '{"name":"demo","sources":[{"dir":"src"}],"suffix":".mjs"}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Helper.res").write_text("let helperValue = 1\n", encoding="utf-8")
    (repo_path / "src" / "Main.res").write_text(
        "open Helper\nlet main = helperValue\n",
        encoding="utf-8",
    )
    (repo_path / "web").mkdir(parents=True)
    for index in range(18):
        (repo_path / "web" / f"file{index}.ts").write_text(
            f"export const value{index}: number = {index};\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "rescript" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] != "rescript"


def test_connected_dependency_map_follows_rescript_open_and_symbol_edges(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "rescript-connected-map-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "rescript.json").write_text(
        '{"name":"demo","sources":[{"dir":"src"}]}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Helper.res").write_text("let helperValue = 1\n", encoding="utf-8")
    (repo_path / "src" / "Main.res").write_text(
        "open Helper\nlet main = helperValue\n",
        encoding="utf-8",
    )

    connected_map = _build_connected_dependency_map(
        repo_path=repo_path,
        seed_paths=["src/Main.res"],
        bridge_paths=["src", "rescript.json"],
        include_patterns=["src/**/*.res", "src/*.res", "*.res", "*.resi", "rescript.json"],
        max_files=128,
        max_file_size_bytes=100_000,
        max_dependency_depth=4,
        max_connected_files=16,
    )

    assert connected_map["connected_file_count"] == 2
    assert connected_map["resolved_dependency_edges"] >= 1
    assert set(connected_map["connected_files"]) == {
        "src/Main.res",
        "src/Helper.res",
    }


def test_repository_snapshot_graph_contains_rescript_dependency_and_symbol_reference_edges(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = tmp_path / "rescript-dependency-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "rescript.json").write_text(
        '{"name":"demo","sources":[{"dir":"src"}]}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "Helper.res").write_text("let helperValue = 1\n", encoding="utf-8")
    (repo_path / "src" / "Main.res").write_text(
        "open Helper\nlet main = helperValue\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["src"],
            include_patterns=["src/**/*.res", "src/*.res", "*.res", "*.resi", "rescript.json"],
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
        and str(row["source_node"]) == "file:src/Main.res"
        and str(row["target_node"]) == "file:src/Helper.res"
        for row in graph_rows
    )
    main_symbol_id = symbol_ids[("src/Main.res", "main")]
    helper_value_symbol_id = symbol_ids[("src/Helper.res", "helperValue")]
    assert any(
        str(row["edge_type"]) == "references_symbol"
        and str(row["source_node"]) == f"symbol:{main_symbol_id}"
        and str(row["target_node"]) == f"symbol:{helper_value_symbol_id}"
        for row in graph_rows
    )
