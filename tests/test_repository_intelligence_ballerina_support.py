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
    repository_intelligence_ballerina_parser_dispatch as repository_ballerina_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    ballerina_analysis_support as repository_ballerina_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    ballerina_primitives as repository_ballerina_primitives,
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


def test_repository_intelligence_ballerina_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["ballerina"] is (
        repository_ballerina_parser_dispatch._parse_ballerina_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["ballerina"] is (
        repository_ballerina_parser_dispatch._parse_ballerina_dependencies_only
    )


def test_repository_intelligence_ballerina_helpers_are_modularized() -> None:
    assert repository_service.ballerina_adapter.strip_comments is (
        repository_ballerina_primitives.strip_comments
    )
    assert repository_service.ballerina_adapter.has_ballerina_path_hints is (
        repository_ballerina_primitives.has_ballerina_path_hints
    )
    assert repository_service.ballerina_adapter.is_probable_ballerina_source is (
        repository_ballerina_analysis_support.is_probable_ballerina_source
    )
    assert repository_service.ballerina_adapter.is_probable_ballerina_config is (
        repository_ballerina_analysis_support.is_probable_ballerina_config
    )
    assert repository_service.ballerina_adapter.iter_import_entries is (
        repository_ballerina_primitives.iter_import_entries
    )
    assert repository_service.ballerina_adapter.module_aliases_for_path is (
        repository_ballerina_analysis_support.module_aliases_for_path
    )
    assert repository_service.ballerina_adapter.parse_dependencies_only is (
        repository_ballerina_analysis_support.parse_dependencies_only
    )
    assert repository_service.ballerina_adapter.parse_file is (
        repository_ballerina_analysis_support.parse_file
    )


def test_ballerina_adapter_module_aliases_include_symbols_and_module_paths(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ballerina-alias-repo"
    (repo_path / "ballerina").mkdir(parents=True)
    (repo_path / "ballerina" / "service.bal").write_text(
        "import ballerina/io;\n\n"
        "public type Greeting record {| string message; |};\n\n"
        "public function greet() returns Greeting {\n"
        '    io:println("hi");\n'
        '    return {message: "hi"};\n'
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.ballerina_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="ballerina/service.bal",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "ballerina/service.bal" in aliases
    assert "service" in aliases
    assert "greet" in aliases
    assert "Greeting" in aliases


def test_ballerina_adapter_module_aliases_use_provided_text_without_rereading_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "ballerina-inline-text-repo"
    (repo_path / "ballerina").mkdir(parents=True)
    source_text = (
        "import ballerina/io;\n\n"
        "public function greet() returns string {\n"
        '    io:println("hi");\n'
        '    return "hi";\n'
        "}\n"
    )
    source_file = repo_path / "ballerina" / "service.bal"
    source_file.write_text(source_text, encoding="utf-8")

    def _unexpected_read_text(self: Path, *args, **kwargs) -> str:
        raise AssertionError(f"module_aliases_for_path should not reread {self}")

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)

    aliases = repository_service.ballerina_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="ballerina/service.bal",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_ballerina_primitives.strip_comments(source_text),
    )

    assert "ballerina/service.bal" in aliases
    assert "service" in aliases
    assert "greet" in aliases


def test_ballerina_adapter_module_aliases_skip_stable_ids_for_raw_symbol_aliases(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ballerina-raw-alias-repo"
    (repo_path / "ballerina").mkdir(parents=True)
    source_text = (
        "import ballerina/io;\n\n"
        "public type Greeting record {| string message; |};\n\n"
        "public function greet() returns Greeting {\n"
        '    io:println("hi");\n'
        '    return {message: "hi"};\n'
        "}\n"
    )
    (repo_path / "ballerina" / "service.bal").write_text(source_text, encoding="utf-8")

    def _unexpected_stable_identifier(_prefix: str, _payload: object) -> str:
        raise AssertionError("module_aliases_for_path should not build stable identifiers")

    aliases = repository_service.ballerina_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="ballerina/service.bal",
        stable_identifier=_unexpected_stable_identifier,
        text=source_text,
        stripped_text=repository_ballerina_primitives.strip_comments(source_text),
    )

    assert "greet" in aliases
    assert "Greeting" in aliases


def test_ballerina_iter_symbol_entries_reuse_cached_stripped_text_entries() -> None:
    repository_ballerina_primitives._iter_symbol_entries_from_stripped_text.cache_clear()
    stripped_text = repository_ballerina_primitives.strip_comments(
        "public type Greeting record {| string message; |};\n\n"
        "public function greet() returns Greeting {\n"
        '    return {message: "hi"};\n'
        "}\n",
    )

    first_result = repository_ballerina_primitives.iter_symbol_entries(
        "",
        stripped_text=stripped_text,
    )
    first_cache_info = (
        repository_ballerina_primitives._iter_symbol_entries_from_stripped_text.cache_info()
    )
    second_result = repository_ballerina_primitives.iter_symbol_entries(
        "",
        stripped_text=stripped_text,
    )
    second_cache_info = (
        repository_ballerina_primitives._iter_symbol_entries_from_stripped_text.cache_info()
    )

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_ballerina_iter_reference_entries_reuse_cached_stripped_text_entries() -> None:
    repository_ballerina_primitives._iter_reference_entries_from_stripped_text.cache_clear()
    stripped_text = repository_ballerina_primitives.strip_comments(
        "import acme/common as common;\n\n"
        "public function greet() returns string {\n"
        "    return common:render();\n"
        "}\n",
    )

    first_result = repository_ballerina_primitives.iter_reference_entries(
        "",
        stripped_text=stripped_text,
    )
    first_cache_info = (
        repository_ballerina_primitives._iter_reference_entries_from_stripped_text.cache_info()
    )
    second_result = repository_ballerina_primitives.iter_reference_entries(
        "",
        stripped_text=stripped_text,
    )
    second_cache_info = (
        repository_ballerina_primitives._iter_reference_entries_from_stripped_text.cache_info()
    )

    assert first_result == second_result
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_ballerina_probable_source_reuses_cached_stripped_text_decision() -> None:
    repository_ballerina_primitives._is_probable_ballerina_source_from_stripped_text.cache_clear()
    stripped_text = repository_ballerina_primitives.strip_comments(
        "import ballerina/io;\n\n"
        "public function greet() returns string {\n"
        '    io:println("hi");\n'
        '    return "hi";\n'
        "}\n",
    )

    first_result = repository_ballerina_primitives.is_probable_ballerina_source(
        path=Path("ballerina/service.bal"),
        text="ignored because stripped_text is provided",
        stripped_text=stripped_text,
    )
    first_cache_info = (
        repository_ballerina_primitives._is_probable_ballerina_source_from_stripped_text.cache_info()
    )
    second_result = repository_ballerina_primitives.is_probable_ballerina_source(
        path=Path("ballerina/service.bal"),
        text="ignored because stripped_text is provided",
        stripped_text=stripped_text,
    )
    second_cache_info = (
        repository_ballerina_primitives._is_probable_ballerina_source_from_stripped_text.cache_info()
    )

    assert first_result is True
    assert second_result is True
    assert first_cache_info.hits == 0
    assert second_cache_info.hits == 1


def test_ballerina_strip_comments_returns_original_text_when_no_comment_markers() -> None:
    source_text = (
        "public function greet() returns string {\n"
        '    return "hi";\n'
        "}\n"
    )

    assert repository_ballerina_primitives.strip_comments(source_text) == source_text


def test_build_module_index_reuses_preloaded_text_for_ballerina_root_scoped_aliases(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "ballerina-module-index-repo"
    (repo_path / "ballerina").mkdir(parents=True)
    source_file = repo_path / "ballerina" / "service.bal"
    source_file.write_text(
        "import ballerina/io;\n\n"
        "public function greet() returns string {\n"
        '    io:println("hi");\n'
        '    return "hi";\n'
        "}\n",
        encoding="utf-8",
    )

    original_read_text = Path.read_text
    read_count = {"value": 0}

    def _counting_read_text(self: Path, *args, **kwargs) -> str:
        if self == source_file:
            read_count["value"] += 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)

    module_index = repository_service._build_module_index(
        ["ballerina/service.bal"],
        root_path=repo_path,
    )

    assert read_count["value"] == 1
    assert module_index["greet"] == "ballerina/service.bal"


def test_ballerina_adapter_parse_file_extracts_dependencies_and_references() -> None:
    module_index = repository_service._build_module_index(
        ["ballerina/main.bal", "ballerina/modules/common/main.bal", "Ballerina.toml"],
        root_path=Path("/tmp/ballerina-index"),
    )
    text = (
        "import acme/common as common;\n\n"
        "public function main() returns string {\n"
        "    return common:greet();\n"
        "}\n"
    )

    symbols, dependencies, references = repository_service.ballerina_adapter.parse_file(
        "ballerina/main.bal",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(
        dependency.target_file == "ballerina/modules/common/main.bal"
        for dependency in dependencies
    )
    assert any(symbol.symbol_name == "main" for symbol in symbols)
    assert any(
        reference.target_file == "ballerina/modules/common/main.bal" for reference in references
    )
    assert any(reference.target_names == ("greet",) for reference in references)


def test_ballerina_adapter_parse_file_reuses_stripped_text(
    monkeypatch,
) -> None:
    module_index = repository_service._build_module_index(
        ["ballerina/main.bal", "ballerina/modules/common/main.bal", "Ballerina.toml"],
        root_path=Path("/tmp/ballerina-index"),
    )
    text = (
        "import acme/common as common;\n\n"
        "public function main() returns string {\n"
        "    return common:greet();\n"
        "}\n"
    )

    original_strip_comments = repository_ballerina_primitives.strip_comments
    strip_comment_calls = {"value": 0}

    def _counting_strip_comments(text: str) -> str:
        strip_comment_calls["value"] += 1
        return original_strip_comments(text)

    monkeypatch.setattr(
        repository_ballerina_primitives,
        "strip_comments",
        _counting_strip_comments,
    )
    monkeypatch.setattr(
        repository_ballerina_analysis_support,
        "strip_comments",
        _counting_strip_comments,
    )

    repository_service.ballerina_adapter.parse_file(
        "ballerina/main.bal",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert strip_comment_calls["value"] == 1


def test_ballerina_language_detection_supports_sources_and_configs_without_overclaiming() -> None:
    assert ".bal" in repository_service._TEXT_FILE_SUFFIXES
    assert "Ballerina.toml" in repository_service._TEXT_FILE_BASENAMES
    assert (
        repository_service._language_for_path(
            Path("ballerina/main.bal"),
            text=(
                "import ballerina/io;\n\n"
                "public function main() returns error? {\n"
                '    io:println("hello");\n'
                "}\n"
            ),
        )
        == "ballerina"
    )
    assert (
        repository_service._language_for_path(
            Path("Ballerina.toml"),
            text="[package]\norg = \"acme\"\nname = \"demo\"\nversion = \"0.1.0\"\n",
        )
        == "ballerina"
    )
    assert (
        repository_service._language_for_path(
            Path("notes.bal"),
            text="plain notes without ballerina constructs\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_ballerina_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ballerina-profile-repo"
    (repo_path / "ballerina").mkdir(parents=True)
    (repo_path / "Ballerina.toml").write_text(
        "[package]\norg = \"acme\"\nname = \"demo\"\nversion = \"0.1.0\"\n",
        encoding="utf-8",
    )
    for index in range(6):
        (repo_path / "ballerina" / f"Module{index}.bal").write_text(
            "import ballerina/io;\n\n"
            f"public function greet{index}() returns string {{\n"
            '    io:println("hi");\n'
            '    return "hi";\n'
            "}\n",
            encoding="utf-8",
        )
    (repo_path / "scripts").mkdir(parents=True)
    for index in range(2):
        (repo_path / "scripts" / f"helper_{index}.py").write_text(
            "def helper() -> int:\n    return 1\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "ballerina" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "ballerina"
    assert "Ballerina.toml" in seed_plan["config_paths"]


def test_operational_seed_plan_without_diagnostics_keeps_java_visible_in_mixed_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "ballerina-mixed-java-repo"
    (repo_path / "ballerina").mkdir(parents=True)
    (repo_path / "Ballerina.toml").write_text(
        "[package]\norg = \"acme\"\nname = \"demo\"\nversion = \"0.1.0\"\n",
        encoding="utf-8",
    )
    for index in range(5):
        (repo_path / "ballerina" / f"Module{index}.bal").write_text(
            "import ballerina/io;\n\n"
            f"public function greet{index}() returns string {{\n"
            '    io:println("hi");\n'
            '    return "hi";\n'
            "}\n",
            encoding="utf-8",
        )
    (repo_path / "src" / "main" / "java").mkdir(parents=True)
    for index in range(20):
        (repo_path / "src" / "main" / "java" / f"Host{index}.java").write_text(
            "public class Host { int run() { return 1; } }\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert "ballerina" in seed_plan["detected_ecosystems"]
    assert "ballerina" in seed_plan["operational_ecosystems"]
    assert "java" in seed_plan["operational_ecosystems"]


def test_repository_snapshot_graph_contains_ballerina_symbol_reference_edges(
    tmp_path: Path,
) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "ballerina-graph-repo"
    (repo_path / "ballerina" / "modules" / "common").mkdir(parents=True)
    (repo_path / "Ballerina.toml").write_text(
        "[package]\norg = \"acme\"\nname = \"demo\"\nversion = \"0.1.0\"\n",
        encoding="utf-8",
    )
    (repo_path / "ballerina" / "modules" / "common" / "main.bal").write_text(
        "public function greet() returns string {\n"
        '    return "hello";\n'
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "ballerina" / "main.bal").write_text(
        "import acme/common as common;\n\n"
        "public function main() returns string {\n"
        "    return common:greet();\n"
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["."],
            include_patterns=["*.bal", "Ballerina.toml"],
            max_files=8,
        ),
    )
    graph = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()
    symbol_rows = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()

    target_ids = {
        row["symbol_id"]
        for row in symbol_rows
        if row["file_path"] == "ballerina/modules/common/main.bal"
        and row["symbol_name"] == "greet"
    }
    assert target_ids
    target_nodes = {f"symbol:{symbol_id}" for symbol_id in target_ids}
    assert any(
        row["edge_type"] == "references_symbol"
        and row["target_node"] in target_nodes
        and row["source_node"].startswith("symbol:")
        for row in graph
    )
